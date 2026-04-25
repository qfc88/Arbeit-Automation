import Link from "next/link";

import { listCategories, listJobs } from "@/lib/api";

type Search = {
  q?: string;
  location?: string;
  category?: string;
  page?: string;
};

export default async function HomePage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const page = Number(searchParams.page ?? 1);
  const [{ items, total, limit }, categories] = await Promise.all([
    listJobs({
      q: searchParams.q,
      location: searchParams.location,
      category: searchParams.category,
      page,
    }),
    listCategories(),
  ]);
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <>
      <form
        method="get"
        style={{
          display: "flex",
          gap: "0.5rem",
          marginBottom: "1rem",
          flexWrap: "wrap",
        }}
      >
        <input
          name="q"
          placeholder="Beruf"
          defaultValue={searchParams.q ?? ""}
          style={inputStyle}
        />
        <input
          name="location"
          placeholder="Ort"
          defaultValue={searchParams.location ?? ""}
          style={inputStyle}
        />
        <select
          name="category"
          defaultValue={searchParams.category ?? ""}
          style={{ ...inputStyle, minWidth: 160 }}
        >
          <option value="">Alle Kategorien</option>
          {categories.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} ({c.count})
            </option>
          ))}
        </select>
        <button type="submit" style={buttonStyle}>
          Suchen
        </button>
      </form>

      <p style={{ color: "#666", fontSize: 14 }}>
        {total.toLocaleString("de-DE")} Treffer · Seite {page} / {totalPages}
      </p>

      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {items.map((job) => (
          <li
            key={job.id}
            style={{
              padding: "1rem",
              border: "1px solid #e5e5e5",
              borderRadius: 6,
              marginBottom: "0.75rem",
              background: "#fff",
            }}
          >
            <Link
              href={`/jobs/${job.id}`}
              style={{
                fontWeight: 600,
                color: "#0d47a1",
                textDecoration: "none",
                fontSize: 16,
              }}
            >
              {job.profession}
            </Link>
            <div style={{ color: "#444", fontSize: 14, marginTop: 4 }}>
              {job.company_name}
              {job.location ? ` · ${job.location}` : null}
              {job.job_type ? ` · ${job.job_type}` : null}
            </div>
            {job.predicted_category ? (
              <span
                style={{
                  display: "inline-block",
                  marginTop: 6,
                  padding: "2px 8px",
                  background: "#eef",
                  color: "#0d47a1",
                  borderRadius: 12,
                  fontSize: 12,
                }}
              >
                {job.predicted_category}
                {typeof job.category_confidence === "number"
                  ? ` · ${(job.category_confidence * 100).toFixed(0)}%`
                  : null}
              </span>
            ) : null}
          </li>
        ))}
      </ul>

      {totalPages > 1 ? (
        <nav style={{ marginTop: "1rem" }}>
          {page > 1 ? (
            <Link href={pageHref(searchParams, page - 1)}>← Zurück</Link>
          ) : null}
          {" "}
          {page < totalPages ? (
            <Link href={pageHref(searchParams, page + 1)}>Weiter →</Link>
          ) : null}
        </nav>
      ) : null}
    </>
  );
}

function pageHref(s: Search, page: number) {
  const sp = new URLSearchParams();
  if (s.q) sp.set("q", s.q);
  if (s.location) sp.set("location", s.location);
  if (s.category) sp.set("category", s.category);
  sp.set("page", String(page));
  return `/?${sp.toString()}`;
}

const inputStyle: React.CSSProperties = {
  padding: "0.5rem 0.75rem",
  border: "1px solid #ccc",
  borderRadius: 4,
  fontSize: 14,
};

const buttonStyle: React.CSSProperties = {
  padding: "0.5rem 1rem",
  border: 0,
  borderRadius: 4,
  background: "#0d47a1",
  color: "#fff",
  cursor: "pointer",
  fontSize: 14,
};
