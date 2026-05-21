/**
 * PersonaBuilder.jsx — Nova AI Suite  v3
 * Joveo brand theme: light, Poppins/Inter, Iris #5454BF primary
 */

import { useState, useCallback, useEffect, useRef } from "react";

// ─── Brand tokens ──────────────────────────────────────────────────────────────
const B = {
  iris:       "#5454BF",
  irisLight:  "#DDDBFD",
  irisHover:  "#4444AF",
  moonstone:  "#6BB5CF",
  moonstoneL: "#DFF4FE",
  magenta:    "#B7669E",
  magentaL:   "#FDEFFA",
  orange:     "#D09247",
  orangeL:    "#FFF5E6",
  pennBlue:   "#202058",
  davyGray:   "#575966",
  slateGray:  "#7B7E8C",
  frenchGray: "#ACAFBF",
  platinum:   "#D3D6E1",
  ghostWhite: "#E7E8F0",
  antiFlash:  "#F5F6FA",
  white:      "#FFFDFD",
  success:    "#438765",
  successL:   "#DAF2E5",
  error:      "#D2091D",
  errorL:     "#FFE4E6",
};

// ─── API ───────────────────────────────────────────────────────────────────────
const API_BASE = "";

async function callAPI(endpoint, body) {
  const resp = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ─── Joveo logo SVG ────────────────────────────────────────────────────────────
function JoveoLogo({ height = 28 }) {
  return (
    <svg height={height} viewBox="0 0 647 305" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M286.193 108.445C284.261 108.445 282.466 107.755 281.224 106.375C279.844 104.995 279.292 103.338 279.292 101.406C279.292 99.4736 279.844 97.6792 281.224 96.4369C282.604 95.0566 284.261 94.3665 286.193 94.3665C288.126 94.3665 289.92 95.0566 291.162 96.4369C292.542 97.8172 293.233 99.4736 293.233 101.406C293.233 103.338 292.542 105.133 291.162 106.375C289.782 107.755 288.126 108.445 286.193 108.445ZM291.3 195.404C291.3 200.925 289.92 205.066 287.021 207.688C284.261 210.311 279.982 211.553 274.599 211.553H268.525V202.719H272.942C275.841 202.719 277.911 202.167 279.016 200.925C280.258 199.821 280.81 197.888 280.81 195.128V118.384H291.3V195.404ZM337.954 182.705C332.019 182.705 326.636 181.325 321.805 178.702C317.112 176.08 313.247 172.215 310.486 167.246C307.864 162.277 306.483 156.48 306.483 149.992C306.483 143.505 307.864 137.846 310.624 133.015C313.523 128.046 317.25 124.319 322.081 121.558C326.912 118.798 332.295 117.555 338.368 117.555C344.441 117.555 349.825 118.936 354.656 121.558C359.487 124.181 363.213 127.908 366.112 132.877C369.011 137.846 370.253 143.505 370.253 149.992C370.253 156.48 368.873 162.277 365.836 167.246C362.937 172.215 359.211 175.942 354.242 178.702C349.41 181.325 344.027 182.705 337.954 182.705ZM337.954 173.595C341.819 173.595 345.27 172.629 348.582 170.973C351.895 169.178 354.518 166.556 356.45 163.105C358.52 159.654 359.487 155.237 359.487 150.268C359.487 145.299 358.52 140.882 356.45 137.432C354.518 133.981 351.895 131.22 348.582 129.564C345.408 127.77 341.957 126.941 338.092 126.941C334.227 126.941 330.639 127.908 327.464 129.564C324.289 131.22 321.805 133.843 319.872 137.432C317.94 140.882 316.974 145.299 316.974 150.268C316.974 155.237 317.94 159.654 319.734 163.243C321.667 166.694 324.151 169.454 327.326 171.111C330.5 172.767 333.951 173.595 337.678 173.595H337.954ZM408.901 171.939L428.363 118.522H439.543L414.836 181.739H402.552L377.844 118.522H389.163L408.901 171.939ZM508.972 147.784C508.972 149.716 508.834 151.925 508.558 154.133H458.177C458.592 160.344 460.662 165.175 464.527 168.764C468.392 172.215 473.085 173.871 478.744 173.871C484.403 173.871 487.025 172.905 490.062 170.835C493.099 168.626 495.307 165.866 496.55 162.277H507.868C506.212 168.35 502.899 173.319 497.654 177.184C492.685 181.049 486.335 182.843 478.744 182.843C471.152 182.843 467.425 181.463 462.594 178.84C458.039 176.218 454.313 172.353 451.552 167.384C448.929 162.415 447.549 156.618 447.549 150.13C447.549 143.643 448.929 137.846 451.414 133.015C454.037 128.046 457.625 124.457 462.318 121.696C467.011 119.074 472.533 117.693 478.606 117.693C484.679 117.693 489.924 119.074 494.479 121.558C499.034 124.181 502.623 127.77 505.107 132.325C507.73 136.879 508.972 141.987 508.972 147.784ZM498.068 145.575C498.068 141.572 497.102 138.122 495.445 135.361C493.651 132.463 491.304 130.254 488.13 128.736C485.093 127.217 481.78 126.527 478.192 126.527C472.947 126.527 468.392 128.184 464.665 131.496C460.938 134.947 458.868 139.502 458.315 145.575H498.206H498.068ZM551.623 182.705C545.688 182.705 540.305 181.325 535.474 178.702C530.781 176.08 526.916 172.215 524.155 167.246C521.533 162.277 520.153 156.48 520.153 149.992C520.153 143.505 521.533 137.846 524.293 133.015C527.192 128.046 530.919 124.319 535.75 121.558C540.581 118.936 545.964 117.555 552.037 117.555C558.111 117.555 563.494 118.936 568.325 121.558C573.156 124.181 576.882 127.908 579.781 132.877C582.68 137.846 584.06 143.505 584.06 149.992C584.06 156.48 582.68 162.277 579.643 167.246C576.744 172.215 573.018 175.942 568.049 178.702C563.08 181.325 557.834 182.705 551.761 182.705H551.623ZM551.623 173.595C555.488 173.595 558.939 172.629 562.251 170.973C565.564 169.178 568.187 166.556 570.119 163.105C572.189 159.654 573.156 155.237 573.156 150.268C573.156 145.299 572.189 140.882 570.119 137.432C568.187 133.981 565.564 131.22 562.251 129.564C559.077 127.77 555.626 126.941 551.761 126.941C547.896 126.941 544.308 127.908 541.133 129.564C537.958 131.22 535.474 133.843 533.541 137.432C531.609 141.02 530.643 145.299 530.643 150.268C530.643 155.237 531.609 159.654 533.403 163.243C535.336 166.694 537.82 169.454 540.995 171.111C544.032 172.767 547.62 173.595 551.347 173.595H551.623Z" fill={B.pennBlue}/>
      <path d="M97.5 89.84C103.99 89.84 109.23 95.09 109.23 101.57C109.23 108.05 103.98 113.3 97.5 113.3C91.02 113.3 85.77 108.05 85.77 101.57C85.77 95.09 91.02 89.84 97.5 89.84Z" fill={B.moonstone}/>
      <path d="M204.5 89.84C210.99 89.84 216.23 95.09 216.23 101.57C216.23 108.05 210.99 113.3 204.5 113.3C198.01 113.3 192.77 108.05 192.77 101.57C192.77 95.09 198.01 89.84 204.5 89.84Z" fill={B.magenta}/>
      <path d="M97.57 192.64C104.06 192.64 109.3 197.88 109.3 204.37C109.3 210.86 104.05 216.1 97.57 216.1C91.09 216.1 85.84 210.85 85.84 204.37C85.84 197.89 91.09 192.64 97.57 192.64Z" fill={B.orange}/>
      <path d="M204.5 192.64C210.99 192.64 216.23 197.88 216.23 204.37C216.23 210.86 210.99 216.1 204.5 216.1C198.01 216.1 192.77 210.85 192.77 204.37C192.77 197.89 198.01 192.64 204.5 192.64Z" fill={B.iris}/>
      <path d="M125 158H68C65.24 158 63 155.76 63 153C63 150.24 65.24 148 68 148H125C136.58 148 146 138.58 146 127V70C146 67.24 148.24 65 151 65C153.76 65 156 67.24 156 70V127C156 144.09 142.09 158 125 158Z" fill={B.moonstone}/>
      <path d="M151.04 241C148.28 241 146.04 238.76 146.04 236V179C146.04 161.91 159.95 148 177.04 148H234.04C236.8 148 239.04 150.24 239.04 153C239.04 155.76 236.8 158 234.04 158H177.04C165.46 158 156.04 167.42 156.04 179V236C156.04 238.76 153.8 241 151.04 241Z" fill={B.iris}/>
      <path d="M119.5 136.45H75.5C72.74 136.45 70.5 134.21 70.5 131.45C70.5 128.69 72.74 126.45 75.5 126.45H119.5C122.26 126.45 124.5 124.21 124.5 121.45V77.45C124.5 74.69 126.74 72.45 129.5 72.45C132.26 72.45 134.5 74.69 134.5 77.45V121.45C134.5 129.72 127.77 136.45 119.5 136.45Z" fill={B.moonstone}/>
      <path d="M172.5 233.5C169.74 233.5 167.5 231.26 167.5 228.5V184.5C167.5 176.23 174.23 169.5 182.5 169.5H226.5C229.26 169.5 231.5 171.74 231.5 174.5C231.5 177.26 229.26 179.5 226.5 179.5H182.5C179.74 179.5 177.5 181.74 177.5 184.5V228.5C177.5 231.26 175.26 233.5 172.5 233.5Z" fill={B.iris}/>
      <path d="M129.5 233.5C126.74 233.5 124.5 231.26 124.5 228.5V184.5C124.5 181.74 122.26 179.5 119.5 179.5H75.5C72.74 179.5 70.5 177.26 70.5 174.5C70.5 171.74 72.74 169.5 75.5 169.5H119.5C127.77 169.5 134.5 176.23 134.5 184.5V228.5C134.5 231.26 132.26 233.5 129.5 233.5Z" fill={B.orange}/>
      <path d="M226.5 136.45H182.5C174.23 136.45 167.5 129.72 167.5 121.45V77.45C167.5 74.69 169.74 72.45 172.5 72.45C175.26 72.45 177.5 74.69 177.5 77.45V121.45C177.5 124.21 179.74 126.45 182.5 126.45H226.5C229.26 126.45 231.5 128.69 231.5 131.45C231.5 134.21 229.26 136.45 226.5 136.45Z" fill={B.magenta}/>
    </svg>
  );
}

// ─── Demo data ─────────────────────────────────────────────────────────────────
const DEMO_DATA = {
  source: "job_description",
  sources_used: ["text_analysis", "people_data_labs", "sparktoro", "lightcast"],
  itsma_validated: true,
  industry: "defense",
  company_name: "RTX · Missile Defense Systems",
  jd_quality: {
    score: 6.2, max_score: 10.0, grade: "C",
    issues: [
      "No salary range — listings with salary get 3× more applicants (Indeed, 2024)",
      "Work arrangement not stated — cleared candidates filter by location before reading anything else",
      "Benefits not mentioned — 68% of candidates say benefits significantly influence their decision",
    ],
    strengths: [
      "Clearance requirement clearly stated (high self-qualification signal)",
      "Good technical specificity — DO-178C, VxWorks, MBSE all named",
      "Mission/impact clearly articulated",
    ],
    word_count: 387,
  },
  personas: [{
    name: "The Guardian",
    role: "Senior Embedded Software Engineer — Missile Defense",
    profile: "35–48 · Senior/Staff · Currently at Northrop Grumman, L3Harris, or SAIC · Active TS/SCI",
    core_job: "Build safety-critical systems whose failure modes are measured in geopolitical consequences, not user complaints.",
    context_trigger: "Current classified program winding down or becoming technically stale — clearance intact, motivation lagging.",
    functional_goals: [
      "Maintain active TS/SCI on a funded, long-horizon program",
      "Work on novel embedded RTOS problems (VxWorks, LynxOS) at DO-178C DAL A",
      "Compensation with defense-weighted benefits: clearance maintenance, pension, strong 401K",
    ],
    emotional_goals: [
      "Feel that their work has consequence at national scale — not just a P&L line",
      "Feel trusted with hard problems, not process-managed into mediocrity",
    ],
    concern: "Losing clearance continuity or landing on a dead-end program with no real technical growth.",
    acquisition_trigger: "A real staff engineer posting an unclassified technical detail about a system they shipped.",
    primary_message: '"The problem you\'re cleared to know about — we\'re building the solution."',
    background: "15 years in defense electronics. Has shipped DO-178C-certified flight software. Passive — will not respond to cold LinkedIn spam. Reachable only through technical credibility signals.",
    disc_type: "C",
    disc_implication: "Lead with technical depth and verifiable evidence. Name the RTOS, the certification standard, the architecture. They will self-qualify if the bar is visible.",
    job_quality_issues: [
      "No salary range deters this persona — they benchmark against Northrop and L3Harris ranges on ClearanceJobs",
      "No mention of clearance maintenance benefit — table-stakes for TS/SCI talent",
    ],
    color: B.iris,
    skills: ["C/C++", "VxWorks", "DO-178C", "MBSE", "SysML", "MATLAB", "Simulink", "MIL-STD-882", "LynxOS"],
    publishers: ["Joveo Programmatic", "ClearanceJobs", "LinkedIn", "DEF CON / Embedded World", "IEEE Spectrum Jobs"],
    attributes: { seniority: "senior", work_arrangement: "On-site", salary: "$140,000–$180,000", location: "Tucson, AZ", clearance: true },
    pdl_signals: {
      typical_prior_employers: ["Northrop Grumman", "L3Harris", "Raytheon", "SAIC", "General Dynamics"],
      typical_schools: ["Georgia Tech", "MIT", "Purdue", "University of Arizona", "Carnegie Mellon"],
      avg_tenure_years: 4.2, sample_size: 18,
    },
    sparktoro: {
      websites: ["clearancejobs.com", "embeddedrelated.com", "defenseone.com", "aviationweek.com", "janes.com"],
      subreddits: ["embedded", "cscareerquestions", "defense", "military"],
      podcasts: ["Defense One Radio", "Embedded FM", "The Aerospace Engineer Podcast"],
    },
    lightcast: { top_skills_in_demand: ["Embedded C/C++", "VxWorks", "DO-178C", "Systems Engineering", "MBSE", "SysML", "MATLAB", "Simulink"], source: "lightcast" },
    messaging_variants: [
      { label: "Technical depth (C-type primary)", headline: "DO-178C. VxWorks 7. Real MBSE. Not the buzzword kind.", body: "Our missile defense stack is DO-178C DAL A certified. We run VxWorks 7 with full ARINC 653 partitioning, MBSE built on Cameo, and architecture reviews before — not after — first commit.", cta: "Read the technical brief →" },
      { label: "Mission/consequence (C-type alt)", headline: "We built the system protecting six allied cities. Join the team.", body: "Three different classified RTOS platforms. DO-178C Level A certification completed last year. Next-gen guidance subsystem on rack testing Q3. We need your hands on it.", cta: "Active TS/SCI? Apply directly →" },
      { label: "Transparency/process (C-type alt 2)", headline: "Exact role. Real salary. Clear year-one expectations.", body: "Year 1: DO-178C module ownership. Year 2: architecture lead. Salary: $140K–$180K DOE. 3-round interview, decision in 5 business days. No surprises.", cta: "See the full spec on ClearanceJobs →" },
    ],
  }],
  channels: [
    { name: "Joveo Programmatic", tier: "platform", why: "Distributes across 7,053 publishers with real-time CPA optimisation. Baseline reach layer for all roles.", budget_pct: 30, color: B.iris },
    { name: "ClearanceJobs", tier: "niche", why: "1M+ candidates with active DoD clearances. Only board where clearance is a searchable filter — highest intent-per-dollar for TS/SCI.", budget_pct: 35, color: B.success },
    { name: "LinkedIn", tier: "premium", why: "Primary passive professional channel. Employee story creative outperforms branded job ads 3–4× CTR.", budget_pct: 20, color: B.moonstone },
    { name: "DEF CON / Embedded World", tier: "niche", why: "Technical persona discovers employers through demonstrated expertise. Sponsored talk reaches exactly the right people.", budget_pct: 10, color: B.success },
    { name: "IEEE Spectrum Jobs", tier: "niche", why: "IEEE-verified technical professionals across engineering disciplines.", budget_pct: 5, color: B.success },
  ],
  competitive: [
    { company: "Northrop Grumman", rating: "4.0", recommend: "73%", hook: '"Defining possible"', weakness: "Slow promotion velocity and matrix org complexity reduce individual visibility." },
    { company: "L3Harris", rating: "3.7", recommend: "62%", hook: '"Mission critical"', weakness: "Lower brand recognition vs. Raytheon among STEM graduates. Mid-tier compensation." },
    { company: "Boeing", rating: "3.5", recommend: "60%", hook: '"You just make things possible"', weakness: "Safety and culture PR damage (737 MAX) creates significant candidate hesitation in 2025–26." },
    { company: "Lockheed Martin", rating: "4.0", recommend: "73%", hook: '"Your work classified in the best way"', weakness: "Slow promotion velocity. Long-horizon programs make individual contributions harder to attribute." },
  ],
  ad_strategy: [
    { platform: "ClearanceJobs", objective: "Direct sourcing", format: "Sponsored listing", hook: '"Active TS/SCI? Skip the queue."', insight: "The only board where clearance level is a searchable filter. Target $800–$1,200/month against 8–12 qualified applicants." },
    { platform: "LinkedIn", objective: "Passive professional", format: "Employee story — unclassified project fragment", hook: '"The system you\'ve heard about. We built it."', insight: "Cleared candidates are passive and sceptical of branded ads. A real engineer posting about a specific challenge generates more inbound than equivalent ad spend." },
    { platform: "DEF CON / Embedded World", objective: "Technical credibility", format: "Talk sponsorship + booth", hook: '"Come see what we\'re actually defending."', insight: "A sponsored talk (est. $8–15K) costs less than 3 months of LinkedIn CPC and reaches exactly the right density of TS/SCI embedded engineers." },
  ],
  li_signals: null,
  generated_at: Math.floor(Date.now() / 1000),
};

// ─── Utilities ─────────────────────────────────────────────────────────────────
function useCopy(timeout = 2000) {
  const [copied, setCopied] = useState(null);
  const copy = useCallback((text, id = "default") => {
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopied(id);
    setTimeout(() => setCopied(null), timeout);
  }, [timeout]);
  return [copied, copy];
}

// ─── Sub-components ────────────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return (
    <p style={{ color: B.slateGray }} className="text-[10px] font-semibold uppercase tracking-widest mb-2">
      {children}
    </p>
  );
}

