import type { Metadata } from "next";
import "./globals.css";

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
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Optiqal — Rank Your Health Interventions",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Optiqal — Rank Your Health Interventions",
    description:
      "Compare health interventions on a common QALY-informed scale with Bayesian uncertainty and profile-aware estimates.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
