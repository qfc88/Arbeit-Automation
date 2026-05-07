"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
  LineChart, Line, CartesianGrid,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";

// ── Types ────────────────────────────────────────────────────

type Overview = {
  total_jobs: number; with_email: number; with_phone: number;
  with_description: number; with_category: number; avg_quality_score: number;
  unique_companies: number; unique_locations: number;
  email_rate: number; phone_rate: number; description_rate: number;
};
type NameCount = { name: string; count: number };
type DateCount = { date: string; count: number };
type WordCount = { word: string; count: number };
type FieldRate = { field: string; count: number; rate: number };
type QualityData = {
  quality_scores: { score: number; count: number }[];
  completeness: { bucket: string; count: number }[];
};
type ScrapingProgress = {
  total_input_urls: number; jobs_in_database: number;
  sessions: { session_id: string; batch_files: number; total_jobs_in_batches: number; progress_csv_rows: number }[];
};

// ── Palette ──────────────────────────────────────────────────

const COLORS = [
  "#2563eb", "#16a34a", "#ea580c", "#9333ea", "#0891b2",
  "#dc2626", "#ca8a04", "#4f46e5", "#059669", "#e11d48",
  "#7c3aed", "#0284c7", "#d97706", "#be185d", "#15803d",
];

// ── API helpers (client-side fetch) ──────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function api<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