function Badge({ children, variant = "default" }) {
  const styles = {
    default:   { background: B.ghostWhite,   color: B.davyGray,   border: `1px solid ${B.platinum}` },
    iris:      { background: B.irisLight,    color: B.iris,       border: `1px solid ${B.iris}40` },
    moonstone: { background: B.moonstoneL,   color: "#4a8fa8",    border: `1px solid ${B.moonstone}50` },
    magenta:   { background: B.magentaL,     color: B.magenta,    border: `1px solid ${B.magenta}50` },
    orange:    { background: B.orangeL,      color: B.orange,     border: `1px solid ${B.orange}50` },
    success:   { background: B.successL,     color: B.success,    border: `1px solid ${B.success}50` },
    error:     { background: B.errorL,       color: B.error,      border: `1px solid ${B.error}30` },
  };
  const s = styles[variant] || styles.default;
  return (
    <span style={s} className="inline-block text-[10px] px-2 py-0.5 rounded-full font-medium">
      {children}
    </span>
  );
}

function AttrRow({ label, value }) {
  return (
    <div style={{ borderColor: B.ghostWhite }} className="flex justify-between items-start py-1.5 border-b last:border-0 gap-4">
      <span style={{ color: B.slateGray }} className="text-xs flex-shrink-0">{label}</span>
      <span style={{ color: B.pennBlue }} className="text-xs text-right leading-relaxed">{value}</span>
    </div>
  );
}

