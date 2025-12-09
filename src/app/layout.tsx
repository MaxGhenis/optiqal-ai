import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Optiqal — Quantify Your Choices in Quality-Adjusted Life",
  description:
    "AI-powered QALY estimation. Understand how your lifestyle decisions affect your health and longevity based on the best available causal evidence.",
  keywords: [
    "QALY",
    "quality-adjusted life years",
    "health optimization",
    "lifestyle choices",
    "longevity",
    "evidence-based health",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
