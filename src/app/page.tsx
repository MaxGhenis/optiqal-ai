import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { LogoLockup } from "@/components/brand/logo";
import {
  ArrowRight,
  Sparkles,
  Clock3,
  FlaskConical,
  Shield,
  Pill,
  BarChart3,
  BookOpen,
  Target,
} from "lucide-react";
import { MobileNav } from "@/components/mobile-nav";

const focusAreas = [
  {
    icon: Clock3,
    title: "Sleep extension",
    detail: "Boring, high-value, often under-prioritized.",
    value: "+0.18 expected QALYs",
  },
  {
    icon: FlaskConical,
    title: "ApoB reduction",
    detail: "A classic example of something clinically strong but easy to ignore.",
    value: "81% probability of benefit",
  },
  {
    icon: Shield,
    title: "Daily sunscreen",
    detail: "Small habit, asymmetric upside, minimal burden.",
    value: "Low burden, durable gain",
  },
  {
    icon: Pill,
    title: "Supplement swaps",
    detail: "Where Bayesian shrinkage matters most.",
    value: "Avoid expensive noise",
  },
] as const;

const outputs = [
  {
    title: "Expected value",
    body: "How much net QALY gain the intervention is worth for you, not for an abstract population average.",
  },
  {
    title: "Probability of benefit",
    body: "A clearer question than “is this good?” - how likely is it to help at all?",
  },
  {
    title: "Downside risk",
    body: "Harms, fragility, and reversibility belong in the same frame as upside.",
  },
  {
    title: "Burden and cost",
    body: "The best move is not always the biggest effect. It is the best tradeoff.",
  },
] as const;

const steps = [
  {
    title: "Build your baseline",
    body: "Start with profile, habits, conditions, and the stack you already run.",
  },
  {
    title: "Estimate the posterior",
    body: "Combine priors, published evidence, uncertainty, and profile fit into a net distribution.",
  },
  {
    title: "Rank the next move",
    body: "Compare additions, removals, and swaps on one explicit decision surface.",
  },
] as const;

