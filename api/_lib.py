"""
Shared persona builder logic — imported by all three Vercel function handlers.
This is a trimmed version of persona_builder.py adapted for Vercel serverless:
- Removes BaseHTTPRequestHandler dependency
- Works with plain dicts in / dict out
- All API keys read from Vercel environment variables
"""
import json, os, re, time, hashlib, logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import urllib.request, urllib.error

logger = logging.getLogger(__name__)

# ── Env ───────────────────────────────────────────────────────────────────────
JINA_BASE         = "https://r.jina.ai/"
BRIGHTDATA_TOKEN  = os.environ.get("BRIGHTDATA_API_TOKEN", "")
PDL_API_KEY       = os.environ.get("PDL_API_KEY", "")
SPARKTORO_API_KEY = os.environ.get("SPARKTORO_API_KEY", "")
LIGHTCAST_CLIENT  = os.environ.get("LIGHTCAST_CLIENT_ID", "")
LIGHTCAST_SECRET  = os.environ.get("LIGHTCAST_CLIENT_SECRET", "")
ANTHROPIC_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-haiku-4-5"

# ── L1 cache ──────────────────────────────────────────────────────────────────
_L1: dict = {}

def _ck(*parts): return hashlib.sha256(":".join(parts).encode()).hexdigest()[:20]
def _lg(k):
    e = _L1.get(k)
    return e["v"] if e and time.time() < e["x"] else None
def _ls(k, v, ttl=3600): _L1[k] = {"v": v, "x": time.time() + ttl}

# ── HTTP util (no requests lib on Vercel — use urllib) ────────────────────────
def _http_get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"GET {url} failed: {e}")
        return ""

def _http_post(url, data, headers=None, timeout=15):
    body = json.dumps(data).encode()
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(f"POST {url} failed: {e}")
        return {}

# ── Web fetch ─────────────────────────────────────────────────────────────────
def _fetch_url(url):
    text = _http_get(JINA_BASE + url, {"Accept": "text/plain"})
    if len(text) > 200: return text[:40_000]
    text = _http_get(url, {"User-Agent": "Mozilla/5.0 (Nova/2.0)"})
    return text[:40_000]

# ── Signal extractors ─────────────────────────────────────────────────────────
INDUSTRY_RE = {
    "tech":       r"software|engineer|developer|devops|data scien|ml |ai |cloud|aws|gcp|azure|python|java|react|node|kubernetes",
    "healthcare": r"nurse|rn |lpn |physician|clinical|icu|er |surgery|hospital|health|medical|patient care",
    "logistics":  r"warehouse|fulfillment|distribution|logistics|driver|forklift|picker|packer|shipping",
    "retail":     r"retail|store associate|cashier|sales associate|customer service|shift manager",
    "finance":    r"finance|fintech|banking|trading|accounting|cpa |audit|wealth management",
    "defense":    r"defense|clearance|secret |ts\/sci|missile|radar|military|dod|hypersonic",
}
SENIORITY_RE = {
    "executive": r"vp |vice president|cto|cpo|coo|ceo|chief\s|svp|evp",
    "director":  r"director of|head of",
    "manager":   r"\bmanager\b|supervisor|team lead\b",
    "senior":    r"\bsenior\b|\bstaff\b|principal\b|lead engineer|sr\.",
    "junior":    r"\bjunior\b|entry.?level|associate engineer|new grad|\bintern\b",
}
SKILL_VOCAB = [
    "Python","Java","Go","JavaScript","TypeScript","React","Node.js","C++","C#","Rust",
    "AWS","GCP","Azure","Kubernetes","Docker","Kafka","Terraform","PostgreSQL","Redis",
    "TensorFlow","PyTorch","SQL","dbt","Snowflake","VHDL","MATLAB","DO-178C","MIL-STD-882",
    "RF","Radar","MBSE","SysML","ACLS","BLS","BSN","Epic","Cerner","Spanish","Bilingual","Salesforce",
]

def _detect_industry(t):
    tl = t.lower()
    scores = {i: len(re.findall(p, tl)) for i, p in INDUSTRY_RE.items()}
    scores = {k: v for k, v in scores.items() if v}
    return max(scores, key=scores.get) if scores else "general"

