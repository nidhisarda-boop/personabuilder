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
        "mid":       "entry",
        "junior":    "training",
    }
    return mapping.get(seniority, "entry")


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
        "campus":     [{"name":"Handshake","tier":"niche","why":"16M students at 1,400+ universities — the campus recruiting standard."},
                       {"name":"Chegg Internships","tier":"niche","why":"High-intent student and early career audience."}],
    }

    additions = industry_map.get(industry, [])
    if "clearance" in signals:
        additions.extend(industry_map.get("defense", []))
    if "bilingual" in signals:
        additions.extend(industry_map.get("bilingual", []))

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
    "tech":        r"software\b|engineer\b|developer\b|devops|data scien|machine learning|\bml\b|\bai\b|cloud|aws|gcp|azure|python|javascript|typescript|react|node\.js|kubernetes|backend|frontend|full.?stack|sre\b|platform engineer",
    "healthcare":  r"\bnurse\b|\brn\b|\blpn\b|\bphysician\b|\bclinical\b|\bicu\b|\ber\b|\bsurgery\b|\bhospital\b|\bhealthcare\b|\bmedical\b|patient care|\bbsn\b|\badn\b|\bcna\b|radiology|pharmacy",
    "logistics":   r"\bwarehouse\b|\bfulfillment\b|\bdistribution\b|\blogistics\b|\bdriver\b|\bforklift\b|picker|packer|\bshipping\b|\bfreight\b|supply chain|last.?mile",
    "retail":      r"\bretail\b|store associate|\bcashier\b|sales associate|shift manager|\bpharma\b",
    "hospitality": r"\brestaurant\b|\bhotel\b|\bhospitality\b|\bserver\b|\bcook\b|\bchef\b|front desk|housekeeping|barista|concierge",
    "finance":     r"\bfinance\b|fintech|\bbanking\b|\btrading\b|\baccounting\b|\bcpa\b|\baudit\b|wealth management|investment|financial analyst|actuar",
    "defense":     r"\bdefense\b|\bclearance\b|\bsecret\b|ts\/sci|\bmissile\b|\bradar\b|\bmilitary\b|\bdod\b|\bdarpa\b|hypersonic|ballistic|aerospace engineer",
    "marketing":   r"\bmarketing\b|brand strateg|demand gen|growth hacker|content strateg|seo\b|sem\b|paid media|campaign manager|product marketing|social media manager|communications manager",
    "sales":       r"\bsales\b|account executive|account manager|business development|sdr\b|bdr\b|revenue|quota|closing deals|pipeline|crm",
    "hr":          r"\brecruiting\b|\brecruitment\b|talent acquisition|hrbp|human resources|\bpeople ops\b|compensation.{0,20}benefits|workforce planning",
}

SENIORITY_RE = {
    "executive": r"vp |vice president|cto|cpo|coo|ceo|chief\s|svp|evp",
    "director":  r"director of|head of",
    "manager":   r"\bmanager\b|supervisor|team lead\b",
    "senior":    r"\bsenior\b|\bstaff\b|principal\b|lead engineer|sr\.",
    "junior":    r"\bjunior\b|entry.?level|associate engineer|new grad|\bintern\b",
}

SKILL_VOCAB = [
    "Python","Java","Go","JavaScript","TypeScript","React","Node.js","C++","C#","Rust","Swift",
    "AWS","GCP","Azure","Kubernetes","Docker","Kafka","Terraform","PostgreSQL","Redis","Spark",
    "TensorFlow","PyTorch","scikit-learn","SQL","dbt","Snowflake",
    "RTOS","VxWorks","LynxOS","VHDL","MATLAB","Simulink","DO-178C","MIL-STD-882","ADA",
    "RF","Radar","EO/IR","MBSE","SysML","JIRA","Confluence",
    "ACLS","BLS","BSN","ADN","ACLS","IV Therapy","Epic","Cerner",
    "Spanish","Bilingual","Salesforce","HubSpot","CRM",
]

def _detect_industry(text: str) -> str:
    text_lower = text.lower()
    scores = {ind: len(re.findall(pat, text_lower)) for ind, pat in INDUSTRY_RE.items()}
    scores = {k: v for k, v in scores.items() if v}
    return max(scores, key=scores.get) if scores else "general"

def _detect_seniority(text: str) -> str:
    text_lower = text.lower()
    for level in ("executive", "director", "manager", "senior", "junior"):
        if re.search(SENIORITY_RE[level], text_lower):
            return level
    return "mid"

