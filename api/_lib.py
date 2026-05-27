"""
persona_builder.py — Nova AI Suite
Persona Builder backend module — v2 (research-informed)

Endpoints (register via register_routes):
  POST /api/persona-builder/analyze-jd        – JD text/URL → persona
  POST /api/persona-builder/analyze-url       – Careers page → multi-persona
  POST /api/persona-builder/analyze-linkedin  – LinkedIn + careers → enriched persona

━━━ Data source stack (priority order) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Bright Data LinkedIn Company Scraper   — employee industries, colleges, skills,
                                            headcount, growth (replaces Proxycurl,
                                            which was shut down Jan 2026 after
                                            LinkedIn filed a federal lawsuit)
2. People Data Labs (PDL)                 — 1.5B+ profiles, career trajectories,
                                            skills, education; strongest resume-
                                            trajectory data on the market ($98/mo)
3. SparkToro API                          — "where does this audience actually hang
                                            out?" → websites, podcasts, subreddits,
                                            YouTube channels → feeds channel recs
4. Lightcast (EMSI Burning Glass)         — 2.5B job postings, 32K+ skills taxonomy,
                                            supply/demand by role + location + skill
5. Jina reader                            — primary web scraper for careers pages
6. Apify                                  — fallback scraper for careers pages
7. Claude Haiku 4.5                       — persona generation via LLM router

━━━ Methodology ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• ITSMA best practice: combine ≥3 data sources per persona for validation
• Jobs-to-be-Done (JTBD) framework: core job statement, context triggers,
  functional goals, emotional goals, outcomes — not just demographics
• SparkToro insight: persona value = WHERE the audience spends time,
  not just WHO they are
• Draup: 40+ attributes per persona, refreshed from 70K+ sources
• Crystal Knows: DISC personality signal added for outreach tone guidance
• HubSpot: goals-and-challenges segmentation; update personas ≥ semi-annually

Author: Nova AI Suite / Joveo Strategic Products Division
Updated: 2026-04-26
"""

import json
import os
import re
import time
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── Environment keys ─────────────────────────────────────────────────────────
JINA_BASE          = "https://r.jina.ai/"
BRIGHTDATA_TOKEN   = os.environ.get("BRIGHTDATA_API_TOKEN", "")
BRIGHTDATA_ZONE    = os.environ.get("BRIGHTDATA_ZONE", "linkedin_company")   # Bright Data dataset zone
PDL_API_KEY        = os.environ.get("PDL_API_KEY", "")
SPARKTORO_API_KEY  = os.environ.get("SPARKTORO_API_KEY", "")
LIGHTCAST_CLIENT   = os.environ.get("LIGHTCAST_CLIENT_ID", "")
LIGHTCAST_SECRET   = os.environ.get("LIGHTCAST_CLIENT_SECRET", "")
ANTHROPIC_KEY      = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPSEEK_KEY       = os.environ.get("DEEPSEEK_API_KEY", "")
GROQ_KEY           = os.environ.get("GROQ_API_KEY", "")
GEMINI_KEY         = os.environ.get("GEMINI_API_KEY", "")
OPENAI_KEY         = os.environ.get("OPENAI_API_KEY", "")
MISTRAL_KEY        = os.environ.get("MISTRAL_API_KEY", "")
TOGETHER_KEY       = os.environ.get("TOGETHER_API_KEY", "")
FIREWORKS_KEY      = os.environ.get("FIREWORKS_API_KEY", "")
CEREBRAS_KEY       = os.environ.get("CEREBRAS_API_KEY", "")
SAMBANOVA_KEY      = os.environ.get("SAMBANOVA_API_KEY", "")
PERPLEXITY_KEY     = os.environ.get("PERPLEXITY_API_KEY", "")
OPENROUTER_KEY     = os.environ.get("OPENROUTER_API_KEY", "")
NVIDIA_KEY         = os.environ.get("NVIDIA_API_KEY", "")
XAI_KEY            = os.environ.get("XAI_API_KEY", "")
COHERE_KEY         = os.environ.get("COHERE_API_KEY", "")
APIFY_KEY          = os.environ.get("APIFY_API_KEY", "")

CLAUDE_MODEL       = "claude-haiku-4-5"
SCRAPER_TIMEOUT    = 25
LLM_TIMEOUT        = 30
PDL_TIMEOUT        = 10
SPARKTORO_TIMEOUT  = 10
LIGHTCAST_TIMEOUT  = 10

# ─── L1 in-memory cache ───────────────────────────────────────────────────────
_L1: dict = {}

def _cache_key(*parts: str) -> str:
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

def _l1_get(key: str) -> Optional[dict]:
    entry = _L1.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["value"]
    return None

def _l1_set(key: str, value: dict, ttl: int = 3600):
    _L1[key] = {"value": value, "expires": time.time() + ttl}


# ══════════════════════════════════════════════════════════════════════════════
# 1. BRIGHT DATA — LinkedIn Company Scraper
#    (Replaces Proxycurl, shut down 2026-07-04 after LinkedIn lawsuit)
#    Docs: https://docs.brightdata.com/api-reference/web-scraper-api/social-media-apis/linkedin
# ══════════════════════════════════════════════════════════════════════════════

def _brightdata_linkedin_company(linkedin_url: str) -> dict:
    """
    Fetch LinkedIn company People-tab signals via Bright Data.
    Returns: industries, colleges, skills, headcount, growth, name, description.
    Falls back to empty structure if credentials missing.
    """
    cache_key = _cache_key("bd_li", linkedin_url)
    cached = _l1_get(cache_key)
    if cached:
        return cached

    if not BRIGHTDATA_TOKEN:
        logger.warning("BRIGHTDATA_API_TOKEN not set — LinkedIn signals unavailable")
        return _empty_li_signals(linkedin_url)

    try:
        # Bright Data Web Scraper API — LinkedIn Company dataset
        resp = requests.post(
            "https://api.brightdata.com/datasets/v3/trigger",
            params={"dataset_id": "gd_l1viktl72bvl7bjuj0",   # LinkedIn Company dataset
                    "format": "json",
                    "uncompressed_webhook": "true"},
            headers={
                "Authorization": f"Bearer {BRIGHTDATA_TOKEN}",
                "Content-Type": "application/json",
            },
            json=[{"url": linkedin_url, "type": "company"}],
            timeout=SCRAPER_TIMEOUT,
        )

        if resp.status_code in (200, 202):
            # Bright Data returns a snapshot_id; poll for results
            snapshot_id = resp.json().get("snapshot_id")
            if snapshot_id:
                result = _brightdata_poll(snapshot_id)
                if result:
                    parsed = _parse_brightdata_company(result)
                    _l1_set(cache_key, parsed, ttl=86400)
                    return parsed

    except Exception as e:
        logger.warning(f"Bright Data LinkedIn scrape failed: {e}")

    # Fallback: Apify LinkedIn Company scraper
    return _apify_linkedin_fallback(linkedin_url)


def _brightdata_poll(snapshot_id: str, max_wait: int = 20) -> Optional[list]:
    """Poll Bright Data for a completed snapshot (up to max_wait seconds)."""
    url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
    headers = {"Authorization": f"Bearer {BRIGHTDATA_TOKEN}"}
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data
                if isinstance(data, dict) and data.get("status") == "ready":
                    return data.get("data", [])
        except Exception:
            pass
        time.sleep(3)
    return None


def _parse_brightdata_company(data: list) -> dict:
    """Normalise Bright Data company response into Nova's li_signals schema."""
    if not data:
        return _empty_li_signals("")
    item = data[0] if isinstance(data, list) else data

    # Bright Data fields: name, about, industries, employees, employee_count,
    # top_companies, school_employees, specialties, followers
    raw_industries = item.get("employees_by_function", []) or item.get("industries", [])
    raw_colleges   = item.get("school_employees", []) or item.get("top_schools", [])
    raw_skills     = item.get("specialties", []) or item.get("top_skills", [])

    industries = [
        {"name": i.get("name", i) if isinstance(i, dict) else str(i),
         "pct": i.get("pct", 0) if isinstance(i, dict) else 0}
        for i in raw_industries[:8]
    ]
    colleges = [
        {"name": c.get("name", c) if isinstance(c, dict) else str(c),
         "pct": c.get("pct", 0) if isinstance(c, dict) else 0}
        for c in raw_colleges[:8]
    ]
    skills = [s.get("name", s) if isinstance(s, dict) else str(s) for s in raw_skills[:12]]

    return {
        "name":       item.get("name", ""),
        "description":item.get("about", item.get("description", "")),
        "headcount":  str(item.get("employee_count", item.get("employees", "Unknown"))),
        "growth":     item.get("employee_count_growth", "Unknown"),
        "followers":  item.get("followers", ""),
        "industries": industries,
        "colleges":   colleges,
        "skills":     skills,
        "source":     "bright_data",
    }


def _apify_linkedin_fallback(linkedin_url: str) -> dict:
    """Apify fallback when Bright Data is unavailable."""
    if not APIFY_KEY:
        return _empty_li_signals(linkedin_url)
    try:
        resp = requests.post(
            "https://api.apify.com/v2/acts/apify~linkedin-company-scraper/run-sync-get-dataset-items",
            params={"token": APIFY_KEY},
            json={"startUrls": [{"url": linkedin_url}], "maxResults": 1},
            timeout=40,
        )
        if resp.status_code == 200:
            items = resp.json()
            if items:
                item = items[0]
                return {
                    "name":       item.get("name", ""),
                    "description":item.get("description", ""),
                    "headcount":  str(item.get("employeeCount", "Unknown")),
                    "growth":     str(item.get("employeeCountGrowth", "Unknown")),
                    "industries": [{"name": i, "pct": 0} for i in item.get("topIndustriesOfEmployees", [])],
                    "colleges":   [{"name": c, "pct": 0} for c in item.get("topUniversitiesOfEmployees", [])],
                    "skills":     item.get("topSkillsOfEmployees", []),
                    "source":     "apify",
                }
    except Exception as e:
        logger.warning(f"Apify LinkedIn fallback failed: {e}")
    return _empty_li_signals(linkedin_url)


def _empty_li_signals(url: str) -> dict:
    company = url.split("/company/")[-1].strip("/").replace("-", " ").title() if url else ""
    return {"name": company, "description": "", "headcount": "Unknown",
            "growth": "Unknown", "industries": [], "colleges": [], "skills": [], "source": "none"}


# ══════════════════════════════════════════════════════════════════════════════
# 2. PEOPLE DATA LABS (PDL)
#    1.5B+ profiles, strongest career-trajectory data
#    Docs: https://docs.peopledatalabs.com/docs/person-enrichment-api
#    Pricing: from $98/mo
# ══════════════════════════════════════════════════════════════════════════════

def _pdl_search_by_job(title: str, location: str, industry: str, seniority: str = "mid", limit: int = 20) -> list:
    """
    Search PDL for people matching a role — returns career trajectory signals.
    Used to enrich persona with: typical past employers, education, seniority distribution,
    average tenure, and career path patterns.
    """
    cache_key = _cache_key("pdl", title, location, industry, seniority)
    cached = _l1_get(cache_key)
    if cached:
        return cached

    if not PDL_API_KEY:
        logger.warning("PDL_API_KEY not set — career trajectory signals unavailable")
        return []

    # Only filter by country for non-remote roles
    country_filter = [] if location in ("Remote", "Hybrid") else [{"term": {"location_country": "united states"}}]

    try:
        resp = requests.post(
            "https://api.peopledatalabs.com/v5/person/search",
            headers={"X-Api-Key": PDL_API_KEY, "Content-Type": "application/json"},
            json={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"job_title_levels": _map_seniority_to_pdl(seniority)}},
                            {"match": {"job_title": title}},
                        ],
                        "filter": country_filter,
                    }
                },
                "size": limit,
                "dataset": "resume",
            },
            timeout=PDL_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            profiles = data.get("data", [])
            _l1_set(cache_key, profiles, ttl=86400)
            return profiles
    except Exception as e:
        logger.warning(f"PDL search failed: {e}")
    return []


def _map_seniority_to_pdl(seniority: str) -> str:
    mapping = {
        "executive": "c_suite",
        "director":  "director",
        "manager":   "manager",
        "senior":    "senior",
        "mid":       "mid",       # was wrongly "entry" — PDL has a distinct "mid" level
        "junior":    "entry",     # was "training" — entry is the right PDL enum for junior
    }
    return mapping.get(seniority, "mid")