function DecisionBoard() {
  return (
    <Card className="decision-card card-highlight hover-lift">
      <CardContent className="p-0">
        <div className="border-b border-border/80 px-6 py-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-primary mb-2">
                Decision board
              </p>
              <h2 className="font-serif text-3xl font-semibold leading-tight">
                What is most worth doing next?
              </h2>
            </div>
            <span className="data-pill">Personalized</span>
          </div>
        </div>

        <div className="space-y-3 px-6 py-5">
          {[
            {
              rank: "01",
              title: "Add 45 minutes of sleep",
              expected: "+0.18",
              probability: "72%",
              burden: "Moderate",
            },
            {
              rank: "02",
              title: "Push ApoB below 60",
              expected: "+0.14",
              probability: "81%",
              burden: "Medium",
            },
            {
              rank: "03",
              title: "Make sunscreen daily",
              expected: "+0.05",
              probability: "88%",
              burden: "Low",
            },
          ].map((item) => (
            <div
              key={item.rank}
              className="surface-panel-soft rounded-2xl p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex gap-4">
                  <div className="text-xs font-mono text-muted-foreground pt-1">
                    {item.rank}
                  </div>
                  <div>
                    <h3 className="font-medium text-[1.02rem]">{item.title}</h3>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className="data-pill">E[Δ] {item.expected} QALYs</span>
                      <span className="data-pill">P(benefit) {item.probability}</span>
                      <span className="data-pill">Burden {item.burden}</span>
                    </div>
                  </div>
                </div>
                <Target className="h-4 w-4 text-primary mt-1" />
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-border/80 px-6 py-4 text-sm text-muted-foreground">
          Same unit. Different actions. Explicit tradeoffs.
        </div>
      </CardContent>
    </Card>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen mesh-gradient paper-grid relative overflow-hidden">
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      <div className="pointer-events-none absolute left-[-8rem] top-24 h-72 w-72 rounded-full bg-primary/10 blur-[100px]" />
      <div className="pointer-events-none absolute right-[-6rem] top-40 h-80 w-80 rounded-full bg-accent/10 blur-[110px]" />

      <header className="fixed top-0 left-0 right-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <LogoLockup
              size="sm"
              markClassName="transition-transform group-hover:scale-[1.04]"
            />
          </Link>

          <nav className="hidden sm:flex items-center gap-2">
            <Button
              variant="ghost"
              className="text-muted-foreground hover:text-foreground"
              asChild
            >
              <Link href="#how-it-works">How it works</Link>
            </Button>
            <Button
              className="btn-glow bg-primary text-primary-foreground hover:bg-primary/95"
              asChild
            >
              <Link href="/analyze">
                Start analysis
                <Sparkles className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
          </nav>

          <div className="sm:hidden">
            <MobileNav />
          </div>
        </div>
      </header>

      <main className="relative z-10">
        <section className="px-4 sm:px-6 pt-28 sm:pt-36 pb-18 sm:pb-24">
          <div className="max-w-6xl mx-auto grid lg:grid-cols-[1.05fr_0.95fr] gap-10 lg:gap-14 items-center">
            <div className="space-y-8 opacity-0 animate-slide-up">
              <div className="section-chip">
                <BarChart3 className="h-4 w-4" />
                Bayesian health decision engine
              </div>

              <div className="space-y-5">
                <h1 className="font-serif text-5xl sm:text-6xl lg:text-7xl font-semibold leading-[0.98] tracking-[-0.04em] max-w-3xl">
                  Stop collecting health advice.
                  <span className="block gradient-text">
                    Start ranking it.
                  </span>
                </h1>

                <p className="max-w-2xl text-lg sm:text-xl text-muted-foreground leading-relaxed">
                  Optiqal compares sleep, exercise, lipids, supplements,
                  sunscreen, and other interventions on one common decision
                  surface so you can see what is actually worth doing next.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <span className="data-pill">Expected net QALY delta</span>
                <span className="data-pill">Probability of benefit</span>
                <span className="data-pill">Downside tail risk</span>
                <span className="data-pill">Burden and cost</span>
              </div>

              <div className="flex flex-wrap gap-4 pt-2">
                <Button
                  size="lg"
                  className="btn-glow bg-primary text-primary-foreground hover:bg-primary/95 h-12 px-8 text-base"
                  asChild
                >
                  <Link href="/analyze">
                    Open analyzer
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  className="h-12 px-8 text-base border-primary/15 bg-surface-panel/70 hover:bg-surface-panel"
                  asChild
                >
                  <Link href="#how-it-works">See the logic</Link>
                </Button>
              </div>
            </div>

            <div className="opacity-0 animate-scale-in delay-200">
              <DecisionBoard />
            </div>
          </div>
        </section>

        <section className="px-4 sm:px-6 py-16 sm:py-20">
          <div className="max-w-6xl mx-auto">
            <div className="flex items-end justify-between gap-6 mb-10">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-primary mb-3">
                  Common unit, different actions
                </p>
                <h2 className="font-serif text-3xl md:text-4xl font-semibold tracking-[-0.03em]">
                  The product is memorable if the comparisons are.
                </h2>
              </div>
              <div className="hidden md:block text-sm text-muted-foreground max-w-sm">
                People do not need one more dashboard. They need a way to stack
                unlike health moves against each other.
              </div>
            </div>

            <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
              {focusAreas.map((item, index) => (
                <Card
                  key={item.title}
                  className="mesh-gradient-card card-highlight hover-lift opacity-0 animate-slide-up"
                  style={{ animationDelay: `${(index + 1) * 100}ms` }}
                >
                  <CardContent className="p-6 space-y-5">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 border border-primary/12">
                      <item.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div className="space-y-2">
                      <h3 className="font-medium text-lg">{item.title}</h3>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {item.detail}
                      </p>
                    </div>
                    <div className="editorial-rule" />
                    <div className="text-sm font-medium text-primary">
                      {item.value}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section id="how-it-works" className="px-4 sm:px-6 py-16 sm:py-20">
          <div className="max-w-6xl mx-auto">
            <div className="mb-10">
              <p className="text-xs uppercase tracking-[0.24em] text-primary mb-3">
                Workflow
              </p>
              <h2 className="font-serif text-3xl md:text-4xl font-semibold tracking-[-0.03em]">
                Structured enough to trust, simple enough to use.
              </h2>
            </div>

            <div className="grid md:grid-cols-3 gap-4">
              {steps.map((step, index) => (
                <Card
                  key={step.title}
                  className="decision-card hover-lift opacity-0 animate-slide-up"
                  style={{ animationDelay: `${(index + 1) * 100}ms` }}
                >
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold">
                        0{index + 1}
                      </div>
                      <h3 className="font-medium text-lg">{step.title}</h3>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {step.body}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="px-4 sm:px-6 py-16 sm:py-20">
          <div className="max-w-6xl mx-auto grid lg:grid-cols-[0.92fr_1.08fr] gap-8 lg:gap-12 items-start">
            <div className="space-y-6">
              <p className="text-xs uppercase tracking-[0.24em] text-primary">
                What you actually get
              </p>
              <h2 className="font-serif text-3xl md:text-4xl font-semibold tracking-[-0.03em]">
                Not a vibe. A decision card.
              </h2>
              <p className="text-lg text-muted-foreground leading-relaxed">
                The interface should make it obvious why one action ranks above
                another and how fragile that ranking is.
              </p>
              <div className="rounded-3xl border border-primary/12 bg-card/80 p-6 shadow-[0_24px_56px_-40px_rgba(28,52,48,0.28)]">
                <div className="flex items-center gap-3 mb-4">
                  <BookOpen className="h-5 w-5 text-primary" />
                  <h3 className="font-medium">App for decisions, paper for methods</h3>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  The product should feel operational and comparative. The
                  manuscript should handle methodology, limitations, and
                  citations in full.
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              {outputs.map((item, index) => (
                <Card
                  key={item.title}
                  className="mesh-gradient-card hover-lift opacity-0 animate-scale-in"
                  style={{ animationDelay: `${(index + 1) * 100}ms` }}
                >
                  <CardContent className="p-6">
                    <p className="text-xs uppercase tracking-[0.2em] text-primary mb-3">
                      0{index + 1}
                    </p>
                    <h3 className="font-medium text-xl mb-3">{item.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {item.body}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="px-4 sm:px-6 py-18 sm:py-24">
          <div className="max-w-5xl mx-auto">
            <Card className="decision-card border-primary/18 card-highlight overflow-hidden">
              <CardContent className="p-8 sm:p-10">
                <div className="grid lg:grid-cols-[1fr_auto] gap-8 items-end">
                  <div className="space-y-5">
                    <p className="text-xs uppercase tracking-[0.24em] text-primary">
                      Ready to pressure test it?
                    </p>
                    <h2 className="font-serif text-4xl sm:text-5xl font-semibold tracking-[-0.04em] leading-[1.02]">
                      Rank the next health move before you buy the next stack.
                    </h2>
                    <p className="max-w-2xl text-lg text-muted-foreground leading-relaxed">
                      Use the analyzer to compare actions, not just admire a
                      score. That is where the product becomes useful.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <Button
                      size="lg"
                      className="btn-glow bg-primary text-primary-foreground hover:bg-primary/95 h-12 px-8"
                      asChild
                    >
                      <Link href="/analyze">
                        Start analysis
                        <Sparkles className="ml-2 h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>
      </main>
    </div>
  );
}
