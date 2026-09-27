import Link from "next/link";
import { ArrowRight, Pill } from "lucide-react";
import { LogoLockup } from "@/components/brand/logo";
import { MobileNav } from "@/components/mobile-nav";
import { Button } from "@/components/ui/button";

const rankedResults = [
  {
    rank: "01",
    name: "HIIT 2x/week",
    category: "Exercise",
    days: "+6.4",
    probability: "Fixed scenario",
    annualCost: "$0",
    prescription: false,
  },
  {
    rank: "02",
    name: "Strength maintenance",
    category: "Exercise",
    days: "+0.9",
    probability: "Fixed scenario",
    annualCost: "$0",
    prescription: false,
  },
  {
    rank: "03",
    name: "Statin",
    category: "Medication",
    days: "+142.0",
    probability: "91%",
    annualCost: "$120",
    prescription: true,
  },
] as const;

const rankingSteps = [
  {
    number: "01",
    title: "Set the baseline",
    body: "Add the profile and risk factors that shape which options fit.",
  },
  {
    number: "02",
    title: "Review the first pass",
    body: "Compare quality-adjusted days, benefit probability, harms, and cost on one scale.",
  },
  {
    number: "03",
    title: "Re-rank what is next",
    body: "Mark what you already do, account for overlap, and reveal the next addition.",
  },
] as const;

