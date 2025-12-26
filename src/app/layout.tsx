import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Optiqal — Understand Your Healthspan",
  description:
    "Explore how lifestyle factors affect life expectancy and quality of life. Educational estimates based on published research and actuarial data.",
  keywords: [
    "QALY",
    "quality-adjusted life years",
    "life expectancy calculator",
    "healthspan",
    "longevity",
    "actuarial data",
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