// ── Component ────────────────────────────────────────────────

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [locations, setLocations] = useState<NameCount[]>([]);
  const [jobTypes, setJobTypes] = useState<NameCount[]>([]);
  const [categories, setCategories] = useState<NameCount[]>([]);
  const [quality, setQuality] = useState<QualityData | null>(null);
  const [timeline, setTimeline] = useState<DateCount[]>([]);
  const [companies, setCompanies] = useState<NameCount[]>([]);
  const [keywords, setKeywords] = useState<WordCount[]>([]);
  const [fields, setFields] = useState<FieldRate[]>([]);
  const [progress, setProgress] = useState<ScrapingProgress | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadAll = useCallback(async () => {
    try {
      const [ov, loc, jt, cat, q, tl, co, kw, fc, sp] = await Promise.all([
        api<Overview>("/stats/overview"),
        api<NameCount[]>("/stats/locations?limit=15"),
        api<NameCount[]>("/stats/job-types"),
        api<NameCount[]>("/stats/categories"),
        api<QualityData>("/stats/quality"),
        api<DateCount[]>("/stats/timeline"),
        api<NameCount[]>("/stats/companies?limit=12"),
        api<WordCount[]>("/stats/keywords?limit=40"),
        api<FieldRate[]>("/stats/field-completeness"),
        api<ScrapingProgress>("/stats/scraping-progress"),
      ]);
      setOverview(ov); setLocations(loc); setJobTypes(jt); setCategories(cat);
      setQuality(q); setTimeline(tl); setCompanies(co); setKeywords(kw);
      setFields(fc); setProgress(sp); setLastRefresh(new Date());
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Auto-refresh every 30s
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(loadAll, 30_000);
    return () => clearInterval(id);
  }, [autoRefresh, loadAll]);

  if (!overview) return <p style={{ padding: 40, textAlign: "center" }}>Loading Dashboard...</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0 }}>Web Mining Dashboard</h1>
          <p style={{ color: "#666", margin: "4px 0 0", fontSize: 13 }}>
            Last updated: {lastRefresh.toLocaleTimeString()}
            {autoRefresh ? " · Auto-Refresh 30s" : ""}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={loadAll} style={btnStyle}>⟳ Refresh</button>
          <button onClick={() => setAutoRefresh(!autoRefresh)}
            style={{ ...btnStyle, background: autoRefresh ? "#16a34a" : "#666" }}>
            {autoRefresh ? "Auto ●" : "Auto ○"}
          </button>
        </div>
      </div>

      {/* ── KPI Cards ──────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        <KPI label="Total Jobs" value={overview.total_jobs} />
        <KPI label="Companies" value={overview.unique_companies} />
        <KPI label="Locations" value={overview.unique_locations} />
        <KPI label="Avg Quality" value={`${overview.avg_quality_score}/11`} />
        <KPI label="Email Rate" value={`${overview.email_rate}%`} color={overview.email_rate > 30 ? "#16a34a" : "#ea580c"} />
        <KPI label="Phone Rate" value={`${overview.phone_rate}%`} color={overview.phone_rate > 30 ? "#16a34a" : "#ea580c"} />
        <KPI label="Description" value={`${overview.description_rate}%`} color="#16a34a" />
        <KPI label="ML Categories" value={overview.with_category} />
      </div>

      {/* ── Scraping Progress ──────────────────────────────── */}
      {progress && (
        <Card title="Scraping Progress (Realtime)">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 13, color: "#666" }}>Input URLs</div>
              <div style={{ fontSize: 28, fontWeight: 700 }}>{progress.total_input_urls.toLocaleString()}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: "#666" }}>In Database</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#16a34a" }}>{progress.jobs_in_database.toLocaleString()}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: "#666" }}>Progress</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#2563eb" }}>
                {progress.total_input_urls > 0
                  ? `${Math.round(progress.jobs_in_database / progress.total_input_urls * 100)}%`
                  : "–"}
              </div>
            </div>
          </div>
          {/* Progress bar */}
          <div style={{ background: "#e5e7eb", borderRadius: 8, height: 20, overflow: "hidden" }}>
            <div style={{
              width: `${Math.min(100, progress.total_input_urls > 0 ? progress.jobs_in_database / progress.total_input_urls * 100 : 0)}%`,
              height: "100%", background: "linear-gradient(90deg, #2563eb, #16a34a)",
              borderRadius: 8, transition: "width 0.5s ease",
            }} />
          </div>
          {progress.sessions.length > 0 && (
            <div style={{ marginTop: 12, fontSize: 13, color: "#666" }}>
              {progress.sessions.map(s => (
                <div key={s.session_id}>
                  📁 {s.session_id}: {s.batch_files} Batches, {s.total_jobs_in_batches} Jobs
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ── Scraping Timeline ──────────────────────────────── */}
      {timeline.length > 0 && (
        <Card title="Scraping Timeline (Jobs per Day)">
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* ── Two-col: Locations + Job Types ─────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card title="Top Locations">
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={locations} layout="vertical" margin={{ left: 80 }}>
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={80} />
              <Tooltip />
              <Bar dataKey="count" fill="#2563eb" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Job Types">
          <ResponsiveContainer width="100%" height={350}>
            <PieChart>
              <Pie data={jobTypes} dataKey="count" nameKey="name" cx="50%" cy="50%"
                outerRadius={120} label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}>
                {jobTypes.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* ── Field Completeness Radar ───────────────────────── */}
      <Card title="Data Completeness (11 Required Fields)">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <ResponsiveContainer width="100%" height={350}>
            <RadarChart data={fields.map(f => ({ field: fieldLabel(f.field), rate: f.rate }))}>
              <PolarGrid />
              <PolarAngleAxis dataKey="field" tick={{ fontSize: 11 }} />
              <PolarRadiusAxis domain={[0, 100]} />
              <Radar dataKey="rate" stroke="#2563eb" fill="#2563eb" fillOpacity={0.3} />
              <Tooltip formatter={(v) => [`${v}%`]} />
            </RadarChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, justifyContent: "center" }}>
            {fields.map(f => (
              <div key={f.field} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                <span style={{ width: 120, color: "#666" }}>{fieldLabel(f.field)}</span>
                <div style={{ flex: 1, background: "#e5e7eb", borderRadius: 4, height: 16, overflow: "hidden" }}>
                  <div style={{
                    width: `${f.rate}%`, height: "100%",
                    background: f.rate > 80 ? "#16a34a" : f.rate > 40 ? "#ca8a04" : "#dc2626",
                    borderRadius: 4,
                  }} />
                </div>
                <span style={{ width: 50, textAlign: "right", fontWeight: 600, color: f.rate > 80 ? "#16a34a" : f.rate > 40 ? "#ca8a04" : "#dc2626" }}>
                  {f.rate}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* ── Quality Distribution ───────────────────────────── */}
      {quality && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Card title="Data Quality Score Distribution">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={quality.quality_scores}>
                <XAxis dataKey="score" label={{ value: "Score (0–11)", position: "bottom", offset: -5 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#9333ea" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Completeness Distribution">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={quality.completeness}>
                <XAxis dataKey="bucket" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#0891b2" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}

      {/* ── Top Companies ──────────────────────────────────── */}
      <Card title="Top Companies (by Job Count)">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={companies} layout="vertical" margin={{ left: 120 }}>
            <XAxis type="number" />
            <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={120} />
            <Tooltip />
            <Bar dataKey="count" fill="#ea580c" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* ── Word Cloud (simplified as sized tags) ──────────── */}
      <Card title="Text Mining — Top Keywords from Job Descriptions">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: "8px 0", justifyContent: "center" }}>
          {keywords.map((kw, i) => {
            const maxCount = keywords[0]?.count ?? 1;
            const size = 12 + Math.round((kw.count / maxCount) * 24);
            const opacity = 0.4 + (kw.count / maxCount) * 0.6;
            return (
              <span key={kw.word} style={{
                fontSize: size, fontWeight: size > 24 ? 700 : 400,
                color: COLORS[i % COLORS.length], opacity,
                padding: "2px 6px", cursor: "default",
              }} title={`${kw.count} occurrences`}>
                {kw.word}
              </span>
            );
          })}
        </div>
      </Card>

      {/* ── ML Categories ──────────────────────────────────── */}
      {categories.length > 1 || (categories.length === 1 && categories[0].name !== "Nicht klassifiziert") ? (
        <Card title="ML Categories (Industry Classification)">
          <ResponsiveContainer width="100%" height={350}>
            <PieChart>
              <Pie data={categories} dataKey="count" nameKey="name" cx="50%" cy="50%"
                outerRadius={130} label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}>
                {categories.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      ) : (
        <Card title="ML Categories (Industry Classification)">
          <p style={{ color: "#666", textAlign: "center", padding: 24 }}>
            ⏳ ML model not trained yet. Industry distribution will be shown here after training.
          </p>
        </Card>
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────

function KPI({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e5e5", borderRadius: 8,
      padding: "16px 20px", textAlign: "center",
    }}>
      <div style={{ fontSize: 13, color: "#666", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: color ?? "#1a1a1a" }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e5e5", borderRadius: 8,
      padding: "20px 24px",
    }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, marginTop: 0, marginBottom: 16 }}>{title}</h2>
      {children}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────

const FIELD_LABELS: Record<string, string> = {
  profession: "Profession", salary: "Salary", company_name: "Company",
  location: "Location", start_date: "Start Date", telephone: "Phone",
  email: "Email", job_description: "Description", ref_nr: "Ref No.",
  external_link: "Ext. Link", application_link: "Application Link",
};
function fieldLabel(f: string) { return FIELD_LABELS[f] ?? f; }

const btnStyle: React.CSSProperties = {
  padding: "8px 16px", border: "none", borderRadius: 6,
  background: "#2563eb", color: "#fff", cursor: "pointer",
  fontSize: 13, fontWeight: 600,
};