function RankedResultPreview() {
  return (
    <div className="surface-panel overflow-hidden rounded-[2rem] opacity-0 animate-scale-in delay-200">
      <div className="flex flex-col gap-5 border-b border-border/80 px-5 py-5 sm:flex-row sm:items-end sm:justify-between sm:px-7 sm:py-6">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-primary">
            Illustrative ranking
          </p>
          <h2 className="font-serif text-2xl font-semibold tracking-[-0.025em] sm:text-3xl">
            Most worth doing next
          </h2>
        </div>
        <p className="max-w-[18rem] text-sm leading-relaxed text-muted-foreground sm:text-right">
          Stylized higher-risk profile
        </p>
      </div>

      <div className="hidden grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,0.65fr))] gap-4 border-b border-border/60 px-7 py-3 text-[0.68rem] font-medium uppercase tracking-[0.14em] text-muted-foreground sm:grid">
        <span>Next move</span>
        <span>Quality-adjusted days</span>
        <span>Net-benefit model</span>
        <span>Annual cost</span>
      </div>

      <ol>
        {rankedResults.map((result) => (
          <li
            key={result.rank}
            className="border-b border-border/60 px-5 py-5 last:border-b-0 sm:grid sm:grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,0.65fr))] sm:items-center sm:gap-4 sm:px-7"
          >
            <div className="flex items-start gap-4">
              <span className="pt-0.5 font-mono text-xs text-muted-foreground">
                {result.rank}
              </span>
              <div className="min-w-0">
                <p className="font-medium leading-snug">{result.name}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {result.category}
                  </span>
                  {result.prescription ? (
                    <span className="inline-flex items-center gap-1 text-[0.68rem] font-medium text-highlight">
                      <Pill aria-hidden="true" className="h-3 w-3" />
                      Prescription · clinician required
                    </span>
                  ) : null}
                </div>
              </div>
            </div>

            <dl className="mt-5 grid grid-cols-3 gap-3 sm:contents">
              <div>
                <dt className="text-[0.64rem] font-medium uppercase tracking-[0.12em] text-muted-foreground sm:sr-only">
                  Quality-adjusted days
                </dt>
                <dd className="mt-1 font-mono text-sm font-medium tabular-nums text-foreground sm:mt-0 sm:text-base">
                  {result.days}
                </dd>
              </div>
              <div>
                <dt className="text-[0.64rem] font-medium uppercase tracking-[0.12em] text-muted-foreground sm:sr-only">
                  Net-benefit model
                </dt>
                <dd className="mt-1 font-mono text-sm font-medium tabular-nums text-foreground sm:mt-0 sm:text-base">
                  {result.probability}
                </dd>
              </div>
              <div>
                <dt className="text-[0.64rem] font-medium uppercase tracking-[0.12em] text-muted-foreground sm:sr-only">
                  Annual cost
                </dt>
                <dd className="mt-1 font-mono text-sm font-medium tabular-nums text-foreground sm:mt-0 sm:text-base">
                  {result.annualCost}
                </dd>
              </div>
            </dl>
          </li>
        ))}
      </ol>

      <div className="border-t border-border/80 bg-surface-panel-soft/70 px-5 py-4 sm:px-7">
        <p className="text-xs leading-relaxed text-muted-foreground">
          Ordered by marginal cost per quality-adjusted life year, not by days alone. Exercise rows use fixed scenario assumptions; medication uncertainty is simulated. Values are illustrative and can change with model releases.
        </p>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen overflow-hidden bg-background text-foreground">
      <header className="fixed inset-x-0 top-0 z-50 glass border-b border-border/30">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="group flex items-center gap-2.5">
            <LogoLockup
              size="sm"
              markClassName="transition-transform group-hover:scale-[1.04]"
            />
          </Link>

          <nav className="hidden items-center gap-2 sm:flex">
            <Button
              variant="ghost"
              className="text-muted-foreground hover:text-foreground"
              asChild
            >
              <Link href="#how-it-works">How it works</Link>
            </Button>
            <Button
              variant="ghost"
              className="text-muted-foreground hover:text-foreground"
              asChild
            >
              <Link href="/about">About</Link>
            </Button>
            <Button
              variant="ghost"
              className="text-muted-foreground hover:text-foreground"
              asChild
            >
              <Link href="/faq">FAQ</Link>
            </Button>
            <Button
              className="btn-glow bg-primary text-primary-foreground hover:bg-primary/95"
              asChild
            >
              <Link href="/analyze">
                Start analysis
                <ArrowRight className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
          </nav>

          <div className="sm:hidden">
            <MobileNav />
          </div>
        </div>
      </header>

      <main>
        <section className="mesh-gradient paper-grid relative min-h-[calc(100svh-4.5rem)] px-4 pb-20 pt-28 sm:px-6 sm:pb-24 sm:pt-36">
          <div className="noise-overlay pointer-events-none absolute inset-0" />
          <div className="pointer-events-none absolute left-[-10rem] top-24 h-80 w-80 rounded-full bg-primary/10 blur-[110px]" />
          <div className="pointer-events-none absolute right-[-8rem] top-40 h-80 w-80 rounded-full bg-accent/10 blur-[120px]" />

          <div className="relative z-10 mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[0.82fr_1.18fr] lg:gap-16">
            <div className="opacity-0 animate-slide-up">
              <p className="mb-5 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                Health decisions, ranked
              </p>
              <h1 className="max-w-xl font-serif text-5xl font-semibold leading-[0.98] tracking-[-0.045em] sm:text-6xl lg:text-[4.6rem]">
                Optiqal ranks which health addition comes next.
              </h1>
              <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted-foreground sm:text-xl">
                Compare health interventions by quality-adjusted days,
                modeled net benefit, and annual cost.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Button
                  size="lg"
                  className="btn-glow h-12 bg-primary px-7 text-base text-primary-foreground hover:bg-primary/95"
                  asChild
                >
                  <Link href="/analyze">
                    Rank my next move
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button
                  variant="ghost"
                  size="lg"
                  className="h-12 px-4 text-base text-muted-foreground hover:text-foreground"
                  asChild
                >
                  <Link href="#how-it-works">How the ranking works</Link>
                </Button>
              </div>

              <p className="mt-7 max-w-md border-l border-primary/25 pl-4 text-sm leading-relaxed text-muted-foreground">
                The ranking updates with your baseline and current stack, so it
                reflects marginal value rather than generic advice.
              </p>
            </div>

            <RankedResultPreview />
          </div>
        </section>

        <section id="how-it-works" className="px-4 py-20 sm:px-6 sm:py-28">
          <div className="mx-auto max-w-6xl">
            <div className="grid gap-10 border-b border-border pb-12 lg:grid-cols-[0.7fr_1.3fr] lg:items-end">
              <div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-primary">
                  How it works
                </p>
                <h2 className="font-serif text-4xl font-semibold tracking-[-0.035em] sm:text-5xl">
                  One question. Three passes.
                </h2>
              </div>
              <p className="max-w-2xl text-lg leading-relaxed text-muted-foreground lg:justify-self-end">
                Optiqal turns your baseline, the evidence, and the cost of each
                option into an ordered next-step list.
              </p>
            </div>

            <ol className="grid md:grid-cols-3">
              {rankingSteps.map((step) => (
                <li
                  key={step.number}
                  className="border-b border-border py-9 last:border-b-0 md:border-b-0 md:border-r md:px-8 md:first:pl-0 md:last:border-r-0 md:last:pr-0"
                >
                  <p className="font-mono text-xs text-primary">{step.number}</p>
                  <h3 className="mt-5 text-xl font-semibold">{step.title}</h3>
                  <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted-foreground">
                    {step.body}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="bg-primary px-4 py-16 text-primary-foreground sm:px-6 sm:py-20">
          <div className="mx-auto flex max-w-6xl flex-col gap-8 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-primary-foreground/70">
                Your ranking
              </p>
              <h2 className="max-w-2xl font-serif text-4xl font-semibold leading-tight tracking-[-0.035em] sm:text-5xl">
                See what rises to the top for you.
              </h2>
            </div>
            <Button
              size="lg"
              className="h-12 shrink-0 bg-surface-panel px-7 text-base text-primary hover:bg-surface-panel/90"
              asChild
            >
              <Link href="/analyze">
                Start analysis
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </section>
      </main>

    </div>
  );
}