function CopyButton({ text, id }) {
  const [copied, copy] = useCopy();
  return (
    <button
      onClick={() => copy(text, id)}
      style={{
        border: `1px solid ${B.platinum}`,
        color: copied === id ? B.success : B.slateGray,
        background: copied === id ? B.successL : "transparent",
      }}
      className="text-[10px] px-2 py-1 rounded-md transition-all hover:opacity-80"
    >
      {copied === id ? "✓ Copied" : "Copy"}
    </button>
  );
}

function PersonaChip({ persona, active, onClick }) {
  const avatarLetter = (persona.name || "P").split(/\s+/).filter(Boolean).slice(-1)[0]?.[0]?.toUpperCase() || "P";
  return (
    <button
      onClick={onClick}
      style={{
        border: active ? `1.5px solid ${B.iris}` : `1px solid ${B.platinum}`,
        background: active ? B.irisLight : B.white,
      }}
      className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left transition-all"
    >
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
        style={{ background: (persona.color || B.iris) + "20", border: `1.5px solid ${persona.color || B.iris}50`, color: persona.color || B.iris }}
      >
        {avatarLetter}
      </div>
      <div className="min-w-0">
        <p style={{ color: B.pennBlue }} className="text-sm font-semibold truncate">{persona.name}</p>
        <p style={{ color: B.slateGray }} className="text-[10px] truncate">{persona.role}</p>
      </div>
    </button>
  );
}

