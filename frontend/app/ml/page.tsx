"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

// ── Types ──────────────────────────────────────────────────────────────────
type CategoryStat = { name: string; count: number; avg_confidence: number };
type MLStats = { total_jobs: number; classified: number; categories: CategoryStat[] };
type ModelInfo = { loaded: boolean; model_type: string; model_path: string; num_categories: number };
type ClassifyResult = { category: string; confidence: number; top_k: { category: string; confidence: number }[] };
type PredictStatus = { running: boolean; progress: string; error: string | null };

const PALETTE = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
  "#06b6d4", "#e11d48", "#94a3b8",
];

const API = "/api";

// ── Primitives ─────────────────────────────────────────────────────────────
function Badge({ pct }: { pct: number }) {
  const cls =
    pct >= 70
      ? "bg-emerald-100 text-emerald-700 ring-emerald-200"
      : pct >= 45
      ? "bg-amber-100 text-amber-700 ring-amber-200"
      : "bg-red-100 text-red-700 ring-red-200";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${cls}`}>
      {pct}%
    </span>
  );
}

function ProgressBar({ value, color = "#3b82f6", height = "h-2" }: { value: number; color?: string; height?: string }) {
  return (
    <div className={`w-full rounded-full bg-slate-100 ${height}`}>
      <div
        className={`${height} rounded-full transition-all duration-500`}
        style={{ width: `${Math.max(2, value)}%`, backgroundColor: color }}
      />
    </div>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {children}
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

// ── Stat Card ──────────────────────────────────────────────────────────────
function StatCard({
  label, value, sub, icon, accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  accent: string;
}) {
  return (
    <Card className="p-5 flex gap-4 items-start">
      <div className={`size-10 rounded-xl grid place-items-center shrink-0 ${accent}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</div>
        <div className="text-2xl font-bold text-slate-900 mt-0.5 leading-none">{value}</div>
        {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
      </div>
    </Card>
  );
}

// ── Tooltip ────────────────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-lg text-xs">
      <div className="font-semibold text-slate-800">{payload[0]?.payload?.fullName}</div>
      <div className="text-slate-500 mt-0.5">{payload[0]?.value} postings</div>
    </div>
  );
}

