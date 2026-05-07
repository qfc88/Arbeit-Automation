"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Treemap,
} from "recharts";

// ── Types ──────────────────────────────────────────────────────────────────
type SkillEntry = {
  skill: string;
  category: string;
  job_count: number;
  total_mentions: number;
  pct: number;
};
type CategoryEntry = {
  category: string;
  unique_skills: number;
  job_count: number;
  total_mentions: number;
};
type SkillStats = {
  total_jobs: number;
  extracted: number;
  total_skill_entries: number;
  unique_skills: number;
  avg_skills_per_job: number;
};
type ExtractStatus = { running: boolean; progress: string; error: string | null };
type ExtractResult = {
  skills: { skill: string; category: string; mentions: number; context: string | null }[];
  languages: { language: string; level?: string }[];
  total: number;
};

const API = "/api";

const PALETTE = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
  "#06b6d4", "#e11d48", "#94a3b8",
];

const CAT_COLORS: Record<string, string> = {
  programming: "#3b82f6",
  framework: "#6366f1",
  cloud_devops: "#8b5cf6",
  database: "#14b8a6",
  data_bi: "#06b6d4",
  erp_software: "#f97316",
  office: "#94a3b8",
  design_tool: "#ec4899",
  certification: "#ef4444",
  language: "#10b981",
  soft_skill: "#f59e0b",
  industry_skill: "#84cc16",
};

const CAT_LABELS: Record<string, string> = {
  programming: "Programming",
  framework: "Frameworks",
  cloud_devops: "Cloud & DevOps",
  database: "Databases",
  data_bi: "Data & BI",
  erp_software: "ERP & Software",
  office: "Office Tools",
  design_tool: "Design Tools",
  certification: "Certifications",
  language: "Languages",
  soft_skill: "Soft Skills",
  industry_skill: "Industry Skills",
};

// ── Primitives ─────────────────────────────────────────────────────────────
function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function ProgressBar({ value, color = "#3b82f6", height = "h-2" }: { value: number; color?: string; height?: string }) {
  return (
    <div className={`w-full rounded-full bg-slate-100 ${height}`}>
      <div
        className={`${height} rounded-full transition-all duration-500`}
        style={{ width: `${Math.max(1, value)}%`, backgroundColor: color }}
      />
    </div>
  );
}

function SectionHeader({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <div className="mt-0.5 size-9 rounded-xl bg-slate-100 grid place-items-center text-slate-600 shrink-0">
        {icon}
      </div>
      <div>
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, icon, accent }: {
  label: string; value: string | number; sub?: string; icon: React.ReactNode; accent: string;
}) {
  return (
    <Card className="p-5 flex gap-4 items-start">
      <div className={`size-10 rounded-xl grid place-items-center shrink-0 ${accent}`}>{icon}</div>
      <div className="min-w-0">
        <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</div>
        <div className="text-2xl font-bold text-slate-900 mt-0.5 leading-none">{value}</div>
        {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
      </div>
    </Card>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────────
function IconCode() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
    </svg>
  );
}
function IconLayers() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
    </svg>
  );
}
function IconTrend() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  );
}
function IconStack() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  );
}
function IconHash() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
    </svg>
  );
}
function IconSearch() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}
function IconDatabase() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
    </svg>
  );
}
function IconPlay() {
  return <svg className="size-4" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>;
}
function IconChart() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}
function IconGlobe() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
    </svg>
  );
}