def _extract_pdl_signals(profiles: list) -> dict:
    """
    Aggregate PDL profiles into persona signals:
    - Most common previous employers (where they come FROM)
    - Typical education level and schools
    - Average years of experience
    - Career path patterns
    """
    if not profiles:
        return {}

    prior_companies = {}
    schools = {}
    tenures = []

    for p in profiles:
        # Prior employers (not current)
        for exp in (p.get("experience") or [])[1:3]:
            co = exp.get("company", {}).get("name", "")
            if co:
                prior_companies[co] = prior_companies.get(co, 0) + 1

        # Education
        for edu in (p.get("education") or [])[:1]:
            school = edu.get("school", {}).get("name", "")
            if school:
                schools[school] = schools.get(school, 0) + 1

        # Tenure at current role
        if p.get("experience"):
            curr = p["experience"][0]
            start = (curr.get("start_date") or {}).get("year")
            if start:
                tenures.append(2026 - int(start))

    top_companies = sorted(prior_companies, key=prior_companies.get, reverse=True)[:5]
    top_schools   = sorted(schools, key=schools.get, reverse=True)[:5]
    avg_tenure    = round(sum(tenures) / len(tenures), 1) if tenures else None

    return {
        "typical_prior_employers": top_companies,
        "typical_schools":         top_schools,
        "avg_tenure_years":        avg_tenure,
        "sample_size":             len(profiles),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. SPARKTORO — Audience Intelligence
#    "Where does your audience actually hang out?"
#    Outputs: websites, podcasts, YouTube channels, subreddits, social accounts
#    Pricing: $38/mo (50 searches); API available on higher tiers
#    Docs: https://sparktoro.com
#
#    THIS IS THE KEY DIFFERENTIATOR: channel recs grounded in real audience
#    behaviour data, not rule-based guesswork.
# ══════════════════════════════════════════════════════════════════════════════

def _sparktoro_audience(query: str, query_type: str = "talks_about") -> dict:
    """
    Query SparkToro for audience intelligence.
    query_type: "talks_about" | "visits_website" | "follows_account"
    Returns: websites, podcasts, subreddits, social accounts the audience engages with.
    """
    cache_key = _cache_key("sparktoro", query, query_type)
    cached = _l1_get(cache_key)
    if cached:
        return cached

    if not SPARKTORO_API_KEY:
        logger.info("SPARKTORO_API_KEY not set — channel intelligence from rule-based fallback")
        return {}

    try:
        resp = requests.get(
            "https://api.sparktoro.com/v1/search",
            headers={"Authorization": f"Bearer {SPARKTORO_API_KEY}"},
            params={"query": query, "type": query_type, "limit": 20},
            timeout=SPARKTORO_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "websites":   [s.get("domain") for s in data.get("websites", [])[:8]],
                "podcasts":   [p.get("title") for p in data.get("podcasts", [])[:5]],
                "subreddits": [r.get("name") for r in data.get("subreddits", [])[:5]],
                "youtube":    [y.get("title") for y in data.get("youtube_channels", [])[:5]],
                "social":     [s.get("account") for s in data.get("social_accounts", [])[:5]],
                "source":     "sparktoro",
            }
            _l1_set(cache_key, result, ttl=86400 * 7)   # SparkToro data changes slowly
            return result
    except Exception as e:
        logger.warning(f"SparkToro API failed: {e}")
    return {}


def _channel_recs_from_sparktoro(sparktoro: dict, industry: str, signals: list) -> list:
    """
    Merge SparkToro audience data with Nova's publisher database.
    Priority: SparkToro-confirmed channels > rule-based defaults.
    """
    recs = []

    # Always include Joveo Programmatic as the distribution layer
    recs.append({"name": "Joveo Programmatic", "tier": "platform",
                 "why": "Distributes across 7,053 publishers with real-time CPA optimisation via Joblet.ai."})

    # SparkToro-informed recommendations
    st_sites = sparktoro.get("websites", [])
    st_subs  = sparktoro.get("subreddits", [])

    if "stackoverflow.com" in st_sites or "stackexchange.com" in st_sites:
        recs.append({"name": "Stack Overflow Jobs", "tier": "niche",
                     "why": "SparkToro confirms your target audience actively visits Stack Overflow — high context-match for tech roles."})

    if any("reddit" in s or s.startswith("r/") for s in st_subs):
        sub_names = [s for s in st_subs if s]
        recs.append({"name": f"Reddit ({', '.join(sub_names[:3])})", "tier": "nontraditional",
                     "why": f"SparkToro data shows your audience is active in {', '.join(sub_names[:3])}. Organic seeding from real employees outperforms paid ads here."})

    if "github.com" in st_sites:
        recs.append({"name": "GitHub Jobs", "tier": "niche",
                     "why": "SparkToro confirms this audience visits GitHub — open-source context fit."})

    if "nursing.com" in st_sites or "allnurses.com" in st_sites:
        recs.append({"name": "Nursing.com", "tier": "niche",
                     "why": "SparkToro confirms your audience visits nursing community sites — peer-driven, high intent."})

    # Fallback rule-based additions
    recs.extend(_rule_based_publishers(industry, signals))

    # Deduplicate
    seen = set()
    unique = []
    for r in recs:
        if r["name"] not in seen:
            seen.add(r["name"])
            unique.append(r)
    return unique[:12]


def _rule_based_publishers(industry: str, signals: list) -> list:
    """Rule-based publisher fallback when SparkToro is unavailable."""
    base = [
        {"name": "Indeed",   "tier": "premium", "why": "Largest job board by volume — essential for all roles."},
        {"name": "LinkedIn",  "tier": "premium", "why": "Primary channel for passive professional talent."},
        {"name": "Glassdoor", "tier": "premium", "why": "High-intent candidates researching employer culture."},
    ]

    industry_map = {
        "tech":       [{"name":"Dice","tier":"niche","why":"6M+ registered tech professionals. Unmatched for engineering roles."},
                       {"name":"Stack Overflow Jobs","tier":"niche","why":"Developers in problem-solving mode — highest context fit."},
                       {"name":"GitHub Jobs","tier":"niche","why":"Open-source developer audience. High signal, low noise."}],
        "healthcare": [{"name":"Nursing.com","tier":"niche","why":"Largest nurse-specific community. Highest intent per dollar in clinical hiring."},
                       {"name":"Health eCareers","tier":"niche","why":"3M+ healthcare professionals including physicians and allied health."},
                       {"name":"iHireNursing","tier":"niche","why":"Verified RN/LPN profiles with licensure validation."}],
        "logistics":  [{"name":"Talroo","tier":"niche","why":"Pay-per-applicant platform optimised for frontline and hourly workers."},
                       {"name":"Snagajob","tier":"niche","why":"80M+ registered hourly workers. Purpose-built for shift-work hiring."},
                       {"name":"Facebook Jobs","tier":"standard","why":"Geo-targeted passive reach for local frontline roles."}],
        "defense":    [{"name":"ClearanceJobs","tier":"niche","why":"1M+ candidates with active or recent DoD clearances."},
                       {"name":"Hire Heroes USA","tier":"niche","why":"USCC veteran transition initiative — direct military-to-civilian pipeline."},
                       {"name":"IEEE Spectrum Jobs","tier":"niche","why":"IEEE-verified technical professionals across engineering disciplines."}],
        "finance":    [{"name":"eFinancialCareers","tier":"niche","why":"The definitive finance job board globally."},
                       {"name":"LinkedIn","tier":"premium","why":"Recruiters and headhunters dominate finance hiring — LinkedIn is the channel."}],
        "bilingual":  [{"name":"Hispanic-Jobs.com","tier":"niche","why":"Dedicated English/Spanish bilingual board. Essential for bilingual roles."},
                       {"name":"LatPro","tier":"niche","why":"Longest-standing board for bilingual professionals."},
                       {"name":"BeBee","tier":"niche","why":"Affinity hiring platform — strong for bilingual SMB sales roles."},
                       {"name":"Prospanica","tier":"niche","why":"Hispanic professional association events and board."}],
        "marketing":  [{"name":"Marketing Hire","tier":"niche","why":"Specialist board for marketing roles across digital, content, brand, and growth."},
                       {"name":"HubSpot Job Board","tier":"niche","why":"Inbound marketing community — strong for content, growth, and demand gen roles."},
                       {"name":"Built In","tier":"niche","why":"Strong for marketing roles at tech-adjacent companies."}],
        "sales":      [{"name":"Sales Gravy","tier":"niche","why":"The leading sales-specific job board for quota-carrying roles."},
                       {"name":"Rainmakers","tier":"niche","why":"Curated platform for B2B sales talent with verified quota attainment."}],
        "hr":         [{"name":"SHRM HR Jobs","tier":"niche","why":"Society for Human Resource Management's official job board — 325K+ HR members."},
                       {"name":"HR.com","tier":"niche","why":"2M+ HR community members; strong for HR generalist and specialist roles."},
                       {"name":"ERE Recruiting Intelligence","tier":"niche","why":"Specialist board for talent acquisition and recruiting ops roles."}],
        "campus":     [{"name":"Handshake","tier":"niche","why":"16M students at 1,400+ universities — the campus recruiting standard."},
                       {"name":"Chegg Internships","tier":"niche","why":"High-intent student and early career audience."},
                       {"name":"Internshala","tier":"niche","why":"Dominant internship and trainee board in South Asia; 16M+ student users."},
                       {"name":"Naukri Campus","tier":"niche","why":"India's largest campus hiring platform for fresher and management trainee roles."}],
    }

    additions = industry_map.get(industry, [])
    if "clearance" in signals:
        additions.extend(industry_map.get("defense", []))
    if "bilingual" in signals:
        additions.extend(industry_map.get("bilingual", []))
    if "campus" in signals:
        additions = list(additions)  # copy
        additions.extend(industry_map.get("campus", []))

    return base + additions


# ══════════════════════════════════════════════════════════════════════════════
# 4. LIGHTCAST (formerly EMSI Burning Glass)
#    2.5B job postings, 800M career profiles, 32K+ skills taxonomy
#    Gives: supply/demand ratio per role+location, top skills in demand,
#           salary benchmarks, hiring velocity
#    Docs: https://lightcast.io/solutions/enterprise-and-staffing/talent-api
# ══════════════════════════════════════════════════════════════════════════════

_lightcast_token: Optional[str] = None
_lightcast_token_expiry: float = 0.0

def _get_lightcast_token() -> Optional[str]:
    global _lightcast_token, _lightcast_token_expiry
    if not LIGHTCAST_CLIENT or not LIGHTCAST_SECRET:
        return None
    if _lightcast_token and time.time() < _lightcast_token_expiry - 60:
        return _lightcast_token
    try:
        resp = requests.post(
            "https://auth.emsicloud.com/connect/token",
            data={"client_id": LIGHTCAST_CLIENT, "client_secret": LIGHTCAST_SECRET,
                  "grant_type": "client_credentials", "scope": "emsi_open"},
            timeout=10,
        )
        if resp.status_code == 200:
            token_data = resp.json()
            _lightcast_token = token_data["access_token"]
            _lightcast_token_expiry = time.time() + token_data.get("expires_in", 3600)
            return _lightcast_token
    except Exception as e:
        logger.warning(f"Lightcast auth failed: {e}")
    return None


def _lightcast_skills_demand(soc_code: str = None, title: str = None) -> dict:
    """
    Get top in-demand skills + supply/demand ratio for a role from Lightcast.
    Returns: top_skills (with demand scores), supply_demand_ratio, salary_median
    """
    if not LIGHTCAST_CLIENT:
        return {}

    cache_key = _cache_key("lightcast", soc_code or "", title or "")
    cached = _l1_get(cache_key)
    if cached:
        return cached

    token = _get_lightcast_token()
    if not token:
        return {}

    try:
        # Skills demand endpoint
        resp = requests.get(
            "https://emsiservices.com/skills/versions/latest/skills",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": title or "", "limit": 20, "fields": "id,name,type"},
            timeout=LIGHTCAST_TIMEOUT,
        )
        if resp.status_code == 200:
            skills_data = resp.json().get("data", [])
            result = {
                "top_skills_in_demand": [s.get("name") for s in skills_data[:10]],
                "skills_taxonomy":      [{"name": s.get("name"), "type": s.get("type", {}).get("name")}
                                          for s in skills_data[:10]],
                "source": "lightcast",
            }
            _l1_set(cache_key, result, ttl=86400 * 7)
            return result
    except Exception as e:
        logger.warning(f"Lightcast skills demand failed: {e}")
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# 5. WEB FETCHING (Jina primary, Apify fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_url(url: str) -> str:
    """Fetch a URL via Jina reader; fall back to direct GET."""
    try:
        resp = requests.get(JINA_BASE + url,
                            headers={"Accept": "text/plain"},
                            timeout=SCRAPER_TIMEOUT)
        if resp.status_code == 200 and len(resp.text) > 200:
            return resp.text[:40_000]
    except Exception as e:
        logger.warning(f"Jina fetch failed for {url}: {e}")

    try:
        resp = requests.get(url, timeout=SCRAPER_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0 (Nova/2.0)"})
        if resp.status_code == 200:
            return resp.text[:40_000]
    except Exception as e:
        logger.warning(f"Direct fetch failed for {url}: {e}")
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# 6. TEXT SIGNAL EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

INDUSTRY_RE = {
    # tech: require explicit tech keywords — bare 'ai' fires on 'paid', 'training', 'biomedical'
    "tech":        r"software\b|(?<!\w)engineer(?:ing)?\b|developer\b|devops|data scien|machine learning"
                   r"|(?<!\w)ml(?!\w)|(?:generative\s+)?ai\s+(?:engineer|model|platform|safety|product)"
                   r"|cloud(?:\s+engineer|\s+architect)|\baws\b|\bgcp\b|\bazure\b"
                   r"|\bpython\b|\bjavascript\b|\btypescript\b|\breact\b|node\.js|kubernetes"
                   r"|backend|frontend|full.?stack|\bsre\b|platform engineer",
    # healthcare: use specific clinical terms, avoid 'er' alone
    "healthcare":  r"\bnurse\b|\brn\b|\blpn\b|\bphysician\b|\bclinical\b"
                   r"|\bicu\b|\bemergency\s+room\b|\bsurgery\b|\bhospital\b"
                   r"|\bhealthcare\b|\bmedical\b|patient care|\bbsn\b|\badn\b|\bcna\b"
                   r"|radiology|pharmacy|\bpharmacist\b|therapist\b|emt\b|paramedic",
    "logistics":   r"\bwarehouse\b|\bfulfillment\b|\bdistribution\b|\blogistics\b"
                   r"|\bdriver\b|\bforklift\b|picker|packer|\bshipping\b|\bfreight\b"
                   r"|supply chain|last.?mile",
    "retail":      r"\bretail\b|store associate|\bcashier\b|sales associate|shift manager",
    "hospitality": r"\brestaurant\b|\bhotel\b|\bhospitality\b|\bserver\b|\bcook\b"
                   r"|\bchef\b|front desk|housekeeping|barista|concierge",
    "finance":     r"\bfinance\b|fintech|\bbanking\b|\btrading\b|\baccounting\b"
                   r"|\bcpa\b|\baudit\b|wealth management|investment|financial analyst|actuar",
    # defense: require 'clearance' context around 'secret' to avoid 'secret sauce'
    "defense":     r"\bdefense\b|(?:security\s+)?clearance\b|secret\s+clearance|ts\/sci"
                   r"|\bmissile\b|\bradar\b|\bmilitary\b|\bdod\b|\bdarpa\b"
                   r"|hypersonic|ballistic|aerospace engineer",
    "marketing":   r"\bmarketing\b|brand strateg|demand gen|growth hacker|content strateg"
                   r"|\bseo\b|\bsem\b|paid media|campaign manager|product marketing"
                   r"|social media manager|communications manager",
    # sales: require B2B signals, not bare 'sales' which fires on retail
    "sales":       r"account executive|account manager|business development"
                   r"|\bsdr\b|\bbdr\b|\bquota\b|closing deals|sales pipeline"
                   r"|revenue\s+target|sales\s+rep\b|inside sales|outside sales",
    "hr":          r"\brecruiting\b|\brecruitment\b|talent acquisition|hrbp"
                   r"|human resources|\bpeople ops\b|compensation.{0,20}benefits|workforce planning",
}

# INDUSTRY_PRIORITY: when scores tie, use this order (higher index = lower priority)
_INDUSTRY_PRIORITY = ["defense","healthcare","finance","tech","marketing","sales","hr","logistics","retail","hospitality"]

SENIORITY_RE = {
    # Word boundaries on ALL tokens — cto/cpo/coo/ceo without \b match inside 'director', 'executive', etc.
    # Full C-suite acronym coverage: CFO, CIO, CMO, CRO, CHRO, CDO, CSO also included
    "executive": r"\bvp\b|vice\s+president|\bcto\b|\bcpo\b|\bcoo\b|\bceo\b|\bcfo\b|\bcio\b|\bcmo\b|\bcro\b|\bchro\b|\bcdo\b|\bcso\b|chief\s+\w+\s+officer|\bsvp\b|\bevp\b",
    # \bdirector\b (not just \bdirector\s+of\b) so "Director, Product" and "Director of X" both match
    "director":  r"\bdirector\b|\bhead\s+of\b",
    # check senior/staff BEFORE manager so "Senior Manager" → "senior"
    # \bstaff\b alone matches "500+ staff across facilities" (company size, not seniority).
    # Require "staff" to precede a role noun so only "Staff Engineer / Staff SRE / Staff Scientist" etc. are caught.
    # \blead\s+engineer\b → broadened to \blead\s+(?:\w+\s+){0,2}(?:engineer|...) to catch
    # "Lead Software Engineer", "Lead Data Scientist", "Lead Machine Learning Engineer" etc.
    # {0,2} allows 0–2 intervening words (e.g. "Machine Learning" = 2 words)
    "senior":    r"\bsenior\b"
                 r"|\bstaff\s+(?:\w+\s+)?(?:engineer|sre|developer|architect|scientist|researcher|product\s+manager|designer|data)\b"
                 r"|\bprincipal\b"
                 r"|\blead\s+(?:\w+\s+){0,2}(?:engineer|developer|architect|scientist|analyst|designer|researcher)\b"
                 r"|\bsr\.",
    "manager":   r"\bmanager\b|\bsupervisor\b|\bteam\s+lead\b|\btech\s+lead\b|\bengineering\s+lead\b",
    # "entry-level" removed — appears in EEO boilerplate for almost every JD, not a reliable seniority signal
    # \bintern\b catches "Software Engineering Intern" (word boundary prevents matching "internal")
    # new\s+grad extended to also catch "new grad campus|program|hire" (not just "new grad engineer")
    # (?:\w+\s+)? allows one optional adjective word so "Entry-Level Software Engineer" matches
    "junior":    r"\bjunior\b|\bintern\b|\binternship\b"
                 r"|(?:entry.?level|new\s+grad(?:uate)?|fresh\s+grad(?:uate)?)\s+(?:\w+\s+)?(?:engineer|developer|analyst|position|role|program|hire|campus|recruit)"
                 r"|\bassociate\s+engineer\b"
                 r"|\btrainee\b|\bfresher\b",
}

# SKILL_VOCAB: use word-boundary patterns for short/ambiguous names
# Each entry is (display_name, regex_pattern)
SKILL_VOCAB_RE = [
    ("Python",      r"\bPython\b"),
    ("Java",        r"\bJava\b(?!Script)"),          # exclude JavaScript
    ("Go",          r"\bGolang\b|\bGo\s+(?:programming|lang|developer|engineer|service|microservice)\b"),  # 'Go' alone too ambiguous
    ("JavaScript",  r"\bJavaScript\b"),
    ("TypeScript",  r"\bTypeScript\b"),
    ("React",       r"\bReact(?:\.js)?\b"),
    ("Node.js",     r"\bNode\.js\b"),
    ("C++",         r"\bC\+\+\b"),
    ("C#",          r"\bC#\b"),
    ("Rust",        r"\bRust\b"),
    ("Swift",       r"\bSwift\b"),
    ("AWS",         r"\bAWS\b"),
    ("GCP",         r"\bGCP\b"),
    ("Azure",       r"\bAzure\b"),
    ("Kubernetes",  r"\bKubernetes\b"),
    ("Docker",      r"\bDocker\b"),
    ("Kafka",       r"\bKafka\b"),
    ("Terraform",   r"\bTerraform\b"),
    ("PostgreSQL",  r"\bPostgreSQL\b"),
    ("Redis",       r"\bRedis\b"),
    ("Spark",       r"\bSpark\b"),
    ("TensorFlow",  r"\bTensorFlow\b"),
    ("PyTorch",     r"\bPyTorch\b"),
    ("scikit-learn",r"\bscikit-learn\b"),
    ("SQL",         r"\bSQL\b"),
    ("dbt",         r"\bdbt\b"),
    ("Snowflake",   r"\bSnowflake\b"),
    ("RTOS",        r"\bRTOS\b"),
    ("VxWorks",     r"\bVxWorks\b"),
    ("LynxOS",      r"\bLynxOS\b"),
    ("VHDL",        r"\bVHDL\b"),
    ("MATLAB",      r"\bMATLAB\b"),
    ("Simulink",    r"\bSimulink\b"),
    ("DO-178C",     r"\bDO-178C\b"),
    ("MIL-STD-882", r"\bMIL-STD-882\b"),
    # "Ada" removed — \bAda\b fires on "ADA" (disability act) in EEO boilerplate
    ("RF",          r"\bRF\s+(?:engineer|design|circuit|frequency|antenna|transceiver|frontend)\b"),  # "RF system" too broad; require hardware-specific context
    ("Radar",       r"\bRadar\b"),
    ("MBSE",        r"\bMBSE\b"),
    ("SysML",       r"\bSysML\b"),
    ("JIRA",        r"\bJIRA\b"),
    ("Confluence",  r"\bConfluence\b"),
    ("ACLS",        r"\bACLS\b"),
    ("BLS",         r"\bBLS\b"),
    ("BSN",         r"\bBSN\b"),
    ("ADN",         r"\bADN\b"),
    ("IV Therapy",  r"\bIV Therapy\b"),
    ("Epic",        r"\bEpic\b(?!\s+Games)"),  # Epic EHR not Epic Games
    ("Cerner",      r"\bCerner\b"),
    ("Salesforce",  r"\bSalesforce\b"),
    ("HubSpot",     r"\bHubSpot\b"),
    ("CRM",         r"\bCRM\b"),
    # ── Accounting & Finance ──────────────────────────────────────────────────
    ("QuickBooks",     r"\bQuickBooks\b|\bQBO\b"),
    ("Tally ERP",      r"\bTally\s*(?:ERP|Prime)?\b"),
    ("SAP FICO",       r"\bSAP\s+(?:FICO|FI|CO|ERP|S/4HANA)\b"),
    ("Oracle Financials", r"\bOracle\s+(?:Financials|ERP|Cloud|NetSuite|E-Business)\b"),
    ("Zoho Books",     r"\bZoho\s+Books\b"),
    ("Xero",           r"\bXero\b"),
    ("NetSuite",       r"\bNetSuite\b"),
    # ── Marketing ──────────────────────────────────────────────────────────────
    ("Google Analytics", r"\bGoogle\s+Analytics\b|\bGA4\b"),
    ("Google Ads",     r"\bGoogle\s+Ads\b|\bGoogle\s+AdWords\b"),
    ("Meta Ads",       r"\bMeta\s+(?:Ads|Business\s+Suite)\b|\bFacebook\s+Ads\b"),
    ("Marketo",        r"\bMarketo\b"),
    ("Mailchimp",      r"\bMailchimp\b"),
    ("SEMrush",        r"\bSEM[Rr]ush\b"),
    ("Ahrefs",         r"\bAhrefs\b"),
    # ── HR Tools ──────────────────────────────────────────────────────────────
    ("Workday",        r"\bWorkday\b"),
    ("ADP",            r"\bADP\b"),
    ("Greenhouse ATS", r"\bGreenhouse\b(?!\s+gas)"),
    ("Lever ATS",      r"\bLever\b(?:\s+ATS)?"),
    ("BambooHR",       r"\bBamboo\s*HR\b"),
    ("SAP SuccessFactors", r"\bSuccessFactors\b|\bSAP\s+SF\b"),
    ("Dask",        r"\bDask\b"),
    ("Hadoop",      r"\bHadoop\b"),
    ("Scala",       r"\bScala\b"),
]

def _detect_industry(text: str) -> str:
    text_lower = text.lower()
    scores = {ind: len(re.findall(pat, text_lower, re.IGNORECASE)) for ind, pat in INDUSTRY_RE.items()}
    scores = {k: v for k, v in scores.items() if v}
    if not scores:
        return "general"
    max_score = max(scores.values())
    winners = [k for k, v in scores.items() if v == max_score]
    if len(winners) == 1:
        return winners[0]
    # Tiebreak by priority order
    for ind in _INDUSTRY_PRIORITY:
        if ind in winners:
            return ind
    return winners[0]

def _detect_seniority(text: str) -> str:
    """
    Detect seniority from the JD.
    IMPORTANT: Executive/director detection is restricted to the first 200 characters
    (the job title area) to prevent company boilerplate ("Executive Vice President of
    Care at Genesis HealthCare...") from contaminating a frontline role's seniority.
    """
    # Job title = first non-empty line only (prevents "Executive Director of Care at Genesis"
    # from making a frontline RN look executive-level)
    # Use >= 2 (not > 3) so 3-letter acronyms like "CTO", "CFO", "CIO" are captured
    first_line = next((ln.strip().lower() for ln in text.split("\n") if len(ln.strip()) >= 2), "")
    title_area = (first_line + " " + text[:200].lower())   # first line + fallback window
    body_area  = text[:600].lower()                         # broader body for other levels

    # Executive and director: first-line title only
    for level in ("executive", "director"):
        if re.search(SENIORITY_RE[level], first_line):
            return level
    # Junior: check first_line FIRST — prevents "mentored by senior engineers" in the
    # body from overriding a title like "Junior Frontend Developer" or "Entry-Level Analyst"
    if re.search(SENIORITY_RE["junior"], first_line):
        return "junior"
    # Senior, manager: check wider body (up to 600 chars)
    # senior before manager so "Senior Manager" → "senior"
    for level in ("senior", "manager"):
        if re.search(SENIORITY_RE[level], body_area):
            return level
    # Junior body fallback (entry-level phrasing only in body, no title match)
    if re.search(SENIORITY_RE["junior"], body_area):
        return "junior"
    return "mid"

def _extract_skills(text: str) -> list:
    """Extract skills using word-boundary-safe regex patterns."""
    found = [name for name, pat in SKILL_VOCAB_RE if re.search(pat, text, re.IGNORECASE)]
    return found[:12]

def _extract_salary(text: str) -> str:
    """
    Extract salary/compensation from JD.
    Handles:  $X–$Y  |  $X/hr  |  $Xk–$Yk  |  $X,000–$Y,000/yr
    For multi-location JDs (McLean $229K vs NY $262K), returns first match.
    """
    _CURR = r"(?:[$₹€£]|USD|INR|GBP|EUR|CAD|AUD)\s*"
    m = re.search(
        rf"{_CURR}[\d,]+\.?\d*[k]?\s*[-–—]\s*(?:{_CURR})?[\d,]+\.?\d*[k]?(?:\s*/\s*(?:hr|hour|yr|year|annually|month|mo)|\s+(?:annually|per\s+year|per\s+month|per\s+hour))?"
        rf"|{_CURR}[\d,]+\.?\d*[k]?\s*(?:/\s*(?:hr|hour|yr|year|annually|month|mo)|per\s+(?:hr|hour|year|annum|month))"
        rf"|{_CURR}[\d,]+\.?\d*[k]\+?"
        rf"|(?:from|starting\s+at|upto|up\s+to)\s+{_CURR}[\d,]+\.?\d*[k]?"
        r"|(?:salary|compensation|pay(?:rate)?|ctc)\D{{0,20}}(\d{{2,3}},\d{{3}})\s*[-–—]\s*(\d{{2,3}},\d{{3}})",
        text, re.IGNORECASE,
    )
    if not m:
        return "Not specified"
    result = m.group(0)
    # If a group-based match (numeric range), reconstruct it
    if m.lastindex and m.lastindex >= 3 and m.group(2) and m.group(3):
        result = f"${m.group(2)} – ${m.group(3)}"
    return result.strip()

_US_STATES = (
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    r"Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|"
    r"Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|"
    r"Nebraska|Nevada|New\s+Hampshire|New\s+Jersey|New\s+Mexico|New\s+York|"
    r"North\s+Carolina|North\s+Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
    r"Rhode\s+Island|South\s+Carolina|South\s+Dakota|Tennessee|Texas|Utah|"
    r"Vermont|Virginia|Washington|West\s+Virginia|Wisconsin|Wyoming"
)

def _extract_location(text: str) -> str:
    """
    Extract city/state from JD text.
    Supports both abbreviated states (McLean, VA) and full names (Orono, Maine).
    Falls back to "Not specified" — NOT "On-site" (that is work arrangement, not location).
    For multiple locations (McLean, VA or New York, NY), returns the first match.
    """
    # Pattern: require preposition or separator before city to avoid matching job titles.
    # Supports: "in McLean, VA"  "at Orono, Maine"  "– McLean, VA"  "based in Orono, Maine"
    # Full state names BEFORE [A-Z]{2} to prevent 'Ma' matching inside 'Machine'
    # State pattern: full names first (before [A-Z]{2} to avoid partial match on "Ma" from "Machine").
    # The 2-letter abbreviation uses (?-i:) to stay case-SENSITIVE even inside a re.IGNORECASE match
    # — this prevents "Go", "in", "py" etc. from matching as state codes.
    state_pat = rf"(?:{_US_STATES}|(?-i:[A-Z]{{2}}))\b"
    # First pass: require context (preposition / em-dash).
    # Exclude bare bullet-point hyphens by requiring the separator to be surrounded by non-alpha context
    # (em-dash or "in/at/based in") rather than the list-item hyphen "- Python, Go, Java".
    m = re.search(
        rf"(?:(?:in|at|based\s+in|located\s+in)\s+|[–—]\s*)([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+)*,\s*{state_pat})",
        text,
        re.IGNORECASE,
    )
    if m:
        loc = m.group(1).strip()
        city_part = loc.split(",")[0].strip()
        if len(city_part) >= 3:
            return loc
    # Second pass: bare "City, State" if preceded by whitespace/start of field (no preposition)
    m = re.search(
        rf"(?<!\w)([A-Z][a-z][a-zA-Z'-]{{1,}}(?:\s+[A-Z][a-zA-Z'-]+)*,\s*{state_pat})",
        text,
    )
    if m:
        loc = m.group(1).strip()
        city_part = loc.split(",")[0].strip()
        if len(city_part) >= 3:
            return loc
    # No city/state found — location is unknown. Do NOT return arrangement words
    # like "Remote" or "Hybrid" here; those come from _detect_arrangement.
    return "Not specified"

def _detect_arrangement(text: str) -> str:
    # "Fully remote" signals — including bare \bremote\b (catches "Remote." "Remote-first" etc.)
    # Safe because hybrid/on-site are checked first; bare "remote" without those = fully remote.
    if re.search(r"fully remote|100% remote|work from home|wfh|\bremote.?first\b|\bremote.?only\b", text, re.IGNORECASE):
        return "Fully remote"
    if re.search(r"\bhybrid\b", text, re.IGNORECASE):
        return "Hybrid"
    if re.search(r"\bon.?site\b|\bin.?office\b|in\s+person\b|on\s+location\b", text, re.IGNORECASE):
        return "On-site"
    # Bare "remote" with no other arrangement signals → fully remote
    if re.search(r"\bremote\b", text, re.IGNORECASE):
        return "Fully remote"
    return "Not specified"

def _detect_flags(text: str) -> dict:
    return {
        "clearance":  bool(re.search(
            r"security\s+clearance|secret\s+clearance|ts\/sci|top\s+secret|dod\s+clearance"
            r"|active\s+clearance|clearance\s+required|must\s+have\s+clearance",
            text, re.IGNORECASE)),
        "bilingual":  bool(re.search(
            r"bilingual|spanish.*english|english.*spanish|fluent.*spanish|spanish\s+required",
            text, re.IGNORECASE)),
        # veteran: only flag when veterans/military experience is a job REQUIREMENT or preference,
        # not mere EEO boilerplate ("veterans encouraged to apply" → NOT flagged)
        "veteran":    bool(re.search(
            r"skillbridge|military\s+(?:experience|background|service)\s+(?:preferred|required|a plus)"
            r"|veteran\s+(?:preferred|required|status\s+preferred)"
            r"|dod\s+(?:experience|background)|security\s+clearance\s+required",
            text, re.IGNORECASE)),
        # campus: only flag if this is explicitly a campus/intern/new-grad role, not if "intern" appears in EEO
        "campus":     bool(re.search(
            r"\binternship\b|\bco-?op\b|new\s+grad(?:uate)?\s+(?:program|hire|role|position)"
            r"|campus\s+recruit|recent\s+graduate"
            r"|\btrainee\b|\bfresher\b|fresh\s+grad(?:uate)?"
            r"|management\s+trainee|graduate\s+trainee|entry.?level\s+(?:program|hire|role)",
            text, re.IGNORECASE)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. LLM PERSONA GENERATION — JTBD Framework
#    Jobs-to-be-Done: core job, context triggers, functional + emotional goals,
#    desired outcomes. Better than pure demographic personas.
#    Per ITSMA: combine ≥3 data sources per persona.
# ══════════════════════════════════════════════════════════════════════════════

PERSONA_SYSTEM = """You are a senior recruitment marketing strategist at Joveo building candidate personas for B2B talent acquisition campaigns.

════ GROUND RULES — READ BEFORE GENERATING ════
1. ROLE TYPE: If the JD is for a PEOPLE MANAGER (manages engineers/teams, has direct reports, owns org), the persona MUST reflect a people manager — not an individual contributor. Look for: "manage a team", "direct reports", "hiring manager", "team lead responsible for", "build and grow the team". Never generate an IC persona for a management JD.
2. SKILLS: Only list skills EXPLICITLY named in the JD. Do NOT invent or infer common skills (e.g. do not add Java or Go if the JD doesn't mention them). If skills are vague, leave the list short.
3. DISC: Derive DISC from the role's actual day-to-day, NOT from seniority. Senior ≠ always D. A senior researcher is C. A senior people manager could be D or S. A senior community manager is I. Think about what drives the person in THIS role.
4. AGE RANGE: Only include an age range if the JD or signals explicitly imply one. If not stated, use "experienced professional" — do NOT guess 40-55 or any specific range.
5. SPECIFICITY: Every field must be JD-specific. If context_trigger or acquisition_trigger sounds generic, rewrite it. These fields must describe THIS role at THIS company type, not a generic senior professional.

════ FRAMEWORK ════
Jobs-to-be-Done (JTBD) + Crystal Knows DISC:
- Core job: what career outcome are they fundamentally working toward
- Context trigger: the concrete situation making them open RIGHT NOW (program ending, team politics, ceiling hit, budget cuts — pick the most plausible for THIS role)
- Functional goals: 3 concrete deliverables the new role must provide
- Emotional goals: 2 feelings they need from work
- Concern: single most specific hesitation for THIS role (not generic "culture fit")

DISC personality (derive from role, not seniority):
- D: autonomous scope, ownership, results accountability — outreach: direct, outcomes-first
- I: team-building, stakeholder influence, visibility — outreach: story, social proof, community
- S: process, stability, long-horizon programs — outreach: reliability, belonging, mission
- C: deep technical craft, evidence, precision — outreach: data, technical depth, transparency

════ OUTPUT ════
Return ONLY valid JSON — no markdown fences, no commentary:
{
  "name": "The [Archetype — specific to this role, not generic]",
  "role": "Exact title from JD or closest accurate equivalent",
  "profile": "Seniority · role_type (people manager OR individual contributor) · current employer type · location/remote",
  "core_job": "One precise sentence tied to THIS specific JD",
  "context_trigger": "Specific situation making them open RIGHT NOW — name the real trigger for this role type",
  "functional_goals": ["specific to THIS JD need 1", "specific to THIS JD need 2", "specific to THIS JD need 3"],
  "emotional_goals": ["emotional state tied to this role", "second emotional state"],
  "concern": "Most specific hesitation for THIS role at THIS company type",
  "primary_message": "Compelling headline for this persona — in quotes, max 15 words, JD-specific",
  "background": "2-sentence narrative. Name real company types, real JD technologies, real situations.",
  "disc_type": "D or I or S or C — derived from role dynamics, NOT seniority",
  "disc_implication": "Concrete outreach guidance specific to this persona: what to lead with, what to avoid",
  "acquisition_trigger": "Exact content type that moves THIS persona (e.g. 'a Substack post by a FAANG ML manager on team culture')",
  "job_quality_issues": ["JD weakness that would deter THIS specific persona", "second weakness if real"],
  "messaging_variants": [
    {
      "label": "Results-first (D-type)",
      "headline": "Max 12 words. Direct, outcome-focused, JD-specific.",
      "body": "2-3 sentences referencing THIS JD's tech stack, company type, scope. No platitudes.",
      "cta": "Strong action CTA, max 8 words"
    },
    {
      "label": "Social/story (I-type)",
      "headline": "Max 12 words. Team, growth, community angle tied to THIS role.",
      "body": "2-3 sentences. Reference real communities or career moments relevant to this discipline.",
      "cta": "Inviting CTA, max 8 words"
    },
    {
      "label": "Evidence/process (C-type)",
      "headline": "Max 12 words. Data-led, specific to this role's craft.",
      "body": "2-3 sentences. Include specifics from the JD — stack, scale, process. No vague claims.",
      "cta": "Transparency-promise CTA, max 8 words"
    }
  ]
}"""


# ══════════════════════════════════════════════════════════════════════════════
# MECE ARCHETYPE POOLS
# Up to 6 Mutually Exclusive, Collectively Exhaustive archetypes per (seniority, role_type).
# Ordered by market prevalence — first 2 cover ~60% of the candidate market, each
# additional archetype adds orthogonal coverage up to 6 total.
# Defined on 4 axes: DISC type, core motivation, background style, context trigger.
# Call _get_mece_archetypes(seniority, role_type, count) to get the first N.
# ══════════════════════════════════════════════════════════════════════════════

_MECE_ARCHETYPES: dict = {
    # ─── Senior Individual Contributor ───────────────────────────────────────
    ("senior", "individual_contributor"): [
        {
            "archetype_name": "The Deep Specialist",
            "disc": "C",
            "motivation": "Technical mastery — solving problems few can; depth over breadth.",
            "background_style": "Research-adjacent or long-tenure specialist; shaped by projects with real engineering constraints and high craft standards.",
            "trigger": "Current role narrowing scope or pushing toward management they don't want.",
            "messaging_angle": "Lead with technical depth, precision of the stack, and scale of unsolved problems. Cite specific technologies and constraints from the JD. Avoid generalist or leadership language.",
        },
        {
            "archetype_name": "The Impact Builder",
            "disc": "D",
            "motivation": "Shipping at scale — owns outcomes, not just code. Cares what the work produces in the world.",
            "background_style": "Startup or high-growth background; bias for action; has shipped to millions of users; knows when to cut scope.",
            "trigger": "Current team moves too slowly or their work doesn't reach users at meaningful scale.",
            "messaging_angle": "Lead with ownership, scope, and measurable outcomes. Name the scale this JD enables. Avoid org-chart complexity language.",
        },
        {
            "archetype_name": "The Collaborative Architect",
            "disc": "S",
            "motivation": "Systemic reliability — cares about how the team works together as much as what they build; champions shared standards and cross-team trust.",
            "background_style": "Long-tenure IC who became the connective tissue of a large engineering org; known for documentation, design reviews, and unblocking others.",
            "trigger": "Current environment is too fragmented — teams silo and duplicate work, or there's no culture of shared ownership.",
            "messaging_angle": "Lead with collaboration model, cross-team design culture, and how engineering decisions get made. Show the connective tissue of the org.",
        },
        {
            "archetype_name": "The Thought Leader",
            "disc": "I",
            "motivation": "External influence — wants their work to matter beyond the company: conference talks, open source, community reputation.",
            "background_style": "Active in the industry through writing, speaking, or OSS; known beyond their current employer; career is a platform, not just a job.",
            "trigger": "Current employer restricts external publication, OSS contribution, or is in a domain with no industry standing.",
            "messaging_angle": "Lead with company reputation, open source posture, conference presence, and whether engineers here build public credibility. Name recognizable tech the team uses or contributes to.",
        },
        {
            "archetype_name": "The Principal Tech Lead",
            "disc": "DC",
            "motivation": "Outcome at quality — drives delivery at pace while holding the line on architecture and craft; will not ship something they'd be embarrassed by.",
            "background_style": "Has held both IC and tech lead roles; bridges delivery pressure and engineering excellence; trusted by both PMs and engineers.",
            "trigger": "Current role forces a trade-off between speed and quality that feels unsustainable — either shipping junk or moving too slowly to matter.",
            "messaging_angle": "Lead with engineering velocity AND quality signals together. Show that the team ships fast and ships well — cite both cadence and technical bar in the JD.",
        },
        {
            "archetype_name": "The Staff Platform Builder",
            "disc": "SI",
            "motivation": "Enabling others — finds deep satisfaction in building internal tools, platforms, and foundations that make every other engineer faster.",
            "background_style": "Evolved from product engineering into platform/infra; motivated by leverage, not personal output; measures success by what the rest of the org can do.",
            "trigger": "Current company doesn't invest in internal developer experience — tooling is patchy and engineers waste time on undifferentiated work.",
            "messaging_angle": "Lead with developer experience investment, internal tooling maturity, and the scale impact of platform work. Show how platform decisions are made and funded.",
        },
    ],
    # ─── People Manager (senior / engineering manager level) ─────────────────
    ("senior", "people_manager"): [
        {
            "archetype_name": "The Technical Leader",
            "disc": "C",
            "motivation": "Elevating engineering craft — wants a team that ships high-quality work and has strong engineering standards.",
            "background_style": "IC-first career path; became a manager to protect craft standards at scale; still deeply technical.",
            "trigger": "Current org has weak engineering culture or technical debt preventing the team from doing their best work.",
            "messaging_angle": "Lead with engineering bar, codebase quality, tech stack maturity, and how the team makes technical decisions. Show technical excellence is valued.",
        },
        {
            "archetype_name": "The People Developer",
            "disc": "S",
            "motivation": "Building team capability — finds meaning in coaching, removing blockers, and watching their reports grow.",
            "background_style": "People-first orientation from early career; naturally gravitated toward team health, retention, and psychological safety.",
            "trigger": "Current employer doesn't invest in people development, or the manager is stretched too thin to coach effectively.",
            "messaging_angle": "Lead with team culture, mentorship investment, and how the company grows managers. Show the support structure and headcount for their team.",
        },
        {
            "archetype_name": "The Delivery Manager",
            "disc": "D",
            "motivation": "Execution — measures their worth by what ships; drives clarity on priorities, removes blockers fast, and holds the team to commitments.",
            "background_style": "Often from a product-adjacent or high-growth background; comfortable in ambiguity; known for unblocking teams and shipping on time.",
            "trigger": "Current org is indecisive — too many priorities, unclear roadmap, or delivery that slips without accountability.",
            "messaging_angle": "Lead with product velocity, roadmap clarity, and how decisions get made. Show the team ships regularly and has a clear north star.",
        },
        {
            "archetype_name": "The Culture Builder",
            "disc": "I",
            "motivation": "Team identity and belonging — believes team culture is a competitive advantage; invests in rituals, psychological safety, and team reputation.",
            "background_style": "Known inside and outside their team for building high-energy, high-trust environments; often has strong hiring and retention track record.",
            "trigger": "Current team has turnover, low morale, or a culture that doesn't reflect what they want to lead.",
            "messaging_angle": "Lead with team culture, hiring quality, retention metrics, and what distinguishes this team. Show the social fabric of the engineering org.",
        },
        {
            "archetype_name": "The Engineering Excellence Lead",
            "disc": "CD",
            "motivation": "Operational discipline — closes the gap between engineering quality and delivery pace; builds the processes that let both coexist.",
            "background_style": "Strong IC who moved into management precisely to fix the system-level issues slowing their team down; has introduced and improved engineering practices at scale.",
            "trigger": "Current team ships but accumulates hidden debt, or the opposite — high standards but slow velocity that frustrates stakeholders.",
            "messaging_angle": "Lead with engineering process maturity — sprint cadence, incident reviews, code review culture, and on-call health. Show the team has discipline without bureaucracy.",
        },
        {
            "archetype_name": "The Growth Manager",
            "disc": "IS",
            "motivation": "People and org growth — wants to scale the team, build the next layer of management, and be known for the careers they've launched.",
            "background_style": "Manager of managers or on-track for it; has hired and promoted ICs into senior and staff roles; career is measured in the people they've developed.",
            "trigger": "Current scope is too narrow — wants a larger team, more headcount to hire, or a real people-growth mandate.",
            "messaging_angle": "Lead with team size trajectory, headcount budget, and internal promotion rates. Show this is a place where great managers make other great managers.",
        },
    ],
    # ─── Director / Head of ───────────────────────────────────────────────────
    ("director", "people_manager"): [
        {
            "archetype_name": "The Strategy Operator",
            "disc": "C",
            "motivation": "Systems thinking — creates alignment across teams and builds org capabilities that compound over time.",
            "background_style": "Background in program or product leadership; brought order to complex, cross-functional environments and cross-team dependencies.",
            "trigger": "Current org is siloed; strategy doesn't cascade into team-level execution reliably.",
            "messaging_angle": "Lead with organizational clarity, how strategy connects to execution, and the operating model the team runs. Cite scope, headcount, and cross-functional reach.",
        },
        {
            "archetype_name": "The Talent Multiplier",
            "disc": "I",
            "motivation": "Org capability — believes the quality of the team is the strategy; recruits and develops high performers.",
            "background_style": "Career defined by building strong teams and cultivating internal talent pipelines; known for developing the next layer of leadership.",
            "trigger": "Inherited or is inheriting a team that needs rebuilding — sees this as the core challenge worth solving.",
            "messaging_angle": "Lead with team quality, hiring bar, and investment in people. Show caliber of existing leadership and career growth trajectory within the org.",
        },
        {
            "archetype_name": "The Execution Director",
            "disc": "D",
            "motivation": "Delivery at scale — holds multiple teams to shared commitments; cuts through complexity to keep the org shipping.",
            "background_style": "P&L or delivery-facing background; has run large programs or multiple product lines; known for ending ambiguity and driving decisions.",
            "trigger": "Current org has too many initiatives in flight with unclear ownership — wants to run a tighter, more accountable operation.",
            "messaging_angle": "Lead with delivery track record, product scope, and decision-making authority. Show how many teams report up, what they ship, and how priorities are set.",
        },
        {
            "archetype_name": "The Team Builder Director",
            "disc": "S",
            "motivation": "Organizational stability — builds cultures where people stay, grow, and do their best work without burning out.",
            "background_style": "Known for low attrition and high internal promotion rates; creates environments of trust and clear career ladders.",
            "trigger": "Current org has high turnover or a toxic subculture that leadership hasn't fixed — sees org health as an urgent business problem.",
            "messaging_angle": "Lead with retention data, culture investment, and engineering career ladder. Show the org is stable, growing, and cares about the people inside it.",
        },
        {
            "archetype_name": "The Technical Director",
            "disc": "CD",
            "motivation": "Technical strategy — sets the architectural direction for the engineering org and ensures technical decisions support long-term business goals.",
            "background_style": "Principal or Staff engineer who moved into director-level leadership while staying hands-on with technical direction; trusted by both ICs and executives.",
            "trigger": "Current company's technical strategy is reactive or underfunded — architecture accumulates debt without a long-term owner.",
            "messaging_angle": "Lead with engineering org's technical roadmap, architecture review processes, and how technical decisions are made at the leadership level.",
        },
        {
            "archetype_name": "The Culture Director",
            "disc": "IS",
            "motivation": "Org identity — builds engineering brands people want to join and shapes cultures that attract and retain A-players.",
            "background_style": "Known externally for building great teams; active in communities, conferences, or employer brand initiatives; treats culture as a product.",
            "trigger": "Current org has no employer brand, high attrition, or a culture that doesn't reflect what they believe engineering should look like.",
            "messaging_angle": "Lead with employer brand, team reputation, engineering blog, and conference presence. Show the team is known for something worth joining.",
        },
    ],
    # ─── Executive (VP, C-suite) ─────────────────────────────────────────────
    ("executive", "people_manager"): [
        {
            "archetype_name": "The Operator",
            "disc": "D",
            "motivation": "Business results — P&L ownership, speed of execution, removing obstacles to growth.",
            "background_style": "Led large orgs through growth phases or turnarounds; holds self and team to hard metrics and clear accountability.",
            "trigger": "Wants full ownership of a domain — not to be the second layer of a large org with bureaucratic drag.",
            "messaging_angle": "Lead with scope of decision authority, clear accountability structure, and what the business outcome is. Show the resources and team behind the role.",
        },
        {
            "archetype_name": "The Visionary Builder",
            "disc": "I",
            "motivation": "Transformation — building something that outlasts them; culture and brand as competitive moat.",
            "background_style": "Career defined by org-building and mission alignment; known for attracting and retaining exceptional people around a compelling narrative.",
            "trigger": "Current role lacks blank-sheet-of-paper opportunity or company mission is no longer personally compelling.",
            "messaging_angle": "Lead with company mission, cultural opportunity, and what can be built. Name the transformation horizon and caliber of people they'd build it with.",
        },
        {
            "archetype_name": "The Systems Thinker",
            "disc": "C",
            "motivation": "Durable architecture — builds orgs, processes, and platforms that scale without breaking; treats the org itself as a system to be designed.",
            "background_style": "Technical executive or former principal-turned-VP; brings engineering rigor to org design, planning cycles, and resource allocation.",
            "trigger": "Current company's org model can't scale — they've hit the ceiling of informal coordination and need someone to build the operating system.",
            "messaging_angle": "Lead with operating model, planning cadence, and org design intentionality. Show the company thinks structurally about how engineering scales.",
        },
        {
            "archetype_name": "The People-First Executive",
            "disc": "S",
            "motivation": "Long-term retention — believes great companies are built on low attrition and high trust; culture is the product strategy.",
            "background_style": "CHRO-adjacent executive or engineering leader known for psychological safety and employer brand; has built orgs where people stay 5+ years.",
            "trigger": "Current company has a talent problem — high churn, mediocre hiring bar, or a culture that burns people out.",
            "messaging_angle": "Lead with retention stats, DEI investment, career ladder, and psychological safety. Show the org as a place people build careers, not just jobs.",
        },
        {
            "archetype_name": "The Technical Executive",
            "disc": "DC",
            "motivation": "Technical leverage at business scale — makes bets on platform, infra, and architecture that determine the company's technical ceiling for years.",
            "background_style": "CTO or VP Eng who came up through a deep technical track; still engages with architecture decisions and technical hiring; credible with investors and ICs alike.",
            "trigger": "Current company underinvests in technical foundation — shipping fast now but accumulating structural debt that will limit future growth.",
            "messaging_angle": "Lead with technical strategy, platform investment, and engineering bar at the top. Show that the C-suite values technical excellence as a business driver.",
        },
        {
            "archetype_name": "The Transformational Leader",
            "disc": "IS",
            "motivation": "Org-wide change — drives cultural and operational transformation across entire business units; energizes organizations through transitions.",
            "background_style": "Led companies or divisions through M&A, hypergrowth, or pivots; known for communication, change management, and rallying large orgs.",
            "trigger": "Current role is in steady state — they want to lead through a significant transformation, not just maintain what exists.",
            "messaging_angle": "Lead with the transformation arc: what is changing, at what scale, and why this moment matters. Show the executive will have room to reshape, not just maintain.",
        },
    ],
    # ─── Mid-level Individual Contributor (default for most JDs) ─────────────
    ("mid", "individual_contributor"): [
        {
            "archetype_name": "The Craftsperson",
            "disc": "C",
            "motivation": "Quality and precision — builds things right, not just fast; has strong opinions on standards and how work is done.",
            "background_style": "Methodical career progression; has accumulated depth in a domain and is picky about their next environment.",
            "trigger": "Current team ships fast but accumulates technical or process debt that erodes the quality of their work.",
            "messaging_angle": "Lead with tech stack, code quality expectations, and what 'done well' looks like on your team. Show the day-to-day craft environment.",
        },
        {
            "archetype_name": "The Opportunity Seeker",
            "disc": "I",
            "motivation": "Growth and impact — wants a role that accelerates their trajectory and connects their work to visible outcomes.",
            "background_style": "Adaptable and eager; has built lateral skills across domains; optimises for learning velocity and team caliber.",
            "trigger": "Current role has plateaued — no new problems, no growth, or team has stopped learning together.",
            "messaging_angle": "Lead with learning opportunities, team caliber, and how this role accelerates their career. Name recent initiatives the team shipped or challenges ahead.",
        },
        {
            "archetype_name": "The Ambitious Mover",
            "disc": "D",
            "motivation": "Career acceleration — wants to compress the timeline to senior/staff; optimises for scope, ownership, and promotable impact.",
            "background_style": "Strong performer at their current company but hitting a ceiling — promo process is slow, or the org can't give them the scope they're ready for.",
            "trigger": "Has outgrown their current role and title — actively looking for a step up in ownership, not just a lateral move.",
            "messaging_angle": "Lead with promotion trajectory, scope of ownership from day one, and examples of ICs who've grown quickly here. Show the path to senior is real.",
        },
        {
            "archetype_name": "The Reliable Builder",
            "disc": "S",
            "motivation": "Stability and craft — wants a role they can grow deeply into, on a team with low turnover and high trust.",
            "background_style": "Mid-career with 3–6 years; has found a domain they love and wants to go deeper, not wider; values consistency over novelty.",
            "trigger": "Current team has high attrition or constant context-switching — they want to join somewhere people stay and ship meaningful work over time.",
            "messaging_angle": "Lead with team tenure, project continuity, and what the average day looks like. Show this is a team that invests in its people and their work.",
        },
        {
            "archetype_name": "The Senior-Track IC",
            "disc": "DC",
            "motivation": "Scope expansion — wants to move from execution to influence; ready to lead projects, mentor juniors, and own architectural decisions.",
            "background_style": "3–5 years in; strong individual performer who is being tapped for leadership responsibilities but hasn't been given the title yet.",
            "trigger": "Doing senior work without senior recognition or compensation — looking for a company that will formally invest in their growth.",
            "messaging_angle": "Lead with clear senior promotion criteria, the kind of projects they'd own, and examples of recent mid-level-to-senior promotions. Be specific.",
        },
        {
            "archetype_name": "The Community-Engaged Contributor",
            "disc": "IS",
            "motivation": "Connection and belonging — wants to work on a team with a strong social fabric and industry presence; career and community are intertwined.",
            "background_style": "Active in their local tech community, Slack groups, or online forums; values colleagues they can learn from and be energized by; may be selective based on team vibes.",
            "trigger": "Current job is technically fine but isolated — no team culture, no external presence, and no sense of shared mission.",
            "messaging_angle": "Lead with team events, community involvement, engineering blog, and what makes this team's culture distinctive. Show the team as a community, not just a headcount.",
        },
    ],
    # ─── Mid-level People Manager ─────────────────────────────────────────────
    ("mid", "people_manager"): [
        {
            "archetype_name": "The Technical Leader",
            "disc": "C",
            "motivation": "Engineering craft — manages to protect and elevate quality standards across the team.",
            "background_style": "Grew into management organically from a strong IC foundation; still codes or reviews closely.",
            "trigger": "Current org's engineering bar is slipping — wants to join a team that takes quality seriously.",
            "messaging_angle": "Lead with engineering bar, review culture, and technical decision-making process. Show that managers here stay close to the work.",
        },
        {
            "archetype_name": "The People Developer",
            "disc": "S",
            "motivation": "Team capability and belonging — grows people intentionally and creates stable, high-trust team environments.",
            "background_style": "People-first orientation; natural coach; built early credibility through team health and low attrition.",
            "trigger": "Wants an org that invests in manager development and gives them real tools to grow their reports.",
            "messaging_angle": "Lead with mentorship programs, 1:1 investment, and manager support structures. Show what team culture looks like at this company.",
        },
        {
            "archetype_name": "The Execution-First Manager",
            "disc": "D",
            "motivation": "Delivery — measures success by what the team ships; clears blockers, sets clear priorities, and holds people accountable.",
            "background_style": "PM or tech lead background; comfortable with ambiguity and tight deadlines; known for getting things across the line.",
            "trigger": "Current org has an unclear roadmap or too many competing priorities — wants to own a tight scope and drive it to completion.",
            "messaging_angle": "Lead with roadmap clarity, delivery cadence, and how priorities are set. Show the team ships on a predictable rhythm.",
        },
        {
            "archetype_name": "The Culture Builder",
            "disc": "I",
            "motivation": "Team energy and identity — believes the best teams have a distinct culture and invests in building it deliberately.",
            "background_style": "Known for high team NPS and retention; builds rituals, onboarding, and social fabric intentionally.",
            "trigger": "Current team has no culture by design — attrition is high and nobody has made it a priority.",
            "messaging_angle": "Lead with team culture, onboarding experience, and retention. Show this is a team people choose to join and choose to stay on.",
        },
        {
            "archetype_name": "The Tech-Lead Manager",
            "disc": "CD",
            "motivation": "Bridging execution and craft — manages by staying close to the code; drives technical decisions alongside delivery.",
            "background_style": "New or recent manager who still contributes technically; not ready to go fully hands-off; wants to grow into senior leadership while staying grounded.",
            "trigger": "Current role is pushing them to go fully hands-off before they're ready — wants an org that values technical depth in managers.",
            "messaging_angle": "Lead with how much managers stay technical here and what the path from tech lead to senior manager looks like. Show this is not a forced choice.",
        },
        {
            "archetype_name": "The People-First Operator",
            "disc": "DS",
            "motivation": "Balanced accountability — runs a team that meets its commitments without burning people out; holds delivery AND wellbeing as non-negotiables.",
            "background_style": "Mid-career manager who learned from a burnout-heavy environment early in their career; now builds sustainable team norms as a personal mission.",
            "trigger": "Current org optimises only for velocity — people are burning out, and leadership doesn't see it as a problem.",
            "messaging_angle": "Lead with team sustainability, on-call health, workload norms, and how the company thinks about manager wellbeing. Show this is a sane place to lead.",
        },
    ],
    # ─── Junior / Entry-level IC ──────────────────────────────────────────────
    ("junior", "individual_contributor"): [
        {
            "archetype_name": "The Eager Builder",
            "disc": "D",
            "motivation": "Hands-on reps — wants to ship, make mistakes, and own real things early in their career.",
            "background_style": "CS or bootcamp background; has built side projects; proof-of-ability mindset; reads about the field obsessively.",
            "trigger": "Graduating or current internship ending; wants a full-time home where they can move fast and have real ownership.",
            "messaging_angle": "Lead with early ownership, what they'll ship in the first 90 days, and the caliber of teammates they'll learn from. Show the ramp-up plan.",
        },
        {
            "archetype_name": "The Thoughtful Learner",
            "disc": "S",
            "motivation": "Mentorship and safety — wants structure, good code review culture, and to learn from seniors without burning out.",
            "background_style": "Career changer or deliberate academic background; has mapped out what they want to build over 5 years; risk-averse about their first hire.",
            "trigger": "Evaluating first or second role carefully — won't accept chaos or sink-or-swim environments.",
            "messaging_angle": "Lead with mentorship programs, code review culture, senior investment in juniors, and psychological safety. Show what onboarding looks like.",
        },
        {
            "archetype_name": "The Detail-Oriented Starter",
            "disc": "C",
            "motivation": "Getting it right — perfectionist streak; wants to understand the system deeply before shipping; cares about code quality from day one.",
            "background_style": "Strong academic or self-taught background with a focus on fundamentals; has read books, taken courses, and built careful mental models before entering the workforce.",
            "trigger": "Scared of joining a team that ships sloppy code — wants to start their career with good habits and good examples.",
            "messaging_angle": "Lead with code review culture, documentation standards, and how seniors invest in junior quality. Show the team values doing things right, not just fast.",
        },
        {
            "archetype_name": "The Social Learner",
            "disc": "I",
            "motivation": "Community and growth — learns best by pairing, asking questions, and being part of an engaged team; wants colleagues as much as a job.",
            "background_style": "Active in student orgs, hackathons, or online communities; energized by group learning and peer feedback; thrives with open communication norms.",
            "trigger": "Wants to avoid a remote, quiet, or isolating first job — needs an environment where asking questions is welcomed and celebrated.",
            "messaging_angle": "Lead with pairing culture, team Slack norms, social onboarding, and how approachable senior engineers are. Show this is a team that talks to each other.",
        },
        {
            "archetype_name": "The Ambitious Precise Builder",
            "disc": "DC",
            "motivation": "Fast career growth with high standards — wants to ship real things quickly but refuses to cut corners; has a chip on their shoulder about proving themselves.",
            "background_style": "Competitive academic or bootcamp background; has something to prove; has already shipped a side project or internship deliverable they're proud of.",
            "trigger": "Doesn't want to be a CRUD developer for 2 years — wants early exposure to interesting problems with high-quality code.",
            "messaging_angle": "Lead with what they'll build in their first 6 months, the technical bar of the codebase, and how quickly strong juniors advance here.",
        },
        {
            "archetype_name": "The Mentorship-Seeking Contributor",
            "disc": "SI",
            "motivation": "Guided growth — wants a dedicated mentor or buddy, structured feedback, and a clear 6-month ramp plan; values relationship over raw exposure.",
            "background_style": "First-generation tech professional or career changer; aware of gaps in their network and experience; looking for sponsorship as much as opportunity.",
            "trigger": "Evaluating whether the team will invest in them personally — not just give them tickets to close.",
            "messaging_angle": "Lead with formal mentorship programs, buddy systems, structured 30/60/90 plans, and examples of juniors who were sponsored into meaningful work.",
        },
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# PASSIVE CANDIDATE ARCHETYPE POOLS
# Passive candidates are currently employed, not actively job-hunting, and have
# a much higher "move" bar than active candidates. They need sourcing + outreach,
# not job board ads. Defined by latent dissatisfaction trigger, not explicit
# search intent. Ordered by recruiter-reachability / segment size.
#
# 6 universal passive archetypes per role profile:
#   1. Ambition-Blocked Expert  (D)  — doing the work, not getting the title/scope
#   2. Culture Refugee          (S)  — strong performer, miserable in their environment
#   3. Comp-Lagged Specialist   (C)  — below market, hasn't refreshed in 2+ years
#   4. Mission Drifter          (I)  — company pivoted away from what they joined for
#   5. Scope-Hungry Grower      (DC) — senior output, mid-level ownership
#   6. Pre-Burnout Professional (SI) — still employed, emotionally checking out
# ══════════════════════════════════════════════════════════════════════════════

_MECE_PASSIVE_ARCHETYPES: dict = {
    # ─── Senior Individual Contributor ───────────────────────────────────────
    ("senior", "individual_contributor"): [
        {
            "archetype_name": "The Promo-Blocked Principal",
            "disc": "D",
            "activity_level": "passive",
            "motivation": "Recognition and scope — has been doing Staff/Principal-level work for 12–18 months without the title, leverage, or compensation to match.",
            "background_style": "High performer at a company with a slow or opaque promo process; passed over once or told to 'wait another cycle'; has a strong portfolio of impact but feels capped.",
            "latent_trigger": "A confidential conversation showing they'd get the Staff/Principal title, the corresponding scope (e.g. multi-team or multi-product ownership), and a real comp reset.",
            "outreach_angle": "Lead with the title, the scope of the role, and the fact that their background would let them start at the level they've already been working at. Be specific about what they'd own.",
            "passive_barrier": "Loyalty to teammates; fear of starting over; uncertain the new place is better — not worse.",
            "reachability": "LinkedIn InMail, referral from mutual connection, conference or meetup encounter.",
        },
        {
            "archetype_name": "The Environment Escapee",
            "disc": "S",
            "activity_level": "passive",
            "motivation": "Stability in a team worth trusting — not unhappy with the work itself, but exhausted by the people, process, or culture around the work.",
            "background_style": "Strong IC who joined a company for the mission or tech but found themselves in a dysfunctional team, bad manager, or high-attrition environment.",
            "latent_trigger": "Evidence that the team they'd join is healthy — low attrition, genuine manager investment, peers they'd be proud to work with.",
            "outreach_angle": "Lead with team culture, manager tenure, and team stability signals. Never lead with comp or prestige — they're not motivated by that. They want to trust the people around them.",
            "passive_barrier": "Exhausted from the search for 'the right place'; worried it'll be the same everywhere; protective of their remaining energy.",
            "reachability": "Warm referral from someone who worked on the team. Avoid cold InMail — they're skeptical of anything that sounds like recruiting.",
        },
        {
            "archetype_name": "The Market-Lagged Expert",
            "disc": "C",
            "activity_level": "passive",
            "motivation": "Fair compensation for rare expertise — has developed deep, hard-to-replace skills and suspects (or knows) they're being significantly underpaid versus market.",
            "background_style": "Long-tenure specialist at a company that doesn't do transparent or frequent comp reviews; has accumulated leverage but hasn't acted on it; doing comp research quietly.",
            "latent_trigger": "A credible, specific comp number that makes the gap concrete. They already suspect the gap exists — they just need confirmation it's real and the role is worth the disruption.",
            "outreach_angle": "Be direct about comp range upfront. Lead with the technical scope to establish credibility, then name the comp. Avoid vague 'competitive package' language — they've heard it before.",
            "passive_barrier": "Inertia and transition cost; not sure if it's worth the disruption; loyal to their accumulated technical context.",
            "reachability": "Targeted LinkedIn outreach with explicit comp range in the first message. Technical community Slack groups or Discord servers.",
        },
        {
            "archetype_name": "The Mission-Disappointed Builder",
            "disc": "I",
            "activity_level": "passive",
            "motivation": "Work that matters again — joined for a mission they believed in, but the product has pivoted, been acquired, or deprioritized in ways that feel like a betrayal.",
            "background_style": "IC who self-selected into a mission-driven company; has stayed longer than rational because of team loyalty; now working on something they privately think is meaningless.",
            "latent_trigger": "A clear, specific articulation of what they'd be building, why it matters, and who benefits. Mission needs to pass their personal 'does this make the world better?' filter.",
            "outreach_angle": "Lead with what the product does and who it helps. The mission has to be real — they've been fooled by vague mission statements before. Specificity is credibility.",
            "passive_barrier": "Guilt about leaving teammates; worried they'll make the wrong call again; not sure if anywhere is truly mission-aligned.",
            "reachability": "Engineering blog posts, conference talks, open source contributions, community Slack groups for their domain.",
        },
        {
            "archetype_name": "The Ceiling-Hitting Tech Lead",
            "disc": "DC",
            "activity_level": "passive",
            "motivation": "Real architectural ownership — leads technically but the decisions always get overridden upstream; wants a role with actual authority, not just influence.",
            "background_style": "Senior IC who de facto leads technical direction for their team but has no formal authority over infrastructure, platform, or cross-team standards.",
            "latent_trigger": "A role where they'd be the last decision-maker on a meaningful architectural domain — not a consultant to a decision-maker.",
            "outreach_angle": "Be explicit about decision authority and what they'd own end-to-end. Name the scope of the architecture (infra, platform, a product line) and who they'd report to. Show reporting line clarity.",
            "passive_barrier": "Comfortable with their current technical context; risk of losing knowledge capital; not sure if 'Staff Engineer' at a new company is better or worse.",
            "reachability": "Engineering blog, conference talks, GitHub activity, internal referrals from engineers who've worked with them.",
        },
        {
            "archetype_name": "The Quietly Burning Out Senior",
            "disc": "SI",
            "activity_level": "passive",
            "motivation": "Sustainable pace with interesting work — still capable and motivated, but the current environment has been grinding them down; looking for a reset before it becomes permanent.",
            "background_style": "3–7 year IC who survived a hypergrowth or firefighting phase; once energized, now defensive of their energy; has started optimizing for 'manageable' over 'exciting'.",
            "latent_trigger": "A team that ships meaningful work at a pace that doesn't require heroics — proof that the environment is sustainable, not just described as sustainable.",
            "outreach_angle": "Lead with team norms, on-call health, and sustainable engineering practices. Avoid heroic language ('fast-paced', 'move fast'). They've been there and don't want to go back.",
            "passive_barrier": "Too tired to interview; scared the new place will be worse; unsure if they have the energy to start over.",
            "reachability": "Warm referral only. Cold outreach hits their cynicism filter. A peer who can vouch for the team culture is worth 10 InMail messages.",
        },
    ],
    # ─── People Manager (senior / engineering manager level) ─────────────────
    ("senior", "people_manager"): [
        {
            "archetype_name": "The Director-Ready Manager",
            "disc": "D",
            "activity_level": "passive",
            "motivation": "Scope and title progression — has been managing effectively for 2–3 years, ready for a director title and multi-team ownership, but their current org has no headroom.",
            "background_style": "Engineering manager at a company with a flat leadership structure or slow headcount growth; managed through a successful product launch or reorg but sees no path upward.",
            "latent_trigger": "A director or senior manager role with more headcount, cross-team scope, and a clear path to VP.",
            "outreach_angle": "Lead with team size, scope of ownership, and explicit statement that this role is positioned as a step up. Name the current director/VP they'd report to.",
            "passive_barrier": "Reluctant to give up team they've built; worried about political navigation at a new company.",
            "reachability": "LinkedIn InMail, referral from a peer manager, engineering leadership communities.",
        },
        {
            "archetype_name": "The Manager in a Broken Culture",
            "disc": "S",
            "activity_level": "passive",
            "motivation": "Leading a team that's actually healthy — currently managing in a high-attrition, low-trust environment; spending more time on damage control than people development.",
            "background_style": "Strong people manager stuck in a dysfunctional org; has tried to shield their team but is running out of runway; quietly researching exit options.",
            "latent_trigger": "Evidence of a healthy engineering culture with low attrition, supportive leadership, and real investment in manager development.",
            "outreach_angle": "Lead with retention data, psychological safety, and what the org does for managers. Show the culture from the outside — not just described, but evidenced.",
            "passive_barrier": "Feels responsible for their current team; scared of repeating the same mistake.",
            "reachability": "Engineering leadership Slack communities, warm referral from a manager who trusts the culture.",
        },
        {
            "archetype_name": "The Underpaid Technical Manager",
            "disc": "C",
            "activity_level": "passive",
            "motivation": "Market-rate compensation — knows their technical depth and people leadership combination is rare but hasn't tested the market in 2+ years.",
            "background_style": "IC-to-manager with strong technical credibility; at a company that doesn't benchmark manager comp aggressively; has a nagging sense they're underpaid.",
            "latent_trigger": "A direct, credible comp range that reflects both their technical and management track record.",
            "outreach_angle": "Open with comp range and engineering bar. They're evaluating whether the disruption is worth it — give them the numbers to make the calculation.",
            "passive_barrier": "Comfortable with their technical context; transition cost of rebuilding credibility in a new org.",
            "reachability": "LinkedIn outreach with explicit comp range, engineering leadership conferences.",
        },
        {
            "archetype_name": "The Lost-Mission EM",
            "disc": "I",
            "activity_level": "passive",
            "motivation": "Leading a team on work that matters — joined for a product mission but now manages a maintenance team or a legacy platform they don't believe in.",
            "background_style": "People-driven manager who cares deeply about what their team builds; currently managing a team whose work feels disconnected from any meaningful user impact.",
            "latent_trigger": "A team building something they'd be proud to recruit for — where the product roadmap is exciting and the manager can sell it honestly.",
            "outreach_angle": "Lead with what the team builds, who uses it, and why it matters. Give them something real to be excited about — they'll recruit for it if they believe in it.",
            "passive_barrier": "Loyalty to their current team members; worried about abandoning people who depend on them.",
            "reachability": "Engineering blog, Slack community leadership forums, referral from engineers on the team.",
        },
        {
            "archetype_name": "The Scope-Starved Manager",
            "disc": "DC",
            "activity_level": "passive",
            "motivation": "Cross-functional ownership — currently managing a single small team with no influence on product strategy or cross-team direction; wants a broader mandate.",
            "background_style": "Effective EM who has solved their current team's challenges and is now bored; ready for a larger team, multi-team scope, or a director-track role.",
            "latent_trigger": "A role with meaningful headcount growth, cross-team responsibilities, or a seat at product planning conversations.",
            "outreach_angle": "Be specific about team size, reporting structure, and what decisions they'd have influence over. Scope and authority are the hook.",
            "passive_barrier": "Risk of looking like a lateral move; not sure new scope is real or will materialize.",
            "reachability": "LinkedIn, referral from a director or VP who can vouch for the scope being real.",
        },
        {
            "archetype_name": "The Burning-Out People Lead",
            "disc": "SI",
            "activity_level": "passive",
            "motivation": "A manageable, purposeful workload — currently absorbing team dysfunction, leadership gaps above them, and product chaos; giving more than they're getting back.",
            "background_style": "High-empathy manager who never learned to protect their own energy; team runs well because they've absorbed all the friction from above and below.",
            "latent_trigger": "A role with a clear scope, a good manager above them, and a team they don't have to rescue from dysfunction on day one.",
            "outreach_angle": "Lead with manager support, team stability, and what the EM would NOT have to deal with. Removal of negatives is more compelling than positive promises for this archetype.",
            "passive_barrier": "Too depleted to think about a transition; feels guilty about leaving their team mid-crisis.",
            "reachability": "Warm referral only. Their guard is high and their energy is low — only a trusted voucher will get through.",
        },
    ],
    # ─── Director / Head of ───────────────────────────────────────────────────
    ("director", "people_manager"): [
        {
            "archetype_name": "The VP-Ready Director",
            "disc": "D",
            "activity_level": "passive",
            "motivation": "Executive-level authority — has been driving org-wide impact as a director but has no VP headroom above them; the layer is occupied and isn't moving.",
            "background_style": "High-performing director at a stable or post-hypergrowth company; has proven they can run a large org but is capped by the current structure.",
            "latent_trigger": "A VP or Senior Director title with real P&L or product line ownership — not a title inflation, but a genuine step in decision authority.",
            "outreach_angle": "Open with the title, reporting line, and the scope of what they'd own. Be explicit that this is a promotion, not a lateral move.",
            "passive_barrier": "Knows the politics of a new company; sceptical of 'VP' titles that are nominal.",
            "reachability": "Direct LinkedIn outreach from the hiring executive or a trusted peer network referral.",
        },
        {
            "archetype_name": "The Culture-Fled Director",
            "disc": "S",
            "activity_level": "passive",
            "motivation": "Leading in a functional, values-aligned org — currently in a company where leadership values don't match what they model for their teams.",
            "background_style": "Director known for high-trust, high-retention teams; working in an org where exec behavior contradicts the values they try to instill.",
            "latent_trigger": "Evidence of exec team alignment on values — how the C-suite actually behaves, not what the company website says.",
            "outreach_angle": "Lead with specific executive behavior and culture signals. Name people on the leadership team they can research. Avoid culture buzzwords — they know what they mean.",
            "passive_barrier": "Deep skepticism of culture claims; has been fooled before; protective of their team's stability.",
            "reachability": "Peer referral from someone who has seen the culture from the inside.",
        },
        {
            "archetype_name": "The Comp-Reset Director",
            "disc": "C",
            "activity_level": "passive",
            "motivation": "Market-rate compensation at their level — director comp at their company hasn't kept pace with the market; they haven't benchmarked in 2+ years.",
            "background_style": "Methodical leader who doesn't make moves impulsively; building a case internally but getting resistance from HR or finance.",
            "latent_trigger": "A credible, research-backed comp offer that makes the market gap undeniable and the new role worth the disruption.",
            "outreach_angle": "Be direct about total comp (base + equity). Directors do the math — don't make them guess. Include equity vesting and refresh cadence.",
            "passive_barrier": "Equity vesting cliff; political capital built over years; fear of starting the credibility game over.",
            "reachability": "Direct LinkedIn InMail with comp range stated, or executive recruiter introduction.",
        },
        {
            "archetype_name": "The Mission-Misaligned Director",
            "disc": "I",
            "activity_level": "passive",
            "motivation": "Leading an org where the mission is personally meaningful — has built strong teams but the company's strategic direction no longer aligns with why they do this work.",
            "background_style": "Director who joined for a specific product or social mission; company has been acquired, pivoted to enterprise, or lost its original identity.",
            "latent_trigger": "A mission they can personally believe in and sell to their future team — something real, not PR.",
            "outreach_angle": "Lead with mission specificity. Name what users or markets they'd serve. Show why this problem is worth solving at this company, in this moment.",
            "passive_barrier": "Has been burned by mission-washing before; sceptical that any company's stated mission matches daily reality.",
            "reachability": "Speaking engagements, industry conferences, engineering leadership communities, referral from a mission-credible peer.",
        },
        {
            "archetype_name": "The Blocked-Strategist Director",
            "disc": "DC",
            "activity_level": "passive",
            "motivation": "Strategic autonomy — develops strong org and technical strategies but has them consistently overridden or watered down by a VP layer that doesn't delegate.",
            "background_style": "Director with strong strategic instincts working under a micromanaging VP; their plans get modified upward before they can execute.",
            "latent_trigger": "A role where they'd have real decision authority — explicit clarity on what they own end-to-end without layers second-guessing them.",
            "outreach_angle": "Be specific about who they'd report to and how that person operates. Name the operating model. Show the VP/exec they'd work with has a track record of delegating.",
            "passive_barrier": "Doesn't want to trade one micromanager for another; wants to verify the autonomy claim before making a move.",
            "reachability": "Referral from the hiring VP's direct reports, LinkedIn from the hiring exec directly.",
        },
        {
            "archetype_name": "The Exhausted Builder Director",
            "disc": "SI",
            "activity_level": "passive",
            "motivation": "Sustainable leadership at scale — has been the load-bearing wall of a scaling org; absorbed the dysfunction of two reorgs and a leadership vacuum above them.",
            "background_style": "High-empathy director who has over-indexed on protecting their teams; running on fumes; privately worried their leadership quality is declining.",
            "latent_trigger": "An org with a healthy exec team above them and a mandate that doesn't require them to compensate for systemic dysfunction.",
            "outreach_angle": "Lead with what would NOT be their problem in this role. Show executive team stability and a healthy org above the role, not just below it.",
            "passive_barrier": "Deeply depleted; high transition cost; scared the new role will have the same hidden dysfunction.",
            "reachability": "Warm peer referral only. Skeptical of cold outreach, especially anything that sounds like an exaggerated opportunity.",
        },
    ],
    # ─── Executive (VP, C-suite) ─────────────────────────────────────────────
    ("executive", "people_manager"): [
        {
            "archetype_name": "The C-Suite-Ready VP",
            "disc": "D",
            "activity_level": "passive",
            "motivation": "Full P&L ownership — has run a large org with strong results but is one layer below the decision-making table; wants a CTO/CPO or equivalent seat.",
            "background_style": "Strong VP who has been passed over for C-suite internally or joined a company that hired externally above them; has board-level credibility but lacks the title.",
            "latent_trigger": "A C-suite role with genuine authority — not an expanded VP title, but a seat where they set the agenda, not execute someone else's.",
            "outreach_angle": "Open with the reporting structure and the board relationship. Be explicit about what strategic decisions are theirs to make. Exec search firm introduction preferred.",
            "passive_barrier": "Equity cliff; board relationships built at current company; sceptical of 'fractional' or 'acting' C-suite roles.",
            "reachability": "Executive search firm (retained), board member referral, peer C-suite network.",
        },
        {
            "archetype_name": "The Values-Broken Executive",
            "disc": "S",
            "activity_level": "passive",
            "motivation": "Executive team alignment — is a strong operator but has lost faith in the character or values of their CEO or board; staying for equity but checking out.",
            "background_style": "VP or C-1 exec at a company where recent leadership decisions (layoffs mishandled, culture promises broken, ethical compromises) have eroded their commitment.",
            "latent_trigger": "Evidence that the founding team or CEO is someone they can respect and learn from — not just a compelling pitch, but a track record of principled decisions.",
            "outreach_angle": "Let them talk to the CEO directly early in the process. They're evaluating the person, not the job description. Give them access, not more collateral.",
            "passive_barrier": "Equity vesting; public brand tied to current company; fear of burning bridges.",
            "reachability": "Peer exec referral, board member who knows them personally.",
        },
        {
            "archetype_name": "The Equity-Reset Executive",
            "disc": "C",
            "activity_level": "passive",
            "motivation": "Meaningful equity upside — has significant unvested equity at a company where growth has stalled or the exit thesis has weakened; doing the math on staying vs. moving.",
            "background_style": "Exec at a Series C–E company that has missed milestones, done a down round, or seen its exit horizon pushed out significantly; doing quiet optionality planning.",
            "latent_trigger": "A credible equity package at a company with a clear, believable path to liquidity — not promises, but business fundamentals that support the exit story.",
            "outreach_angle": "Lead with equity structure and the exit thesis. Provide data: ARR growth, runway, investor syndicate, comparable exits. They will do the math — give them something real to calculate.",
            "passive_barrier": "Unvested equity at current company; uncertainty about new company's exit; fear of bad timing.",
            "reachability": "Executive search firm, investor referral (the portfolio company CEO or board member), peer exec network.",
        },
        {
            "archetype_name": "The Meaning-Seeking Executive",
            "disc": "I",
            "activity_level": "passive",
            "motivation": "Legacy and purpose — has achieved financial and career success but is asking 'what do I want the next 10 years to stand for?'; increasingly driven by impact over comp.",
            "background_style": "Financially secure exec at a company that's technically successful but no longer exciting; may be quietly exploring board seats, advisory roles, or mission-driven orgs.",
            "latent_trigger": "A mission that could become their 'chapter 2' — something they'd be proud to build regardless of financial outcome.",
            "outreach_angle": "Lead with mission and impact. Comp is secondary — they need to believe this is a problem worth spending the next decade on. Be honest about the difficulty of the challenge.",
            "passive_barrier": "Inertia of success; fear of a step down in brand prestige; uncertainty about what 'meaningful' really means for them.",
            "reachability": "Conference keynotes, board advisory network, peer exec introductions through shared investors.",
        },
        {
            "archetype_name": "The Autonomy-Constrained VP",
            "disc": "DC",
            "activity_level": "passive",
            "motivation": "Strategic ownership — has strong opinions and execution capability but is in a company where the CEO or founder is highly controlling; their strategy keeps getting overridden.",
            "background_style": "VP at a founder-led company where the founder hasn't fully transitioned to a CEO model; the VP's role is more execution than strategy.",
            "latent_trigger": "A role with genuine strategic ownership — evidence that the exec team runs the business, not just executes the founder's intuition.",
            "outreach_angle": "Be specific about decision rights and governance. Name what decisions are the VP's to make unilaterally vs. collaboratively. Founder-operator dynamic matters — address it directly.",
            "passive_barrier": "Comfortable with the product domain; has built credibility in a specific technical/market area they'd have to rebuild.",
            "reachability": "Executive recruiter who can provide candid color on the leadership model, peer network referral.",
        },
        {
            "archetype_name": "The Quietly Exiting Executive",
            "disc": "SI",
            "activity_level": "passive",
            "motivation": "A genuinely sustainable leadership environment — has been the company's shock absorber through a difficult period; privately planning their exit but not in a rush.",
            "background_style": "Exec who has stayed through a turnaround, a difficult board situation, or a values-misaligned period out of loyalty; their team doesn't know they're thinking about leaving.",
            "latent_trigger": "An org where the culture is genuinely healthy at the top, not just described as healthy — a place where they can lead without constantly managing upward dysfunction.",
            "outreach_angle": "Be patient and relationship-first. This archetype doesn't respond to urgency. A first conversation about their career, not the role, is the right opener.",
            "passive_barrier": "Loyalty to their team; emotional cost of leaving after investing so much; fear of looking like they're abandoning ship.",
            "reachability": "Executive coach network, peer C-suite introduction, long-term exec recruiter relationship.",
        },
    ],
    # ─── Mid-level Individual Contributor ─────────────────────────────────────
    ("mid", "individual_contributor"): [
        {
            "archetype_name": "The Promo-Blocked Mid",
            "disc": "D",
            "activity_level": "passive",
            "motivation": "Overdue title and scope — has been performing at the next level but the promo cycle has passed them twice; not angry yet, but the clock is running out.",
            "background_style": "3–5 year engineer doing senior-level work without the title; got a 'not yet' with vague criteria; starting to look at other options quietly.",
            "latent_trigger": "A role that starts at senior level — an immediate title match to the work they're already doing, not a promise that it might happen.",
            "outreach_angle": "Lead with the level and what they'd own from day one. Name specific projects or systems they'd be responsible for. Be clear it's a senior-level offer, not a senior-track offer.",
            "passive_barrier": "Loyalty to their team; hope that the next promo cycle is different; transition cost of rebuilding context.",
            "reachability": "LinkedIn, GitHub profile, internal referral from a colleague who's already at the company.",
        },
        {
            "archetype_name": "The Quiet Unhappy Mid",
            "disc": "S",
            "activity_level": "passive",
            "motivation": "A team worth staying on — technically competent but drained by team dynamics, a bad manager, or a high-attrition environment that keeps resetting their context.",
            "background_style": "Mid-level IC who has been at a company 2–4 years and has seen too many teammates leave; starting to wonder if they're the problem or the company is.",
            "latent_trigger": "A stable team with low attrition where they could go deep on a problem over multiple years without the environment constantly resetting.",
            "outreach_angle": "Lead with team tenure, manager stability, and what the average IC's tenure looks like. They want to join somewhere people stay.",
            "passive_barrier": "Not sure if anywhere is actually better; scared of going somewhere worse.",
            "reachability": "Peer referral from a current team member who can speak to the culture honestly.",
        },
        {
            "archetype_name": "The Quietly Underpaid Mid",
            "disc": "C",
            "activity_level": "passive",
            "motivation": "Market-rate pay for their skills — has been doing good work at a company that doesn't proactively revisit comp; is doing research and doesn't like what they're finding.",
            "background_style": "2–5 year IC at a company with infrequent or below-market raises; looked at levels.fyi or Glassdoor recently and saw a gap; not in a rush but noticing.",
            "latent_trigger": "A concrete comp number that closes the gap — they're not looking to get rich, just to be paid fairly for what they do.",
            "outreach_angle": "State the comp range in the first message. For this archetype, vague outreach is filtered immediately. They've been gaslit by 'competitive comp' enough times.",
            "passive_barrier": "Low risk tolerance; comfortable with the known; transition risk feels high for a comp correction.",
            "reachability": "LinkedIn InMail with explicit comp, engineering community Slack groups, job board browsing in private mode.",
        },
        {
            "archetype_name": "The Disconnected Builder",
            "disc": "I",
            "activity_level": "passive",
            "motivation": "Work that connects to real user impact — currently building features that feel disconnected from users; unclear if anything they ship matters.",
            "background_style": "Mid-level IC at a company with a weak product sense or an internal tools focus; shipped a lot but doesn't know if any of it moved a metric they care about.",
            "latent_trigger": "A product with clear user feedback loops — evidence that the team knows if what they ship works, and that they care.",
            "outreach_angle": "Lead with product culture and how the team stays close to users. Mention metrics, user research, or feedback loops. Show them they'd see their work matter.",
            "passive_barrier": "Comfortable with their current stack and team; unsure if 'user impact' is real at any company or just marketing.",
            "reachability": "Product/engineering community Slack groups, engineering blog comments, Twitter/X tech communities.",
        },
        {
            "archetype_name": "The Under-Challenged Mid",
            "disc": "DC",
            "activity_level": "passive",
            "motivation": "Harder problems — has mastered their current domain and is bored; the work is comfortable but no longer challenging; privately worried they're getting dumber.",
            "background_style": "Strong mid-level IC who's become the team expert in their area and now mostly answers questions and reviews PRs rather than solving hard problems.",
            "latent_trigger": "A role with unsolved, genuinely hard technical problems at a scale or complexity they haven't encountered before.",
            "outreach_angle": "Lead with the technical challenge. Name the hard problem — don't just say 'interesting work'. If there's scale, complexity, or novelty, name it specifically.",
            "passive_barrier": "Comfortable with their current expertise; fear of being a beginner again; don't want to take a step back in perceived seniority.",
            "reachability": "Technical blog comments, open source contributions, conference talks or workshops in their domain.",
        },
        {
            "archetype_name": "The Drifting Coaster",
            "disc": "SI",
            "activity_level": "passive",
            "motivation": "Renewed purpose — has been at the same company long enough that muscle memory runs the job; not unhappy exactly, but knows they've stopped growing.",
            "background_style": "4–7 year IC who optimized for comfort after a difficult period; still competent but not applying themselves; occasionally wonders if they've become too comfortable.",
            "latent_trigger": "A compelling enough opportunity that makes continuing to coast feel like an obvious mistake — has to be specific, credible, and represent a meaningful step up.",
            "outreach_angle": "Don't sell the role hard — plant a specific question about their current situation that activates their latent dissatisfaction. The role sells itself once they admit they've stopped growing.",
            "passive_barrier": "High inertia; good enough is comfortable; social cost of leaving a team that depends on them.",
            "reachability": "Warm referral from a peer they respect; someone who can say 'this is the kind of work you used to get excited about'.",
        },
    ],
    # ─── Mid-level People Manager ─────────────────────────────────────────────
    ("mid", "people_manager"): [
        {
            "archetype_name": "The Promotion-Stalled EM",
            "disc": "D",
            "activity_level": "passive",
            "motivation": "Senior EM or Director title — has been managing effectively for 18+ months, ready for more headcount and cross-team scope, but the org is flat or frozen.",
            "background_style": "Effective EM at a post-growth company with a tight headcount budget; has grown their team's output but can't grow their team's size.",
            "latent_trigger": "A senior manager or director-track role with a real path to managing managers within 12–18 months.",
            "outreach_angle": "Lead with team size trajectory and what the promotion path looks like. Name what senior EM or director criteria look like at this company. Be specific.",
            "passive_barrier": "Loyalty to their team; uncertain the new place will actually deliver on the growth promise.",
            "reachability": "LinkedIn, engineering manager Slack communities, referral from a peer EM who's made a similar move.",
        },
        {
            "archetype_name": "The Manager Poorly Supported",
            "disc": "S",
            "activity_level": "passive",
            "motivation": "Being managed well themselves — is a strong people developer but has a bad manager above them; gets no coaching, no advocacy, no air cover.",
            "background_style": "Good manager who gives their reports what they never got; working for a director or VP who is disengaged, political, or technically out of touch.",
            "latent_trigger": "A director or VP they'd respect, learn from, and who would actively advocate for them.",
            "outreach_angle": "Lead with the manager they'd report to — their leadership style, their track record, and how they support their EMs. Make the manager credible and specific.",
            "passive_barrier": "Not sure if any manager is actually better; scared of jumping from bad to worse.",
            "reachability": "Referral from someone who can vouch for the hiring manager personally.",
        },
        {
            "archetype_name": "The Comp-Gap EM",
            "disc": "C",
            "activity_level": "passive",
            "motivation": "Fair total comp for management scope — has taken on management responsibilities without a proportional comp increase; knows they're underpriced.",
            "background_style": "IC who transitioned to management at the same company; didn't negotiate hard at transition; has seen new EM hires come in at higher packages.",
            "latent_trigger": "An offer that reflects management scope — base, equity, and bonus structure that matches their current level of responsibility.",
            "outreach_angle": "State total comp upfront including any management bonus structure. They've done the internal math and know the gap — confirm it's real with a number.",
            "passive_barrier": "Team loyalty; uncertainty about whether the new package is actually better after taxes and equity cliff.",
            "reachability": "LinkedIn InMail with comp stated, engineering manager communities like Rands Leadership Slack.",
        },
        {
            "archetype_name": "The Purpose-Hungry Manager",
            "disc": "I",
            "activity_level": "passive",
            "motivation": "Leading a team building something meaningful — currently manages a team on a legacy product or internal tool; wants to be energized by what their team ships.",
            "background_style": "People-first manager who finds motivation in the mission as much as in the team; currently managing a team whose roadmap they can't sell to new hires with a straight face.",
            "latent_trigger": "A product area with a clear, exciting roadmap that they can recruit for honestly.",
            "outreach_angle": "Lead with the team's roadmap and what they'd be building in the next 12 months. If it's exciting, say exactly why. If you can't make it exciting, this archetype won't bite.",
            "passive_barrier": "Team loyalty; fear of joining a company with a shiny roadmap that evaporates post-hire.",
            "reachability": "Engineering manager communities, referral from a team member who joined recently.",
        },
        {
            "archetype_name": "The Technically Suffocated EM",
            "disc": "DC",
            "activity_level": "passive",
            "motivation": "Staying close to the technical work — currently in an EM role that has gone fully hands-off; misses engaging with technical decisions and is feeling distance from the craft.",
            "background_style": "Strong IC who moved into management but didn't want to go fully non-technical; at a company where managers are expected to be pure people managers.",
            "latent_trigger": "A role where managers are expected (or at least allowed) to stay technical — reviewing PRs, contributing to architecture decisions, and not being 'people managers only'.",
            "outreach_angle": "Lead with how technical this EM role is. Name what technical involvement looks like day-to-day. Show they won't have to choose between managing and staying sharp.",
            "passive_barrier": "Unsure any company truly lets managers stay technical at scale.",
            "reachability": "GitHub, engineering conference talks, technical leadership communities.",
        },
        {
            "archetype_name": "The Surviving Burnout EM",
            "disc": "SI",
            "activity_level": "passive",
            "motivation": "A role that doesn't consume their entire life — currently managing through chaos (constant reorgs, understaffed team, unclear priorities) with no end in sight.",
            "background_style": "Caring manager who over-invests in their team at the expense of their own wellbeing; has taken on scope that should be distributed across two EMs.",
            "latent_trigger": "A clearly scoped, adequately staffed team with a director above them who understands workload limits.",
            "outreach_angle": "Lead with team size, how priorities are set, and what support structure exists for EMs. Explain what they would NOT inherit on day one.",
            "passive_barrier": "Too tired to interview; worried new role will have the same hidden chaos.",
            "reachability": "Warm referral only. Too depleted for cold outreach to feel worth responding to.",
        },
    ],
    # ─── Junior / Entry-level IC ──────────────────────────────────────────────
    ("junior", "individual_contributor"): [
        {
            "archetype_name": "The Growth-Starved Junior",
            "disc": "D",
            "activity_level": "passive",
            "motivation": "Faster learning and real ownership — has been in their first role 12–18 months, doing repetitive tickets with no mentorship or increasing scope.",
            "background_style": "Junior who hit the ground running but found themselves stuck in a backlog of small tasks with no one investing in their growth; starting to feel their career is stalling.",
            "latent_trigger": "Evidence of a structured ramp-up that leads to real ownership within 6–9 months — a trajectory, not just a promise.",
            "outreach_angle": "Lead with a specific 30/60/90 plan and what they'd own by month 6. Show, don't tell. Vague 'great learning opportunity' language won't move them.",
            "passive_barrier": "Doesn't want to look like a job hopper after 12–18 months; worried a new company might be worse.",
            "reachability": "LinkedIn, GitHub, coding community Slack groups, bootcamp alumni networks.",
        },
        {
            "archetype_name": "The Mentorship-Deprived Junior",
            "disc": "S",
            "activity_level": "passive",
            "motivation": "A team that actually invests in them — was told the job would include mentorship and code reviews; in practice, they're on their own and their skills aren't developing.",
            "background_style": "Junior who needs structure to grow but landed in a sink-or-swim environment; technically surviving but not learning at the rate they hoped.",
            "latent_trigger": "Concrete evidence that seniors invest in junior growth — paired programming culture, structured code reviews, a named mentor or buddy system.",
            "outreach_angle": "Lead with the mentorship model. Name who would mentor them, what code review culture looks like, and how much senior time they'd get each week.",
            "passive_barrier": "Fear that the promise of mentorship won't materialize at the new place either.",
            "reachability": "Bootcamp alumni groups, college career networks, LinkedIn with specific mention of mentorship culture.",
        },
        {
            "archetype_name": "The Skill-Plateau Junior",
            "disc": "C",
            "activity_level": "passive",
            "motivation": "Technical depth — has been doing CRUD work for 12+ months and feels their skills aren't growing; wants exposure to harder problems and better engineering practices.",
            "background_style": "Self-taught or bootcamp grad who pushed into a job quickly but landed somewhere with low technical standards; knows they're not developing the skills they need.",
            "latent_trigger": "A codebase with high engineering standards and colleagues who will challenge them technically.",
            "outreach_angle": "Lead with the technical bar and what they'd learn in the first year. Name the technologies, practices, and caliber of engineers they'd work alongside.",
            "passive_barrier": "Doesn't want to be the worst person in the room; scared of failing in a higher-standards environment.",
            "reachability": "GitHub portfolio, technical Discord servers, engineering bootcamp communities.",
        },
        {
            "archetype_name": "The Isolated Junior",
            "disc": "I",
            "activity_level": "passive",
            "motivation": "Team belonging — working fully remote with no social engineering culture; no peer connection, no watercooler learning, no shared identity with their team.",
            "background_style": "Junior who thrives in social environments but is stuck in a remote job with async-only communication; learning is slow and motivation is dropping.",
            "latent_trigger": "A team with an active, social engineering culture — synchronous collaboration, pairing, team rituals, and a sense of shared identity.",
            "outreach_angle": "Lead with team culture, communication norms, and whether the team is remote, hybrid, or in-person. Show the team exists as a community, not just a Slack workspace.",
            "passive_barrier": "Remote work offers flexibility they value; worried an in-person requirement trades one problem for another.",
            "reachability": "Local tech meetups, coding bootcamp communities, LinkedIn with culture signals.",
        },
        {
            "archetype_name": "The Restless Overachiever",
            "disc": "DC",
            "activity_level": "passive",
            "motivation": "Being taken seriously — is clearly one of the strongest juniors at their company but is still treated as a junior in every decision and conversation.",
            "background_style": "High-output junior who has already exceeded their initial role expectations but hasn't been given more responsibility; itching to contribute above their title.",
            "latent_trigger": "A team that gives ownership based on demonstrated capability, not tenure — somewhere they could be punching above their weight class within 6 months.",
            "outreach_angle": "Lead with how quickly strong juniors get real ownership here. Give examples. Show the progression is based on performance, not just time in seat.",
            "passive_barrier": "Doesn't want to be back at 'junior' in a new environment; worried a new company will also underutilize them.",
            "reachability": "GitHub profile with strong commit history, bootcamp top-of-class networks, direct LinkedIn outreach from the hiring manager (not a recruiter).",
        },
        {
            "archetype_name": "The Quiet Validator",
            "disc": "SI",
            "activity_level": "passive",
            "motivation": "Confirmation that a better environment exists — not quite unhappy enough to actively look, but when a credible opportunity appears, they evaluate it carefully.",
            "background_style": "Junior who is fine at their current company but privately wonders if the grass is greener; will engage if approached thoughtfully but won't apply on their own.",
            "latent_trigger": "A credible, specific opportunity that makes them think 'this is exactly what I wished my current job was' — precise enough to be real.",
            "outreach_angle": "Be specific about what's different here. Don't just describe the role — describe why this place is different from wherever they currently are. Make it feel honest, not like a pitch.",
            "passive_barrier": "Low urgency; generally comfortable; won't make a move without very high conviction.",
            "reachability": "Warm peer referral is the only reliable channel. They're not browsing anything actively.",
        },
    ],
}


def _get_passive_archetypes(seniority: str, role_type: str, count: int = 3) -> list:
    """
    Return `count` passive candidate archetypes for this (seniority, role_type).
    Passive candidates are currently employed and need outreach, not job board ads.
    `count` is clamped to [1, len(pool)]. Default is 3.
    """
    key = (seniority, role_type)
    if key in _MECE_PASSIVE_ARCHETYPES:
        pool = _MECE_PASSIVE_ARCHETYPES[key]
    elif role_type == "people_manager":
        if seniority in ("senior", "manager"):
            pool = _MECE_PASSIVE_ARCHETYPES[("senior", "people_manager")]
        elif seniority == "director":
            pool = _MECE_PASSIVE_ARCHETYPES[("director", "people_manager")]
        else:
            pool = _MECE_PASSIVE_ARCHETYPES[("executive", "people_manager")]
    else:
        if seniority in ("senior", "staff", "principal"):
            pool = _MECE_PASSIVE_ARCHETYPES[("senior", "individual_contributor")]
        elif seniority == "junior":
            pool = _MECE_PASSIVE_ARCHETYPES[("junior", "individual_contributor")]
        else:
            pool = _MECE_PASSIVE_ARCHETYPES[("mid", "individual_contributor")]

    n = max(1, min(count, len(pool)))
    return pool[:n]


def _get_mece_archetypes(seniority: str, role_type: str, count: int = 2) -> list:
    """
    Return `count` MECE archetypes for this (seniority, role_type) combination.
    Archetypes are ordered by market prevalence — the first 2 cover the broadest
    candidate segments; each additional one adds orthogonal coverage.
    `count` is clamped to [2, len(pool)] so callers can request 2–6 safely.
    Falls back gracefully across tiers when no exact key match exists.
    """
    key = (seniority, role_type)
    if key in _MECE_ARCHETYPES:
        pool = _MECE_ARCHETYPES[key]
    elif role_type == "people_manager":
        if seniority in ("senior", "manager"):
            pool = _MECE_ARCHETYPES[("senior", "people_manager")]
        elif seniority == "director":
            pool = _MECE_ARCHETYPES[("director", "people_manager")]
        else:
            pool = _MECE_ARCHETYPES[("executive", "people_manager")]
    else:
        # IC fallbacks by seniority tier
        if seniority in ("senior", "staff", "principal"):
            pool = _MECE_ARCHETYPES[("senior", "individual_contributor")]
        elif seniority == "junior":
            pool = _MECE_ARCHETYPES[("junior", "individual_contributor")]
        else:
            pool = _MECE_ARCHETYPES[("mid", "individual_contributor")]

    # Clamp count to [2, pool size]
    n = max(2, min(count, len(pool)))
    return pool[:n]


def _detect_role_type(text: str) -> str:
    """
    Detect whether this is a people manager or individual contributor role.
    First checks the job title area (first 200 chars) for "Manager", "Director",
    "Head of", "VP" which almost always implies people management.
    Then checks the body for explicit management responsibility language.
    """
    # Use ONLY the first non-empty line as the job title — prevents company org descriptions
    # (e.g. "Executive Director of Care at Genesis") from contaminating frontline roles
    first_line = next((ln.strip() for ln in text.split("\n") if len(ln.strip()) >= 2), text[:80])
    body = text

    # Title-level signals: Manager/Director/VP/Head in the job title = people manager
    title_mgr = bool(re.search(
        r"\bmanager\b|\bdirector\b|\bvp\b|vice\s+president|\bhead\s+of\b|\bvp,\b",
        first_line, re.IGNORECASE
    ))
    # Body signals: explicit management responsibility described in JD
    body_mgr = bool(re.search(
        # "direct reports?" excluded as bare phrase — catches "no direct reports" (false pos).
        # Instead require explicit context: "has/have/your/manage direct reports"
        r"manage[sd]?\s+(?:a\s+)?team|(?:has|have|your|manage[sd]?)\s+direct\s+reports?|people\s+manager|hiring\s+manager"
        r"|build\s+(?:and\s+grow\s+)?(?:the\s+)?team|grow\s+the\s+team"
        r"|team\s+of\s+\d+\s+(?:engineers?|people|employees?|professionals?)"
        r"|lead\s+(?:and\s+mentor|a\s+team)|manage\s+engineers?"
        r"|manage\s+(?:a\s+)?group|org\s+leader|people\s+leadership"
        r"|mentor\s+and\s+coach|engineering\s+lead\b"
        r"|chapter\s+lead\b|squad\s+lead\b|people\s+management\s+responsibilit"
        r"|owns?\s+headcount|cross.functional\s+leader|manage\s+\d+\s+engineer"
        r"|oversee[sd]?\s+(?:a\s+)?team|responsible\s+for\s+(?:a\s+)?team",
        body, re.IGNORECASE
    ))
    # Explicit IC override: "no direct reports", "IC role", "individual contributor",
    # "no management responsibilities" — beats title-level signals.
    # Handles: "Product Manager, no direct reports" → IC, not people_manager.
    body_ic = bool(re.search(
        r"no\s+direct\s+reports?|no\s+management\s+responsibilit|individual\s+contributor"
        r"|\bIC\s+role\b|non.?managerial|no\s+people\s+management",
        body, re.IGNORECASE
    ))
    if body_ic:
        return "individual_contributor"
    return "people_manager" if (title_mgr or body_mgr) else "individual_contributor"


def _build_llm_prompt(signals: dict) -> str:
    """Build the user prompt from signals dict, including JD excerpt for grounding."""
    role_type = signals.get("role_type", "individual_contributor")
    role_type_label = "PEOPLE MANAGER (manages a team, has direct reports)" if role_type == "people_manager" else "INDIVIDUAL CONTRIBUTOR (no direct reports)"

    parts = []
    # MECE archetype instruction (takes priority over generic variant instruction)
    if signals.get("mece_archetype"):
        arch = signals["mece_archetype"]
        parts.append(
            f"MECE ARCHETYPE CONSTRAINT — generate exactly this candidate archetype:\n"
            f"  Archetype name: {arch['archetype_name']}\n"
            f"  DISC type: {arch['disc']}  ← mandatory, do not change\n"
            f"  Core motivation: {arch['motivation']}\n"
            f"  Background style: {arch['background_style']}\n"
            f"  Context trigger: {arch['trigger']}\n"
            f"  Messaging angle: {arch['messaging_angle']}\n"
            f"The archetype name, DISC type, and motivation are fixed. "
            f"All other fields (name, core_job, functional_goals, background, etc.) "
            f"MUST be grounded in the actual JD provided — do not invent details not implied by the JD."
        )
    elif signals.get("persona_variant") == 2:
        # Legacy fallback if mece_archetype not provided
        first = signals.get("first_persona_summary", "the first persona")
        parts.append(
            f"VARIATION REQUIREMENT: Generate an ALTERNATIVE candidate archetype for the same role.\n"
            f"The first persona was: {first}.\n"
            f"Your new persona MUST have: a different DISC type, different career background, "
            f"different primary motivation, and a different archetype name. "
            f"Do not repeat any field values from the first persona."
        )

    parts += [
        f"Role type: {role_type_label}",
        f"Industry: {signals['industry']}",
        f"Seniority: {signals['seniority']}",
        f"Location: {signals['location']}",
        f"Work arrangement: {signals['work_arrangement']}",
        f"Salary: {signals['salary']}",
        f"Skills explicitly in JD: {', '.join(signals.get('skills', [])) or 'none extracted'}",
        f"Clearance required: {signals.get('clearance', False)}",
        f"Bilingual required: {signals.get('bilingual', False)}",
        f"Veteran pathway: {signals.get('veteran', False)}",
    ]
    # Ground the LLM in the actual JD text (first 800 chars)
    if signals.get("jd_excerpt"):
        parts.append(f"\nActual JD excerpt (use this to derive specific skills, scope, technologies — do NOT invent skills not mentioned here):\n{signals['jd_excerpt']}")
    if signals.get("li_industries"):
        parts.append(f"LinkedIn top industries: {', '.join(signals['li_industries'])}")
    if signals.get("li_colleges"):
        parts.append(f"LinkedIn top schools: {', '.join(signals['li_colleges'])}")
    if signals.get("pdl_prior_employers"):
        parts.append(f"Typical prior employers (PDL data): {', '.join(signals['pdl_prior_employers'])}")
    if signals.get("lightcast_skills"):
        parts.append(f"Top skills in market demand (Lightcast): {', '.join(signals['lightcast_skills'])}")
    if signals.get("sparktoro_sites"):
        parts.append(f"Audience visits these sites (SparkToro): {', '.join(signals['sparktoro_sites'])}")
    if signals.get("sparktoro_subreddits"):
        parts.append(f"Audience active on subreddits (SparkToro): {', '.join(signals['sparktoro_subreddits'])}")
    return "Job signals:\n" + "\n".join(parts) + "\n\nGenerate the candidate persona JSON."


def _parse_llm_json(text: str) -> dict:
    """
    Strip markdown fences and parse JSON from LLM response.
    Falls back to regex extraction if the model wraps JSON in commentary.
    Also normalises disc_type to a valid single uppercase letter.
    """
    text = text.strip()
    # Remove markdown fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```\s*$", "", text)
    # If JSON is embedded in prose, extract the first {...} block
    if not text.startswith("{"):
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            text = m.group(0)
    data = json.loads(text)
    # Normalise disc_type: must be single uppercase letter in {D,I,S,C}
    disc = str(data.get("disc_type", "S")).strip().upper()
    data["disc_type"] = disc[0] if disc and disc[0] in "DISC" else "S"
    return data


def _call_openai_compat(api_key: str, base_url: str, model: str, prompt: str) -> dict:
    """Generic caller for any OpenAI-compatible API (DeepSeek, Groq, OpenAI, etc.)."""
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "max_tokens": 1800,
            "temperature": 0.2,    # Low but non-zero: deterministic DISC while still allowing JD-specific variation
            "messages": [
                {"role": "system", "content": PERSONA_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_llm_json(resp.json()["choices"][0]["message"]["content"])


def _call_anthropic(api_key: str, model: str, prompt: str) -> dict:
    """Anthropic Messages API caller."""
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1800,
            "temperature": 0.2,
            "system": PERSONA_SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_llm_json(resp.json()["content"][0]["text"])


def _call_gemini(api_key: str, prompt: str) -> dict:
    """Google Gemini API caller."""
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": PERSONA_SYSTEM + "\n\n" + prompt}]}],
            "generationConfig": {"maxOutputTokens": 1800, "temperature": 0.2},
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_llm_json(resp.json()["candidates"][0]["content"]["parts"][0]["text"])


def _call_cohere(api_key: str, prompt: str) -> dict:
    """Cohere Chat API caller (different request/response shape)."""
    resp = requests.post(
        "https://api.cohere.com/v2/chat",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "command-r-plus-08-2024",
            "messages": [
                {"role": "system", "content": PERSONA_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": 1800,
            "temperature": 0.2,
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_llm_json(resp.json()["message"]["content"][0]["text"])


def _generate_persona_llm(signals: dict) -> dict:
    """
    Call the best available LLM. First key found in env wins.
    Priority order (quality + cost optimised):
      1.  DeepSeek-V3          DEEPSEEK_API_KEY    platform.deepseek.com        ~$0.27/1M
      2.  Groq / Llama-3.3-70B GROQ_API_KEY        console.groq.com             Free tier
      3.  Gemini 2.0 Flash     GEMINI_API_KEY       aistudio.google.com          Free tier
      4.  Cerebras / Llama-3.3 CEREBRAS_API_KEY     cloud.cerebras.ai            Free tier
      5.  SambaNova / Llama-3.3 SAMBANOVA_API_KEY   cloud.sambanova.ai           Free tier
      6.  Fireworks / Llama-3.3 FIREWORKS_API_KEY   fireworks.ai                 Free trial
      7.  Together / Llama-3.3 TOGETHER_API_KEY     api.together.xyz             Free $1 credit
      8.  Mistral Small        MISTRAL_API_KEY      console.mistral.ai           Free trial
      9.  Perplexity Sonar     PERPLEXITY_API_KEY   perplexity.ai/settings/api   $5 credit
      10. Nvidia NIM / Llama   NVIDIA_API_KEY       build.nvidia.com             Free credits
      11. xAI Grok-3-mini      XAI_API_KEY          console.x.ai                 Free trial
      12. OpenRouter (any)     OPENROUTER_API_KEY   openrouter.ai                Pay-per-use
      13. Cohere Command-R+    COHERE_API_KEY       dashboard.cohere.com         Free trial
      14. OpenAI GPT-4o-mini   OPENAI_API_KEY       platform.openai.com          ~$0.15/1M
      15. Anthropic Claude Haiku ANTHROPIC_API_KEY  console.anthropic.com        ~$0.25/1M
      16. Rule-based fallback (no key needed)
    """
    prompt = _build_llm_prompt(signals)

    providers = []
    if DEEPSEEK_KEY:
        providers.append(("DeepSeek-V3",           lambda: _call_openai_compat(DEEPSEEK_KEY,   "https://api.deepseek.com/v1",                      "deepseek-chat",                                      prompt)))
    if GROQ_KEY:
        providers.append(("Groq/Llama-3.3-70B",    lambda: _call_openai_compat(GROQ_KEY,       "https://api.groq.com/openai/v1",                   "llama-3.3-70b-versatile",                            prompt)))
    if GEMINI_KEY:
        providers.append(("Gemini-2.0-Flash",      lambda: _call_gemini(GEMINI_KEY, prompt)))
    if CEREBRAS_KEY:
        providers.append(("Cerebras/Llama-3.3-70B",lambda: _call_openai_compat(CEREBRAS_KEY,   "https://api.cerebras.ai/v1",                       "llama-3.3-70b",                                      prompt)))
    if SAMBANOVA_KEY:
        providers.append(("SambaNova/Llama-3.3-70B",lambda: _call_openai_compat(SAMBANOVA_KEY, "https://api.sambanova.ai/v1",                      "Meta-Llama-3.3-70B-Instruct",                        prompt)))
    if FIREWORKS_KEY:
        providers.append(("Fireworks/Llama-3.3-70B",lambda: _call_openai_compat(FIREWORKS_KEY, "https://api.fireworks.ai/inference/v1",             "accounts/fireworks/models/llama-v3p3-70b-instruct",  prompt)))
    if TOGETHER_KEY:
        providers.append(("Together/Llama-3.3-70B", lambda: _call_openai_compat(TOGETHER_KEY,  "https://api.together.xyz/v1",                      "meta-llama/Llama-3.3-70B-Instruct-Turbo",            prompt)))
    if MISTRAL_KEY:
        providers.append(("Mistral-Small",          lambda: _call_openai_compat(MISTRAL_KEY,    "https://api.mistral.ai/v1",                        "mistral-small-latest",                               prompt)))
    if PERPLEXITY_KEY:
        providers.append(("Perplexity-Sonar-Pro",   lambda: _call_openai_compat(PERPLEXITY_KEY, "https://api.perplexity.ai",                       "sonar-pro",                                          prompt)))
    if NVIDIA_KEY:
        providers.append(("Nvidia/Llama-3.3-70B",   lambda: _call_openai_compat(NVIDIA_KEY,    "https://integrate.api.nvidia.com/v1",              "meta/llama-3.3-70b-instruct",                        prompt)))
    if XAI_KEY:
        providers.append(("xAI/Grok-3-mini",        lambda: _call_openai_compat(XAI_KEY,       "https://api.x.ai/v1",                              "grok-3-mini",                                        prompt)))
    if OPENROUTER_KEY:
        providers.append(("OpenRouter/Llama-3.3",   lambda: _call_openai_compat(OPENROUTER_KEY, "https://openrouter.ai/api/v1",                    "meta-llama/llama-3.3-70b-instruct",                  prompt)))
    if COHERE_KEY:
        providers.append(("Cohere/Command-R+",      lambda: _call_cohere(COHERE_KEY, prompt)))
    if OPENAI_KEY:
        providers.append(("GPT-4o-mini",            lambda: _call_openai_compat(OPENAI_KEY,    "https://api.openai.com/v1",                        "gpt-4o-mini",                                        prompt)))
    if ANTHROPIC_KEY:
        providers.append(("Claude-Haiku",           lambda: _call_anthropic(ANTHROPIC_KEY, CLAUDE_MODEL, prompt)))

    for name, caller in providers:
        try:
            persona = caller()
            if not persona.get("messaging_variants"):
                persona["messaging_variants"] = _rule_based_messaging(
                    persona.get("disc_type", "S"),
                    signals.get("industry", "general"),
                    persona.get("role", "Professional"),
                )
            if "job_quality_issues" not in persona:
                persona["job_quality_issues"] = []
            if signals.get("mece_archetype"):
                arch_disc = signals["mece_archetype"].get("disc", "")
                if arch_disc:
                    enforced = arch_disc[0].upper()
                    if enforced in "DISC":
                        persona["disc_type"] = enforced
            persona["_llm_provider"] = name
            persona["_used_fallback"] = False
            logger.info(f"Persona generated via {name}")
            return persona
        except Exception as e:
            logger.warning(f"{name} failed: {e}")
            continue

    logger.warning("All LLM providers failed — falling back to rule-based persona")
    p = _rule_based_persona(signals)
    p["_llm_provider"] = "rule_based"
    p["_used_fallback"] = True
    return p



def _derive_jd_fields(signals: dict, disc: str, archetype_name: str = "") -> dict:
    industry    = signals.get("industry", "general")
    seniority   = signals.get("seniority", "mid")
    skills      = signals.get("skills", [])
    salary      = signals.get("salary", "")
    arrangement = signals.get("work_arrangement", "")
    disc_key    = (disc[0] if disc else "S").upper()
    top_skill_phrase = f" with {skills[0]}" if skills else ""
    _INDUSTRY_GOALS = {
        "tech": [f"Solve non-trivial engineering problems{top_skill_phrase}, not ticket-based maintenance","Work at a scale where architectural decisions have real consequences"],
        "healthcare": ["Provide patient care in a well-staffed, adequately resourced unit","Clear shift structure with predictable scheduling and reliable handoff protocols"],
        "logistics": ["Predictable schedule close to home with no last-minute shift changes","Weekly or bi-weekly pay with transparent shift differentials upfront"],
        "defense": ["Work on classified programs with genuine national-security consequence","Access to up-to-date tooling and infrastructure appropriate to a cleared environment"],
        "marketing": ["Own a measurable channel or campaign — not just supporting someone else's plan","Budget and authority to run experiments and iterate on results without a 6-week approval chain"],
        "sales": ["Clean territory with a realistic quota and a transparent OTE structure","A product they can genuinely believe in and sell without over-promising to prospects"],
        "finance": ["Influence real decisions with their models — not just report on them after the fact","Access to current tooling and clean data, not monthly manual reconciliation"],
        "hr": ["A strategic seat at the table when the business is making people decisions","Systems and HRIS that don't require workarounds to get basic reporting done"],
        "general": ["Role clarity: a defined scope with real ownership from day one","A team environment where their background and working style are genuinely valued"],
    }
    _DISC_EMOTIONAL = {
        "D": ["Feel their work drives a measurable result that is visible to the business","Feel trusted with real ownership — not managed through micro-approval chains"],
        "I": ["Feel genuinely welcomed by the team and part of something people are proud of","Feel their contributions are seen and celebrated, not just tracked in a system"],
        "S": ["Feel stable — that the environment they join is the one they will still recognise after 90 days","Feel supported by people who invested in their success before they had to prove themselves"],
        "C": ["Feel their depth of expertise is respected and not overridden by schedule pressure","Feel the quality standards they care about are shared by the team, not merely tolerated"],
    }
    skill_ctx = f" — and whether {skills[0]} depth is real and not cosmetic" if skills else ""
    _INDUSTRY_CONCERN = {
        "tech":      f"Whether the engineering environment is as technically rigorous as the JD implies{skill_ctx}.",
        "healthcare":"Whether the unit is actually well-staffed and the culture matches what the posting describes.",
        "logistics": "Whether schedule stability and pay transparency hold up once they are on the floor.",
        "defense":   "Whether the program has funding continuity and cleared work is genuinely the day-to-day.",
        "marketing": "Whether they will have real budget authority or end up as support without ownership of outcomes.",
        "sales":     "Whether the OTE numbers are realistic for the average rep — not just the top 10% — and whether the product can be sold honestly.",
        "finance":   "Whether their models will actually inform decisions or get filed away in a shared drive.",
        "hr":        "Whether the business genuinely treats HR as a strategic function or as an administrative cost centre.",
        "general":   "Whether the day-to-day environment and growth trajectory match what the JD describes.",
    }
    _DISC_ACQUISITION = {
        "D": f"A specific, outcome-focused post or JD that names deliverables, ownership, and measurable goals for the first 90 days{top_skill_phrase}.",
        "I": "A peer testimonial or team culture post — ideally from someone in a similar role — showing what it is actually like to work here.",
        "S": "A detailed, honest job description with a clear 30/60/90 plan, team structure, and what the onboarding experience looks like.",
        "C": f"Genuine depth in the JD itself — specific scope, tooling, and methodology decisions{top_skill_phrase} — or a first-person post by someone currently doing this role.",
    }
    _SENIORITY_GOAL = {
        "junior":    "Clear onboarding with real mentorship — not a sink-or-swim environment from week one",
        "mid":       "Defined career milestone path with a timeline they can hold their manager accountable to",
        "senior":    "Autonomy to make architectural or process decisions without seeking constant approval",
        "director":  "Reporting line and stakeholder access that genuinely match the scope of the role",
        "executive": "Organisational mandate and resource allocation that make the strategy achievable",
    }
    industry_goals = _INDUSTRY_GOALS.get(industry, _INDUSTRY_GOALS["general"])
    goal_1 = industry_goals[0]
    goal_2 = industry_goals[1]
    if not salary or salary in ("Comp TBD", "Not specified", ""):
        goal_3 = "Transparent compensation range shared upfront — not revealed only after two rounds of interviews"
    elif arrangement and "remote" in arrangement.lower() and seniority in ("senior", "director", "executive"):
        goal_3 = "Remote-first team norms: async communication, documented decisions, no invisible presence penalties"
    else:
        goal_3 = _SENIORITY_GOAL.get(seniority, _SENIORITY_GOAL["mid"])
    return {
        "functional_goals": [goal_1, goal_2, goal_3],
        "emotional_goals":  _DISC_EMOTIONAL.get(disc_key, _DISC_EMOTIONAL["S"]),
        "concern":          _INDUSTRY_CONCERN.get(industry, _INDUSTRY_CONCERN["general"]),
        "acquisition_trigger": _DISC_ACQUISITION.get(disc_key, _DISC_ACQUISITION["S"]),
    }


def _filter_skills_for_persona(skills: list, disc: str, archetype_name: str = "") -> list:
    if not skills:
        return []
    disc_key = (disc[0] if disc else "S").upper()
    _HIGH = {
        "C": ["python","sql","r ","scala","java","rust","go","c++","c#",".net","kotlin","swift","machine learning","deep learning","tensorflow","pytorch","keras","statistics","regression","hypothesis","data science","analytics","modeling","algorithm","excel","tableau","power bi","looker","databricks","spark","hadoop","aws","azure","gcp","kubernetes","docker","terraform","sap","oracle","sas","stata","quickbooks","tally","erp","powerbi","matlab","julia"],
        "D": ["product","agile","scrum","jira","roadmap","kpi","okr","salesforce","crm","negotiation","closing","pipeline","revenue","leadership","strategy","growth","scaling","hiring","budget","delivery","api","cloud","javascript","react","node"],
        "S": ["excel","powerpoint","word","notion","confluence","jira","asana","slack","teams","google workspace","sharepoint","workday","adp","greenhouse","bamboohr","hris","payroll","onboarding","training","communication","documentation","process","compliance","hr","recruiting","coordination"],
        "I": ["marketing","content","seo","sem","social media","linkedin","hubspot","marketo","mailchimp","google analytics","salesforce","crm","pr","communication","presentation","public speaking","community","design","canva","figma","photoshop","video","storytelling","copywriting","brand"],
    }
    _LOW = {
        "C": ["leadership","stakeholder","social media","content","pr","marketing","mailchimp"],
        "D": ["documentation","statistics","modeling","tdd","unit test","integration test"],
        "S": ["machine learning","deep learning","algorithm","rust","kubernetes","c++","terraform"],
        "I": ["kubernetes","terraform","rust","c++","algorithm","statistics","databricks"],
    }
    high_fragments = _HIGH.get(disc_key, [])
    low_fragments  = _LOW.get(disc_key, [])
    def _score(skill):
        sl = skill.lower()
        if any(h in sl or sl in h for h in high_fragments): return 2
        if any(l in sl or sl in l for l in low_fragments): return 0
        return 1
    scored = sorted(enumerate(skills), key=lambda x: (-_score(x[1]), x[0]))
    filtered = [skills[i] for i, _ in scored if _score(skills[i]) > 0][:5]
    if len(filtered) < 3:
        filtered = [skills[i] for i, _ in scored][:5]
    return filtered

def _rule_based_persona(signals: dict) -> dict:
    """
    Fallback when LLM is unavailable.
    When mece_archetype is provided, builds the persona directly from the MECE
    archetype definition so both rule-based personas are principled and MECE.
    """
    # ── MECE archetype path (preferred) ──────────────────────────────────────
    if signals.get("mece_archetype"):
        arch = signals["mece_archetype"]
        disc = arch.get("disc", "S")
        ind  = signals.get("industry", "general")
        seniority = signals.get("seniority", "mid")
        role_type = signals.get("role_type", "individual_contributor")
        role_label = "People Manager" if role_type == "people_manager" else "Individual Contributor"
        return {
            "name":    arch["archetype_name"],
            "role":    f"{seniority.title()} {role_label}",
            "profile": (
                f"{seniority.title()} · {role_label} · "
                f"{signals.get('work_arrangement', 'On-site')} · "
                f"{signals.get('location', 'Unspecified')}"
            ),
            "core_job":         arch["motivation"],
            "context_trigger":  arch["trigger"],
            **_derive_jd_fields(signals, disc, arch.get("archetype_name", "")),
            "primary_message":     f'"{arch["archetype_name"]} — built for this kind of challenge."',
            "background":          arch["background_style"],
            "disc_type":           disc,
            "disc_implication":    arch["messaging_angle"],
            "job_quality_issues":  [],
            "messaging_variants":  _rule_based_messaging(disc, ind, arch["archetype_name"]),
        }

    ind = signals.get("industry", "general")
    templates = {
        "tech":     ("The Creator",   "Software / AI Engineer",
                     "Build systems with real consequence — not ad-ranking models.",
                     "Stagnation: skills narrowing and problems shrinking.",
                     "A Hacker News post or conference talk by a current engineer.",
                     '"Real engineering problems. Classified because they matter."', "C"),
        "healthcare":("The Caregiver","Clinical Professional",
                     "Provide excellent patient care in a well-staffed, supportive unit.",
                     "That benefits, schedule, or unit culture won't match what's promised.",
                     "A peer's specific review of the unit environment.",
                     '"We know what a 12-hour shift costs. Here\'s how we support you."', "S"),
        "logistics": ("The Frontliner","Logistics Associate",
                     "Stable income close to home with predictable shift times.",
                     "Hidden costs, inconsistent scheduling, or culture that ignores frontline workers.",
                     "A mobile apply flow that takes under 90 seconds.",
                     '"Same-week start. Weekly pay. Night differential from day one."', "D"),
        "defense":  ("The Guardian",  "Cleared Defense Engineer",
                     "Work on systems whose outcomes matter at national scale.",
                     "Losing access to classified work or a program with real stakes.",
                     "A technical talk at DEF CON or Embedded World by a current engineer.",
                     '"The problem you\'re cleared to know about — we\'re building the solution."', "C"),
        "bilingual":("The Connector", "Bilingual Specialist",
                     "Use bilingual ability as a strategic asset, not an afterthought.",
                     "Being hired for language but undervalued for strategic judgment.",
                     "A bilingual employee testimonial or community event presence.",
                     '"Your language is the product. We built the role around it."', "I"),
        "marketing":("The Amplifier","Marketing / Growth Professional",
                     "Drive measurable pipeline and brand equity through programs that actually get funded.",
                     "Being a cost center rather than a revenue driver — metrics that don't tie to business outcomes.",
                     "A peer's LinkedIn post about ownership, budget, and measurable wins.",
                     '"Here\'s the budget, the channel mix, and the number you\'ll own."', "I"),
        "sales":    ("The Closer","Account Executive / Sales Professional",
                     "Hit quota on a product they can genuinely believe in, with a territory they can win.",
                     "A leaky funnel, opaque commission structures, or a product that can't be sold honestly.",
                     "Glassdoor OTE verification and a conversation with a current AE.",
                     '"Here\'s average OTE, the ramp plan, and the wins your peers closed last quarter."', "D"),
        "finance":  ("The Analyst","Finance / Accounting Professional",
                     "Build models and processes that actually influence decisions — not just report on them.",
                     "Manual processes, outdated tooling, or being kept at arm\'s length from strategy.",
                     "A case study or LinkedIn post on a finance transformation they drove.",
                     '"You\'ll own the model that drives the board deck — not just reconcile it."', "C"),
        "hr":       ("The Builder","HR / Talent Acquisition Professional",
                     "Build people systems and hiring pipelines that scale without losing the human touch.",
                     "Being a resume-screener rather than a strategic partner to the business.",
                     "A thoughtful careers page and a Glassdoor culture score above 4.0.",
                     '"You\'ll have a seat at the leadership table — starting in week one."', "S"),
        "general":  ("The Professional","Specialist",
                     "Advance their career in a role that values their specific expertise.",
                     "Process disorganisation or unclear growth trajectory.",
                     "A transparent job description with honest salary and clear next steps.",
                     '"Here\'s exactly what the role is, who you\'ll work with, and what growth looks like."', "S"),
    }
    key = "bilingual" if signals.get("bilingual") else "defense" if signals.get("clearance") else ind
    t = templates.get(key, templates["general"])
    disc = t[6]

    # Variant 2: pick a contrasting template so we don't duplicate the first persona
    if signals.get("persona_variant") == 2:
        # Rotate to a different industry template for contrast
        contrast_map = {
            "tech": "marketing", "healthcare": "hr", "defense": "finance",
            "logistics": "retail", "marketing": "tech", "sales": "marketing",
            "hr": "tech", "finance": "tech", "retail": "logistics",
            "hospitality": "hr", "general": "sales",
        }
        alt_key = contrast_map.get(key, "general")
        t2 = templates.get(alt_key, templates["general"])
        # Keep the DISC type different
        disc2 = t2[6] if t2[6] != disc else ({"D":"S","I":"C","S":"D","C":"I"}.get(disc,"S"))
        persona = {
            "name":  f"The {t2[0].split()[-1]} (Alt)",
            "role":  t2[1],
            "profile": f"{signals.get('seniority','mid').title()} · Alternative archetype · {signals.get('location','Unspecified')}",
            "core_job": t2[2],
            "context_trigger": "Reevaluating career trajectory — seeking a role better aligned with long-term goals.",
            **_derive_jd_fields(signals, disc2, t2[1]),
            "concern": t2[3], "acquisition_trigger": t2[4], "primary_message": t2[5],
            "background": "Complementary archetype to the primary persona — different career background, different motivation, same open role.",
            "disc_type": disc2,
            "disc_implication": "Contrasting outreach angle from the primary persona. Test both variants to find the higher-converting message for this role.",
            "job_quality_issues": [],
            "messaging_variants": _rule_based_messaging(disc2, alt_key, t2[1]),
        }
        return persona

    persona = {
        "name": t[0], "role": t[1],
        "profile": f"{signals.get('seniority','mid').title()} · {signals.get('work_arrangement','On-site')} · {signals.get('location','Unspecified')} · {signals.get('salary','Comp TBD')}",
        "core_job": t[2], "context_trigger": "Hitting a ceiling at current employer — no growth path visible.",
        **_derive_jd_fields(signals, disc, t[1]),
        "concern": t[3], "acquisition_trigger": t[4], "primary_message": t[5],
        "background": "Currently employed but selectively open. Evaluating carefully before making any move. Will read deeply before applying.",
        "disc_type": disc, "disc_implication": "Lead with outcomes and evidence. Name real technologies and situations. Avoid buzzwords and vague culture language.",
        "job_quality_issues": [],
        "messaging_variants": _rule_based_messaging(disc, ind, t[1]),
    }
    return persona


# ══════════════════════════════════════════════════════════════════════════════
# 8. JD QUALITY SCORING
#    Evidence-based scoring of job description conversion quality.
#    Salary range alone is worth +3x apply rate (Indeed, 2024).
# ══════════════════════════════════════════════════════════════════════════════

def _score_jd_quality(text: str) -> dict:
    """
    Score a job description for candidate conversion quality.
    Returns: score (0-10), issues, strengths, word_count.
    Each deduction tied to published research on apply-rate impact.
    """
    score = 10.0
    issues = []
    strengths = []
    text_lower = text.lower()
    word_count = len(text.split())

    # ── Salary (largest single factor: +3x applies) ──────────────────────────
    # Note: avoid matching "401k" (retirement benefit) as a salary indicator.
    has_salary = bool(re.search(
        r'\$[\d,]+\.?\d*[k]?'                              # $85,000 or $85k or $35.50
        r'|\bsalary\s+(?:range|of|is)\b'                   # "salary range" / "salary of"
        r'|\bcompensation\s+range\b|\btotal\s+comp\b'       # "compensation range" / "total comp"
        r'|(?:salary|pay(?:rate)?|compensation)\D{0,30}\d{2,3},\d{3}',  # "salary: 85,000"
        text_lower
    ))
    if not has_salary:
        score -= 2.5
        issues.append("No salary range — listings with salary ranges get 3× more applicants (Indeed, 2024)")
    else:
        strengths.append("Salary range present (+3× apply rate impact)")

    # ── Work arrangement ──────────────────────────────────────────────────────
    if not re.search(r'\bremote\b|\bhybrid\b|\bon-site\b|\bin-office\b|work from home|wfh|flexible work', text_lower):
        score -= 1.5
        issues.append("Work arrangement not stated — top candidates filter by this before reading anything else")
    else:
        strengths.append("Work arrangement clearly stated")

    # ── Benefits ─────────────────────────────────────────────────────────────
    if not re.search(r'\bbenefit|\b401k|\bhealth\s+insurance|\bpto\b|\bvacation\b|\bequity\b|\bstock\b|\bbonus\b|\bmaternity|\bpaternity', text_lower):
        score -= 1.0
        issues.append("Benefits not mentioned — 68% of candidates say benefits significantly influence their decision")

    # ── Word count ────────────────────────────────────────────────────────────
    if word_count < 150:
        score -= 1.5
        issues.append(f"Too short ({word_count} words) — candidates can't self-qualify; conversion drops sharply below 200 words")
    elif word_count > 900:
        score -= 0.5
        issues.append(f"Too long ({word_count} words) — completion rate drops 40% above 800 words; trim to the essentials")
    else:
        strengths.append(f"Good length ({word_count} words)")

    # ── Growth / career path ──────────────────────────────────────────────────
    if not re.search(r'\bgrow|\bcareer\b|\badvance|\bpromotion|\bdevelop|\blearn|\bmentor|\bleadership path', text_lower):
        score -= 0.5
        issues.append("No career growth path mentioned — 82% of candidates rank development as top 3 factor")
    else:
        strengths.append("Career growth path mentioned")

    # ── Deterrent / exclusionary language ────────────────────────────────────
    jargon_hits = re.findall(
        r'\brock ?star\b|\bninja\b|\bwizard\b|\bguru\b|\bhero\b|\bsuperstar\b|\bunicorn\b|\b10x\b|\bfast.?paced environment\b|\bwear many hats\b',
        text_lower
    )
    if jargon_hits:
        score -= 0.5
        issues.append(f"Exclusionary language detected: '{', '.join(set(jargon_hits))}' — deters qualified candidates, especially women and underrepresented groups")

    # ── Application process transparency ─────────────────────────────────────
    if not re.search(r'\binterview\b|\bprocess\b|\bstep\b|\bstage\b|\bhiring\b|\bapplication\b', text_lower):
        score -= 0.5
        issues.append("Application/interview process not described — transparency reduces candidate drop-off by 40%")

    # ── Company context ───────────────────────────────────────────────────────
    if not re.search(r'\bmission\b|\bculture\b|\bvalue\b|\bwho we are\b|\babout us\b|\bour team\b', text_lower):
        score -= 0.5
        issues.append("No company context — candidates check this before applying; its absence signals low employer brand investment")

    return {
        "score": round(max(0.0, min(10.0, score)), 1),
        "max_score": 10.0,
        "grade": _jd_grade(score),
        "issues": issues[:5],
        "strengths": strengths[:3],
        "word_count": word_count,
    }


def _jd_grade(score: float) -> str:
    if score >= 8.5:  return "A"
    if score >= 7.0:  return "B"
    if score >= 5.5:  return "C"
    if score >= 4.0:  return "D"
    return "F"


# ══════════════════════════════════════════════════════════════════════════════
# 8b. RULE-BASED MESSAGING VARIANTS
#     3 DISC-calibrated ad copy variants per persona.
#     Used as fallback when LLM doesn't return messaging_variants.
# ══════════════════════════════════════════════════════════════════════════════

def _rule_based_messaging(disc_type: str, industry: str, role: str) -> list:
    """Generate 3 DISC-calibrated messaging variants (ready-to-deploy ad copy)."""

    industry_noun = {
        "tech":        ("engineering",   "systems",              "engineers"),
        "healthcare":  ("clinical",      "patient care",         "clinicians"),
        "defense":     ("defense",       "mission-critical systems", "engineers"),
        "logistics":   ("operations",    "supply chain",         "operators"),
        "finance":     ("finance",       "financial systems",    "analysts"),
        "marketing":   ("marketing",     "campaigns and pipeline","marketers"),
        "sales":       ("sales",         "deals and pipeline",   "account executives"),
        "hr":          ("people ops",    "talent systems",       "HR professionals"),
        "retail":      ("retail",        "customer experience",  "associates"),
        "hospitality": ("hospitality",   "guest experience",     "hospitality professionals"),
    }.get(industry, ("work", "your domain", "professionals"))

    variants_by_disc: dict[str, list] = {
        "D": [
            {
                "label": "Results-first (D-type primary)",
                "headline": f"Own the outcome. Real {industry_noun[0]} problems from day one.",
                "body": (
                    f"No hand-holding. No committees. Just ownership of {industry_noun[1]} that actually ships. "
                    f"We measure people by what they deliver — not by hours logged or meetings attended. "
                    f"If you've been waiting for the role where your output is the ceiling, this is it."
                ),
                "cta": "See the open role →",
            },
            {
                "label": "Challenge/competition (D-type alt)",
                "headline": f"The best {industry_noun[0]} {industry_noun[2]} are already here.",
                "body": (
                    f"We hire the top 5%. Our bar is high because our problems are harder. "
                    f"If you're competing to work on the best {industry_noun[1]} problems, this is where that search ends."
                ),
                "cta": "Apply now — we move fast",
            },
            {
                "label": "Urgency/scarcity (D-type alt 2)",
                "headline": f"One seat. One {industry_noun[0]} team. One shot.",
                "body": (
                    f"This team is deliberately small. Every hire shapes direction. "
                    f"When the role is filled, it's filled. No extended pipelines, no 6-round processes."
                ),
                "cta": "Don't wait — apply today",
            },
        ],
        "I": [
            {
                "label": "Social/story (I-type primary)",
                "headline": f"The {industry_noun[0]} career story you'll be telling in 10 years.",
                "body": (
                    f"Our people don't just work here — they build {industry_noun[1]} they talk about forever. "
                    f"Collaborative team, visible impact, and a culture where the best idea wins regardless of tenure."
                ),
                "cta": "Read their stories →",
            },
            {
                "label": "Community/visibility (I-type alt)",
                "headline": f"The {industry_noun[0]} team that shows its work.",
                "body": (
                    f"We speak at conferences, write the posts that get shared, and open-source the work others benchmark. "
                    f"If you want to be known in {industry_noun[0]}, here's the door."
                ),
                "cta": "Join the conversation →",
            },
            {
                "label": "Growth/energy (I-type alt 2)",
                "headline": f"We're growing fast. Grow faster with us.",
                "body": (
                    f"Our {industry_noun[0]} team doubled in 18 months. Promotions happen when you're ready, not when a seat opens. "
                    f"We invest heavily in {industry_noun[2]} who invest in the mission."
                ),
                "cta": "See where you could go →",
            },
        ],
        "S": [
            {
                "label": "Stability/support (S-type primary)",
                "headline": f"A {industry_noun[0]} team that invests in the long term — including you.",
                "body": (
                    f"Comprehensive benefits from day one. Flexible schedules that respect your life. "
                    f"Mentorship that's real, not aspirational. We design roles around people, not the other way around."
                ),
                "cta": "Explore the benefits →",
            },
            {
                "label": "Team/belonging (S-type alt)",
                "headline": f"The {industry_noun[0]} team people actually stay on.",
                "body": (
                    f"Our average tenure is 4+ years — not because people have to stay, but because the team and mission keep them engaged. "
                    f"Collaborative, low-ego, high-trust environment with real work-life balance."
                ),
                "cta": "Meet the team →",
            },
            {
                "label": "Security/reliability (S-type alt 2)",
                "headline": f"Predictable. Supportive. Real balance in {industry_noun[0]}.",
                "body": (
                    f"Flexible hours, generous PTO, and a culture where no one glorifies overwork. "
                    f"We know what burnout looks like. We've designed our team against it."
                ),
                "cta": "Learn about our culture →",
            },
        ],
        "C": [
            {
                "label": "Evidence-based (C-type primary)",
                "headline": f"The data behind our {industry_noun[0]} culture. No vague claims.",
                "body": (
                    f"87% of our team would recommend working here. Average tenure: 4.2 years. "
                    f"Interview process: 3 rounds, decision within 5 business days. Salary posted — no negotiation games. "
                    f"This is what 'great culture' looks like in numbers."
                ),
                "cta": "See the full role spec →",
            },
            {
                "label": "Craft standards (C-type alt)",
                "headline": f"We hold our {industry_noun[0]} work to a standard. Here's what it looks like.",
                "body": (
                    f"Our processes are documented, not assumed. Our standards are written down and consistently enforced — not just aspirational. "
                    f"We care as much about how {industry_noun[1]} are done as what gets delivered. "
                    f"If you've worked somewhere where 'good enough' was the bar and it frustrated you — this team is different."
                ),
                "cta": "Read the full role spec →",
            },
            {
                "label": "Process/transparency (C-type alt 2)",
                "headline": f"Transparent role. Clear expectations. Real {industry_noun[0]} work.",
                "body": (
                    f"We publish our interview rubric. The job description is accurate. Onboarding is 90 days, documented, "
                    f"and assigned to a senior buddy. We know what 'respecting your time' actually means."
                ),
                "cta": "Read the interview guide →",
            },
        ],
    }

    return variants_by_disc.get(disc_type, variants_by_disc["S"])


# ══════════════════════════════════════════════════════════════════════════════
# 9. COMPETITIVE SNAPSHOT
# ══════════════════════════════════════════════════════════════════════════════

COMPETITOR_INTEL = {
    "tech":       [("Google","4.3","85%",'"Do cool things that matter"',"Increasingly perceived as slow and politically complex post-2024 restructuring."),
                   ("Meta","3.9","72%",'"Move fast"',"Layoffs and culture shift damaged employer brand significantly."),
                   ("Amazon","3.5","63%",'"Day 1 mentality"',"PIP culture and gruelling performance management drive high attrition."),
                   ("Microsoft","4.2","83%",'"Empower every person"',"Slower career trajectory than peak FAANG years — safe but unchallenging.")],
    "healthcare": [("HCA Healthcare","3.6","66%",'"Care and improvement of human life"',"Staffing ratios and traveler dependency damage unit culture."),
                   ("CommonSpirit","3.7","68%",'"Healing body, mind and spirit"',"Geographic inconsistency — great at some facilities, poor at others."),
                   ("Kaiser Permanente","4.0","77%",'"Thrive"',"Bay Area cost of living limits retention despite strong brand.")],
    "defense":    [("Lockheed Martin","4.0","73%",'"Your work classified in the best way"',"Slow promotion velocity and org complexity reduce individual visibility."),
                   ("Northrop Grumman","3.9","69%",'"Defining possible"',"Complex matrix structure dilutes systems thinking."),
                   ("L3Harris","3.7","62%",'"Mission critical"',"Lower brand recognition vs. Raytheon among STEM graduates."),
                   ("Boeing","3.5","60%",'"You just make things possible"',"Safety and culture PR crises create candidate hesitation in 2025–26.")],
    "finance":    [("Goldman Sachs","3.9","72%",'"Progress is everyone\'s business"',"Hours reputation deters younger cohorts who watched 2021 analyst protests."),
                   ("JP Morgan","3.8","70%",'"Make your mark"',"Return-to-office mandates accelerated high-performer attrition."),
                   ("BlackRock","4.0","76%",'"One BlackRock"',"Slow internal promotion despite strong external brand.")],
    "general":    [("Competitor A","3.7","68%",'"Join us"',"No differentiated EVP — defaults to generic job board presence."),
                   ("Competitor B","3.5","63%",'"Great place to work"',"High reliance on Indeed with no niche channel strategy.")],
}

def _get_competitive(industry: str) -> list:
    comps = COMPETITOR_INTEL.get(industry, COMPETITOR_INTEL["general"])
    return [{"company":c[0],"rating":c[1],"recommend":c[2],"hook":c[3],"weakness":c[4]} for c in comps]


# ══════════════════════════════════════════════════════════════════════════════
# 9. AD STRATEGY
# ══════════════════════════════════════════════════════════════════════════════

AD_PLAYBOOK = {
    "tech": [
        {"platform":"LinkedIn","objective":"Passive talent","format":"Employee story — engineer + project","hook":'"The engineer who built X works here"',"insight":"Employee-led creatives outperform branded job ads 3–4× CTR. Use the engineer's actual title and a one-line description of the system they work on — not stock photography."},
        {"platform":"Stack Overflow","objective":"Context-fit awareness","format":"Display + Q&A sidebar","hook":'"Problems that matter at national scale"',"insight":"Engineers see your ad while solving hard problems. Implicit alignment with technical rigour. Highest signal-to-noise of any tech channel."},
        {"platform":"Reddit","objective":"Authenticity","format":"Organic AMA + employee comment","hook":'"What do we actually build here?"',"insight":"An AMA from a real engineer in r/cscareerquestions drives more qualified inbound than paid ads at near-zero marginal cost. Do not buy Reddit ads — earn Reddit."},
        {"platform":"GitHub Sponsors","objective":"Developer trust","format":"README sponsorship","hook":'"See the open-source work our engineers do"',"insight":"Engineers who use GitHub daily are self-selecting as builders. A sponsored README on a relevant repo reaches them in their professional context."},
    ],
    "healthcare": [
        {"platform":"Indeed","objective":"Volume + conversion","format":"Sponsored listing + salary badge","hook":'"$10K sign-on. Benefits day 1. 3×12 schedule."',"insight":"Clinical candidates scan three things first: sign-on bonus, schedule, and unit type. Lead with all three in the headline — not the company name."},
        {"platform":"Nursing.com community","objective":"Peer trust","format":"Community sponsorship + organic","hook":'"Here\'s what a Tuesday on our unit actually looks like"',"insight":"Nurses talk. Allnurses and Nursing.com community posts by real staff convert at 2× the rate of general boards because the audience is 100% clinical."},
        {"platform":"Meta (Facebook/Instagram)","objective":"Passive reach","format":"30s authentic video — filmed on iPhone","hook":'"A nurse explains the unit in their own words"',"insight":"A 30-second low-production nurse testimonial consistently outperforms polished brand video. Realness is the signal — candidates are screening for authenticity."},
    ],
    "defense": [
        {"platform":"LinkedIn","objective":"Passive professional","format":"Employee story — unclassified project fragment","hook":'"The system you\'ve heard about. We built it."',"insight":"Cleared candidates are passive and sceptical. A real engineer posting about a specific (unclassified) technical challenge generates more inbound than any ad spend."},
        {"platform":"DEF CON / Embedded World","objective":"Technical credibility","format":"Talk sponsorship + booth","hook":'"Come see what we\'re actually defending"',"insight":"The technical persona discovers employers through demonstrated expertise, not job postings. A sponsored talk costs less than 3 months of LinkedIn CPC and reaches exactly the right people."},
        {"platform":"ClearanceJobs","objective":"Direct sourcing","format":"Sponsored listing","hook":'"Active TS/SCI? Skip the queue."',"insight":"The only board where clearance level is a searchable filter. For roles requiring TS/SCI, ClearanceJobs delivers the highest intent-per-dollar of any channel."},
    ],
    "bilingual": [
        {"platform":"Meta — Threads + Instagram","objective":"Community discovery","format":"Bilingual Reel — employee testimonial","hook":'"Tu idioma es tu ventaja. En serio."',"insight":"Running bilingual creative (Spanish caption, English CTA) on Threads reaches early-career Latine candidates in a less-cluttered environment at 30–40% lower CPC than main Facebook feed."},
        {"platform":"Hispanic Chamber events","objective":"Authentic trust","format":"Sponsorship + physical presence","hook":'"Part of your community. Part of our team."',"insight":"The community-embedded persona discovers jobs through word of mouth first. Chamber event presence drives referral applications at zero incremental cost per referral."},
        {"platform":"LinkedIn","objective":"Professional tier","format":"Real employee image + bilingual title","hook":'"Bilingual Business Specialist — [City]"',"insight":"Real employees with their specific titles outperform generic job ads significantly. The 'Me. We. V.' framework (Verizon case) is the proven template."},
    ],
    "general": [
        {"platform":"Indeed","objective":"Volume","format":"Sponsored listing","hook":"Transparent salary range in the headline","insight":"The most impactful single optimisation on Indeed: show the salary range. Listings with salary get 3× more applications. Nothing else comes close."},
        {"platform":"LinkedIn","objective":"Professional reach","format":"Single image + Easy Apply","hook":"Answer 'what's in it for me?' in line 1","insight":"LinkedIn Easy Apply reduces drop-off by 60%. The first line must answer the candidate's question — not describe the company. Lead with role, not brand."},
        {"platform":"Glassdoor","objective":"Trust + conversion","format":"Enhanced profile + review responses","hook":"Respond to every review — positive and negative","insight":"Candidates check Glassdoor before applying to anything they care about. Responding to every review increases apply rate by ~18% on average."},
    ],
}

def _get_ad_strategy(industry: str, bilingual: bool = False) -> list:
    key = "bilingual" if bilingual else industry
    return AD_PLAYBOOK.get(key, AD_PLAYBOOK["general"])


# ══════════════════════════════════════════════════════════════════════════════
# 9b. SMART JD EXCERPT EXTRACTION
#     Find the most signal-rich section of the JD (Requirements, Responsibilities)
#     rather than naïvely taking the first 900 chars (which is often job title +
#     company boilerplate, not the actual requirements).
# ══════════════════════════════════════════════════════════════════════════════

def _extract_jd_excerpt(text: str, max_chars: int = 1000) -> str:
    """
    Return the most signal-rich excerpt for LLM grounding.
    Prefers the Requirements / Responsibilities / Qualifications section.
    Falls back to the first max_chars characters.
    """
    section_pat = re.compile(
        r"(?:requirements?|qualifications?|responsibilities|what you.?ll do"
        r"|what we.?re looking for|about the role|job duties|key duties"
        r"|minimum qualifications?|preferred qualifications?|your role)",
        re.IGNORECASE,
    )
    m = section_pat.search(text)
    if m and len(text) - m.start() >= 200:
        excerpt = text[m.start():]
        return excerpt[:max_chars].strip()
    return text[:max_chars].strip()


# ══════════════════════════════════════════════════════════════════════════════
# 10. CORE BUILD FUNCTION — Multi-source, ITSMA ≥3 sources
# ══════════════════════════════════════════════════════════════════════════════

def _build_persona_response(text: str, source_label: str, li_signals: dict = None,
                            num_personas: int = 2, num_passive: int = 0) -> dict:
    """
    Build a full PersonaResponse from raw text + optional LinkedIn signals.
    num_personas: how many active MECE personas to generate (2–6, default 2).
    num_passive:  how many passive candidate personas to generate (0–6, default 0).
    Uses ≥3 data sources per ITSMA best practice.
    """
    industry    = _detect_industry(text)
    seniority   = _detect_seniority(text)
    role_type   = _detect_role_type(text)
    skills      = _extract_skills(text)
    salary      = _extract_salary(text)
    location    = _extract_location(text)
    arrangement = _detect_arrangement(text)
    flags       = _detect_flags(text)
    # Smart excerpt: prefer Requirements/Responsibilities section, else first 1000 chars
    jd_excerpt  = _extract_jd_excerpt(text, max_chars=1000)
    jd_quality  = _score_jd_quality(text)

    li = li_signals or {}

    # Build role-appropriate queries — "mid healthcare engineer" is a nonsense audience
    _SPARKTORO_QUERY = {
        "tech":        f"{seniority} software engineer OR developer",
        "healthcare":  f"{seniority} nurse OR clinical professional",
        "defense":     f"{seniority} defense engineer OR cleared professional",
        "logistics":   f"{seniority} warehouse OR logistics professional",
        "marketing":   f"{seniority} marketing manager OR growth marketer",
        "sales":       f"{seniority} account executive OR sales professional",
        "hr":          f"{seniority} recruiter OR talent acquisition professional",
        "finance":     f"{seniority} financial analyst OR accountant",
        "retail":      f"{seniority} retail associate OR store manager",
        "hospitality": f"{seniority} hospitality professional",
    }
    sparktoro_query = _SPARKTORO_QUERY.get(industry, f"{seniority} professional")

    # ── Sources 1-3: Run SparkToro / PDL / Lightcast IN PARALLEL ──────────
    #    Sequential calls would add up to 30s; parallelising keeps p99 < 12s.
    def _fetch_sparktoro():
        return _sparktoro_audience(sparktoro_query)

    def _fetch_pdl():
        return _pdl_search_by_job(
            title=f"{seniority} {industry}",
            location=location,
            industry=industry,
            seniority=seniority,
            limit=15,
        )

    def _fetch_lightcast():
        _LIGHTCAST_TITLE = {
            "tech":        f"{seniority} software engineer",
            "healthcare":  f"{seniority} registered nurse",
            "defense":     f"{seniority} defense systems engineer",
            "logistics":   f"{seniority} supply chain analyst",
            "marketing":   f"{seniority} marketing manager",
            "sales":       f"{seniority} account executive",
            "hr":          f"{seniority} recruiter",
            "finance":     f"{seniority} financial analyst",
            "retail":      f"{seniority} retail manager",
            "hospitality": f"{seniority} hospitality manager",
        }
        return _lightcast_skills_demand(title=_LIGHTCAST_TITLE.get(industry, f"{seniority} professional"))

    with ThreadPoolExecutor(max_workers=3) as pool:
        st_fut = pool.submit(_fetch_sparktoro)
        pdl_fut = pool.submit(_fetch_pdl)
        lc_fut  = pool.submit(_fetch_lightcast)
        sparktoro    = st_fut.result()
        pdl_profiles = pdl_fut.result()
        lightcast    = lc_fut.result()

    pdl_signals = _extract_pdl_signals(pdl_profiles)

    # Sources used counter (for ITSMA validation)
    sources_used = ["text_analysis"]
    if sparktoro:                sources_used.append("sparktoro")
    if pdl_signals:              sources_used.append("people_data_labs")
    if lightcast:                sources_used.append("lightcast")
    if li and li.get("source") != "none": sources_used.append(li.get("source", "linkedin"))

    # ── Assemble signal dict for LLM ──────────────────────────────────────
    # Clamp counts (already validated by caller, but be safe)
    num_personas = max(2, min(int(num_personas), 6))
    num_passive  = max(0, min(int(num_passive),  6))

    signal_dict = {
        "industry":           industry,
        "seniority":          seniority,
        "role_type":          role_type,
        "skills":             skills,
        "salary":             salary,
        "location":           location,
        "work_arrangement":   arrangement,
        "jd_excerpt":         jd_excerpt,
        "num_personas":       num_personas,
        "num_passive":        num_passive,
        **flags,
        "li_industries":      [i.get("name","") for i in li.get("industries",[])[:5]],
        "li_colleges":        [c.get("name","") for c in li.get("colleges",[])[:5]],
        "pdl_prior_employers":pdl_signals.get("typical_prior_employers", []),
        "lightcast_skills":   lightcast.get("top_skills_in_demand", [])[:6],
        "sparktoro_sites":    sparktoro.get("websites", [])[:5],
        "sparktoro_subreddits":sparktoro.get("subreddits", [])[:4],
    }

    # ── Persona generation: N MECE personas (2–6) ────────────────────────────
    # Archetypes are ordered by market prevalence — each additional persona adds
    # orthogonal DISC/motivation coverage so MECE holds across all N.
    archetypes = _get_mece_archetypes(seniority, role_type, num_personas)

    personas_list = []
    for i, arch in enumerate(archetypes):
        p_signals = {**signal_dict, "persona_variant": i + 1, "mece_archetype": arch}
        personas_list.append(_generate_persona_llm(p_signals))

    # ── Passive candidate personas ────────────────────────────────────────
    # Passive archetypes define latent-dissatisfaction triggers and outreach
    # strategy — fundamentally different from active candidate messaging.
    passive_list = []
    if num_passive > 0:
        passive_archetypes = _get_passive_archetypes(seniority, role_type, num_passive)
        for i, arch in enumerate(passive_archetypes):
            # Build a lightweight passive persona from the archetype definition
            # (no LLM call needed — the archetype itself is the deliverable)
            passive_list.append({
                "archetype_name":   arch["archetype_name"],
                "disc_type":        arch["disc"],
                "activity_level":   "passive",
                "motivation":       arch["motivation"],
                "background_style": arch["background_style"],
                "latent_trigger":   arch["latent_trigger"],
                "outreach_angle":   arch["outreach_angle"],
                "passive_barrier":  arch["passive_barrier"],
                "reachability":     arch["reachability"],
                "role":             f"{seniority.title()} {'People Manager' if role_type == 'people_manager' else 'IC'}",
                "profile":          (f"{seniority.title()} · "
                                     f"{'People Manager' if role_type == 'people_manager' else 'Individual Contributor'} · "
                                     f"Currently Employed · Passive"),
                "skills":           skills,
                "attributes": {
                    "seniority":        seniority,
                    "work_arrangement": arrangement,
                    "salary":           salary,
                    "location":         location,
                    **flags,
                },
                "pdl_signals":  pdl_signals,
                "lightcast":    lightcast,
                "sparktoro":    sparktoro,
            })

    # ── Channel recommendations (SparkToro-informed) ──────────────────────
    flags_list = [k for k, v in flags.items() if v]
    channels = _channel_recs_from_sparktoro(sparktoro, industry, flags_list)

    # Ensure messaging_variants always present on all personas
    for p in personas_list:
        if not p.get("messaging_variants"):
            p["messaging_variants"] = _rule_based_messaging(
                p.get("disc_type", "S"), industry, p.get("role", "Professional")
            )

    # ── Feedback loop: surface fallback status ────────────────────────────
    used_fallback = any(p.get("_used_fallback") for p in personas_list)
    llm_provider  = next(
        (p.get("_llm_provider") for p in personas_list if not p.get("_used_fallback")),
        "rule_based"
    )

    return {
        "source":         source_label,
        "sources_used":   sources_used,
        "itsma_validated":len(sources_used) >= 3,
        "industry":       industry,
        # Top-level signals dict — exposed for frontend, tests, and debugging
        "signals": {
            "seniority":        seniority,
            "role_type":        role_type,
            "arrangement":      arrangement,
            "location":         location,
            "salary":           salary,
            "skills":           skills,
            **flags,
        },
        "jd_quality":     jd_quality,
        "llm_provider":   llm_provider,
        "used_fallback":  used_fallback,
        "personas": [
            {
                **p,
                "skills":     _filter_skills_for_persona(
                                  skills,
                                  p.get("disc_type", "S"),
                                  p.get("name", ""),
                              ),
                "publishers": [c["name"] for c in channels],
                "attributes": {
                    "seniority":       seniority,
                    "work_arrangement":arrangement,
                    "salary":          salary,
                    "location":        location,
                    **flags,
                },
                "pdl_signals":    pdl_signals,
                "lightcast":      lightcast,
                "sparktoro":      sparktoro,
            }
            for p in personas_list
        ],
        "channels":         channels,
        "competitive":      _get_competitive(industry),
        "ad_strategy":      _get_ad_strategy(industry, bilingual=flags.get("bilingual", False)),
        "li_signals":       li,
        "passive_personas": passive_list,  # Empty list if num_passive=0
        "generated_at":     int(time.time()),
    }


def _cluster_jobs(jobs: list) -> list:
    clusters: dict = {}
    for job in jobs:
        text = f"{job.get('title','')} {job.get('description','')}"
        key  = f"{_detect_industry(text)}:{_detect_seniority(text)}"
        if key not in clusters:
            clusters[key] = {"industry": _detect_industry(text),
                             "seniority": _detect_seniority(text), "texts": [], "titles": []}
        clusters[key]["texts"].append(text)
        clusters[key]["titles"].append(job.get("title", ""))

    result = []
    for c in clusters.values():
        c["combined_text"] = " ".join(c["texts"][:5])[:8000]
        result.append(c)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 11. HTTP ENDPOINT HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

def handle_analyze_jd(body: dict) -> dict:
    """POST /api/persona-builder/analyze-jd — body: {text, url, numPersonas?, numPassivePersonas?}"""
    text         = body.get("text", "").strip()
    url          = body.get("url", "").strip()
    num_personas = int(body.get("numPersonas", body.get("num_personas", 2)))
    num_passive  = int(body.get("numPassivePersonas", body.get("num_passive", 0)))
    num_personas = max(2, min(num_personas, 6))   # clamp 2–6
    num_passive  = max(0, min(num_passive,  6))   # clamp 0–6

    if not text and not url:
        return {"error": "Provide 'text' or 'url'"}, 400

    if url and not text:
        cache_key = _cache_key("jd_url", f"{url}:{num_personas}:{num_passive}")
        if cached := _l1_get(cache_key):
            return cached
        text = _fetch_url(url)
        if not text:
            return {"error": f"Could not fetch content from {url}"}, 502

    cache_key = _cache_key("jd_text", f"{text[:2000]}:{num_personas}:{num_passive}")
    if cached := _l1_get(cache_key):
        return cached

    result = _build_persona_response(text, "job_description",
                                     num_personas=num_personas, num_passive=num_passive)
    _l1_set(cache_key, result, ttl=3600)
    return result


def handle_analyze_url(body: dict) -> dict:
    """POST /api/persona-builder/analyze-url — body: {url}"""
    url = body.get("url", "").strip()
    if not url:
        return {"error": "Provide 'url'"}, 400

    cache_key = _cache_key("careers_url", url)
    if cached := _l1_get(cache_key):
        return cached

    raw = _fetch_url(url)
    if not raw:
        return {"error": f"Could not scrape {url}"}, 502

    blocks = re.split(r"\n{2,}", raw)
    jobs = [
        {"title": b[:80], "description": b}
        for b in blocks
        if 20 < len(b) < 2000 and any(
            kw in b.lower() for kw in
            ["engineer","manager","analyst","specialist","nurse","driver","associate","developer"]
        )
    ][:30]

    if not jobs:
        return handle_analyze_jd({"text": raw[:8000]})

    clusters = _cluster_jobs(jobs)
    personas_out = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_build_persona_response, c["combined_text"], "careers_page"): c
                   for c in clusters[:6]}
        for future in as_completed(futures):
            try:
                res = future.result()
                if res.get("personas"):
                    personas_out.extend(res["personas"])
            except Exception as e:
                logger.warning(f"Cluster failed: {e}")

    if not personas_out:
        return {"error": "Could not extract persona clusters from this careers page"}, 422

    base = _build_persona_response(raw[:4000], "careers_page")
    base["personas"] = personas_out
    base["source"]   = "careers_page"
    _l1_set(cache_key, base, ttl=7200)
    return base


def handle_analyze_linkedin(body: dict) -> dict:
    """POST /api/persona-builder/analyze-linkedin — body: {linkedin_url, careers_url}"""
    li_url      = body.get("linkedin_url", "").strip()
    careers_url = body.get("careers_url",  "").strip()

    if not li_url:
        return {"error": "Provide 'linkedin_url'"}, 400

    cache_key = _cache_key("li_full", li_url, careers_url)
    if cached := _l1_get(cache_key):
        return cached

    # Parallel fetch
    li_signals    = {}
    careers_text  = ""
    with ThreadPoolExecutor(max_workers=2) as pool:
        li_fut = pool.submit(_brightdata_linkedin_company, li_url)
        ca_fut = pool.submit(_fetch_url, careers_url) if careers_url else None
        li_signals   = li_fut.result()
        careers_text = ca_fut.result() if ca_fut else ""

    # Build combined signal text from LinkedIn + careers
    li_text = " ".join([
        " ".join(i.get("name","") for i in li_signals.get("industries",[])),
        " ".join(li_signals.get("skills",[])),
        li_signals.get("description",""),
    ])
    combined = f"{li_text} {careers_text}"[:8000]

    if not combined.strip():
        return {"error": "Could not extract signals from LinkedIn or careers page"}, 502

    result = _build_persona_response(combined, "linkedin", li_signals=li_signals)
    if li_signals.get("name"):
        result["company_name"] = li_signals["name"]

    _l1_set(cache_key, result, ttl=86400)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 12. ROUTE REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def register_routes(handler_dispatch: dict):
    """
    Register persona builder endpoints in app.py dispatch table.

    In app.py:
        from persona_builder import register_routes
        register_routes(self.post_routes)

    Required env vars:
        ANTHROPIC_API_KEY       — Claude Haiku (persona generation)
        BRIGHTDATA_API_TOKEN    — Bright Data LinkedIn scraper (replaces Proxycurl)
        PDL_API_KEY             — People Data Labs (career trajectory signals)
        SPARKTORO_API_KEY       — Audience channel intelligence
        LIGHTCAST_CLIENT_ID     — Lightcast skills demand
        LIGHTCAST_CLIENT_SECRET — Lightcast auth
        APIFY_API_KEY           — Fallback LinkedIn scraper

    Optional (system works without them, output degrades gracefully):
        PDL, SparkToro, Lightcast, Apify
    """
    handler_dispatch["/api/persona-builder/analyze-jd"]       = handle_analyze_jd
    handler_dispatch["/api/persona-builder/analyze-url"]       = handle_analyze_url
    handler_dispatch["/api/persona-builder/analyze-linkedin"]  = handle_analyze_linkedin
    logger.info("[PersonaBuilder] Endpoints registered: analyze-jd, analyze-url, analyze-linkedin")
    logger.info("[PersonaBuilder] Active data sources: Bright Data | PDL | SparkToro | Lightcast | Jina | Claude Haiku")


# ── Public aliases for Vercel API handler imports ─────────────────────────────
# The Vercel handlers (analyze-jd.py, analyze-url.py, analyze-linkedin.py)
# import these names directly. Keep as public (no underscore) so they're
# importable without the leading underscore.
build_persona_response = _build_persona_response
cluster_jobs           = _cluster_jobs
