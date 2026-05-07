import Link from "next/link";
import { notFound } from "next/navigation";

import { getJob } from "@/lib/api";

export default async function JobPage({
  params,
}: {
  params: { id: string };
}) {
  let job;
  try {
    job = await getJob(params.id);
  } catch {
    notFound();
  }

  return (
    <article>
      <Link href="/" style={{ color: "#666", fontSize: 14 }}>
        ← Back to Search
      </Link>
      <h1 style={{ marginTop: 12 }}>{job.profession}</h1>
      <p style={{ color: "#444", marginTop: -8 }}>
        {job.company_name}
        {job.location ? ` · ${job.location}` : null}
      </p>

      <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.25rem 1rem", fontSize: 14 }}>
        {job.salary ? (<><dt style={dt}>Salary</dt><dd>{job.salary}</dd></>) : null}
        {job.job_type ? (<><dt style={dt}>Job Type</dt><dd>{job.job_type}</dd></>) : null}
        {job.predicted_category ? (<><dt style={dt}>Category</dt><dd>{job.predicted_category}</dd></>) : null}
        {job.email ? (<><dt style={dt}>Email</dt><dd><a href={`mailto:${job.email}`}>{job.email}</a></dd></>) : null}
        {job.telephone ? (<><dt style={dt}>Phone</dt><dd>{job.telephone}</dd></>) : null}
        {job.application_link ? (
          <><dt style={dt}>Application</dt><dd><a href={job.application_link} target="_blank" rel="noreferrer">Apply directly</a></dd></>
        ) : null}
        {job.ref_nr ? (<><dt style={dt}>Ref No.</dt><dd>{job.ref_nr}</dd></>) : null}
      </dl>

      {job.job_description ? (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>Description</h2>
          <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
            {job.job_description}
          </p>
        </section>
      ) : null}
    </article>
  );
}

const dt: React.CSSProperties = { color: "#666", fontWeight: 500 };
