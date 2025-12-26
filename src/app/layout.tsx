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
  metadataBase: new URL("https://optiqal.ai"),
  openGraph: {
    title: "Optiqal — Understand Your Healthspan",
    description:
      "Explore how lifestyle factors affect life expectancy and quality of life. Educational estimates based on published research and actuarial data.",
    url: "https://optiqal.ai",
    siteName: "Optiqal",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Optiqal — Understand Your Healthspan",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Optiqal — Understand Your Healthspan",
    description:
      "Explore how lifestyle factors affect life expectancy and quality of life. Educational estimates based on published research and actuarial data.",
    images: ["/og-image.png"],
  },
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