function SourceConfidenceBadge({ sources }) {
  const map = {
    text_analysis:    { label: "JD analysis",  variant: "default" },
    sparktoro:        { label: "SparkToro",     variant: "moonstone" },
    people_data_labs: { label: "PDL",           variant: "iris" },
    lightcast:        { label: "Lightcast",     variant: "orange" },
    bright_data:      { label: "Bright Data",   variant: "success" },
    linkedin:         { label: "LinkedIn",      variant: "moonstone" },
    apify:            { label: "Apify",         variant: "default" },
  };
  return (
    <div className="flex flex-wrap gap-1.5 items-center">
      <span style={{ color: B.frenchGray }} className="text-[10px]">Sources:</span>
      {(sources || []).map((s) => {
        const m = map[s] || { label: s, variant: "default" };
        return <Badge key={s} variant={m.variant}>{m.label}</Badge>;
      })}
    </div>
  );
}

function JdQualityCard({ quality }) {
  if (!quality) return null;
  const { score, max_score, grade, issues, strengths, word_count } = quality;
  const pct = Math.round((score / max_score) * 100);
  const gradeColor = { A: B.success, B: "#84cc16", C: B.orange, D: "#f97316", F: B.error }[grade] || B.iris;

  return (
    <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-5 mb-5 shadow-sm">
      <div className="flex items-center gap-5 mb-4">
        <div>
          <SectionLabel>JD Quality Score</SectionLabel>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-bold" style={{ color: gradeColor }}>{score}</span>
            <span style={{ color: B.frenchGray }} className="text-sm mb-1">/ {max_score}</span>
            <div className="ml-1 px-2.5 py-0.5 rounded-lg text-sm font-bold" style={{ background: gradeColor + "18", color: gradeColor }}>
              {grade}
            </div>
          </div>
          <p style={{ color: B.frenchGray }} className="text-[10px] mt-0.5">{word_count} words</p>
        </div>
        <div className="flex-1">
          <div style={{ background: B.ghostWhite }} className="h-2 rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: gradeColor }} />
          </div>
          <div className="flex justify-between text-[9px] mt-1" style={{ color: B.frenchGray }}>
            <span>0</span><span>5</span><span>10</span>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {issues?.length > 0 && (
          <div>
            <p style={{ color: B.error }} className="text-[10px] uppercase tracking-wide font-semibold mb-2">Issues to fix</p>
            <ul className="space-y-2">
              {issues.map((issue, i) => (
                <li key={i} className="flex gap-1.5 items-start">
                  <span style={{ color: B.error }} className="text-xs mt-0.5 flex-shrink-0">↑</span>
                  <span style={{ color: B.davyGray }} className="text-xs leading-relaxed">{issue}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {strengths?.length > 0 && (
          <div>
            <p style={{ color: B.success }} className="text-[10px] uppercase tracking-wide font-semibold mb-2">Strengths</p>
            <ul className="space-y-2">
              {strengths.map((s, i) => (
                <li key={i} className="flex gap-1.5 items-start">
                  <span style={{ color: B.success }} className="text-xs mt-0.5 flex-shrink-0">✓</span>
                  <span style={{ color: B.davyGray }} className="text-xs leading-relaxed">{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function PersonaDetail({ persona }) {
  const [copied, copy] = useCopy();
  if (!persona) return null;
  const p = persona;
  const avatarLetter = (p.name || "P").split(/\s+/).filter(Boolean).slice(-1)[0]?.[0]?.toUpperCase() || "P";
  const discColors = { D: "#ef4444", I: B.orange, S: B.success, C: B.iris };
  const discColor = discColors[p.disc_type] || B.iris;

  return (
    <div className="space-y-3">
      {/* Identity */}
      <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-5 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
            style={{ background: (p.color || B.iris) + "18", border: `2px solid ${p.color || B.iris}40`, color: p.color || B.iris }}>
            {avatarLetter}
          </div>
          <div className="flex-1 min-w-0">
            <p style={{ color: B.pennBlue }} className="text-base font-semibold">{p.name}</p>
            <p style={{ color: B.slateGray }} className="text-xs truncate">{p.role}</p>
          </div>
          {p.disc_type && (
            <div className="flex flex-col items-center px-3 py-1.5 rounded-xl flex-shrink-0"
              style={{ background: discColor + "12", border: `1px solid ${discColor}30` }}>
              <span className="text-lg font-bold" style={{ color: discColor }}>{p.disc_type}</span>
              <span style={{ color: B.frenchGray }} className="text-[9px] uppercase tracking-wide">DISC</span>
            </div>
          )}
        </div>

        <AttrRow label="Profile" value={p.profile} />
        <AttrRow label="Background" value={p.background} />

        <div className="mt-3 pt-3" style={{ borderTop: `1px solid ${B.ghostWhite}` }}>
          <p style={{ color: B.frenchGray }} className="text-[10px] uppercase tracking-widest mb-2">Jobs-to-be-Done</p>
          {p.core_job && <AttrRow label="Core job" value={p.core_job} />}
          {p.context_trigger && <AttrRow label="Context trigger" value={p.context_trigger} />}
          {p.functional_goals?.length > 0 && (
            <div className="py-1.5" style={{ borderBottom: `1px solid ${B.ghostWhite}` }}>
              <p style={{ color: B.slateGray }} className="text-xs mb-1">Functional goals</p>
              <ul className="space-y-1">
                {p.functional_goals.map((g, i) => (
                  <li key={i} className="text-xs flex gap-1.5 items-start" style={{ color: B.pennBlue }}>
                    <span style={{ color: B.iris }} className="mt-0.5 flex-shrink-0">›</span>{g}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {p.emotional_goals?.length > 0 && (
            <div className="py-1.5" style={{ borderBottom: `1px solid ${B.ghostWhite}` }}>
              <p style={{ color: B.slateGray }} className="text-xs mb-1">Emotional goals</p>
              <ul className="space-y-1">
                {p.emotional_goals.map((g, i) => (
                  <li key={i} className="text-xs flex gap-1.5 items-start" style={{ color: B.pennBlue }}>
                    <span style={{ color: B.success }} className="mt-0.5 flex-shrink-0">›</span>{g}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <AttrRow label="Main concern" value={p.concern} />
        <AttrRow label="Acquisition trigger" value={p.acquisition_trigger} />

        {p.disc_implication && (
          <div className="mt-3 px-3 py-2 rounded-xl text-xs" style={{ color: B.davyGray, background: discColor + "08", borderLeft: `3px solid ${discColor}` }}>
            <span className="font-semibold" style={{ color: discColor }}>Outreach ({p.disc_type}-type): </span>
            {p.disc_implication}
          </div>
        )}

        <div className="mt-3 pt-3" style={{ borderTop: `1px solid ${B.ghostWhite}` }}>
          <div className="flex items-center justify-between mb-2">
            <p style={{ color: B.slateGray }} className="text-xs">Primary message</p>
            <CopyButton text={p.primary_message || ""} id="primary_msg" />
          </div>
          <div className="text-sm italic leading-relaxed px-3 py-2.5 rounded-r-xl" style={{ color: B.davyGray, borderLeft: `3px solid ${p.color || B.iris}`, background: (p.color || B.iris) + "08" }}>
            {p.primary_message}
          </div>
        </div>

        {p.skills?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {p.skills.map((s) => <Badge key={s} variant="iris">{s}</Badge>)}
          </div>
        )}

        {p.attributes && (
          <div className="mt-3 pt-3 grid grid-cols-2 gap-1" style={{ borderTop: `1px solid ${B.ghostWhite}` }}>
            {Object.entries(p.attributes).filter(([, v]) => v && v !== false && v !== "Not specified").map(([k, v]) => (
              <div key={k} className="text-[10px]">
                <span style={{ color: B.slateGray }}>{k.replace(/_/g, " ")}: </span>
                <span style={{ color: B.pennBlue }} className="font-medium">{String(v)}</span>
              </div>
            ))}
          </div>
        )}

        {p.job_quality_issues?.length > 0 && (
          <div className="mt-3 pt-3" style={{ borderTop: `1px solid ${B.ghostWhite}` }}>
            <p style={{ color: B.error }} className="text-[10px] uppercase tracking-wide font-semibold mb-1.5">JD issues for this persona</p>
            {p.job_quality_issues.map((issue, i) => (
              <p key={i} style={{ color: B.davyGray }} className="text-xs flex gap-1.5 items-start mb-1">
                <span style={{ color: B.error }} className="flex-shrink-0">↑</span>{issue}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* SparkToro */}
      {(p.sparktoro?.websites?.length > 0 || p.sparktoro?.subreddits?.length > 0) && (
        <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>SparkToro — audience intelligence</SectionLabel>
            <Badge variant="moonstone">Live data</Badge>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {p.sparktoro.websites?.length > 0 && (
              <div>
                <p style={{ color: B.frenchGray }} className="text-[10px] mb-1.5">Top websites</p>
                {p.sparktoro.websites.slice(0, 5).map((s, i) => (
                  <p key={i} style={{ color: B.davyGray }} className="text-xs py-0.5 font-mono">{s}</p>
                ))}
              </div>
            )}
            <div>
              {p.sparktoro.subreddits?.length > 0 && (
                <>
                  <p style={{ color: B.frenchGray }} className="text-[10px] mb-1.5">Subreddits</p>
                  {p.sparktoro.subreddits.slice(0, 4).map((s, i) => (
                    <p key={i} style={{ color: B.davyGray }} className="text-xs py-0.5">r/{s}</p>
                  ))}
                </>
              )}
              {p.sparktoro.podcasts?.length > 0 && (
                <>
                  <p style={{ color: B.frenchGray }} className="text-[10px] mt-2 mb-1.5">Podcasts</p>
                  {p.sparktoro.podcasts.slice(0, 3).map((s, i) => (
                    <p key={i} style={{ color: B.davyGray }} className="text-xs py-0.5">{s}</p>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PDL */}
      {p.pdl_signals?.typical_prior_employers?.length > 0 && (
        <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>PDL — career trajectory signals</SectionLabel>
            <Badge variant="iris">1.5B profiles</Badge>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p style={{ color: B.frenchGray }} className="text-[10px] mb-1.5">Typical prior employers</p>
              {p.pdl_signals.typical_prior_employers.map((co, i) => (
                <p key={i} style={{ color: B.davyGray }} className="text-xs py-0.5">{co}</p>
              ))}
            </div>
            <div>
              {p.pdl_signals.typical_schools?.length > 0 && (
                <>
                  <p style={{ color: B.frenchGray }} className="text-[10px] mb-1.5">Typical schools</p>
                  {p.pdl_signals.typical_schools.slice(0, 4).map((s, i) => (
                    <p key={i} style={{ color: B.davyGray }} className="text-xs py-0.5">{s}</p>
                  ))}
                </>
              )}
              {p.pdl_signals.avg_tenure_years && (
                <p style={{ color: B.slateGray }} className="text-xs mt-2">
                  Avg tenure: <span style={{ color: B.pennBlue }} className="font-semibold">{p.pdl_signals.avg_tenure_years}y</span>
                  {p.pdl_signals.sample_size && <span style={{ color: B.frenchGray }} className="ml-1">(n={p.pdl_signals.sample_size})</span>}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Lightcast */}
      {p.lightcast?.top_skills_in_demand?.length > 0 && (
        <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>Lightcast — market demand</SectionLabel>
            <Badge variant="orange">2.5B postings</Badge>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {p.lightcast.top_skills_in_demand.map((s, i) => <Badge key={i} variant="orange">{s}</Badge>)}
          </div>
        </div>
      )}
    </div>
  );
}

function MessagingTab({ personas }) {
  const [copied, copy] = useCopy();
  const allVariants = (personas || []).flatMap((p) =>
    (p.messaging_variants || []).map((v) => ({ ...v, personaName: p.name, personaColor: p.color, disc: p.disc_type }))
  );

  if (!allVariants.length) {
    return (
      <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-8 text-center">
        <p style={{ color: B.slateGray }} className="text-sm">No messaging variants available for this result.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div style={{ background: B.irisLight, border: `1px solid ${B.iris}30` }} className="rounded-2xl p-4">
        <SectionLabel>Messaging Playbook</SectionLabel>
        <p style={{ color: B.davyGray }} className="text-xs leading-relaxed">
          3 DISC-calibrated ad copy variants per persona — each tuned to a different personality type. Copy any variant directly into LinkedIn Campaign Manager, ClearanceJobs, or your ATS email template.
        </p>
      </div>
      {allVariants.map((v, i) => {
        const copyId = `variant_${i}`;
        const fullText = `${v.headline}\n\n${v.body}\n\n${v.cta}`;
        return (
          <div key={i} style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: v.personaColor || B.iris }} />
                <span style={{ color: B.slateGray }} className="text-[10px]">{v.personaName}</span>
                <Badge variant="default">{v.label}</Badge>
              </div>
              <button
                onClick={() => copy(fullText, copyId)}
                style={{
                  border: `1px solid ${copied === copyId ? B.success : B.platinum}`,
                  color: copied === copyId ? B.success : B.slateGray,
                  background: copied === copyId ? B.successL : "transparent",
                }}
                className="text-xs px-3 py-1 rounded-lg transition-all"
              >
                {copied === copyId ? "✓ Copied" : "Copy all"}
              </button>
            </div>

            <div className="mb-3">
              <p style={{ color: B.frenchGray }} className="text-[10px] uppercase tracking-wide mb-1">Headline</p>
              <div className="flex items-start justify-between gap-2">
                <p style={{ color: B.pennBlue }} className="text-sm font-bold leading-snug flex-1">{v.headline}</p>
                <CopyButton text={v.headline} id={`h_${i}`} />
              </div>
            </div>
            <div className="mb-3">
              <p style={{ color: B.frenchGray }} className="text-[10px] uppercase tracking-wide mb-1">Body</p>
              <div className="flex items-start justify-between gap-2">
                <p style={{ color: B.davyGray }} className="text-xs leading-relaxed flex-1">{v.body}</p>
                <CopyButton text={v.body} id={`b_${i}`} />
              </div>
            </div>
            <div>
              <p style={{ color: B.frenchGray }} className="text-[10px] uppercase tracking-wide mb-1">CTA</p>
              <div className="flex items-center justify-between gap-2">
                <p style={{ color: B.iris }} className="text-xs font-semibold">{v.cta}</p>
                <CopyButton text={v.cta} id={`c_${i}`} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ChannelsTab({ channels }) {
  const totalBudgetPct = (channels || []).filter((c) => c.budget_pct).reduce((s, c) => s + c.budget_pct, 0);
  const hasBudget = totalBudgetPct > 0;
  const tierVariant = { premium: "iris", niche: "success", platform: "moonstone" };

  return (
    <div className="space-y-4">
      <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-4 shadow-sm">
        <SectionLabel>Niche & specialty publisher recommendations</SectionLabel>
        <div style={{ divideColor: B.ghostWhite }} className="divide-y">
          {(channels || []).map((ch, i) => (
            <div key={i} className="py-3 flex gap-3" style={{ borderColor: B.ghostWhite }}>
              <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: ch.color || B.iris }} />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                  <span style={{ color: B.pennBlue }} className="text-sm font-semibold">{ch.name}</span>
                  <Badge variant={tierVariant[ch.tier] || "default"}>{ch.tier}</Badge>
                </div>
                {ch.why && <p style={{ color: B.davyGray }} className="text-xs leading-relaxed">{ch.why}</p>}
              </div>
              {hasBudget && ch.budget_pct && (
                <div className="flex-shrink-0 text-right">
                  <p style={{ color: B.pennBlue }} className="text-sm font-bold">{ch.budget_pct}%</p>
                  <p style={{ color: B.frenchGray }} className="text-[10px]">of budget</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {hasBudget && (
        <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-4 shadow-sm">
          <SectionLabel>Budget allocation guide</SectionLabel>
          <div className="space-y-3">
            {channels.filter((c) => c.budget_pct).map((ch, i) => (
              <div key={i}>
                <div className="flex justify-between text-xs mb-1">
                  <span style={{ color: B.pennBlue }}>{ch.name}</span>
                  <span style={{ color: B.slateGray }}>{ch.budget_pct}%</span>
                </div>
                <div style={{ background: B.ghostWhite }} className="h-2 rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${ch.budget_pct}%`, background: ch.color || B.iris }} />
                </div>
              </div>
            ))}
          </div>
          <p style={{ color: B.frenchGray }} className="text-[10px] mt-3">Allocation based on intent-per-dollar analysis. Adjust based on your CPL targets.</p>
        </div>
      )}

      <p style={{ color: B.frenchGray }} className="text-[10px] text-center">Matched from Nova supply repository · 7,053 global publishers</p>
    </div>
  );
}

function CompetitiveTab({ competitors }) {
  return (
    <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-4 shadow-sm">
      <SectionLabel>Competitive landscape</SectionLabel>
      <div className="grid grid-cols-2 gap-3">
        {(competitors || []).map((c, i) => (
          <div key={i} style={{ background: B.antiFlash, border: `1px solid ${B.platinum}` }} className="rounded-xl p-3">
            <p style={{ color: B.pennBlue }} className="text-sm font-semibold mb-2">{c.company}</p>
            <AttrRow label="Glassdoor" value={`${c.rating}/5`} />
            <AttrRow label="% Recommend" value={c.recommend} />
            <p style={{ color: B.slateGray }} className="text-xs italic mt-2 mb-1">{c.hook}</p>
            <p style={{ color: B.error }} className="text-xs leading-relaxed">{c.weakness}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AdStratTab({ strategy }) {
  return (
    <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-4 shadow-sm">
      <SectionLabel>Ad strategy recommendations</SectionLabel>
      <div className="divide-y" style={{ borderColor: B.ghostWhite }}>
        {(strategy || []).map((s, i) => (
          <div key={i} className="py-3" style={{ borderColor: B.ghostWhite }}>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span style={{ color: B.pennBlue }} className="text-sm font-semibold">{s.platform}</span>
              <Badge variant="default">{s.objective}</Badge>
              <Badge variant="default">{s.format}</Badge>
            </div>
            <div className="text-xs italic px-3 py-1.5 rounded-lg mb-2" style={{ color: B.davyGray, background: B.irisLight }}>
              {s.hook}
            </div>
            <p style={{ color: B.davyGray }} className="text-xs leading-relaxed">{s.insight}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function LinkedInSignals({ signals }) {
  if (!signals || (!signals.industries?.length && !signals.colleges?.length)) return null;
  return (
    <div className="grid grid-cols-3 gap-3 mb-4">
      {[
        { title: "Top industries", items: signals.industries?.slice(0, 6), barColor: B.iris },
        { title: "Top schools", items: signals.colleges?.slice(0, 7), barColor: B.success },
      ].map((sec) => sec.items?.length > 0 && (
        <div key={sec.title} style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-3 shadow-sm">
          <SectionLabel>{sec.title}</SectionLabel>
          {sec.items.map((item, i) => (
            <div key={i} className="mb-2">
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: B.davyGray }}>{item.name}</span>
                <span style={{ color: B.slateGray }}>{item.pct}%</span>
              </div>
              <div style={{ background: B.ghostWhite }} className="h-1.5 rounded overflow-hidden">
                <div className="h-full rounded" style={{ width: `${Math.min(item.pct * 2, 100)}%`, background: sec.barColor }} />
              </div>
            </div>
          ))}
        </div>
      ))}
      <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-3 shadow-sm">
        <SectionLabel>Company signals</SectionLabel>
        {signals.headcount && <AttrRow label="Headcount" value={signals.headcount} />}
        {signals.growth && <AttrRow label="Growth" value={signals.growth} />}
        {signals.skills?.length > 0 && (
          <div className="mt-2">
            <p style={{ color: B.frenchGray }} className="text-[10px] mb-1">Top skills</p>
            <div className="flex flex-wrap gap-1">
              {signals.skills.slice(0, 8).map((s) => <Badge key={s} variant="default">{s}</Badge>)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Export ────────────────────────────────────────────────────────────────────
function exportHtmlReport(result) {
  if (!result) return;
  const p = result.personas?.[0];
  const ts = new Date().toLocaleString();
  const html = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Nova Persona Report — ${result.company_name || "Persona"}</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{font-family:'Poppins',system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 24px;color:#202058;background:#F5F6FA;line-height:1.6}
h1{font-size:24px;font-weight:700;color:#202058;margin-bottom:4px}h2{font-size:16px;font-weight:600;margin:32px 0 8px;color:#5454BF;border-bottom:1px solid #D3D6E1;padding-bottom:6px}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:12px;background:#DDDBFD;color:#5454BF;margin-right:6px}
.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #E7E8F0;font-size:13px}
.row .label{color:#7B7E8C;flex-shrink:0;margin-right:16px}.msg-card{border:1px solid #D3D6E1;border-radius:12px;padding:16px;margin-bottom:12px;background:#fff}
.headline{font-size:15px;font-weight:700;margin-bottom:8px;color:#202058}.body-text{font-size:13px;color:#575966;margin-bottom:8px}
.cta{font-size:13px;font-weight:600;color:#5454BF}.issue{color:#D2091D;font-size:12px;margin:4px 0}.strength{color:#438765;font-size:12px;margin:4px 0}
.footer{margin-top:48px;font-size:11px;color:#ACAFBF;border-top:1px solid #E7E8F0;padding-top:16px}</style></head><body>
<h1>Nova Persona Report</h1>
<p style="color:#7B7E8C;font-size:13px">${result.company_name || "Role Analysis"} · Generated ${ts} · Nova AI Suite</p>
${result.jd_quality ? `<h2>JD Quality Score: ${result.jd_quality.score}/10 (${result.jd_quality.grade})</h2>${(result.jd_quality.issues||[]).map(i=>`<p class="issue">↑ ${i}</p>`).join("")}${(result.jd_quality.strengths||[]).map(s=>`<p class="strength">✓ ${s}</p>`).join("")}` : ""}
${p ? `<h2>Persona: ${p.name}</h2><div class="row"><span class="label">Role</span><span>${p.role}</span></div><div class="row"><span class="label">Core job</span><span>${p.core_job}</span></div><div class="row"><span class="label">DISC</span><span>${p.disc_type}</span></div><div class="row"><span class="label">Primary message</span><span><em>${p.primary_message}</em></span></div>
<h2>Messaging Playbook</h2>${(p.messaging_variants||[]).map(v=>`<div class="msg-card"><div class="badge">${v.label}</div><div class="headline">${v.headline}</div><div class="body-text">${v.body}</div><div class="cta">${v.cta}</div></div>`).join("")}` : ""}
<h2>Channels</h2>${(result.channels||[]).map(c=>`<div class="row"><span class="label">${c.name} <span class="badge">${c.tier}</span></span><span style="font-size:12px;color:#575966">${c.why}</span></div>`).join("")}
<div class="footer">Nova AI Suite · Joveo Strategic Products Division · 7,053 publishers</div></body></html>`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  a.download = `nova_persona_report_${Date.now()}.html`;
  a.click();
}

// ─── Main ──────────────────────────────────────────────────────────────────────
const SOURCE_OPTS = [
  { id: "jd",       label: "Paste JD",          desc: "Text or job link" },
  { id: "url",      label: "Careers page",       desc: "Scrape live roles" },
  { id: "linkedin", label: "LinkedIn + careers", desc: "Employee signals" },
];

const OUTPUT_TABS = [
  { id: "personas",    label: "Personas" },
  { id: "messaging",   label: "Messaging" },
  { id: "channels",    label: "Channels" },
  { id: "competitive", label: "Competitive" },
  { id: "adstrat",     label: "Ad strategy" },
];

const PERSONA_COLORS = [B.iris, B.moonstone, B.magenta, B.orange, "#0891b2", "#059669"];

export default function PersonaBuilder() {
  const [src, setSrc]               = useState("jd");
  const [jdText, setJdText]         = useState("");
  const [jdUrl, setJdUrl]           = useState("");
  const [careersUrl, setCareersUrl] = useState("");
  const [liUrl, setLiUrl]           = useState("");
  const [liCareers, setLiCareers]   = useState("");
  const [loading, setLoading]         = useState(false);
  const [loadingStep, setLoadingStep] = useState("");
  const [loadingPct, setLoadingPct]   = useState(0);
  const [error, setError]             = useState("");
  const [result, setResult]         = useState(null);
  const [selPersona, setSelPersona] = useState(0);
  const [selTab, setSelTab]         = useState("personas");
  const textareaRef = useRef(null);

  useEffect(() => {
    const handler = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !loading) run(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const applyDemo = () => {
    setSrc("jd");
    setJdText("Senior Embedded Software Engineer — Missile Defense Systems\nRTX · Tucson, AZ\nRequired: Active SECRET clearance\n5+ years C/C++, VxWorks, DO-178C experience...");
    const colored = { ...DEMO_DATA, personas: DEMO_DATA.personas.map((p, i) => ({ ...p, color: PERSONA_COLORS[i % PERSONA_COLORS.length] })) };
    setResult(colored); setSelPersona(0); setSelTab("personas");
  };

  const run = useCallback(async () => {
    setError(""); setLoading(true); setResult(null); setLoadingPct(5);
    const steps = src === "jd"
      ? ["Parsing job description…", "Running SparkToro lookup…", "Querying People Data Labs…", "Generating persona via Claude…", "Building channel recs…"]
      : src === "url"
      ? ["Scraping careers page…", "Clustering roles…", "Running audience intelligence…", "Building output…"]
      : ["Fetching LinkedIn signals…", "Running audience intelligence…", "Synthesising personas…"];
    let stepIdx = 0;
    const interval = setInterval(() => {
      if (stepIdx < steps.length) { setLoadingStep(steps[stepIdx]); setLoadingPct(Math.min(90, 10 + stepIdx * (80 / steps.length))); stepIdx++; }
    }, 1500);
    try {
      let data;
      if (src === "jd") data = await callAPI("/api/analyze-jd", { text: jdText, url: jdUrl });
      else if (src === "url") data = await callAPI("/api/analyze-url", { url: careersUrl });
      else data = await callAPI("/api/analyze-linkedin", { linkedin_url: liUrl, careers_url: liCareers });
      setLoadingPct(100);
      if (data.personas) data.personas = data.personas.map((p, i) => ({ ...p, color: PERSONA_COLORS[i % PERSONA_COLORS.length] }));
      setResult(data); setSelPersona(0); setSelTab("personas");
    } catch (e) { setError(e.message || "Something went wrong."); }
    finally { clearInterval(interval); setLoading(false); setLoadingStep(""); setLoadingPct(0); }
  }, [src, jdText, jdUrl, careersUrl, liUrl, liCareers]);

  const personas    = result?.personas || [];
  const channels    = result?.channels || [];
  const competitive = result?.competitive || [];
  const adStrat     = result?.ad_strategy || [];
  const liSignals   = result?.li_signals;
  const jdQuality   = result?.jd_quality;

  return (
    <div style={{ background: B.antiFlash, minHeight: "100vh", fontFamily: "'Inter', 'Poppins', system-ui, sans-serif" }} className="p-6">
      {/* Header */}
      <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-5 mb-5 shadow-sm flex items-center justify-between">
        <div className="flex items-center gap-4">
          <JoveoLogo height={32} />
          <div style={{ width: 1, height: 32, background: B.platinum }} />
          <div>
            <p style={{ color: B.pennBlue }} className="text-base font-semibold leading-tight">Persona Builder</p>
            <p style={{ color: B.slateGray }} className="text-xs">Candidate archetypes · DISC ad copy · Channel recs · Competitive intel</p>
          </div>
        </div>
        <span style={{ background: B.irisLight, color: B.iris, border: `1px solid ${B.iris}30` }} className="text-[10px] px-2 py-0.5 rounded-full font-semibold">Nova AI Suite</span>
      </div>

      {/* Input card */}
      <div style={{ background: B.white, border: `1px solid ${B.platinum}` }} className="rounded-2xl p-5 mb-5 shadow-sm">
        {/* Source selector */}
        <div className="flex gap-2 mb-5">
          {SOURCE_OPTS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setSrc(opt.id)}
              style={{
                border: src === opt.id ? `1.5px solid ${B.iris}` : `1px solid ${B.platinum}`,
                background: src === opt.id ? B.irisLight : B.antiFlash,
                color: src === opt.id ? B.iris : B.davyGray,
              }}
              className="flex-1 text-center py-2.5 px-3 rounded-xl text-sm transition-all"
            >
              <div className="font-semibold">{opt.label}</div>
              <div className="text-[10px] opacity-60 mt-0.5">{opt.desc}</div>
            </button>
          ))}
        </div>

        {/* Input fields */}
        {src === "jd" && (
          <div className="space-y-3">
            <input type="url" value={jdUrl} onChange={(e) => setJdUrl(e.target.value)}
              placeholder="Job posting URL (optional)"
              style={{ background: B.antiFlash, border: `1px solid ${B.platinum}`, color: B.pennBlue }}
              className="w-full rounded-xl px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-2"
            />
            <textarea ref={textareaRef} value={jdText} onChange={(e) => setJdText(e.target.value)} rows={6}
              placeholder="Paste job description text here…&#10;&#10;Example: Senior Embedded Software Engineer — Missile Defense&#10;RTX · Tucson, AZ · Active SECRET clearance required..."
              style={{ background: B.antiFlash, border: `1px solid ${B.platinum}`, color: B.pennBlue }}
              className="w-full rounded-xl px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 resize-y"
            />
          </div>
        )}
        {src === "url" && (
          <input type="url" value={careersUrl} onChange={(e) => setCareersUrl(e.target.value)}
            placeholder="https://careers.company.com"
            style={{ background: B.antiFlash, border: `1px solid ${B.platinum}`, color: B.pennBlue }}
            className="w-full rounded-xl px-3 py-2 text-sm placeholder-gray-400 focus:outline-none"
          />
        )}
        {src === "linkedin" && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p style={{ color: B.slateGray }} className="text-[11px] mb-1.5">LinkedIn company page</p>
              <input type="url" value={liUrl} onChange={(e) => setLiUrl(e.target.value)}
                placeholder="https://linkedin.com/company/rtx"
                style={{ background: B.antiFlash, border: `1px solid ${B.platinum}`, color: B.pennBlue }}
                className="w-full rounded-xl px-3 py-2 text-sm focus:outline-none"
              />
            </div>
            <div>
              <p style={{ color: B.slateGray }} className="text-[11px] mb-1.5">Careers page (optional)</p>
              <input type="url" value={liCareers} onChange={(e) => setLiCareers(e.target.value)}
                placeholder="https://careers.rtx.com"
                style={{ background: B.antiFlash, border: `1px solid ${B.platinum}`, color: B.pennBlue }}
                className="w-full rounded-xl px-3 py-2 text-sm focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 mt-4 flex-wrap">
          <button onClick={run} disabled={loading}
            style={{ background: loading ? B.frenchGray : B.iris, color: B.white }}
            className="text-sm font-semibold px-5 py-2 rounded-xl transition-all disabled:opacity-50 hover:opacity-90"
          >
            {loading ? "Building…" : "Build personas"}
          </button>
          <button onClick={applyDemo} disabled={loading}
            style={{ border: `1px solid ${B.platinum}`, color: B.slateGray, background: "transparent" }}
            className="text-sm px-4 py-2 rounded-xl transition-all hover:opacity-70"
          >
            Try demo
          </button>
          <span style={{ color: B.frenchGray }} className="text-[10px]">⌘↵ to run</span>
          {loading && (
            <div className="flex-1 min-w-[200px]">
              <div style={{ background: B.ghostWhite }} className="h-1.5 rounded-full overflow-hidden">
                <div style={{ width: `${loadingPct}%`, background: B.iris }} className="h-full rounded-full transition-all duration-500" />
              </div>
              {loadingStep && <p style={{ color: B.slateGray }} className="text-[10px] mt-1 animate-pulse">{loadingStep}</p>}
            </div>
          )}
          {error && <span style={{ color: B.error }} className="text-xs">{error}</span>}
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {jdQuality && <JdQualityCard quality={jdQuality} />}

          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <p style={{ color: B.pennBlue }} className="text-base font-semibold">
              {result.company_name || "Detected personas"}
            </p>
            <Badge variant="iris">{personas.length} persona{personas.length !== 1 ? "s" : ""} · {result.source?.replace(/_/g, " ")}</Badge>
            {result.itsma_validated && <Badge variant="success">✓ ITSMA validated</Badge>}
            {result.sources_used?.length > 0 && <SourceConfidenceBadge sources={result.sources_used} />}
            <div className="ml-auto flex gap-2">
              <button style={{ border: `1px solid ${B.platinum}`, color: B.slateGray }} className="text-xs rounded-xl px-3 py-1.5 hover:opacity-70 transition-all" onClick={() => exportHtmlReport(result)}>Export report</button>
              <button style={{ border: `1px solid ${B.platinum}`, color: B.slateGray }} className="text-xs rounded-xl px-3 py-1.5 hover:opacity-70 transition-all"
                onClick={() => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" })); a.download = `nova_personas_${Date.now()}.json`; a.click(); }}>
                Export JSON
              </button>
            </div>
          </div>

          {liSignals && <LinkedInSignals signals={liSignals} />}

          {/* Output tabs */}
          <div className="flex gap-1.5 mb-4 flex-wrap">
            {OUTPUT_TABS.map((t) => (
              <button key={t.id} onClick={() => setSelTab(t.id)}
                style={{
                  background: selTab === t.id ? B.white : "transparent",
                  border: selTab === t.id ? `1px solid ${B.platinum}` : "1px solid transparent",
                  color: selTab === t.id ? B.pennBlue : B.slateGray,
                  boxShadow: selTab === t.id ? "0 1px 3px rgba(0,0,0,0.06)" : "none",
                }}
                className="px-3 py-1.5 text-xs rounded-lg transition-all font-medium"
              >
                {t.label}
                {t.id === "messaging" && personas[0]?.messaging_variants?.length > 0 && (
                  <span style={{ background: B.iris, color: B.white }} className="ml-1.5 text-[9px] px-1.5 py-0.5 rounded-full">
                    {personas[0].messaging_variants.length * personas.length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {selTab === "personas" && (
            <div className={`grid gap-4 ${personas.length > 1 ? "grid-cols-[200px_1fr]" : "grid-cols-1"}`}>
              {personas.length > 1 && (
                <div>
                  <SectionLabel>Archetypes</SectionLabel>
                  <div className="space-y-1.5">
                    {personas.map((p, i) => <PersonaChip key={i} persona={p} active={i === selPersona} onClick={() => setSelPersona(i)} />)}
                  </div>
                </div>
              )}
              <PersonaDetail persona={personas[selPersona]} />
            </div>
          )}
          {selTab === "messaging"   && <MessagingTab personas={personas} />}
          {selTab === "channels"    && <ChannelsTab channels={channels} />}
          {selTab === "competitive" && <CompetitiveTab competitors={competitive} />}
          {selTab === "adstrat"     && <AdStratTab strategy={adStrat} />}
        </>
      )}

      {/* Footer */}
      <div className="mt-8 pt-4 flex justify-between text-[10px] flex-wrap gap-2" style={{ borderTop: `1px solid ${B.platinum}`, color: B.frenchGray }}>
        <span>Nova AI Suite · Persona Builder v3 · Joveo</span>
        <span>SparkToro · PDL · Lightcast · Bright Data · Claude Haiku 4.5</span>
      </div>
    </div>
  );
}
