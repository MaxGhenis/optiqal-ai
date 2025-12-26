"use client";

import Link from "next/link";
import { ArrowLeft, Activity, TrendingUp, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// Placeholder - will integrate the existing intervention components
export default function ImprovePage() {
  return (
    <div className="min-h-screen mesh-gradient relative">
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-border/30">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <Activity className="h-6 w-6 text-primary transition-transform group-hover:scale-110" />
            <span className="text-lg font-semibold tracking-tight">optiqal</span>
          </Link>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/predict">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to prediction
            </Link>
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="space-y-8">
          {/* Title */}
          <div className="space-y-2">
            <h1 className="font-serif text-3xl md:text-4xl font-medium">
              How to improve your healthspan
            </h1>
            <p className="text-muted-foreground">
              Evidence-based interventions ranked by impact on your prediction
            </p>
          </div>

          {/* Coming soon placeholder */}
          <Card className="mesh-gradient-card border-border/50">
            <CardContent className="p-12 text-center space-y-4">
              <div className="w-16 h-16 mx-auto rounded-full bg-primary/10 flex items-center justify-center">
                <TrendingUp className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-xl font-medium">Coming soon</h2>
              <p className="text-muted-foreground max-w-md mx-auto">
                We're integrating personalized intervention recommendations based on your profile.
                Check back soon to see which lifestyle changes would have the biggest impact on your healthspan.
              </p>
              <Button asChild className="mt-4">
                <Link href="/predict">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to your prediction
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
