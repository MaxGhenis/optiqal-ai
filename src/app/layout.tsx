import type { Metadata } from "next";
import Link from "next/link";
import { MedicalDisclaimer } from "@/components/medical-disclaimer";
import "./globals.css";

const FOOTER_LINKS: { href: string; label: string; external?: boolean }[] = [
  { href: "/about", label: "About" },
  { href: "/faq", label: "FAQ" },
  { href: "/predict", label: "Predict" },
  { href: "/analyze", label: "Analyze" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
  {
    href: "https://github.com/MaxGhenis/optiqal-ai",
    label: "GitHub",
    external: true,
  },
];

export const metadata: Metadata = {
  title: "Optiqal — Rank Your Health Interventions",
  description:
    "Compare health interventions on a common QALY-informed scale with Bayesian uncertainty and profile-aware estimates.",
  keywords: [
    "QALY",
    "quality-adjusted life years",
    "health intervention ranking",
    "healthspan",
    "longevity",
    "actuarial data",
  ],
  metadataBase: new URL("https://optiqal.ai"),
  openGraph: {
    title: "Optiqal — Rank Your Health Interventions",
    description:
      "Compare health interventions on a common QALY-informed scale with Bayesian uncertainty and profile-aware estimates.",
    url: "https://optiqal.ai",
    siteName: "Optiqal",
    // Images are supplied by the file-based opengraph-image.tsx / twitter-image.tsx
    // routes. Do not set `images` here — an explicit override takes precedence
    // over the generated routes and would point at a non-existent /og-image.png.
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Optiqal — Rank Your Health Interventions",
    description:
      "Compare health interventions on a common QALY-informed scale with Bayesian uncertainty and profile-aware estimates.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // base.css sets smooth scrolling; Next.js needs the attribute declared to
    // suppress it during route transitions.
    <html lang="en" data-scroll-behavior="smooth">
      <body className="antialiased">
        {children}
        <footer className="relative z-10 border-t border-border/40 bg-surface-panel/60">
          <nav
            aria-label="Footer"
            className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-x-6 gap-y-2 px-6 pt-6 text-sm text-muted-foreground"
          >
            {FOOTER_LINKS.map((link) =>
              link.external ? (
                <a
                  key={link.href}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="transition-colors hover:text-foreground"
                >
                  {link.label}
                </a>
              ) : (
                <Link
                  key={link.href}
                  href={link.href}
                  className="transition-colors hover:text-foreground"
                >
                  {link.label}
                </Link>
              )
            )}
          </nav>
          <MedicalDisclaimer variant="compact" className="mx-auto max-w-7xl" />
        </footer>
      </body>
    </html>
  );
}