def _detect_seniority(t):
    tl = t.lower()
    for lvl in ("executive","director","manager","senior","junior"):
        if re.search(SENIORITY_RE[lvl], tl): return lvl
    return "mid"

def _extract_skills(t):
    return [s for s in SKILL_VOCAB if re.search(re.escape(s), t, re.IGNORECASE)][:12]

def _extract_salary(t):
    m = re.search(r"\$[\d,]+[k]?\s*[-–—]\s*\$[\d,]+[k]?|\$[\d,]+[k]?\s*/\s*(hr|hour|yr|year)", t, re.IGNORECASE)
    return m.group(0) if m else "Not specified"

def _extract_location(t):
    m = re.search(r"(?:in|at|–|-)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?,?\s?[A-Z]{2})", t)
    if m: return m.group(1)
    if re.search(r"fully remote|100% remote|work from home|wfh", t, re.IGNORECASE): return "Remote"
    if re.search(r"hybrid", t, re.IGNORECASE): return "Hybrid"
    return "On-site"

def _detect_arrangement(t):
    if re.search(r"fully remote|100% remote|wfh", t, re.IGNORECASE): return "Fully remote"
    if re.search(r"hybrid", t, re.IGNORECASE): return "Hybrid"
    return "On-site"

def _detect_flags(t):
    return {
        "clearance": bool(re.search(r"clearance|secret\b|ts\/sci|dod\b", t, re.IGNORECASE)),
        "bilingual": bool(re.search(r"bilingual|spanish.*english|fluent.*spanish", t, re.IGNORECASE)),
        "veteran":   bool(re.search(r"veteran|military|skillbridge", t, re.IGNORECASE)),
        "campus":    bool(re.search(r"intern|co.?op|new grad|recent grad|entry.?level", t, re.IGNORECASE)),
    }

# ── SparkToro ─────────────────────────────────────────────────────────────────
def _sparktoro_audience(query):
    k = _ck("st", query)
    if c := _lg(k): return c
    if not SPARKTORO_API_KEY: return {}
    resp = _http_get(
        f"https://api.sparktoro.com/v1/search?query={query}&type=talks_about&limit=20",
        {"Authorization": f"Bearer {SPARKTORO_API_KEY}"}
    )
    if not resp: return {}
    try:
        d = json.loads(resp)
        r = {
            "websites":   [s.get("domain") for s in d.get("websites", [])[:8]],
            "podcasts":   [p.get("title")  for p in d.get("podcasts", [])[:5]],
            "subreddits": [r.get("name")   for r in d.get("subreddits", [])[:5]],
            "source": "sparktoro",
        }
        _ls(k, r, 86400*7)
        return r
    except Exception: return {}

# ── PDL ───────────────────────────────────────────────────────────────────────
def _pdl_search(title, location, seniority):
    k = _ck("pdl", title, location, seniority)
    if c := _lg(k): return c
    if not PDL_API_KEY: return []
    country_filter = [] if location in ("Remote", "Hybrid") else [{"term": {"location_country": "united states"}}]
    pdl_level = {"executive":"c_suite","director":"director","manager":"manager","senior":"senior","junior":"training"}.get(seniority, "entry")
    resp = _http_post(
        "https://api.peopledatalabs.com/v5/person/search",
        {"query": {"bool": {"must": [{"term": {"job_title_levels": pdl_level}}, {"match": {"job_title": title}}], "filter": country_filter}}, "size": 15, "dataset": "resume"},
        {"X-Api-Key": PDL_API_KEY}
    )
    profiles = resp.get("data", [])
    _ls(k, profiles, 86400)
    return profiles

def _extract_pdl(profiles):
    if not profiles: return {}
    emp, sch, ten = {}, {}, []
    for p in profiles:
        for ex in (p.get("experience") or [])[1:3]:
            co = ex.get("company", {}).get("name", "")
            if co: emp[co] = emp.get(co, 0) + 1
        for ed in (p.get("education") or [])[:1]:
            s = ed.get("school", {}).get("name", "")
            if s: sch[s] = sch.get(s, 0) + 1
        if p.get("experience"):
            yr = (p["experience"][0].get("start_date") or {}).get("year")
            if yr: ten.append(2026 - int(yr))
    return {
        "typical_prior_employers": sorted(emp, key=emp.get, reverse=True)[:5],
        "typical_schools":         sorted(sch, key=sch.get, reverse=True)[:5],
        "avg_tenure_years":        round(sum(ten)/len(ten), 1) if ten else None,
        "sample_size":             len(profiles),
    }

