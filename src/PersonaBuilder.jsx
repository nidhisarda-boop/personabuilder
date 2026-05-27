/**
 * PersonaBuilder.jsx — Nova AI Suite  v3
 * Mount at: /platform/persona-builder
 *
 * Calls:
 *   POST /api/persona-builder/analyze-jd
 *   POST /api/persona-builder/analyze-url
 *   POST /api/persona-builder/analyze-linkedin
 *
 * v3 additions:
 *   • Rich demo mode (RTX Missile Defense Engineer)
 *   • Messaging Playbook tab — 3 DISC-calibrated ad copy variants with copy buttons
 *   • JD Quality Score card — graded 0-10 with specific improvement actions
 *   • Budget allocation guide in Channels tab
 *   • Keyboard shortcut: Cmd/Ctrl + Enter to build
 *   • Copy-to-clipboard on all key content fields
 *   • HTML export report (formatted, shareable)
 *   • Confidence badges on data sources
 *   • Lightcast skills demand panel
 */

import { useState, useCallback, useEffect, useRef } from "react";

// ─── API ──────────────────────────────────────────────────────────────────────
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

// ─── Demo data (RTX Missile Defense Systems — realistic example) ──────────────
const DEMO_DATA = {
  source: "job_description",
  sources_used: ["text_analysis", "people_data_labs", "sparktoro", "lightcast"],
  itsma_validated: true,
  industry: "defense",
  company_name: "RTX · Missile Defense Systems",
  jd_quality: {
    score: 6.2,
    max_score: 10.0,
    grade: "C",
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
  personas: [
    {
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
      background:
        "15 years in defense electronics. Has shipped DO-178C-certified flight software and knows the difference between a real MBSE practitioner and someone who read a whitepaper. Passive — will not respond to cold LinkedIn spam. Reachable only through technical credibility signals.",
      disc_type: "C",
      disc_implication:
        "Lead with technical depth and verifiable evidence. Name the RTOS, the certification standard, the architecture. Post the engineering blog. Show the open-source repos. They will self-qualify if the bar is visible — if you lead with culture or perks they will disengage immediately.",
      job_quality_issues: [
        "No salary range deters this persona — they benchmark against Northrop and L3Harris ranges publicly posted on ClearanceJobs",
        "No mention of clearance maintenance benefit — this is table-stakes for TS/SCI talent and its absence raises questions",
      ],
      color: "#7c3aed",
      skills: ["C/C++", "VxWorks", "DO-178C", "MBSE", "SysML", "MATLAB", "Simulink", "MIL-STD-882", "LynxOS"],
      publishers: ["Joveo Programmatic", "ClearanceJobs", "LinkedIn", "DEF CON / Embedded World", "IEEE Spectrum Jobs"],
      attributes: {
        seniority: "senior",
        work_arrangement: "On-site",
        salary: "$140,000–$180,000",
        location: "Tucson, AZ",
        clearance: true,
        veteran: false,
      },
      pdl_signals: {
        typical_prior_employers: ["Northrop Grumman", "L3Harris", "Raytheon", "SAIC", "General Dynamics"],
        typical_schools: ["Georgia Tech", "MIT", "Purdue", "University of Arizona", "Carnegie Mellon"],
        avg_tenure_years: 4.2,
        sample_size: 18,
      },
      sparktoro: {
        websites: ["clearancejobs.com", "embeddedrelated.com", "defenseone.com", "aviationweek.com", "janes.com"],
        subreddits: ["embedded", "cscareerquestions", "defense", "military"],
        podcasts: ["Defense One Radio", "Embedded FM", "The Aerospace Engineer Podcast"],
      },
      lightcast: {
        top_skills_in_demand: ["Embedded C/C++", "VxWorks", "DO-178C", "Systems Engineering", "MBSE", "SysML", "MATLAB", "Simulink"],
        source: "lightcast",
      },
      messaging_variants: [
        {
          label: "Technical depth (C-type primary)",
          headline: "DO-178C. VxWorks 7. Real MBSE. Not the buzzword kind.",
          body: "Our missile defense stack is DO-178C DAL A certified. We run VxWorks 7 with full ARINC 653 partitioning, MBSE built on Cameo, and architecture reviews before — not after — first commit. If you care how safety-critical systems are actually built, you'll know this is different.",
          cta: "Read the technical brief →",
        },
        {
          label: "Mission/consequence (C-type alt)",
          headline: "We built the system protecting six allied cities. Join the team.",
          body: "We're not allowed to name them. Three different classified RTOS platforms. DO-178C Level A certification completed last year. Next-gen guidance subsystem on rack testing Q3. We need your hands on it — not your resume keywords.",
          cta: "Active TS/SCI? Apply directly →",
        },
        {
          label: "Transparency/process (C-type alt 2)",
          headline: "Exact role. Real salary. Clear year-one expectations.",
          body: "Year 1: DO-178C module ownership. Year 2: architecture lead, next-gen guidance. Salary: $140K–$180K DOE. Clearance maintenance support included. 401K match + 15% bonus target. 3-round interview, decision in 5 business days. No surprises.",
          cta: "See the full spec on ClearanceJobs →",
        },
      ],
    },
  ],
  channels: [
    {
      name: "Joveo Programmatic",
      tier: "platform",
      why: "Distributes across 7,053 publishers with real-time CPA optimisation via Joblet.ai. Baseline reach layer for all roles.",
      budget_pct: 30,
      color: "#7c3aed",
    },
    {
      name: "ClearanceJobs",
      tier: "niche",
      why: "1M+ candidates with active or recent DoD clearances. The only board where clearance level is a searchable filter — highest intent-per-dollar for TS/SCI roles. Budget $800–$1,200/month.",
      budget_pct: 35,
      color: "#22c55e",
    },
    {
      name: "LinkedIn",
      tier: "premium",
      why: "Primary passive professional channel. Employee story creative outperforms branded job ads 3–4× CTR. Use dark post amplification of organic engineer content.",
      budget_pct: 20,
      color: "#0a66c2",
    },
    {
      name: "DEF CON / Embedded World",
      tier: "niche",
      why: "Technical persona discovers employers through demonstrated expertise, not job boards. Sponsored talk costs less than 3 months of LinkedIn CPC and reaches exactly the right people.",
      budget_pct: 10,
      color: "#22c55e",
    },
    {
      name: "IEEE Spectrum Jobs",
      tier: "niche",
      why: "IEEE-verified technical professionals across engineering disciplines.",
      budget_pct: 5,
      color: "#22c55e",
    },
  ],
  competitive: [
    {
      company: "Northrop Grumman",
      rating: "4.0",
      recommend: "73%",
      hook: '"Defining possible"',
      weakness: "Slow promotion velocity and matrix org complexity reduce individual visibility. Large programs mean lower individual ownership.",
    },
    {
      company: "L3Harris",
      rating: "3.7",
      recommend: "62%",
      hook: '"Mission critical"',
      weakness: "Lower brand recognition vs. Raytheon among STEM graduates. Mid-tier compensation relative to program funding.",
    },
    {
      company: "Boeing",
      rating: "3.5",
      recommend: "60%",
      hook: '"You just make things possible"',
      weakness: "Safety and culture PR damage (737 MAX) creates significant candidate hesitation in 2025–26.",
    },
    {
      company: "Lockheed Martin",
      rating: "4.0",
      recommend: "73%",
      hook: '"Your work classified in the best way"',
      weakness: "Slow promotion velocity and org complexity. Programs are long-horizon — individual contributions harder to attribute.",
    },
  ],
  ad_strategy: [
    {
      platform: "ClearanceJobs",
      objective: "Direct sourcing",
      format: "Sponsored listing",
      hook: '"Active TS/SCI? Skip the queue."',
      insight:
        "The only board where clearance level is a searchable filter. For TS/SCI roles, ClearanceJobs delivers the highest intent-per-dollar of any channel. Target $800–$1,200/month against 8–12 qualified applicants.",
    },
    {
      platform: "LinkedIn",
      objective: "Passive professional",
      format: "Employee story — unclassified project fragment",
      hook: '"The system you\'ve heard about. We built it."',
      insight:
        "Cleared candidates are passive and sceptical of branded ads. A real engineer posting about a specific (unclassified) technical challenge generates more inbound than equivalent ad spend. Dark post amplification of organic content: ~$2K/month.",
    },
    {
      platform: "DEF CON / Embedded World",
      objective: "Technical credibility",
      format: "Talk sponsorship + booth",
      hook: '"Come see what we\'re actually defending."',
      insight:
        "The technical C-type persona discovers employers through demonstrated expertise. A sponsored talk (est. $8–15K) costs less than 3 months of LinkedIn CPC and reaches exactly the right density of TS/SCI embedded engineers.",
    },
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

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return (
    <p className="text-xs font-medium uppercase tracking-widest text-slate-500 mb-2">
      {children}
    </p>
  );
}

function Badge({ children, color = "indigo" }) {
  const colors = {
    indigo: "bg-indigo-900/40 text-indigo-300 border border-indigo-700/40",
    green:  "bg-emerald-900/40 text-emerald-300 border border-emerald-700/40",
    amber:  "bg-amber-900/40 text-amber-300 border border-amber-700/40",
    red:    "bg-red-900/40 text-red-300 border border-red-700/40",
    slate:  "bg-slate-800 text-slate-300 border border-slate-700",
    blue:   "bg-blue-900/40 text-blue-300 border border-blue-700/40",
  };
  return (
    <span className={`inline-block text-[10px] px-2 py-0.5 rounded-full ${colors[color] || colors.slate}`}>
      {children}
    </span>
  );
}

function AttrRow({ label, value }) {
  return (
    <div className="flex justify-between items-start py-1.5 border-b border-slate-800 last:border-0 gap-4">
      <span className="text-xs text-slate-500 flex-shrink-0">{label}</span>
      <span className="text-xs text-slate-200 text-right">{value}</span>
    </div>
  );
}

function CopyButton({ text, id, size = "sm" }) {
  const [copied, copy] = useCopy();
  return (
    <button
      onClick={() => copy(text, id)}
      className="text-[10px] px-2 py-1 rounded border border-slate-700 text-slate-500 hover:text-slate-200 hover:border-slate-600 transition-all"
    >
      {copied === id ? "✓ Copied" : "Copy"}
    </button>
  );
}

function PersonaChip({ persona, active, onClick }) {
  const avatarLetter = (persona.name || "P")
    .split(/\s+/).filter(Boolean).slice(-1)[0]?.[0]?.toUpperCase() || "P";
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg border text-left transition-all
        ${active
          ? "border-indigo-500/50 bg-indigo-900/30"
          : "border-slate-800 hover:border-slate-700 bg-transparent"}`}
    >
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
        style={{ background: persona.color + "22", border: `1.5px solid ${persona.color}55`, color: persona.color }}
      >
        {avatarLetter}
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-200 truncate">{persona.name}</p>
        <p className="text-[10px] text-slate-500 truncate">{persona.role}</p>
      </div>
    </button>
  );
}

function SourceConfidenceBadge({ sources }) {
  const sourceLabels = {
    text_analysis:    { label: "JD analysis", color: "slate" },
    sparktoro:        { label: "SparkToro", color: "blue" },
    people_data_labs: { label: "PDL", color: "indigo" },
    lightcast:        { label: "Lightcast", color: "amber" },
    bright_data:      { label: "Bright Data", color: "green" },
    linkedin:         { label: "LinkedIn", color: "blue" },
    apify:            { label: "Apify", color: "slate" },
  };
  return (
    <div className="flex flex-wrap gap-1.5 items-center">
      <span className="text-[10px] text-slate-600">Data sources:</span>
      {(sources || []).map((s) => {
        const meta = sourceLabels[s] || { label: s, color: "slate" };
        return <Badge key={s} color={meta.color}>{meta.label}</Badge>;
      })}
    </div>
  );
}

function JdQualityCard({ quality }) {
  if (!quality) return null;
  const { score, max_score, grade, issues, strengths, word_count } = quality;
  const pct = Math.round((score / max_score) * 100);
  const gradeColor = {
    A: "#22c55e", B: "#84cc16", C: "#f59e0b", D: "#f97316", F: "#ef4444"
  }[grade] || "#6366f1";

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 mb-5">
      <div className="flex items-center gap-4 mb-4">
        <div>
          <SectionLabel>JD Quality Score</SectionLabel>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-bold" style={{ color: gradeColor }}>{score}</span>
            <span className="text-slate-500 text-sm mb-1">/ {max_score}</span>
            <div className="ml-1 px-2 py-0.5 rounded text-sm font-bold" style={{ background: gradeColor + "20", color: gradeColor }}>
              {grade}
            </div>
          </div>
          <p className="text-[10px] text-slate-600 mt-0.5">{word_count} words</p>
        </div>
        <div className="flex-1">
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${pct}%`, background: gradeColor }}
            />
          </div>
          <div className="flex justify-between text-[9px] text-slate-700 mt-1">
            <span>0</span><span>5</span><span>10</span>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {issues?.length > 0 && (
          <div>
            <p className="text-[10px] text-red-500 uppercase tracking-wide font-medium mb-1.5">Issues to fix</p>
            <ul className="space-y-1.5">
              {issues.map((issue, i) => (
                <li key={i} className="flex gap-1.5 items-start">
                  <span className="text-red-500 text-xs mt-0.5 flex-shrink-0">↑</span>
                  <span className="text-xs text-slate-400 leading-relaxed">{issue}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {strengths?.length > 0 && (
          <div>
            <p className="text-[10px] text-emerald-500 uppercase tracking-wide font-medium mb-1.5">Strengths</p>
            <ul className="space-y-1.5">
              {strengths.map((s, i) => (
                <li key={i} className="flex gap-1.5 items-start">
                  <span className="text-emerald-500 text-xs mt-0.5 flex-shrink-0">✓</span>
                  <span className="text-xs text-slate-400 leading-relaxed">{s}</span>
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
  const avatarLetter = (p.name || "P")
    .split(/\s+/).filter(Boolean).slice(-1)[0]?.[0]?.toUpperCase() || "P";
  const discColors = { D: "#ef4444", I: "#f59e0b", S: "#22c55e", C: "#6366f1" };
  const discColor = discColors[p.disc_type] || "#6366f1";

  return (
    <div className="space-y-3">
      {/* Identity */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
            style={{ background: p.color + "22", border: `2px solid ${p.color}55`, color: p.color }}
          >
            {avatarLetter}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-base font-medium text-slate-100">{p.name}</p>
            <p className="text-xs text-slate-400 truncate">{p.role}</p>
          </div>
          {p.disc_type && (
            <div className="flex flex-col items-center px-3 py-1.5 rounded-lg flex-shrink-0"
              style={{ background: discColor + "15", border: `1px solid ${discColor}40` }}>
              <span className="text-lg font-bold" style={{ color: discColor }}>{p.disc_type}</span>
              <span className="text-[9px] text-slate-500 uppercase tracking-wide">DISC</span>
            </div>
          )}
        </div>

        <AttrRow label="Profile" value={p.profile} />
        <AttrRow label="Background" value={p.background} />

        {/* JTBD */}
        <div className="mt-3 pt-3 border-t border-slate-800">
          <p className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">Jobs-to-be-Done framework</p>
          {p.core_job && <AttrRow label="Core job" value={p.core_job} />}
          {p.context_trigger && <AttrRow label="Context trigger" value={p.context_trigger} />}
          {p.functional_goals?.length > 0 && (
            <div className="py-1.5 border-b border-slate-800">
              <p className="text-xs text-slate-500 mb-1">Functional goals</p>
              <ul className="space-y-1">
                {p.functional_goals.map((g, i) => (
                  <li key={i} className="text-xs text-slate-200 flex gap-1.5 items-start">
                    <span className="text-indigo-500 mt-0.5 flex-shrink-0">›</span>{g}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {p.emotional_goals?.length > 0 && (
            <div className="py-1.5 border-b border-slate-800">
              <p className="text-xs text-slate-500 mb-1">Emotional goals</p>
              <ul className="space-y-1">
                {p.emotional_goals.map((g, i) => (
                  <li key={i} className="text-xs text-slate-200 flex gap-1.5 items-start">
                    <span className="text-emerald-500 mt-0.5 flex-shrink-0">›</span>{g}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <AttrRow label="Main concern" value={p.concern} />
        <AttrRow label="Acquisition trigger" value={p.acquisition_trigger} />

        {/* DISC implication */}
        {p.disc_implication && (
          <div className="mt-2 px-3 py-2 rounded-lg text-xs text-slate-400"
            style={{ background: discColor + "0a", borderLeft: `2px solid ${discColor}60` }}>
            <span className="font-medium" style={{ color: discColor }}>Outreach ({p.disc_type}-type): </span>
            {p.disc_implication}
          </div>
        )}

        {/* Primary message with copy */}
        <div className="mt-3 pt-3 border-t border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-slate-500">Primary message</p>
            <CopyButton text={p.primary_message || ""} id="primary_msg" />
          </div>
          <div
            className="text-sm italic text-slate-300 leading-relaxed px-3 py-2 rounded-r-lg"
            style={{ borderLeft: `3px solid ${p.color}`, background: "rgba(255,255,255,0.03)" }}
          >
            {p.primary_message}
          </div>
        </div>

        {/* Skills */}
        {p.skills?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {p.skills.map((s) => <Badge key={s} color="indigo">{s}</Badge>)}
          </div>
        )}

        {/* Attributes */}
        {p.attributes && (
          <div className="mt-3 pt-3 border-t border-slate-800 grid grid-cols-2 gap-1">
            {Object.entries(p.attributes)
              .filter(([, v]) => v && v !== false && v !== "Not specified")
              .map(([k, v]) => (
                <div key={k} className="text-[10px]">
                  <span className="text-slate-500">{k.replace(/_/g, " ")}: </span>
                  <span className="text-slate-300">{String(v)}</span>
                </div>
              ))}
          </div>
        )}

        {/* JD issues specific to this persona */}
        {p.job_quality_issues?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-800">
            <p className="text-[10px] text-red-500 uppercase tracking-wide font-medium mb-1.5">JD issues for this persona</p>
            {p.job_quality_issues.map((issue, i) => (
              <p key={i} className="text-xs text-slate-400 flex gap-1.5 items-start mb-1">
                <span className="text-red-500 flex-shrink-0">↑</span>{issue}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* SparkToro audience intelligence */}
      {(p.sparktoro?.websites?.length > 0 || p.sparktoro?.subreddits?.length > 0) && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>SparkToro — where this audience spends time</SectionLabel>
            <Badge color="blue">Live data</Badge>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {p.sparktoro.websites?.length > 0 && (
              <div>
                <p className="text-[10px] text-slate-600 mb-1.5">Top websites</p>
                {p.sparktoro.websites.slice(0, 5).map((s, i) => (
                  <p key={i} className="text-xs text-slate-300 py-0.5 font-mono">{s}</p>
                ))}
              </div>
            )}
            <div>
              {p.sparktoro.subreddits?.length > 0 && (
                <>
                  <p className="text-[10px] text-slate-600 mb-1.5">Subreddits</p>
                  {p.sparktoro.subreddits.slice(0, 4).map((s, i) => (
                    <p key={i} className="text-xs text-slate-300 py-0.5">r/{s}</p>
                  ))}
                </>
              )}
              {p.sparktoro.podcasts?.length > 0 && (
                <>
                  <p className="text-[10px] text-slate-600 mt-2 mb-1.5">Podcasts</p>
                  {p.sparktoro.podcasts.slice(0, 3).map((s, i) => (
                    <p key={i} className="text-xs text-slate-300 py-0.5">{s}</p>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PDL career trajectory */}
      {p.pdl_signals?.typical_prior_employers?.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>PDL — career trajectory signals</SectionLabel>
            <Badge color="indigo">1.5B profiles</Badge>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] text-slate-600 mb-1.5">Typical prior employers</p>
              {p.pdl_signals.typical_prior_employers.map((co, i) => (
                <p key={i} className="text-xs text-slate-300 py-0.5">{co}</p>
              ))}
            </div>
            <div>
              {p.pdl_signals.typical_schools?.length > 0 && (
                <>
                  <p className="text-[10px] text-slate-600 mb-1.5">Typical schools</p>
                  {p.pdl_signals.typical_schools.slice(0, 4).map((s, i) => (
                    <p key={i} className="text-xs text-slate-300 py-0.5">{s}</p>
                  ))}
                </>
              )}
              {p.pdl_signals.avg_tenure_years && (
                <p className="text-xs text-slate-400 mt-2">
                  Avg tenure: <span className="text-slate-200 font-medium">{p.pdl_signals.avg_tenure_years}y</span>
                  {p.pdl_signals.sample_size && (
                    <span className="text-slate-600 ml-1">(n={p.pdl_signals.sample_size})</span>
                  )}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Lightcast skills demand */}
      {p.lightcast?.top_skills_in_demand?.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>Lightcast — skills in market demand</SectionLabel>
            <Badge color="amber">2.5B postings</Badge>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {p.lightcast.top_skills_in_demand.map((s, i) => (
              <Badge key={i} color="amber">{s}</Badge>
            ))}
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
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
        <p className="text-slate-500 text-sm">No messaging variants available for this result.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <SectionLabel>Messaging Playbook</SectionLabel>
        <p className="text-xs text-slate-400 leading-relaxed">
          3 DISC-calibrated ad copy variants per persona — each tuned to a different personality type.
          Copy any variant directly into LinkedIn Campaign Manager, ClearanceJobs, or your ATS email template.
        </p>
      </div>
      {allVariants.map((v, i) => {
        const copyId = `variant_${i}`;
        const fullText = `${v.headline}\n\n${v.body}\n\n${v.cta}`;
        return (
          <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: v.personaColor || "#6366f1" }}
                />
                <span className="text-[10px] text-slate-500">{v.personaName}</span>
                <Badge color="slate">{v.label}</Badge>
              </div>
              <button
                onClick={() => copy(fullText, copyId)}
                className={`text-xs px-3 py-1 rounded-lg border transition-all ${
                  copied === copyId
                    ? "border-emerald-600 text-emerald-400 bg-emerald-900/20"
                    : "border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600"
                }`}
              >
                {copied === copyId ? "✓ Copied" : "Copy all"}
              </button>
            </div>

            {/* Headline */}
            <div className="mb-3">
              <p className="text-[10px] text-slate-600 uppercase tracking-wide mb-1">Headline</p>
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold text-slate-100 leading-snug flex-1">{v.headline}</p>
                <CopyButton text={v.headline} id={`h_${i}`} />
              </div>
            </div>

            {/* Body */}
            <div className="mb-3">
              <p className="text-[10px] text-slate-600 uppercase tracking-wide mb-1">Body</p>
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs text-slate-300 leading-relaxed flex-1">{v.body}</p>
                <CopyButton text={v.body} id={`b_${i}`} />
              </div>
            </div>

            {/* CTA */}
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wide mb-1">CTA</p>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-indigo-400 font-medium">{v.cta}</p>
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

  return (
    <div className="space-y-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <SectionLabel>Niche & specialty publisher recommendations</SectionLabel>
        <div className="divide-y divide-slate-800">
          {(channels || []).map((ch, i) => (
            <div key={i} className="py-3 flex gap-3">
              <div
                className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                style={{ background: ch.color || "#6366f1" }}
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                  <span className="text-sm font-medium text-slate-200">{ch.name}</span>
                  <Badge color={ch.tier === "premium" ? "indigo" : ch.tier === "niche" ? "green" : ch.tier === "platform" ? "blue" : "slate"}>
                    {ch.tier}
                  </Badge>
                </div>
                {ch.why && <p className="text-xs text-slate-400 leading-relaxed">{ch.why}</p>}
              </div>
              {hasBudget && ch.budget_pct && (
                <div className="flex-shrink-0 text-right">
                  <p className="text-sm font-bold text-slate-100">{ch.budget_pct}%</p>
                  <p className="text-[10px] text-slate-600">of budget</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {hasBudget && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <SectionLabel>Budget allocation guide</SectionLabel>
          <div className="space-y-2">
            {channels.filter((c) => c.budget_pct).map((ch, i) => (
              <div key={i}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-300">{ch.name}</span>
                  <span className="text-slate-400">{ch.budget_pct}%</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${ch.budget_pct}%`, background: ch.color || "#6366f1" }}
                  />
                </div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-slate-600 mt-3">
            Allocation based on intent-per-dollar analysis for this persona type.
            Adjust based on your CPL targets and A/B test results.
          </p>
        </div>
      )}

      <p className="text-[10px] text-slate-700 text-center">
        Matched from Nova supply repository · 7,053 global publishers
      </p>
    </div>
  );
}

function CompetitiveTab({ competitors }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <SectionLabel>Competitive landscape</SectionLabel>
      <div className="grid grid-cols-2 gap-3">
        {(competitors || []).map((c, i) => (
          <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-lg p-3">
            <p className="text-sm font-medium text-slate-200 mb-2">{c.company}</p>
            <AttrRow label="Glassdoor" value={`${c.rating}/5`} />
            <AttrRow label="% Recommend" value={c.recommend} />
            <p className="text-xs italic text-slate-400 mt-2 mb-1">{c.hook}</p>
            <p className="text-xs text-red-400 leading-relaxed">{c.weakness}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AdStratTab({ strategy }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <SectionLabel>Ad strategy recommendations</SectionLabel>
      <div className="divide-y divide-slate-800">
        {(strategy || []).map((s, i) => (
          <div key={i} className="py-3">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-sm font-medium text-slate-200">{s.platform}</span>
              <Badge color="slate">{s.objective}</Badge>
              <Badge color="slate">{s.format}</Badge>
            </div>
            <div
              className="text-xs italic text-slate-400 px-3 py-1.5 rounded mb-2"
              style={{ background: "rgba(255,255,255,0.03)" }}
            >
              {s.hook}
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">{s.insight}</p>
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
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
        <SectionLabel>Top industries</SectionLabel>
        {signals.industries.slice(0, 6).map((ind, i) => (
          <div key={i} className="mb-2">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300">{ind.name}</span>
              <span className="text-slate-500">{ind.pct}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
              <div className="h-full bg-indigo-500 rounded" style={{ width: `${Math.min(ind.pct * 2, 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
        <SectionLabel>Top schools</SectionLabel>
        {signals.colleges.slice(0, 7).map((c, i) => (
          <div key={i} className="mb-2">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300">{c.name}</span>
              <span className="text-slate-500">{c.pct}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
              <div className="h-full bg-emerald-500 rounded" style={{ width: `${Math.min(c.pct * 8, 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
        <SectionLabel>Company signals</SectionLabel>
        {signals.headcount && <AttrRow label="Headcount" value={signals.headcount} />}
        {signals.growth && <AttrRow label="Growth" value={signals.growth} />}
        {signals.skills?.length > 0 && (
          <div className="mt-2">
            <p className="text-[10px] text-slate-500 mb-1">Top skills</p>
            <div className="flex flex-wrap gap-1">
              {signals.skills.slice(0, 8).map((s) => <Badge key={s} color="slate">{s}</Badge>)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Export to HTML report ────────────────────────────────────────────────────
function exportHtmlReport(result) {
  if (!result) return;
  const p = result.personas?.[0];
  const ts = new Date().toLocaleString();
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>Nova Persona Report — ${result.company_name || "Persona"}</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 24px;color:#1e293b;line-height:1.6}
  h1{font-size:24px;font-weight:700;margin-bottom:4px}
  h2{font-size:16px;font-weight:600;margin:32px 0 8px;color:#4f46e5;border-bottom:1px solid #e2e8f0;padding-bottom:6px}
  h3{font-size:14px;font-weight:600;margin:16px 0 6px}
  .badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:12px;background:#ede9fe;color:#5b21b6;margin-right:6px}
  .row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:13px}
  .row .label{color:#64748b;flex-shrink:0;margin-right:16px}
  .msg-card{border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:12px}
  .headline{font-size:15px;font-weight:700;margin-bottom:8px}
  .body-text{font-size:13px;color:#475569;margin-bottom:8px}
  .cta{font-size:13px;font-weight:600;color:#4f46e5}
  .issue{color:#ef4444;font-size:12px;margin:4px 0}
  .strength{color:#22c55e;font-size:12px;margin:4px 0}
  .footer{margin-top:48px;font-size:11px;color:#94a3b8;border-top:1px solid #f1f5f9;padding-top:16px}
</style>
</head>
<body>
<h1>Nova Persona Report</h1>
<p style="color:#64748b;font-size:13px">${result.company_name || "Role Analysis"} · Generated ${ts} · Nova AI Suite</p>

${result.jd_quality ? `
<h2>JD Quality Score: ${result.jd_quality.score}/10 (${result.jd_quality.grade})</h2>
${(result.jd_quality.issues || []).map((i) => `<p class="issue">↑ ${i}</p>`).join("")}
${(result.jd_quality.strengths || []).map((s) => `<p class="strength">✓ ${s}</p>`).join("")}
` : ""}

${p ? `
<h2>Persona: ${p.name}</h2>
<div class="row"><span class="label">Role</span><span>${p.role}</span></div>
<div class="row"><span class="label">Profile</span><span>${p.profile}</span></div>
<div class="row"><span class="label">Core job</span><span>${p.core_job}</span></div>
<div class="row"><span class="label">Context trigger</span><span>${p.context_trigger}</span></div>
<div class="row"><span class="label">Main concern</span><span>${p.concern}</span></div>
<div class="row"><span class="label">DISC type</span><span>${p.disc_type}</span></div>
<div class="row"><span class="label">Acquisition trigger</span><span>${p.acquisition_trigger}</span></div>
<div class="row"><span class="label">Primary message</span><span><em>${p.primary_message}</em></span></div>

<h2>Messaging Playbook</h2>
${(p.messaging_variants || []).map((v) => `
<div class="msg-card">
  <div class="badge">${v.label}</div>
  <div class="headline">${v.headline}</div>
  <div class="body-text">${v.body}</div>
  <div class="cta">${v.cta}</div>
</div>
`).join("")}
` : ""}

<h2>Recommended Channels</h2>
${(result.channels || []).map((c) => `
<div class="row">
  <span class="label">${c.name} <span class="badge">${c.tier}</span></span>
  <span style="font-size:12px;color:#64748b">${c.why}</span>
</div>`).join("")}

<div class="footer">Nova AI Suite · Joveo Strategic Products Division · joveo_global_supply_repository.json · 7,053 publishers</div>
</body>
</html>`;

  const blob = new Blob([html], { type: "text/html" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `nova_persona_report_${Date.now()}.html`;
  a.click();
}

// ─── Main component ───────────────────────────────────────────────────────────

const SOURCE_OPTS = [
  { id: "jd",       label: "Paste JD",           desc: "Text or job link" },
  { id: "url",      label: "Careers page",        desc: "Scrape live roles" },
  { id: "linkedin", label: "LinkedIn + careers",  desc: "Employee signals + roles" },
];

const OUTPUT_TABS = [
  { id: "personas",   label: "Personas" },
  { id: "messaging",  label: "Messaging" },
  { id: "channels",   label: "Channels" },
  { id: "competitive",label: "Competitive" },
  { id: "adstrat",   label: "Ad strategy" },
];

const PERSONA_COLORS = ["#7c3aed", "#0a66c2", "#059669", "#d97706", "#e11d48", "#0891b2", "#374151"];

export default function PersonaBuilder() {
  const [src, setSrc]             = useState("jd");
  const [jdText, setJdText]       = useState("");
  const [jdUrl, setJdUrl]         = useState("");
  const [careersUrl, setCareersUrl] = useState("");
  const [liUrl, setLiUrl]         = useState("");
  const [liCareers, setLiCareers] = useState("");

  const [loading, setLoading]       = useState(false);
  const [loadingStep, setLoadingStep] = useState("");
  const [loadingPct, setLoadingPct] = useState(0);
  const [error, setError]           = useState("");

  const [result, setResult]       = useState(null);
  const [selPersona, setSelPersona] = useState(0);
  const [selTab, setSelTab]       = useState("personas");

  const textareaRef = useRef(null);

  // Keyboard shortcut: Cmd/Ctrl + Enter
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !loading) {
        run();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const applyDemo = () => {
    setSrc("jd");
    setJdText(
      "Senior Embedded Software Engineer — Missile Defense Systems\n\nRTX · Tucson, AZ\n\nRequired clearance: Active SECRET (TS/SCI preferred)\n\nRequirements:\n• 5+ years embedded C/C++ on safety-critical systems\n• Experience with VxWorks, LynxOS, or equivalent RTOS\n• DO-178C certification experience (DAL A preferred)\n• MBSE/SysML toolchain experience (Cameo, Rhapsody)\n• Familiarity with MIL-STD-882 safety standards\n\nResponsibilities:\n• Design and implement flight software for missile defense systems\n• Lead architecture reviews for next-gen guidance subsystem\n• Coordinate with systems engineers on MBSE documentation\n• Support DO-178C certification activities\n\nAbout RTX: Raytheon Technologies is a world-leading aerospace and defense company. Our mission is to solve the world's most complex problems.\n\nEqual opportunity employer. Veterans encouraged to apply."
    );
    // Apply the pre-built demo result immediately
    const colored = {
      ...DEMO_DATA,
      personas: DEMO_DATA.personas.map((p, i) => ({
        ...p,
        color: PERSONA_COLORS[i % PERSONA_COLORS.length],
      })),
    };
    setResult(colored);
    setSelPersona(0);
    setSelTab("personas");
  };

  const run = useCallback(async () => {
    setError("");
    setLoading(true);
    setResult(null);
    setLoadingPct(5);

    const steps = src === "jd"
      ? ["Parsing job description…", "Running SparkToro audience lookup…", "Querying People Data Labs…", "Generating persona via Claude Haiku…", "Building channel recs…"]
      : src === "url"
      ? ["Scraping careers page via Jina…", "Clustering roles into persona groups…", "Running audience intelligence…", "Building multi-persona output…"]
      : ["Fetching LinkedIn company signals via Bright Data…", "Running audience intelligence…", "Synthesising personas from multi-source signals…"];

    let stepIdx = 0;
    const stepInterval = setInterval(() => {
      if (stepIdx < steps.length) {
        setLoadingStep(steps[stepIdx]);
        setLoadingPct(Math.min(90, 10 + stepIdx * (80 / steps.length)));
        stepIdx++;
      }
    }, 1500);

    try {
      let data;
      if (src === "jd") {
        data = await callAPI("/api/persona-builder/analyze-jd", { text: jdText, url: jdUrl });
      } else if (src === "url") {
        data = await callAPI("/api/persona-builder/analyze-url", { url: careersUrl });
      } else {
        data = await callAPI("/api/persona-builder/analyze-linkedin", {
          linkedin_url: liUrl,
          careers_url: liCareers,
        });
      }
      setLoadingPct(100);
      if (data.personas) {
        data.personas = data.personas.map((p, i) => ({
          ...p,
          color: PERSONA_COLORS[i % PERSONA_COLORS.length],
        }));
      }
      setResult(data);
      setSelPersona(0);
      setSelTab("personas");
    } catch (e) {
      setError(e.message || "Something went wrong — check the console.");
    } finally {
      clearInterval(stepInterval);
      setLoading(false);
      setLoadingStep("");
      setLoadingPct(0);
    }
  }, [src, jdText, jdUrl, careersUrl, liUrl, liCareers]);

  const personas    = result?.personas || [];
  const channels    = result?.channels || [];
  const competitive = result?.competitive || [];
  const adStrat     = result?.ad_strategy || [];
  const liSignals   = result?.li_signals;
  const jdQuality   = result?.jd_quality;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6 font-sans">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="bg-gradient-to-br from-indigo-500 to-blue-600 rounded-lg px-3 py-1.5 text-sm font-bold">
            ◈ Nova
          </div>
          <h1 className="text-xl font-semibold">Persona Builder</h1>
          <span className="text-xs text-slate-600 ml-1">v3</span>
        </div>
        <p className="text-sm text-slate-500">
          Build candidate archetypes, DISC-calibrated ad copy, niche channel recs, and competitive intel — from any JD, careers page, or LinkedIn company page.
        </p>
      </div>

      {/* Input card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-5">
        {/* Source selector */}
        <div className="flex gap-2 mb-5">
          {SOURCE_OPTS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setSrc(opt.id)}
              className={`flex-1 text-center py-2.5 px-3 rounded-lg border text-sm transition-all
                ${src === opt.id
                  ? "border-indigo-500/50 bg-indigo-900/30 text-indigo-300"
                  : "border-slate-800 text-slate-400 hover:border-slate-700"}`}
            >
              <div className="font-medium">{opt.label}</div>
              <div className="text-[10px] opacity-60 mt-0.5">{opt.desc}</div>
            </button>
          ))}
        </div>

        {/* Input fields */}
        {src === "jd" && (
          <div className="space-y-3">
            <input
              type="url"
              value={jdUrl}
              onChange={(e) => setJdUrl(e.target.value)}
              placeholder="Job posting URL (optional) — https://careers.company.com/job/..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-600"
            />
            <textarea
              ref={textareaRef}
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              rows={6}
              placeholder="Paste job description text here…&#10;&#10;Example: Senior Embedded Software Engineer — Missile Defense&#10;RTX · Tucson, AZ · Active SECRET clearance required&#10;&#10;Requirements: 5+ years embedded C/C++, DO-178C, VxWorks..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-600 resize-y"
            />
          </div>
        )}

        {src === "url" && (
          <input
            type="url"
            value={careersUrl}
            onChange={(e) => setCareersUrl(e.target.value)}
            placeholder="https://careers.rtx.com  ·  https://jobs.verizon.com  ·  any careers page"
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-600"
          />
        )}

        {src === "linkedin" && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[11px] text-slate-500 mb-1.5">LinkedIn company page</p>
              <input
                type="url"
                value={liUrl}
                onChange={(e) => setLiUrl(e.target.value)}
                placeholder="https://linkedin.com/company/rtx"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-600"
              />
            </div>
            <div>
              <p className="text-[11px] text-slate-500 mb-1.5">Careers page (optional)</p>
              <input
                type="url"
                value={liCareers}
                onChange={(e) => setLiCareers(e.target.value)}
                placeholder="https://careers.rtx.com"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-600"
              />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 mt-4 flex-wrap">
          <button
            onClick={run}
            disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            {loading ? "Building…" : "Build personas"}
          </button>
          <button
            onClick={applyDemo}
            disabled={loading}
            className="border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600 text-sm px-4 py-2 rounded-lg transition-colors"
          >
            Try demo
          </button>
          <span className="text-[10px] text-slate-700">⌘↵ to run</span>
          {loading && (
            <div className="flex-1 min-w-[200px]">
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    style={{ width: `${loadingPct}%` }}
                  />
                </div>
              </div>
              {loadingStep && (
                <p className="text-[10px] text-slate-500 mt-1 animate-pulse">{loadingStep}</p>
              )}
            </div>
          )}
          {error && <span className="text-xs text-red-400">{error}</span>}
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* JD Quality Score card */}
          {jdQuality && <JdQualityCard quality={jdQuality} />}

          {/* Result header */}
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <p className="text-base font-medium">
              {result.company_name || "Detected personas"}
            </p>
            <Badge color="indigo">
              {personas.length} persona{personas.length !== 1 ? "s" : ""} · {result.source?.replace(/_/g, " ")}
            </Badge>
            {result.itsma_validated && (
              <Badge color="green">✓ ITSMA validated</Badge>
            )}
            {result.sources_used?.length > 0 && (
              <SourceConfidenceBadge sources={result.sources_used} />
            )}
            <div className="ml-auto flex gap-2">
              <button
                className="text-xs text-slate-400 border border-slate-800 rounded-lg px-3 py-1.5 hover:bg-slate-900 transition-colors"
                onClick={() => exportHtmlReport(result)}
              >
                Export report
              </button>
              <button
                className="text-xs text-slate-400 border border-slate-800 rounded-lg px-3 py-1.5 hover:bg-slate-900 transition-colors"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(blob);
                  a.download = `nova_personas_${Date.now()}.json`;
                  a.click();
                }}
              >
                Export JSON
              </button>
            </div>
          </div>

          {/* LinkedIn signals strip */}
          {liSignals && <LinkedInSignals signals={liSignals} />}

          {/* Output tabs */}
          <div className="flex gap-1.5 mb-4 flex-wrap">
            {OUTPUT_TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelTab(t.id)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all
                  ${selTab === t.id
                    ? "bg-slate-800 border-slate-700 text-slate-100 font-medium"
                    : "border-transparent text-slate-500 hover:text-slate-300"}`}
              >
                {t.label}
                {t.id === "messaging" && personas[0]?.messaging_variants?.length > 0 && (
                  <span className="ml-1.5 bg-indigo-700 text-indigo-200 text-[9px] px-1.5 py-0.5 rounded-full">
                    {personas[0].messaging_variants.length * personas.length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Personas tab */}
          {selTab === "personas" && (
            <div className={`grid gap-4 ${personas.length > 1 ? "grid-cols-[200px_1fr]" : "grid-cols-1"}`}>
              {personas.length > 1 && (
                <div>
                  <SectionLabel>Archetypes</SectionLabel>
                  <div className="space-y-1.5">
                    {personas.map((p, i) => (
                      <PersonaChip
                        key={i}
                        persona={p}
                        active={i === selPersona}
                        onClick={() => setSelPersona(i)}
                      />
                    ))}
                  </div>
                </div>
              )}
              <PersonaDetail persona={personas[selPersona]} />
            </div>
          )}

          {/* Messaging tab */}
          {selTab === "messaging" && <MessagingTab personas={personas} />}

          {/* Channels tab */}
          {selTab === "channels" && <ChannelsTab channels={channels} />}

          {/* Competitive tab */}
          {selTab === "competitive" && <CompetitiveTab competitors={competitive} />}

          {/* Ad strategy tab */}
          {selTab === "adstrat" && <AdStratTab strategy={adStrat} />}
        </>
      )}

      {/* Footer */}
      <div className="mt-8 pt-4 border-t border-slate-900 flex justify-between text-[10px] text-slate-700 flex-wrap gap-2">
        <span>Nova AI Suite · Persona Builder v3 · Joveo Strategic Products Division</span>
        <span>Powered by SparkToro · PDL · Lightcast · Bright Data · Claude Haiku 4.5</span>
      </div>
    </div>
  );
}
