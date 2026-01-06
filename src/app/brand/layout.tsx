import Link from "next/link";
import { ArrowLeft, Activity } from "lucide-react";

export const metadata = {
  title: "Brand — Optiqal",
  description: "Optiqal brand guidelines, design system, and writing standards",
};

export default function BrandLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen mesh-gradient relative overflow-hidden">
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="relative">
                <Activity className="h-7 w-7 text-primary transition-transform group-hover:scale-110" />
                <div className="absolute inset-0 bg-primary/30 blur-lg opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <span className="text-xl font-semibold tracking-tight">optiqal</span>
            </Link>
            <span className="text-border">/</span>
            <Link
              href="/brand"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Brand
            </Link>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to home
          </Link>
        </div>
      </header>

      <div className="pt-24 pb-16 relative">{children}</div>
    </main>
  );
}