def _extract_skills(text: str) -> list:
    found = [s for s in SKILL_VOCAB if re.search(re.escape(s), text, re.IGNORECASE)]
    return found[:12]

def _extract_salary(text: str) -> str:
    m = re.search(
        r"\$[\d,]+[k]?\s*[-–—]\s*\$[\d,]+[k]?"
        r"|\$[\d,]+[k]?\s*/\s*(hr|hour|yr|year)"
        r"|\$[\d,.]+[k]?\+",
        text, re.IGNORECASE,
    )
    return m.group(0) if m else "Not specified"

def _extract_location(text: str) -> str:
    m = re.search(r"(?:in|at|–|-)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?,?\s?[A-Z]{2})", text)
    if m:
        return m.group(1)
    if re.search(r"fully remote|100% remote|work from home|wfh", text, re.IGNORECASE):
        return "Remote"
    if re.search(r"hybrid", text, re.IGNORECASE):
        return "Hybrid"
    return "On-site"

def _detect_arrangement(text: str) -> str:
    if re.search(r"fully remote|100% remote|work from home|wfh", text, re.IGNORECASE):
        return "Fully remote"
    if re.search(r"hybrid", text, re.IGNORECASE):
        return "Hybrid"
    return "On-site"

def _detect_flags(text: str) -> dict:
    return {
        "clearance":  bool(re.search(r"clearance|secret\b|ts\/sci|dod\b", text, re.IGNORECASE)),
        "bilingual":  bool(re.search(r"bilingual|spanish.*english|english.*spanish|fluent.*spanish", text, re.IGNORECASE)),
        "veteran":    bool(re.search(r"veteran|military|service member|reservist|skillbridge", text, re.IGNORECASE)),
        "campus":     bool(re.search(r"intern|co.?op|new grad|recent grad|entry.?level", text, re.IGNORECASE)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. LLM PERSONA GENERATION — JTBD Framework
#    Jobs-to-be-Done: core job, context triggers, functional + emotional goals,
#    desired outcomes. Better than pure demographic personas.
#    Per ITSMA: combine ≥3 data sources per persona.
# ══════════════════════════════════════════════════════════════════════════════

PERSONA_SYSTEM = """You are a senior recruitment marketing strategist at Joveo building candidate personas for B2B talent acquisition campaigns.

Use the Jobs-to-be-Done (JTBD) framework combined with Crystal Knows DISC personality typing.

JTBD framework — build insight, not demographics:
- Core job: what they're fundamentally trying to accomplish in their career
- Context trigger: the specific event RIGHT NOW making them open to a move (layoff fear, program ending, ceiling hit, life change)
- Functional goals: 3 concrete things the job must deliver practically
- Emotional goals: 2 ways they need to FEEL in their work
- Concern: their single biggest hesitation (not "culture fit" — be specific)

DISC personality signal (Crystal Knows methodology):
- D: results-driven, direct, hates process — lead with outcomes + ownership
- I: people-oriented, enthusiastic — lead with team story + growth visibility
- S: steady, collaborative, loyal — lead with stability + belonging
- C: analytical, precise, sceptical — lead with evidence + technical depth

Return ONLY valid JSON — no markdown fences, no commentary before or after:
{
  "name": "The [Archetype]",
  "role": "Specific job title / discipline",
  "profile": "Age range · seniority · current employer type (e.g. 'mid-size SaaS, Series B') · location or remote status",
  "core_job": "One precise sentence — what career outcome are they working toward?",
  "context_trigger": "Specific situation making them open RIGHT NOW — be concrete",
  "functional_goals": ["concrete need 1", "concrete need 2", "concrete need 3"],
  "emotional_goals": ["emotional state 1", "emotional state 2"],
  "concern": "Single most specific hesitation — name the real fear",
  "primary_message": "The most compelling headline you could show this person — in quotes, max 15 words",
  "background": "2-sentence narrative. Name real company types, real situations, real technologies.",
  "disc_type": "D",
  "disc_implication": "Concrete outreach guidance: what to lead with, what to avoid, what format works best",
  "acquisition_trigger": "Exact content type or event that triggers engagement (e.g. 'a staff engineer's blog post about architecture decisions')",
  "job_quality_issues": ["specific weakness of THIS job description that would deter this persona", "second issue if applicable"],
  "messaging_variants": [
    {
      "label": "Results-first (D-type)",
      "headline": "Max 12 words. Direct, outcome-focused, no fluff.",
      "body": "2-3 sentences. Reference real technologies, company types, specific situations. No platitudes.",
      "cta": "Strong action CTA, max 8 words"
    },
    {
      "label": "Social/story (I-type)",
      "headline": "Max 12 words. Community, team, growth, story angle.",
      "body": "2-3 sentences. Name real communities, reference real career moments, be warm.",
      "cta": "Inviting CTA, max 8 words"
    },
    {
      "label": "Evidence/process (C-type)",
      "headline": "Max 12 words. Data-led, specific, transparent.",
      "body": "2-3 sentences. Include numbers, process details, technical specifics. No vague claims.",
      "cta": "Transparency-promise CTA, max 8 words"
    }
  ]
}

Every field must be deployment-ready — specific enough to use as actual campaign copy.
Never use placeholder text. Reference real technologies, real company names, real situations."""


def _build_llm_prompt(signals: dict) -> str:
    """Build the user prompt from signals dict."""
    parts = [
        f"Industry: {signals['industry']}",
        f"Seniority: {signals['seniority']}",
        f"Location: {signals['location']}",
        f"Work arrangement: {signals['work_arrangement']}",
        f"Salary: {signals['salary']}",
        f"Skills detected: {', '.join(signals.get('skills', []))}",
        f"Clearance required: {signals.get('clearance', False)}",
        f"Bilingual required: {signals.get('bilingual', False)}",
        f"Veteran pathway: {signals.get('veteran', False)}",
    ]
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
    """Strip markdown fences and parse JSON from LLM response."""
    text = re.sub(r"^```(?:json)?\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _call_openai_compat(api_key: str, base_url: str, model: str, prompt: str) -> dict:
    """Generic caller for any OpenAI-compatible API (DeepSeek, Groq, OpenAI, etc.)."""
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "max_tokens": 1800,
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
            "generationConfig": {"maxOutputTokens": 1800, "temperature": 0.7},
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_llm_json(resp.json()["candidates"][0]["content"]["parts"][0]["text"])


def _generate_persona_llm(signals: dict) -> dict:
    """
    Call the best available LLM to generate a persona.
    Provider priority (first key found wins):
      1. DeepSeek-V3  (DEEPSEEK_API_KEY)   — cheap, excellent reasoning
      2. Groq/Llama-3.3-70B (GROQ_API_KEY) — free tier, very fast
      3. Google Gemini 2.0 Flash (GEMINI_API_KEY) — free tier
      4. OpenAI GPT-4o-mini  (OPENAI_API_KEY)
      5. Anthropic Claude Haiku (ANTHROPIC_API_KEY)
      6. Rule-based fallback
    """
    prompt = _build_llm_prompt(signals)

    providers = []
    if DEEPSEEK_KEY:
        providers.append(("DeepSeek-V3",      lambda: _call_openai_compat(DEEPSEEK_KEY, "https://api.deepseek.com/v1", "deepseek-chat", prompt)))
    if GROQ_KEY:
        providers.append(("Groq/Llama-3.3",   lambda: _call_openai_compat(GROQ_KEY,     "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", prompt)))
    if GEMINI_KEY:
        providers.append(("Gemini-2.0-Flash", lambda: _call_gemini(GEMINI_KEY, prompt)))
    if OPENAI_KEY:
        providers.append(("GPT-4o-mini",      lambda: _call_openai_compat(OPENAI_KEY,   "https://api.openai.com/v1", "gpt-4o-mini", prompt)))
    if ANTHROPIC_KEY:
        providers.append(("Claude-Haiku",     lambda: _call_anthropic(ANTHROPIC_KEY, CLAUDE_MODEL, prompt)))

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
            logger.info(f"Persona generated via {name}")
            return persona
        except Exception as e:
            logger.warning(f"{name} failed: {e}")
            continue

    logger.warning("All LLM providers failed — falling back to rule-based persona")
    return _rule_based_persona(signals)


def _rule_based_persona(signals: dict) -> dict:
    """Fallback when LLM is unavailable."""
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
    persona = {
        "name": t[0], "role": t[1],
        "profile": f"{signals.get('seniority','mid').title()} · {signals.get('work_arrangement','On-site')} · {signals.get('location','Unspecified')} · {signals.get('salary','Comp TBD')}",
        "core_job": t[2], "context_trigger": "Hitting a ceiling at current employer — no growth path visible.",
        "functional_goals": ["Competitive compensation tied to outcomes", "Clear career progression with visible milestones", "High-signal, low-noise work environment"],
        "emotional_goals": ["Feel their expertise is genuinely valued", "Feel the work has consequence beyond a P&L line"],
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
    has_salary = bool(re.search(
        r'\$[\d,]+[k]?|\d{2,3}[k]\s*/\s*(?:yr|year|hr|hour)|salary range|compensation range|total comp',
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
        "tech":       ("engineering", "systems", "engineers"),
        "healthcare": ("clinical", "patient care", "clinicians"),
        "defense":    ("defense", "mission-critical systems", "engineers"),
        "logistics":  ("operations", "supply chain", "operators"),
        "finance":    ("finance", "financial systems", "analysts"),
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
                "label": "Technical depth (C-type alt)",
                "headline": f"No shortcuts. No tech debt excuses. Real {industry_noun[0]} engineering.",
                "body": (
                    f"Full test coverage. Architecture reviews before PRs merge. Retrospectives that actually change things. "
                    f"If you care how {industry_noun[1]} are built — not just that they ship — you'll fit here."
                ),
                "cta": "Read our engineering blog →",
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
# 10. CORE BUILD FUNCTION — Multi-source, ITSMA ≥3 sources
# ══════════════════════════════════════════════════════════════════════════════

def _build_persona_response(text: str, source_label: str, li_signals: dict = None) -> dict:
    """
    Build a full PersonaResponse from raw text + optional LinkedIn signals.
    Uses ≥3 data sources per ITSMA best practice.
    """
    industry    = _detect_industry(text)
    seniority   = _detect_seniority(text)
    skills      = _extract_skills(text)
    salary      = _extract_salary(text)
    location    = _extract_location(text)
    arrangement = _detect_arrangement(text)
    flags       = _detect_flags(text)
    jd_quality  = _score_jd_quality(text)

    li = li_signals or {}

    sparktoro_query = f"{seniority} {industry} engineer" if industry != "general" else f"{seniority} professional"

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
        return _lightcast_skills_demand(title=f"{seniority} {industry} engineer")

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
    signal_dict = {
        "industry":           industry,
        "seniority":          seniority,
        "skills":             skills,
        "salary":             salary,
        "location":           location,
        "work_arrangement":   arrangement,
        **flags,
        "li_industries":      [i.get("name","") for i in li.get("industries",[])[:5]],
        "li_colleges":        [c.get("name","") for c in li.get("colleges",[])[:5]],
        "pdl_prior_employers":pdl_signals.get("typical_prior_employers", []),
        "lightcast_skills":   lightcast.get("top_skills_in_demand", [])[:6],
        "sparktoro_sites":    sparktoro.get("websites", [])[:5],
        "sparktoro_subreddits":sparktoro.get("subreddits", [])[:4],
    }

    persona = _generate_persona_llm(signal_dict)

    # ── Channel recommendations (SparkToro-informed) ──────────────────────
    flags_list = [k for k, v in flags.items() if v]
    channels = _channel_recs_from_sparktoro(sparktoro, industry, flags_list)

    # Ensure messaging_variants always present
    if not persona.get("messaging_variants"):
        persona["messaging_variants"] = _rule_based_messaging(
            persona.get("disc_type", "S"), industry, persona.get("role", "Professional")
        )

    return {
        "source":         source_label,
        "sources_used":   sources_used,
        "itsma_validated":len(sources_used) >= 3,
        "industry":       industry,
        "jd_quality":     jd_quality,
        "personas": [{
            **persona,
            "skills":     skills,
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
        }],
        "channels":    channels,
        "competitive": _get_competitive(industry),
        "ad_strategy": _get_ad_strategy(industry, bilingual=flags.get("bilingual", False)),
        "li_signals":  li,
        "generated_at":int(time.time()),
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
    """POST /api/persona-builder/analyze-jd — body: {text, url}"""
    text = body.get("text", "").strip()
    url  = body.get("url", "").strip()

    if not text and not url:
        return {"error": "Provide 'text' or 'url'"}, 400

    if url and not text:
        cache_key = _cache_key("jd_url", url)
        if cached := _l1_get(cache_key):
            return cached
        text = _fetch_url(url)
        if not text:
            return {"error": f"Could not fetch content from {url}"}, 502

    cache_key = _cache_key("jd_text", text[:400])
    if cached := _l1_get(cache_key):
        return cached

    result = _build_persona_response(text, "job_description")
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
