"use client";

import { useEffect, useState, useCallback } from "react";

// ── Types ────────────────────────────────────────────────────

type FilterOption = { label: string; value: string };
type FilterGroup = {
  param: string;
  label: string;
  multi?: boolean;
  options: FilterOption[];
};
type FiltersData = {
  filters: Record<string, FilterGroup>;
  cities: string[];
};
type ScrapeStatus = {
  running: boolean;
  url: string | null;
  filters: Record<string, unknown> | null;
  pages_scraped: number;
  urls_found: number;
  new_urls: number;
  existing_urls: number;
  total_jobs: number;
  error: string | null;
};

type JobScrapeStatus = {
  running: boolean;
  total: number;
  scraped: number;
  failed: number;
  loaded_db: number;
  error: string | null;
};

// ── API ──────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? "/api";

// ── Styles ───────────────────────────────────────────────────

const card: React.CSSProperties = {
  background: "#fff",
  borderRadius: 10,
  padding: "1.25rem",
  boxShadow: "0 1px 3px rgba(0,0,0,.08)",
  marginBottom: "1rem",
};

const label: React.CSSProperties = {
  fontWeight: 600,
  fontSize: 14,
  marginBottom: 6,
  display: "block",
  color: "#374151",
};

const input: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  border: "1px solid #d1d5db",
  borderRadius: 6,
  fontSize: 14,
  boxSizing: "border-box",
};

const select: React.CSSProperties = { ...input };

const btnPrimary: React.CSSProperties = {
  background: "#2563eb",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "10px 28px",
  fontSize: 15,
  fontWeight: 600,
  cursor: "pointer",
};

const btnDanger: React.CSSProperties = {
  ...btnPrimary,
  background: "#dc2626",
};

const tag: React.CSSProperties = {
  display: "inline-block",
  background: "#eff6ff",
  color: "#2563eb",
  borderRadius: 4,
  padding: "2px 8px",
  fontSize: 12,
  marginRight: 4,
  marginBottom: 4,
};

// ── Component ────────────────────────────────────────────────

