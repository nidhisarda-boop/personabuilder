/**
 * PersonaBuilder.jsx — Nova AI Suite
 * Mount at: /platform/persona-builder
 * Add to platform.html sidebar nav as "Persona Builder"
 *
 * Calls:
 *   POST /api/persona-builder/analyze-jd
 *   POST /api/persona-builder/analyze-url
 *   POST /api/persona-builder/analyze-linkedin
 *
 * Matches Nova dark theme (Tailwind CSS, same palette as CG Automation)
 */

import { useState, useCallback } from "react";

// ─── API ──────────────────────────────────────────────────────────────────────
const API_BASE = "";   // same origin

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
    slate:  "bg-slate-800 text-slate-300 border border-slate-700",
    red:    "bg-red-900/40 text-red-300 border border-red-700/40",
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

function PersonaChip({ persona, active, onClick }) {
  // Extract the archetype word's first letter: "The Creator" → "C", "The Guardian" → "G"
  const avatarLetter = (persona.name || "P").split(/\s+/).filter(Boolean).slice(-1)[0]?.[0]?.toUpperCase() || "P";
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

function PersonaDetail({ persona }) {
  if (!persona) return null;
  const p = persona;
  const avatarLetter = (p.name || "P").split(/\s+/).filter(Boolean).slice(-1)[0]?.[0]?.toUpperCase() || "P";
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
          <div className="flex-1">
            <p className="text-base font-medium text-slate-100">{p.name}</p>
            <p className="text-xs text-slate-400">{p.role}</p>
          </div>
          {p.disc_type && (
            <div className="flex flex-col items-center px-3 py-1.5 rounded-lg"
              style={{ background: discColor + "15", border: `1px solid ${discColor}40` }}>
              <span className="text-lg font-bold" style={{ color: discColor }}>{p.disc_type}</span>
              <span className="text-[9px] text-slate-500 uppercase tracking-wide">DISC</span>
            </div>
          )}
        </div>

        <AttrRow label="Profile" value={p.profile} />
        <AttrRow label="Background" value={p.background} />

        {/* JTBD section */}
        <div className="mt-3 pt-3 border-t border-slate-800">
          <p className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">Jobs-to-be-Done</p>
          {p.core_job && <AttrRow label="Core job" value={p.core_job} />}
          {p.context_trigger && <AttrRow label="Context trigger" value={p.context_trigger} />}
          {p.functional_goals?.length > 0 && (
            <div className="py-1.5 border-b border-slate-800">
              <p className="text-xs text-slate-500 mb-1">Functional goals</p>
              <ul className="space-y-0.5">
                {p.functional_goals.map((g, i) => (
                  <li key={i} className="text-xs text-slate-200 flex gap-1.5 items-start">
                    <span className="text-indigo-500 mt-0.5">›</span>{g}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {p.emotional_goals?.length > 0 && (
            <div className="py-1.5 border-b border-slate-800">
              <p className="text-xs text-slate-500 mb-1">Emotional goals</p>
              <ul className="space-y-0.5">
                {p.emotional_goals.map((g, i) => (
                  <li key={i} className="text-xs text-slate-200 flex gap-1.5 items-start">
                    <span className="text-emerald-500 mt-0.5">›</span>{g}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <AttrRow label="Concern" value={p.concern} />
        <AttrRow label="Acquisition trigger" value={p.acquisition_trigger} />

        {/* DISC implication */}
        {p.disc_implication && (
          <div className="mt-2 px-3 py-2 rounded-lg text-xs text-slate-400 italic"
            style={{ background: discColor + "0a", borderLeft: `2px solid ${discColor}60` }}>
            <span className="not-italic font-medium" style={{ color: discColor }}>Outreach tone ({p.disc_type}): </span>
            {p.disc_implication}
          </div>
        )}

        {/* Primary message */}
        <div className="mt-3 pt-3 border-t border-slate-800">
          <p className="text-xs text-slate-500 mb-2">Primary message</p>
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
      </div>

      {/* SparkToro audience intelligence */}
      {p.sparktoro?.websites?.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <SectionLabel>SparkToro — where this audience spends time</SectionLabel>
          <div className="grid grid-cols-2 gap-3">
            {p.sparktoro.websites?.length > 0 && (
              <div>
                <p className="text-[10px] text-slate-600 mb-1.5">Top websites</p>
                {p.sparktoro.websites.slice(0, 5).map((s, i) => (
                  <p key={i} className="text-xs text-slate-300 py-0.5">{s}</p>
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
          <SectionLabel>PDL career trajectory signals</SectionLabel>
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
                  Avg tenure: <span className="text-slate-200">{p.pdl_signals.avg_tenure_years}y</span>
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ChannelsTab({ channels }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <SectionLabel>Niche & specialty publisher recommendations</SectionLabel>
      <div className="space-y-0 divide-y divide-slate-800">
        {channels.map((ch, i) => (
          <div key={i} className="py-3 flex gap-3">
            <div
              className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
              style={{ background: ch.color || "#6366f1" }}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-medium text-slate-200">{ch.name}</span>
                <Badge color={ch.tier === "premium" ? "indigo" : ch.tier === "niche" ? "green" : "slate"}>
                  {ch.tier}
                </Badge>
                {ch.traffic && <span className="text-[10px] text-slate-500 ml-auto">{ch.traffic}</span>}
                {ch.cpc && <span className="text-[10px] text-slate-400">{ch.cpc}</span>}
              </div>
              {ch.why && <p className="text-xs text-slate-400 leading-relaxed">{ch.why}</p>}
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-slate-600 mt-4">
        Matched from Nova supply repository · 7,053 global publishers · joveo_global_supply_repository.json
      </p>
    </div>
  );
}

function CompetitiveTab({ competitors }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <SectionLabel>Competitive landscape</SectionLabel>
      <div className="grid grid-cols-2 gap-3">
        {competitors.map((c, i) => (
          <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-lg p-3">
            <p className="text-sm font-medium text-slate-200 mb-2">{c.company}</p>
            <AttrRow label="Glassdoor" value={`${c.rating}/5`} />
            <AttrRow label="% Recommend" value={c.recommend} />
            <p className="text-xs italic text-slate-400 mt-2 mb-1">{c.hook}</p>
            <p className="text-xs text-red-400">{c.weakness}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AdStratTab({ strategy }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <SectionLabel>Ad strategy audit & recommendations</SectionLabel>
      <div className="divide-y divide-slate-800">
        {strategy.map((s, i) => (
          <div key={i} className="py-3">
            <div className="flex items-center gap-2 mb-2">
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
              <div className="h-full bg-indigo-500 rounded" style={{ width: `${ind.pct * 2}%` }} />
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
              <div className="h-full bg-emerald-500 rounded" style={{ width: `${c.pct * 8}%` }} />
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

// ─── Main component ───────────────────────────────────────────────────────────

const SOURCE_OPTS = [
  { id: "jd",       label: "Paste JD",        desc: "Text or job link" },
  { id: "url",      label: "Careers page",     desc: "Scrape live jobs" },
  { id: "linkedin", label: "LinkedIn + careers", desc: "Employee signals + roles" },
];

const OUTPUT_TABS = [
  { id: "personas",    label: "Personas" },
  { id: "channels",   label: "Niche channels" },
  { id: "competitive", label: "Competitive" },
  { id: "adstrat",    label: "Ad strategy" },
];

const PERSONA_COLORS = ["#7c3aed","#0a66c2","#059669","#d97706","#e11d48","#0891b2","#374151"];

export default function PersonaBuilder() {
  const [src, setSrc]             = useState("jd");
  const [jdText, setJdText]       = useState("");
  const [jdUrl, setJdUrl]         = useState("");
  const [careersUrl, setCareersUrl] = useState("");
  const [liUrl, setLiUrl]         = useState("");
  const [liCareers, setLiCareers] = useState("");

  const [loading, setLoading]     = useState(false);
  const [loadingStep, setLoadingStep] = useState("");
  const [error, setError]         = useState("");

  const [result, setResult]       = useState(null);
  const [selPersona, setSelPersona] = useState(0);
  const [selTab, setSelTab]       = useState("personas");

  const run = useCallback(async () => {
    setError("");
    setLoading(true);
    setResult(null);

    try {
      let data;
      if (src === "jd") {
        setLoadingStep("Extracting role signals from job description…");
        data = await callAPI("/api/persona-builder/analyze-jd", { text: jdText, url: jdUrl });
      } else if (src === "url") {
        setLoadingStep("Scraping careers page via Jina…");
        await new Promise(r => setTimeout(r, 800));
        setLoadingStep("Clustering roles into persona groups…");
        data = await callAPI("/api/persona-builder/analyze-url", { url: careersUrl });
      } else {
        setLoadingStep("Fetching LinkedIn employee signals…");
        await new Promise(r => setTimeout(r, 1000));
        setLoadingStep("Synthesising personas from company + role signals…");
        data = await callAPI("/api/persona-builder/analyze-linkedin", {
          linkedin_url: liUrl,
          careers_url: liCareers,
        });
      }

      // Colour the personas
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
      setLoading(false);
      setLoadingStep("");
    }
  }, [src, jdText, jdUrl, careersUrl, liUrl, liCareers]);

  const personas   = result?.personas || [];
  const channels   = result?.channels || [];
  const competitive = result?.competitive || [];
  const adStrat    = result?.ad_strategy || [];
  const liSignals  = result?.li_signals;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6 font-sans">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="bg-gradient-to-br from-indigo-500 to-blue-600 rounded-lg px-3 py-1.5 text-sm font-bold">
            ◈ Nova
          </div>
          <h1 className="text-xl font-semibold">Persona Builder</h1>
        </div>
        <p className="text-sm text-slate-500">
          Build candidate archetypes, niche channel recommendations, competitive intel, and ad strategy — from any job description, careers page, or LinkedIn company page.
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
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              rows={5}
              placeholder="Paste job description text here…&#10;&#10;Example: Senior Embedded Software Engineer — Missile Defense Systems&#10;RTX · Tucson, AZ · $120,000–$165,000 · Security clearance required&#10;&#10;Requirements: 5+ years embedded C/C++, DO-178C, active SECRET clearance..."
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
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={run}
            disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            {loading ? "Building personas…" : "Build personas"}
          </button>
          {loading && loadingStep && (
            <span className="text-xs text-slate-400 animate-pulse">{loadingStep}</span>
          )}
          {error && <span className="text-xs text-red-400">{error}</span>}
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Result header */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <p className="text-base font-medium">
              {result.company_name || "Detected personas"}
            </p>
            <Badge color="indigo">
              {personas.length} persona{personas.length !== 1 ? "s" : ""} · {result.source?.replace("_", " ")}
            </Badge>
            {result.itsma_validated && (
              <Badge color="green">✓ ITSMA validated · {result.sources_used?.length} sources</Badge>
            )}
            {result.sources_used?.length > 0 && !result.itsma_validated && (
              <Badge color="amber">{result.sources_used?.length} source{result.sources_used?.length !== 1 ? "s" : ""} used</Badge>
            )}
            <div className="ml-auto flex gap-2">
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
          <div className="flex gap-1.5 mb-4">
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
              </button>
            ))}
          </div>

          {/* Personas tab */}
          {selTab === "personas" && (
            <div className="grid grid-cols-[200px_1fr] gap-4">
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
              <PersonaDetail persona={personas[selPersona]} />
            </div>
          )}

          {/* Channels tab */}
          {selTab === "channels" && <ChannelsTab channels={channels} />}

          {/* Competitive tab */}
          {selTab === "competitive" && <CompetitiveTab competitors={competitive} />}

          {/* Ad strategy tab */}
          {selTab === "adstrat" && <AdStratTab strategy={adStrat} />}
        </>
      )}

      {/* Footer */}
      <div className="mt-8 pt-4 border-t border-slate-900 flex justify-between text-[10px] text-slate-700">
        <span>Nova AI Suite · Persona Builder · Joveo Strategic Products Division</span>
        <span>Publisher data: joveo_global_supply_repository.json · 7,053 publishers</span>
      </div>
    </div>
  );
}