// ── Icons (inline SVG, no extra dependency) ────────────────────────────────
function IconBrain() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
}
function IconBriefcase() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}
function IconTag() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
    </svg>
  );
}
function IconGrid() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  );
}
function IconBarChart() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}
function IconPercent() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
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
function IconRefresh() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function MLPage() {
  const [stats, setStats] = useState<MLStats | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [predictStatus, setPredictStatus] = useState<PredictStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const [profession, setProfession] = useState("");
  const [description, setDescription] = useState("");
  const [result, setResult] = useState<ClassifyResult | null>(null);
  const [classifying, setClassifying] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [s, m, p] = await Promise.all([
        fetch(`${API}/ml/stats`).then(r => r.json()),
        fetch(`${API}/ml/model-info`).then(r => r.json()),
        fetch(`${API}/ml/predict-status`).then(r => r.json()),
      ]);
      setStats(s); setModelInfo(m); setPredictStatus(p);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    if (!predictStatus?.running) return;
    const id = setInterval(async () => {
      const r = await fetch(`${API}/ml/predict-status`).then(r => r.json());
      setPredictStatus(r);
      if (!r.running) { fetchAll(); clearInterval(id); }
    }, 2000);
    return () => clearInterval(id);
  }, [predictStatus?.running, fetchAll]);

  const handleClassify = async () => {
    if (!profession.trim()) return;
    setClassifying(true);
    try {
      const r = await fetch(`${API}/ml/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profession, description: description || null }),
      });
      setResult(await r.json());
    } catch (e) { console.error(e); }
    finally { setClassifying(false); }
  };

  const handlePredictAll = async () => {
    await fetch(`${API}/ml/predict-all`, { method: "POST" });
    setPredictStatus({ running: true, progress: "Starting…", error: null });
  };

  const handleRetrain = async () => {
    await fetch(`${API}/ml/retrain`, { method: "POST" });
    setPredictStatus({ running: true, progress: "Retraining…", error: null });
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-4 text-slate-400">
        <div className="size-10 rounded-full border-2 border-blue-200 border-t-blue-600 animate-spin" />
        <span className="text-sm">Loading ML dashboard…</span>
      </div>
    );
  }

  const coveragePct = stats && stats.total_jobs > 0
    ? Math.round((stats.classified / stats.total_jobs) * 100) : 0;
  const coverageColor = coveragePct >= 80 ? "#10b981" : coveragePct >= 50 ? "#f59e0b" : "#ef4444";

  const sorted = [...(stats?.categories ?? [])].sort((a, b) => b.count - a.count);
  const maxCount = sorted[0]?.count ?? 1;
  const barData = sorted.map(c => ({
    name: c.name.length > 16 ? c.name.slice(0, 15) + "…" : c.name,
    fullName: c.name,
    count: c.count,
  }));

  return (
    <div className="space-y-8">

      {/* Hero Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-100">
              <span className="size-1.5 rounded-full bg-blue-500 animate-pulse" />
              AI Classification
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">ML Job Classifier</h1>
          <p className="mt-1.5 text-sm text-slate-500 max-w-xl">
            Model{" "}
            <span className="font-semibold text-slate-700">{modelInfo?.model_type ?? "GBERT"}</span>{" "}
            automatically labels each posting with an industry sector — enabling labor demand analysis
            and trend tracking across the German job market.
          </p>
        </div>
        <div className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium shrink-0 ${
          modelInfo?.loaded
            ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
            : "bg-red-50 text-red-700 ring-1 ring-red-200"
        }`}>
          <span className={`size-2 rounded-full ${modelInfo?.loaded ? "bg-emerald-500" : "bg-red-500"}`} />
          {modelInfo?.loaded ? "Model loaded" : "Model offline"}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Model" value={modelInfo?.model_type ?? "—"} sub="Fine-tuned BERT" icon={<IconBrain />} accent="bg-blue-50 text-blue-600" />
        <StatCard label="Total Jobs" value={(stats?.total_jobs ?? 0).toLocaleString()} sub="in database" icon={<IconBriefcase />} accent="bg-slate-100 text-slate-600" />
        <StatCard label="Classified" value={(stats?.classified ?? 0).toLocaleString()} sub={`${coveragePct}% coverage`} icon={<IconTag />} accent={coveragePct >= 80 ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"} />
        <StatCard label="Sectors" value={modelInfo?.num_categories ?? 0} sub="industry categories" icon={<IconGrid />} accent="bg-purple-50 text-purple-600" />
      </div>

      {/* Coverage bar */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-sm font-semibold text-slate-800">Classification Coverage</div>
            <div className="text-xs text-slate-500 mt-0.5">
              {(stats?.classified ?? 0).toLocaleString()} of {(stats?.total_jobs ?? 0).toLocaleString()} postings labelled
            </div>
          </div>
          <span className="text-2xl font-bold" style={{ color: coverageColor }}>{coveragePct}%</span>
        </div>
        <ProgressBar value={coveragePct} color={coverageColor} height="h-3" />
      </Card>

      {/* Chart + Confidence table */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <Card className="lg:col-span-3 p-6">
          <SectionHeader icon={<IconBarChart />} title="Jobs by Sector" subtitle="Number of postings per industry category" />
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} layout="vertical" margin={{ left: 0, right: 20 }}>
              <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "#f1f5f9" }} />
              <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                {barData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="lg:col-span-2 p-6">
          <SectionHeader icon={<IconPercent />} title="Avg. Confidence" subtitle="Model certainty per sector" />
          <div className="space-y-4">
            {sorted.map((c, i) => {
              const pct = Math.round(c.avg_confidence * 100);
              return (
                <div key={c.name} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="size-2.5 rounded-full shrink-0" style={{ backgroundColor: PALETTE[i % PALETTE.length] }} />
                      <span className="text-xs font-medium text-slate-700 truncate">{c.name}</span>
                    </div>
                    <Badge pct={pct} />
                  </div>
                  <ProgressBar value={(c.count / maxCount) * 100} color={PALETTE[i % PALETTE.length]} height="h-1.5" />
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Classify form */}
        <Card className="p-6">
          <SectionHeader icon={<IconSearch />} title="Try the Classifier" subtitle="Enter a job title to see the predicted sector" />
          <div className="space-y-3">
            <input
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-100 transition"
              placeholder="e.g. Softwareentwickler, Krankenpfleger, Buchhalter…"
              value={profession}
              onChange={e => setProfession(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleClassify()}
            />
            <textarea
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-100 transition resize-none h-20"
              placeholder="Job description (optional — improves accuracy)"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
            <button
              onClick={handleClassify}
              disabled={classifying || !profession.trim()}
              className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 active:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {classifying ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Classifying…
                </span>
              ) : "Classify →"}
            </button>
          </div>

          {result && (
            <div className="mt-5 rounded-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center justify-between bg-gradient-to-r from-blue-600 to-blue-500 px-4 py-3">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-widest text-blue-200 mb-0.5">Predicted sector</div>
                  <div className="text-lg font-bold text-white">{result.category}</div>
                </div>
                <div className="text-2xl font-bold text-white/90">{Math.round(result.confidence * 100)}%</div>
              </div>
              <div className="px-4 pt-2 pb-1">
                <ProgressBar value={result.confidence * 100} color="#3b82f6" height="h-1" />
              </div>
              {result.top_k.length > 1 && (
                <div className="px-4 py-3 space-y-2.5">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Other candidates</div>
                  {result.top_k.slice(1).map((k, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-xs text-slate-600 w-32 truncate">{k.category}</span>
                      <div className="flex-1"><ProgressBar value={k.confidence * 100} color="#cbd5e1" height="h-1" /></div>
                      <span className="text-xs font-medium text-slate-400 w-8 text-right shrink-0">
                        {Math.round(k.confidence * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Batch operations */}
        <Card className="p-6 flex flex-col gap-5">
          <SectionHeader icon={<IconDatabase />} title="Batch Operations" subtitle="Apply the model across the entire database" />

          <div className="flex flex-col gap-3">
            <div className="rounded-xl border border-slate-200 p-4 hover:border-slate-300 transition-colors">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <div className="text-sm font-semibold text-slate-800">Re-classify All Jobs</div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Run GBERT on all {(stats?.total_jobs ?? 0).toLocaleString()} postings and update DB
                  </div>
                </div>
                <span className="size-7 rounded-lg bg-emerald-50 text-emerald-600 grid place-items-center shrink-0">
                  <IconPlay />
                </span>
              </div>
              <button
                onClick={handlePredictAll}
                disabled={predictStatus?.running}
                className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 active:bg-emerald-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {predictStatus?.running ? "Running…" : "Run Classification"}
              </button>
            </div>

            <div className="rounded-xl border border-slate-200 p-4 hover:border-slate-300 transition-colors">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <div className="text-sm font-semibold text-slate-800">Retrain Model</div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Auto-label DB → fine-tune GBERT on GPU → reload
                  </div>
                </div>
                <span className="size-7 rounded-lg bg-purple-50 text-purple-600 grid place-items-center shrink-0">
                  <IconRefresh />
                </span>
              </div>
              <button
                onClick={handleRetrain}
                disabled={predictStatus?.running}
                className="w-full rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-700 active:bg-purple-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {predictStatus?.running ? "Running…" : "Retrain Model"}
              </button>
            </div>
          </div>

          {predictStatus?.running && (
            <div className="flex items-center gap-3 rounded-xl bg-blue-50 border border-blue-100 px-4 py-3">
              <span className="size-4 rounded-full border-2 border-blue-200 border-t-blue-600 animate-spin shrink-0" />
              <div>
                <div className="text-sm font-semibold text-blue-800">In Progress</div>
                <div className="text-xs text-blue-600 mt-0.5">{predictStatus.progress}</div>
              </div>
            </div>
          )}
          {predictStatus?.error && (
            <div className="rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-xs text-red-700">
              <span className="font-semibold">Error: </span>{predictStatus.error}
            </div>
          )}
          {!predictStatus?.running && predictStatus?.progress && !predictStatus?.error && (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-100 px-4 py-3 text-xs text-emerald-700">
              <svg className="size-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              {predictStatus.progress}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
