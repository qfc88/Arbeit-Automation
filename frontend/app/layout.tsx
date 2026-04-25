import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Deutsch DE — Stellenangebote",
  description: "Aggregierte deutsche Stellenangebote",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          margin: 0,
          background: "#fafafa",
          color: "#1a1a1a",
        }}
      >
        <header
          style={{
            background: "#1a1a1a",
            color: "#fff",
            padding: "0.75rem 1.25rem",
          }}
        >
          <strong>Deutsch DE Jobs</strong>
        </header>
        <main style={{ maxWidth: 960, margin: "1.5rem auto", padding: "0 1rem" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