// ── Custom Tooltip ─────────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function SkillTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-lg text-xs">
      <div className="font-semibold text-slate-800">{d?.fullName || d?.skill || d?.name}</div>
      <div className="text-slate-500 mt-0.5">{d?.job_count ?? payload[0]?.value} jobs</div>
      {d?.pct != null && <div className="text-slate-400">{d.pct}% of postings</div>}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function SkillsPage() {
  const [stats, setStats] = useState<SkillStats | null>(null);
  const [topSkills, setTopSkills] = useState<SkillEntry[]>([]);
  const [categories, setCategories] = useState<CategoryEntry[]>([]);
  const [extractStatus, setExtractStatus] = useState<ExtractStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  // Try-it form
  const [profession, setProfession] = useState("");
  const [description, setDescription] = useState("");
  const [tryResult, setTryResult] = useState<ExtractResult | null>(null);
  const [extracting, setExtracting] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [s, t, c, e] = await Promise.all([
        fetch(`${API}/skills/stats`).then(r => r.json()),
        fetch(`${API}/skills/top?limit=30`).then(r => r.json()),
        fetch(`${API}/skills/categories`).then(r => r.json()),
        fetch(`${API}/skills/extract-status`).then(r => r.json()),
      ]);
      setStats(s);
      setTopSkills(t.skills || []);
      setCategories(c.categories || []);
      setExtractStatus(e);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Poll when running
  useEffect(() => {
    if (!extractStatus?.running) return;
    const id = setInterval(async () => {
      const r = await fetch(`${API}/skills/extract-status`).then(r => r.json());
      setExtractStatus(r);
      if (!r.running) { fetchAll(); clearInterval(id); }
    }, 2000);
    return () => clearInterval(id);
  }, [extractStatus?.running, fetchAll]);

  // Filter by category
  useEffect(() => {
    if (activeCategory === null) return;
    fetch(`${API}/skills/top?limit=30&category=${activeCategory}`)
      .then(r => r.json())
      .then(d => setTopSkills(d.skills || []))
      .catch(console.error);
  }, [activeCategory]);

  const handleExtractAll = async () => {
    await fetch(`${API}/skills/extract-all`, { method: "POST" });
    setExtractStatus({ running: true, progress: "Starting…", error: null });
  };

  const handleTryExtract = async () => {
    if (!profession.trim()) return;
    setExtracting(true);
    try {
      const r = await fetch(`${API}/skills/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profession, description: description || null }),
      });
      setTryResult(await r.json());
    } catch (e) { console.error(e); }
    finally { setExtracting(false); }
  };

  const resetFilter = () => {
    setActiveCategory(null);
    fetch(`${API}/skills/top?limit=30`).then(r => r.json()).then(d => setTopSkills(d.skills || []));
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-4 text-slate-400">
        <div className="size-10 rounded-full border-2 border-blue-200 border-t-blue-600 animate-spin" />
        <span className="text-sm">Loading Skills dashboard…</span>
      </div>
    );
  }

  const coveragePct = stats && stats.total_jobs > 0
    ? Math.round((stats.extracted / stats.total_jobs) * 100) : 0;

  const barData = topSkills.slice(0, 20).map(s => ({
    name: s.skill.length > 20 ? s.skill.slice(0, 19) + "…" : s.skill,
    fullName: s.skill,
    job_count: s.job_count,
    pct: s.pct,
    category: s.category,
  }));

  const pieData = categories.map(c => ({
    name: CAT_LABELS[c.category] || c.category,
    value: c.job_count,
    category: c.category,
  }));

  return (
    <div className="space-y-8">

      {/* Hero */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-100">
              <span className="size-1.5 rounded-full bg-indigo-500 animate-pulse" />
              Skill Extraction (NER)
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Skills Intelligence</h1>
          <p className="mt-1.5 text-sm text-slate-500 max-w-xl">
            Extracts skills, certifications, tools, and language requirements from every job posting
            using a comprehensive German labor-market dictionary — no ML model needed.
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Jobs Processed" value={(stats?.extracted ?? 0).toLocaleString()}
          sub={`${coveragePct}% of ${(stats?.total_jobs ?? 0).toLocaleString()}`}
          icon={<IconDatabase />} accent="bg-blue-50 text-blue-600" />
        <StatCard label="Total Extractions" value={(stats?.total_skill_entries ?? 0).toLocaleString()}
          sub="skill mentions" icon={<IconLayers />} accent="bg-indigo-50 text-indigo-600" />
        <StatCard label="Unique Skills" value={(stats?.unique_skills ?? 0).toLocaleString()}
          sub="distinct skills found" icon={<IconHash />} accent="bg-purple-50 text-purple-600" />
        <StatCard label="Avg / Job" value={stats?.avg_skills_per_job ?? 0}
          sub="skills per posting" icon={<IconStack />} accent="bg-emerald-50 text-emerald-600" />
        <StatCard label="Categories" value={categories.length}
          sub="skill types" icon={<IconChart />} accent="bg-amber-50 text-amber-600" />
      </div>

      {/* Coverage bar */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-sm font-semibold text-slate-800">Extraction Coverage</div>
            <div className="text-xs text-slate-500 mt-0.5">
              {(stats?.extracted ?? 0).toLocaleString()} of {(stats?.total_jobs ?? 0).toLocaleString()} postings processed
            </div>
          </div>
          <span className="text-2xl font-bold" style={{ color: coveragePct >= 80 ? "#10b981" : "#f59e0b" }}>
            {coveragePct}%
          </span>
        </div>
        <ProgressBar value={coveragePct} color={coveragePct >= 80 ? "#10b981" : "#f59e0b"} height="h-3" />
      </Card>

      {/* Category chips + Top Skills chart */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <Card className="lg:col-span-3 p-6">
          <SectionHeader icon={<IconTrend />} title="Most Demanded Skills"
            subtitle={activeCategory ? `Filtered: ${CAT_LABELS[activeCategory] || activeCategory}` : "Across all categories"} />

          {/* Category filter chips */}
          <div className="flex flex-wrap gap-1.5 mb-5">
            <button
              onClick={resetFilter}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                activeCategory === null
                  ? "bg-slate-800 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >All</button>
            {categories.map(c => (
              <button
                key={c.category}
                onClick={() => setActiveCategory(c.category)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  activeCategory === c.category
                    ? "text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
                style={activeCategory === c.category ? { backgroundColor: CAT_COLORS[c.category] || "#64748b" } : {}}
              >
                {CAT_LABELS[c.category] || c.category}
              </button>
            ))}
          </div>

          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={barData} layout="vertical" margin={{ left: 10, right: 20 }}>
              <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis dataKey="name" type="category" width={140}
                tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
              <Tooltip content={<SkillTooltip />} cursor={{ fill: "#f1f5f9" }} />
              <Bar dataKey="job_count" radius={[0, 6, 6, 0]}>
                {barData.map((d, i) => (
                  <Cell key={i} fill={CAT_COLORS[d.category] || PALETTE[i % PALETTE.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Category Distribution */}
        <Card className="lg:col-span-2 p-6">
          <SectionHeader icon={<IconChart />} title="Skill Categories"
            subtitle="Distribution by type" />
          <div className="space-y-3">
            {categories.map(c => {
              const maxJobs = categories[0]?.job_count || 1;
              return (
                <button
                  key={c.category}
                  onClick={() => setActiveCategory(c.category)}
                  className={`w-full text-left rounded-xl p-3 transition-colors ${
                    activeCategory === c.category
                      ? "bg-slate-50 ring-1 ring-slate-300"
                      : "hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="size-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: CAT_COLORS[c.category] || "#94a3b8" }} />
                      <span className="text-xs font-medium text-slate-700 truncate">
                        {CAT_LABELS[c.category] || c.category}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-slate-400">{c.unique_skills} skills</span>
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                        {c.job_count}
                      </span>
                    </div>
                  </div>
                  <ProgressBar
                    value={(c.job_count / maxJobs) * 100}
                    color={CAT_COLORS[c.category] || "#94a3b8"}
                    height="h-1.5"
                  />
                </button>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Actions row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Try Extractor */}
        <Card className="p-6">
          <SectionHeader icon={<IconSearch />} title="Try the Extractor"
            subtitle="Paste a job posting to see extracted skills" />
          <div className="space-y-3">
            <input
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-indigo-100 transition"
              placeholder="Job title: e.g. Softwareentwickler, CNC-Fräser…"
              value={profession}
              onChange={e => setProfession(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleTryExtract()}
            />
            <textarea
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-indigo-100 transition resize-none h-24"
              placeholder="Paste the job description here…"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
            <button
              onClick={handleTryExtract}
              disabled={extracting || !profession.trim()}
              className="w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {extracting ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Extracting…
                </span>
              ) : "Extract Skills →"}
            </button>
          </div>

          {tryResult && (
            <div className="mt-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-800">
                  {tryResult.total} skills found
                </span>
                {tryResult.languages.length > 0 && (
                  <div className="flex items-center gap-1">
                    <IconGlobe />
                    <span className="text-xs text-slate-500">
                      {tryResult.languages.map(l => l.level ? `${l.language} ${l.level}` : l.language).join(", ")}
                    </span>
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {tryResult.skills.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium border"
                    style={{
                      backgroundColor: (CAT_COLORS[s.category] || "#94a3b8") + "15",
                      color: CAT_COLORS[s.category] || "#64748b",
                      borderColor: (CAT_COLORS[s.category] || "#94a3b8") + "40",
                    }}
                    title={s.context || undefined}
                  >
                    {s.skill}
                    {s.mentions > 1 && (
                      <span className="text-[10px] opacity-60">×{s.mentions}</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* Batch Operations */}
        <Card className="p-6 flex flex-col gap-5">
          <SectionHeader icon={<IconDatabase />} title="Batch Extraction"
            subtitle="Extract skills from all jobs in the database" />

          <div className="rounded-xl border border-slate-200 p-4 hover:border-slate-300 transition-colors">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div>
                <div className="text-sm font-semibold text-slate-800">Extract All Jobs</div>
                <div className="text-xs text-slate-400 mt-0.5">
                  Process all {(stats?.total_jobs ?? 0).toLocaleString()} postings and save skills to DB
                </div>
              </div>
              <span className="size-7 rounded-lg bg-indigo-50 text-indigo-600 grid place-items-center shrink-0">
                <IconPlay />
              </span>
            </div>
            <button
              onClick={handleExtractAll}
              disabled={extractStatus?.running}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {extractStatus?.running ? "Running…" : "Run Extraction"}
            </button>
          </div>

          {extractStatus?.running && (
            <div className="flex items-center gap-3 rounded-xl bg-indigo-50 border border-indigo-100 px-4 py-3">
              <span className="size-4 rounded-full border-2 border-indigo-200 border-t-indigo-600 animate-spin shrink-0" />
              <div>
                <div className="text-sm font-semibold text-indigo-800">In Progress</div>
                <div className="text-xs text-indigo-600 mt-0.5">{extractStatus.progress}</div>
              </div>
            </div>
          )}
          {extractStatus?.error && (
            <div className="rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-xs text-red-700">
              <span className="font-semibold">Error: </span>{extractStatus.error}
            </div>
          )}
          {!extractStatus?.running && extractStatus?.progress && !extractStatus?.error && (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-100 px-4 py-3 text-xs text-emerald-700">
              <svg className="size-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              {extractStatus.progress}
            </div>
          )}

          {/* Quick insight cards */}
          {topSkills.length > 0 && (
            <div className="mt-2">
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Top 5 Skills</div>
              <div className="space-y-2">
                {topSkills.slice(0, 5).map((s, i) => (
                  <div key={s.skill} className="flex items-center gap-3">
                    <span className="text-xs font-bold text-slate-300 w-4">{i + 1}</span>
                    <span className="text-xs font-medium text-slate-700 w-28 truncate">{s.skill}</span>
                    <div className="flex-1">
                      <ProgressBar
                        value={s.pct}
                        color={CAT_COLORS[s.category] || PALETTE[i]}
                        height="h-1.5"
                      />
                    </div>
                    <span className="text-xs text-slate-400 w-12 text-right">{s.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