# ── Lightcast ─────────────────────────────────────────────────────────────────
_lc_tok, _lc_exp = None, 0.0

def _get_lc_token():
    global _lc_tok, _lc_exp
    if not LIGHTCAST_CLIENT or not LIGHTCAST_SECRET: return None
    if _lc_tok and time.time() < _lc_exp - 60: return _lc_tok
    import urllib.parse
    data = urllib.parse.urlencode({"client_id": LIGHTCAST_CLIENT, "client_secret": LIGHTCAST_SECRET, "grant_type": "client_credentials", "scope": "emsi_open"}).encode()
    req = urllib.request.Request("https://auth.emsicloud.com/connect/token", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            _lc_tok = d["access_token"]
            _lc_exp = time.time() + d.get("expires_in", 3600)
            return _lc_tok
    except Exception: return None

def _lightcast_skills(title):
    k = _ck("lc", title)
    if c := _lg(k): return c
    tok = _get_lc_token()
    if not tok: return {}
    resp = _http_get(
        f"https://emsiservices.com/skills/versions/latest/skills?q={title}&limit=20&fields=id,name,type",
        {"Authorization": f"Bearer {tok}"}
    )
    if not resp: return {}
    try:
        d = json.loads(resp)
        r = {"top_skills_in_demand": [s.get("name") for s in d.get("data", [])[:10]], "source": "lightcast"}
        _ls(k, r, 86400*7)
        return r
    except Exception: return {}

# ── LLM persona ───────────────────────────────────────────────────────────────
PERSONA_SYSTEM = """You are a senior recruitment marketing strategist at Joveo building candidate personas.

Use the Jobs-to-be-Done (JTBD) framework:
- Core job statement: What is this person fundamentally trying to accomplish in their career?
- Context triggers: What specific event makes them open to a new role RIGHT NOW?
- Functional goals: What does a job need to do for them practically?
- Emotional goals: How do they want to feel in their work?

Also apply Crystal Knows DISC signal: D (results-driven), I (people-oriented), S (steady), C (analytical)

Return ONLY valid JSON — no markdown fences:
{
  "name": "The [Archetype]",
  "role": "Job title / discipline",
  "profile": "Age range · seniority · employer type · location",
  "core_job": "One sentence: what they're fundamentally trying to accomplish",
  "context_trigger": "The specific situation that makes them open to a move",
  "functional_goals": ["3 practical things the job must do for them"],
  "emotional_goals": ["2 things describing how they want to feel"],
  "concern": "Their #1 hesitation about making a move",
  "primary_message": "The most compelling thing to say to them (in quotes)",
  "background": "2-sentence narrative of their current life",
  "disc_type": "D | I | S | C",
  "disc_implication": "One sentence on how to adapt outreach tone",
  "acquisition_trigger": "The specific event or content that makes them engage"
}"""

def _gen_persona(signals):
    if not ANTHROPIC_KEY: return _rule_persona(signals)
    parts = [
        f"Industry: {signals['industry']}", f"Seniority: {signals['seniority']}",
        f"Location: {signals['location']}", f"Skills: {', '.join(signals.get('skills',[]))}",
        f"Clearance: {signals.get('clearance',False)}", f"Bilingual: {signals.get('bilingual',False)}",
    ]
    if signals.get("sparktoro_sites"): parts.append(f"Audience visits (SparkToro): {', '.join(signals['sparktoro_sites'])}")
    if signals.get("pdl_prior_employers"): parts.append(f"Typical prior employers (PDL): {', '.join(signals['pdl_prior_employers'])}")
    if signals.get("lightcast_skills"): parts.append(f"In-demand skills (Lightcast): {', '.join(signals['lightcast_skills'])}")
    prompt = "Job signals:\n" + "\n".join(parts) + "\n\nGenerate the candidate persona JSON."
    resp = _http_post(
        "https://api.anthropic.com/v1/messages",
        {"model": CLAUDE_MODEL, "max_tokens": 700, "system": PERSONA_SYSTEM, "messages": [{"role": "user", "content": prompt}]},
        {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01"}
    )
    try:
        text = resp.get("content", [{}])[0].get("text", "").strip()
        text = re.sub(r"^```(?:json)?\n?", "", text); text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception: return _rule_persona(signals)

def _rule_persona(s):
    ind = "bilingual" if s.get("bilingual") else "defense" if s.get("clearance") else s.get("industry","general")
    T = {
        "tech":     ("The Creator","Software Engineer","Build systems with real consequence.","Skill stagnation at current employer.","A HN post by a current engineer.",'"Real engineering problems — classified because they matter."',"C"),
        "healthcare":("The Caregiver","Clinical Professional","Provide excellent patient care in a well-staffed unit.","Benefits or schedule won't match what's promised.","A peer review of the unit environment.",'"We know what a 12-hour shift costs. Here\'s how we support you."',"S"),
        "logistics": ("The Frontliner","Logistics Associate","Stable income with predictable shift times.","Hidden costs or inconsistent scheduling.","A mobile apply flow under 90 seconds.",'"Same-week start. Weekly pay. Night differential from day one."',"D"),
        "defense":  ("The Guardian","Cleared Defense Engineer","Work on systems that matter at national scale.","Losing access to classified work.","A technical talk at DEF CON.",'"The problem you\'re cleared to know about — we\'re building the solution."',"C"),
        "bilingual":("The Connector","Bilingual Specialist","Use bilingual ability as a strategic asset.","Being hired for language but undervalued for judgment.","A bilingual employee testimonial.",'"Your language is the product. We built the role around it."',"I"),
        "general":  ("The Professional","Specialist","Advance in a role that values their expertise.","Process disorganisation or unclear growth.","A transparent JD with honest salary.",'"Here\'s exactly what the role is and what growth looks like."',"S"),
    }
    t = T.get(ind, T["general"])
    return {
        "name": t[0], "role": t[1],
        "profile": f"{s.get('seniority','mid').title()} · {s.get('work_arrangement','On-site')} · {s.get('location','Unspecified')} · {s.get('salary','Comp TBD')}",
        "core_job": t[2], "context_trigger": "Hitting a ceiling — no growth path visible.",
        "functional_goals": ["Competitive compensation", "Clear career ladder", "Interesting technical problems"],
        "emotional_goals": ["Feel their work matters", "Feel respected and trusted"],
        "concern": t[3], "acquisition_trigger": t[4], "primary_message": t[5],
        "background": "Currently employed but selectively open. Evaluating carefully before any move.",
        "disc_type": t[6], "disc_implication": "Lead with data and outcomes. Be direct and specific.",
    }

# ── Publisher recommendations ─────────────────────────────────────────────────
def _publishers(sparktoro, industry, flags):
    recs = [{"name":"Joveo Programmatic","tier":"platform","why":"7,053 publishers with real-time CPA optimisation via Joblet.ai."}]
    st_sites = sparktoro.get("websites", [])
    st_subs  = sparktoro.get("subreddits", [])
    if "stackoverflow.com" in st_sites:
        recs.append({"name":"Stack Overflow Jobs","tier":"niche","why":"SparkToro confirms your audience visits Stack Overflow — high context-fit for tech roles."})
    if st_subs:
        recs.append({"name":f"Reddit ({', '.join(st_subs[:3])})","tier":"nontraditional","why":f"SparkToro shows audience active in {', '.join(st_subs[:3])}"})
    IMAP = {
        "tech":      [{"name":"Dice","tier":"niche","why":"6M+ registered tech professionals."},{"name":"Stack Overflow Jobs","tier":"niche","why":"Highest context-fit for engineers."}],
        "healthcare":[{"name":"Nursing.com","tier":"niche","why":"Largest nurse community. Highest intent per dollar."},{"name":"Health eCareers","tier":"niche","why":"3M+ healthcare professionals."}],
        "logistics": [{"name":"Talroo","tier":"niche","why":"Pay-per-applicant for frontline workers."},{"name":"Snagajob","tier":"niche","why":"80M+ hourly workers."}],
        "defense":   [{"name":"ClearanceJobs","tier":"niche","why":"1M+ cleared candidates."},{"name":"IEEE Spectrum Jobs","tier":"niche","why":"IEEE-verified technical professionals."}],
        "finance":   [{"name":"eFinancialCareers","tier":"niche","why":"The definitive global finance board."}],
    }
    recs += [{"name":"Indeed","tier":"premium","why":"Largest job board by volume."},
             {"name":"LinkedIn","tier":"premium","why":"Primary passive professional talent channel."}]
    recs += IMAP.get(industry, [])
    if "bilingual" in flags:
        recs += [{"name":"Hispanic-Jobs.com","tier":"niche","why":"Dedicated bilingual board."},{"name":"LatPro","tier":"niche","why":"Longest-standing bilingual professionals board."}]
    if "clearance" in flags:
        recs += [{"name":"ClearanceJobs","tier":"niche","why":"1M+ candidates with DoD clearances."}]
    seen, out = set(), []
    for r in recs:
        if r["name"] not in seen: seen.add(r["name"]); out.append(r)
    return out[:12]

# ── Competitive intel ─────────────────────────────────────────────────────────
COMP = {
    "tech":      [("Google","4.3","85%",'"Do cool things that matter"',"Perceived as slow and politically complex post-2024."),("Meta","3.9","72%",'"Move fast"',"Layoffs damaged employer brand significantly."),("Amazon","3.5","63%",'"Day 1 mentality"',"PIP culture drives high attrition.")],
    "healthcare":[("HCA Healthcare","3.6","66%",'"Care of human life"',"Staffing ratios and traveler dependency damage culture."),("CommonSpirit","3.7","68%",'"Healing body, mind, spirit"',"Geographic inconsistency across facilities.")],
    "defense":   [("Lockheed Martin","4.0","73%",'"Your work classified in the best way"',"Slow promotion velocity."),("Northrop Grumman","3.9","69%",'"Defining possible"',"Complex matrix structure."),("Boeing","3.5","60%",'"You just make things possible"',"Safety PR crises create candidate hesitation.")],
    "finance":   [("Goldman Sachs","3.9","72%",'"Progress is everyone\'s business"',"Hours reputation deters younger cohorts."),("JP Morgan","3.8","70%",'"Make your mark"',"Return-to-office mandates accelerated attrition.")],
    "general":   [("Competitor A","3.7","68%",'"Join us"',"No differentiated EVP."),("Competitor B","3.5","63%",'"Great place to work"',"High reliance on Indeed, no niche strategy.")],
}
def _competitive(industry):
    comps = COMP.get(industry, COMP["general"])
    return [{"company":c[0],"rating":c[1],"recommend":c[2],"hook":c[3],"weakness":c[4]} for c in comps]

# ── Ad strategy ───────────────────────────────────────────────────────────────
ADS = {
    "tech":[
        {"platform":"LinkedIn","objective":"Passive talent","format":"Employee story","hook":'"The engineer who built X works here"',"insight":"Employee-led creatives outperform branded ads 3–4× CTR. Use the engineer's actual title, not stock photography."},
        {"platform":"Stack Overflow","objective":"Context-fit","format":"Sidebar display","hook":'"Problems that matter at national scale"',"insight":"Highest signal-to-noise of any tech channel. Engineers see your ad while solving hard problems."},
        {"platform":"Reddit","objective":"Authenticity","format":"Organic AMA","hook":'"What do we actually build here?"',"insight":"An AMA in r/cscareerquestions drives more qualified inbound than paid ads at near-zero cost."},
    ],
    "healthcare":[
        {"platform":"Indeed","objective":"Volume","format":"Sponsored + salary badge","hook":'"$10K sign-on. Benefits day 1. 3×12."',"insight":"Nurses scan three things first: sign-on bonus, schedule, unit type. Lead with all three."},
        {"platform":"Meta","objective":"Passive reach","format":"30s authentic video","hook":'"A nurse explains the unit in their own words"',"insight":"Low-production nurse testimonials consistently outperform polished brand video."},
    ],
    "defense":[
        {"platform":"LinkedIn","objective":"Passive professional","format":"Employee story","hook":'"The system you\'ve heard about. We built it."',"insight":"Cleared candidates are passive and sceptical. Real engineer posts generate more inbound than any ad spend."},
        {"platform":"ClearanceJobs","objective":"Direct sourcing","format":"Sponsored listing","hook":'"Active TS/SCI? Skip the queue."',"insight":"Only board where clearance level is a searchable filter. Highest intent-per-dollar for TS/SCI roles."},
    ],
    "general":[
        {"platform":"Indeed","objective":"Volume","format":"Sponsored listing","hook":"Transparent salary in the headline","insight":"Listings with salary get 3× more applications. Nothing else comes close."},
        {"platform":"LinkedIn","objective":"Professional reach","format":"Single image + Easy Apply","hook":"Answer 'what's in it for me?' in line 1","insight":"LinkedIn Easy Apply reduces drop-off by 60%."},
        {"platform":"Glassdoor","objective":"Trust","format":"Enhanced profile + review responses","hook":"Respond to every review","insight":"Responding to every review increases apply rate by ~18%."},
    ],
}
def _ad_strategy(industry, bilingual=False):
    return ADS.get("bilingual" if bilingual else industry, ADS["general"])

# ── Core builder ──────────────────────────────────────────────────────────────
def build_persona_response(text, source_label, li_signals=None):
    industry    = _detect_industry(text)
    seniority   = _detect_seniority(text)
    skills      = _extract_skills(text)
    salary      = _extract_salary(text)
    location    = _extract_location(text)
    arrangement = _detect_arrangement(text)
    flags       = _detect_flags(text)
    li          = li_signals or {}

    st_q = f"{seniority} {industry} engineer" if industry != "general" else f"{seniority} professional"

    def _st():  return _sparktoro_audience(st_q)
    def _pdl(): return _pdl_search(f"{seniority} {industry}", location, seniority)
    def _lc():  return _lightcast_skills(f"{seniority} {industry} engineer")

    with ThreadPoolExecutor(max_workers=3) as p:
        sf, pf, lf = p.submit(_st), p.submit(_pdl), p.submit(_lc)
        sparktoro, pdl_profiles, lightcast = sf.result(), pf.result(), lf.result()

    pdl_signals = _extract_pdl(pdl_profiles)

    sources = ["text_analysis"]
    if sparktoro:  sources.append("sparktoro")
    if pdl_signals: sources.append("people_data_labs")
    if lightcast:  sources.append("lightcast")
    if li and li.get("source") != "none": sources.append(li.get("source", "linkedin"))

    sig = {
        "industry": industry, "seniority": seniority, "skills": skills,
        "salary": salary, "location": location, "work_arrangement": arrangement,
        **flags,
        "li_industries":       [i.get("name","") for i in li.get("industries",[])[:5]],
        "pdl_prior_employers": pdl_signals.get("typical_prior_employers", []),
        "lightcast_skills":    lightcast.get("top_skills_in_demand", [])[:6],
        "sparktoro_sites":     sparktoro.get("websites", [])[:5],
        "sparktoro_subreddits":sparktoro.get("subreddits", [])[:4],
    }
    persona = _gen_persona(sig)
    flags_list = [k for k, v in flags.items() if v]
    channels = _publishers(sparktoro, industry, flags_list)

    return {
        "source": source_label, "sources_used": sources,
        "itsma_validated": len(sources) >= 3,
        "industry": industry,
        "personas": [{
            **persona, "skills": skills,
            "publishers": [c["name"] for c in channels],
            "attributes": {"seniority": seniority, "work_arrangement": arrangement, "salary": salary, "location": location, **flags},
            "pdl_signals": pdl_signals, "lightcast": lightcast, "sparktoro": sparktoro,
        }],
        "channels": channels,
        "competitive": _competitive(industry),
        "ad_strategy": _ad_strategy(industry, bilingual=flags.get("bilingual", False)),
        "li_signals": li,
        "generated_at": int(time.time()),
    }

def cluster_jobs(jobs):
    clusters = {}
    for job in jobs:
        text = f"{job.get('title','')} {job.get('description','')}"
        key  = f"{_detect_industry(text)}:{_detect_seniority(text)}"
        if key not in clusters:
            clusters[key] = {"industry": _detect_industry(text), "seniority": _detect_seniority(text), "texts": [], "titles": []}
        clusters[key]["texts"].append(text)
        clusters[key]["titles"].append(job.get("title",""))
    result = []
    for c in clusters.values():
        c["combined_text"] = " ".join(c["texts"][:5])[:8000]
        result.append(c)
    return result