export default function ScrapePage() {
  const [filtersData, setFiltersData] = useState<FiltersData | null>(null);
  const [status, setStatus] = useState<ScrapeStatus | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [loading, setLoading] = useState(false);

  // Job scraper state
  const [jobStatus, setJobStatus] = useState<JobScrapeStatus | null>(null);
  const [maxJobs, setMaxJobs] = useState("");
  const [jobLoading, setJobLoading] = useState(false);

  // Custom URL mode
  const [customUrl, setCustomUrl] = useState("");

  // Preview info
  const [preview, setPreview] = useState<{
    total_jobs: number;
    existing_urls: number;
    url: string;
  } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Filter selections
  const [was, setWas] = useState("");
  const [wo, setWo] = useState("");
  const [umkreis, setUmkreis] = useState("");
  const [arbeitszeit, setArbeitszeit] = useState<string[]>([]);
  const [veroeffentlichtseit, setVeroeffentlichtseit] = useState("");
  const [befristung, setBefristung] = useState("");
  const [angebotsart, setAngebotsart] = useState("");
  const [sort, setSort] = useState("veroeffdatum");

  // Fetch filter definitions
  useEffect(() => {
    fetch(`${API}/scrape/filters`)
      .then((r) => r.json())
      .then(setFiltersData)
      .catch(console.error);
  }, []);

  // Poll status
  useEffect(() => {
    const poll = setInterval(() => {
      fetch(`${API}/scrape/status`)
        .then((r) => r.json())
        .then(setStatus)
        .catch(console.error);
      fetch(`${API}/scrape/jobs/status`)
        .then((r) => r.json())
        .then(setJobStatus)
        .catch(console.error);
    }, 2000);
    return () => clearInterval(poll);
  }, []);

  // Build filter payload
  const buildPayload = useCallback(() => {
    const payload: Record<string, unknown> = {};
    if (was) payload.was = was;
    if (wo) payload.wo = wo;
    if (umkreis) payload.umkreis = umkreis;
    if (arbeitszeit.length) payload.arbeitszeit = arbeitszeit;
    if (veroeffentlichtseit) payload.veroeffentlichtseit = veroeffentlichtseit;
    if (befristung) payload.befristung = befristung;
    if (angebotsart) payload.angebotsart = angebotsart;
    if (sort) payload.sort = sort;
    return payload;
  }, [was, wo, umkreis, arbeitszeit, veroeffentlichtseit, befristung, angebotsart, sort]);

  // Preview URL
  useEffect(() => {
    if (customUrl) {
      setPreviewUrl(customUrl);
      return;
    }
    const payload = buildPayload();
    fetch(`${API}/scrape/preview-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((d) => setPreviewUrl(d.url))
      .catch(console.error);
  }, [buildPayload, customUrl]);

  const handleStart = async () => {
    setLoading(true);
    try {
      const payload = customUrl
        ? { custom_url: customUrl }
        : buildPayload();
      const res = await fetch(`${API}/scrape/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Failed to start");
      }
    } catch (e) {
      alert("Error starting scrape");
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    await fetch(`${API}/scrape/stop`, { method: "POST" });
  };

  const handlePreview = async () => {
    setPreviewLoading(true);
    setPreview(null);
    try {
      const payload = customUrl ? { custom_url: customUrl } : buildPayload();
      const res = await fetch(`${API}/scrape/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        setPreview(data);
      }
    } catch {
      console.error("Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  };

  // Job scraper handlers
  const handleStartJobs = async () => {
    setJobLoading(true);
    try {
      const payload: Record<string, unknown> = { resume: true };
      if (maxJobs) payload.max_jobs = Number(maxJobs);
      const res = await fetch(`${API}/scrape/jobs/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Failed to start job scraper");
      }
    } catch {
      alert("Error starting job scraper");
    } finally {
      setJobLoading(false);
    }
  };

  const handleStopJobs = async () => {
    await fetch(`${API}/scrape/jobs/stop`, { method: "POST" });
  };

  const toggleArbeitszeit = (val: string) => {
    setArbeitszeit((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val]
    );
  };

  if (!filtersData) return <p>Loading filters…</p>;

  const f = filtersData.filters;
  const isRunning = status?.running ?? false;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>
        Link Scraper
      </h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: "1.25rem" }}>
        Configure filters and start collecting job URLs from arbeitsagentur.de
      </p>

      {/* ── Status Banner ──────────────────────────────────── */}
      {isRunning && (
        <div
          style={{
            ...card,
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <strong style={{ color: "#1d4ed8" }}>⏳ Scraping in progress</strong>
            <div style={{ fontSize: 13, color: "#374151", marginTop: 4 }}>
              Pages: <strong>{status?.pages_scraped}</strong> &nbsp;|&nbsp;
              Total URLs: <strong>{status?.urls_found}</strong> &nbsp;|&nbsp;
              New: <strong style={{ color: "#16a34a" }}>{status?.new_urls ?? 0}</strong> &nbsp;|&nbsp;
              Existing: <strong>{status?.existing_urls ?? 0}</strong>
            </div>
          </div>
          <button style={btnDanger} onClick={handleStop}>
            Stop
          </button>
        </div>
      )}

      {status?.error && !isRunning && (
        <div
          style={{
            ...card,
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#991b1b",
          }}
        >
          <strong>Error:</strong> {status.error}
        </div>
      )}

      {/* ── Custom URL ────────────────────────────────────── */}
      <div style={card}>
        <span style={label}>Custom URL (paste a full arbeitsagentur.de search link)</span>
        <input
          style={input}
          placeholder="https://www.arbeitsagentur.de/jobsuche/suche?..."
          value={customUrl}
          onChange={(e) => setCustomUrl(e.target.value)}
        />
        {customUrl && (
          <p style={{ fontSize: 12, color: "#ea580c", margin: "6px 0 0" }}>
            Custom URL mode — filters below are ignored
          </p>
        )}
      </div>

      {/* ── Filters ────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", opacity: customUrl ? 0.4 : 1, pointerEvents: customUrl ? "none" : "auto" }}>
        {/* Keyword */}
        <div style={card}>
          <span style={label}>Keyword</span>
          <input
            style={input}
            placeholder="e.g. Software Engineer, Pflege…"
            value={was}
            onChange={(e) => setWas(e.target.value)}
          />
        </div>

        {/* Location */}
        <div style={card}>
          <span style={label}>Location</span>
          <input
            list="cities"
            style={input}
            placeholder="City name…"
            value={wo}
            onChange={(e) => setWo(e.target.value)}
          />
          <datalist id="cities">
            {filtersData.cities.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </div>

        {/* Radius */}
        <div style={card}>
          <span style={label}>{f.radius.label}</span>
          <select
            style={select}
            value={umkreis}
            onChange={(e) => setUmkreis(e.target.value)}
          >
            {f.radius.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Published Since */}
        <div style={card}>
          <span style={label}>{f.published_since.label}</span>
          <select
            style={select}
            value={veroeffentlichtseit}
            onChange={(e) => setVeroeffentlichtseit(e.target.value)}
          >
            {f.published_since.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Working Hours */}
        <div style={card}>
          <span style={label}>{f.working_hours.label}</span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {f.working_hours.options.map((o) => (
              <label
                key={o.value}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={arbeitszeit.includes(o.value)}
                  onChange={() => toggleArbeitszeit(o.value)}
                />
                {o.label}
              </label>
            ))}
          </div>
        </div>

        {/* Contract Type */}
        <div style={card}>
          <span style={label}>{f.contract_type.label}</span>
          <select
            style={select}
            value={befristung}
            onChange={(e) => setBefristung(e.target.value)}
          >
            {f.contract_type.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Offer Type */}
        <div style={card}>
          <span style={label}>{f.offer_type.label}</span>
          <select
            style={select}
            value={angebotsart}
            onChange={(e) => setAngebotsart(e.target.value)}
          >
            {f.offer_type.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Sort */}
        <div style={card}>
          <span style={label}>{f.sort_by.label}</span>
          <select
            style={select}
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            {f.sort_by.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── URL Preview + Actions ──────────────────────────── */}
      <div style={{ ...card, marginTop: 4 }}>
        <span style={label}>Generated URL</span>
        <div
          style={{
            background: "#f3f4f6",
            padding: "10px 14px",
            borderRadius: 6,
            fontSize: 13,
            fontFamily: "monospace",
            wordBreak: "break-all",
            marginBottom: 12,
            color: "#1f2937",
          }}
        >
          {previewUrl || "—"}
        </div>

        {/* Preview info */}
        {preview && (
          <div
            style={{
              background: "#fefce8",
              border: "1px solid #fde68a",
              borderRadius: 6,
              padding: "10px 14px",
              marginBottom: 12,
              fontSize: 14,
            }}
          >
            <strong style={{ color: "#92400e" }}>
              {preview.total_jobs.toLocaleString("de-DE")} Jobs
            </strong>{" "}
            gefunden
            <span style={{ color: "#6b7280", marginLeft: 12 }}>
              (≈ {Math.ceil(preview.total_jobs / 25)} pages)
            </span>
            <span style={{ color: "#6b7280", marginLeft: 12 }}>
              | Already collected: <strong>{preview.existing_urls.toLocaleString("de-DE")}</strong> URLs
            </span>
          </div>
        )}

        {/* Active filter tags */}
        <div style={{ marginBottom: 12 }}>
          {was && <span style={tag}>keyword: {was}</span>}
          {wo && <span style={tag}>location: {wo}</span>}
          {umkreis && <span style={tag}>radius: {umkreis} km</span>}
          {arbeitszeit.map((a) => (
            <span key={a} style={tag}>
              {f.working_hours.options.find((o) => o.value === a)?.label ?? a}
            </span>
          ))}
          {veroeffentlichtseit && (
            <span style={tag}>
              {f.published_since.options.find((o) => o.value === veroeffentlichtseit)?.label}
            </span>
          )}
          {befristung && (
            <span style={tag}>
              {f.contract_type.options.find((o) => o.value === befristung)?.label}
            </span>
          )}
          {angebotsart && (
            <span style={tag}>
              {f.offer_type.options.find((o) => o.value === angebotsart)?.label}
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <button
            style={{
              ...btnPrimary,
              background: "#f59e0b",
              opacity: previewLoading || isRunning ? 0.5 : 1,
            }}
            disabled={previewLoading || isRunning}
            onClick={handlePreview}
          >
            {previewLoading ? "Loading…" : "Preview"}
          </button>
          <button
            style={{
              ...btnPrimary,
              opacity: isRunning || loading ? 0.5 : 1,
            }}
            disabled={isRunning || loading}
            onClick={handleStart}
          >
            {loading ? "Starting…" : "Start Scraping"}
          </button>
          {isRunning && (
            <button style={btnDanger} onClick={handleStop}>
              Stop Scraping
            </button>
          )}
        </div>
      </div>

      {/* ── Last Result ────────────────────────────────────── */}
      {!isRunning && status && status.urls_found > 0 && !status.error && (
        <div
          style={{
            ...card,
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
          }}
        >
          <strong style={{ color: "#166534" }}>✓ Last scrape completed</strong>
          <div style={{ fontSize: 13, color: "#374151", marginTop: 4 }}>
            Pages: <strong>{status.pages_scraped}</strong> &nbsp;|&nbsp;
            Total URLs: <strong>{status.urls_found}</strong> &nbsp;|&nbsp;
            New this run: <strong style={{ color: "#16a34a" }}>{status.new_urls ?? 0}</strong>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════ */}
      {/* Phase 2: Job Detail Scraper                           */}
      {/* ══════════════════════════════════════════════════════ */}
      <hr style={{ border: "none", borderTop: "2px solid #e5e7eb", margin: "2rem 0 1.5rem" }} />

      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>
        Job Detail Scraper
      </h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: "1.25rem" }}>
        Scrape full job details from collected URLs and save to database in real-time
      </p>

      {/* Job scraper status banner */}
      {jobStatus?.running && (
        <div
          style={{
            ...card,
            background: "#faf5ff",
            border: "1px solid #e9d5ff",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <strong style={{ color: "#7c3aed" }}>⏳ Scraping job details…</strong>
            <div style={{ fontSize: 13, color: "#374151", marginTop: 4 }}>
              Progress: <strong>{jobStatus.scraped}</strong> / {jobStatus.total} scraped
              &nbsp;|&nbsp; Failed: <strong>{jobStatus.failed}</strong>
              &nbsp;|&nbsp; Saved to DB: <strong style={{ color: "#16a34a" }}>{jobStatus.loaded_db}</strong>
            </div>
            {/* Progress bar */}
            {jobStatus.total > 0 && (
              <div style={{ background: "#e5e7eb", borderRadius: 6, height: 12, marginTop: 8, overflow: "hidden", width: "100%" }}>
                <div
                  style={{
                    width: `${Math.min(100, (jobStatus.scraped / jobStatus.total) * 100)}%`,
                    height: "100%",
                    background: "linear-gradient(90deg, #7c3aed, #16a34a)",
                    borderRadius: 6,
                    transition: "width 0.5s ease",
                  }}
                />
              </div>
            )}
          </div>
          <button style={btnDanger} onClick={handleStopJobs}>
            Stop
          </button>
        </div>
      )}

      {jobStatus?.error && !jobStatus.running && (
        <div
          style={{
            ...card,
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#991b1b",
          }}
        >
          <strong>Error:</strong> {jobStatus.error}
        </div>
      )}

      {/* Job scraper controls */}
      <div style={card}>
        <div style={{ display: "flex", gap: "1rem", alignItems: "flex-end", flexWrap: "wrap" }}>
          <div>
            <span style={label}>Max jobs (optional)</span>
            <input
              style={{ ...input, width: 140 }}
              type="number"
              placeholder="All"
              value={maxJobs}
              onChange={(e) => setMaxJobs(e.target.value)}
            />
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <button
              style={{
                ...btnPrimary,
                background: "#7c3aed",
                opacity: jobStatus?.running || jobLoading ? 0.5 : 1,
              }}
              disabled={jobStatus?.running || jobLoading}
              onClick={handleStartJobs}
            >
              {jobLoading ? "Starting…" : "Start Job Scraper"}
            </button>
            {jobStatus?.running && (
              <button style={btnDanger} onClick={handleStopJobs}>
                Stop
              </button>
            )}
          </div>
        </div>
        <p style={{ fontSize: 12, color: "#6b7280", marginTop: 8, marginBottom: 0 }}>
          Reads URLs from job_urls.csv → scrapes each job detail → inserts into database.
          Results appear on Dashboard and Job Listings in real-time.
        </p>
      </div>

      {/* Job scraper last result */}
      {!jobStatus?.running && jobStatus && jobStatus.scraped > 0 && !jobStatus.error && (
        <div
          style={{
            ...card,
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
          }}
        >
          <strong style={{ color: "#166534" }}>✓ Job scraping completed</strong>
          <div style={{ fontSize: 13, color: "#374151", marginTop: 4 }}>
            Scraped: <strong>{jobStatus.scraped}</strong>
            &nbsp;|&nbsp; Failed: <strong>{jobStatus.failed}</strong>
            &nbsp;|&nbsp; Loaded to DB: <strong>{jobStatus.loaded_db}</strong>
          </div>
        </div>
      )}
    </div>
  );
}
