import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Deutsch DE — Job Listings",
  description: "Web Mining — German Job Market Analysis",
};

const navItems = [
  { href: "/", label: "Job Listings" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/scrape", label: "Scraper" },
  { href: "/skills", label: "Skills" },
  { href: "/ml", label: "ML" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-slate-50 text-slate-900 antialiased min-h-screen">
        <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-sm">
          <div className="mx-auto max-w-7xl px-4 flex items-center gap-6 h-14">
            <Link href="/" className="flex items-center gap-2 font-bold text-slate-900 shrink-0">
              <span className="size-7 rounded-lg bg-blue-600 text-white text-xs font-bold grid place-items-center">
                DE
              </span>
              Deutsch DE
            </Link>
            <nav className="flex gap-1">
              {navItems.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="px-3 py-1.5 rounded-md text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
