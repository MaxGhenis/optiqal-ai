import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "About — Optiqal",
  description: "Learn about Optiqal and how it ranks health interventions using QALYs, Bayesian uncertainty, and profile-aware estimates",
};

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="max-w-3xl mx-auto px-4 py-12">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to home
        </Link>

        <h1 className="text-3xl font-bold mb-8">About Optiqal</h1>

        <div className="prose prose-invert prose-sm max-w-none space-y-6">
          <section>
            <h2 className="text-xl font-semibold mb-3">What is Optiqal?</h2>
            <p className="text-muted-foreground leading-relaxed">
              Optiqal is a health decision tool that ranks interventions using
              Quality-Adjusted Life Years (QALYs), Bayesian uncertainty, and
              profile-aware estimates. The goal is not just to estimate
              healthspan in the abstract, but to help you compare unlike
              choices on one explicit scale.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-3">
              QALYs weight years of life by health quality, where 1 QALY represents one year lived
              in perfect health. That framework lets Optiqal compare actions
              that would otherwise be hard to stack against each other, such as
              sleep, exercise, lipid lowering, and supplements.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Data Sources</h2>
            <p className="text-muted-foreground leading-relaxed">
              Our estimates are built on peer-reviewed research and official statistics:
            </p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4 mt-3">
              <li>
                <strong className="text-foreground">CDC Life Tables</strong> — U.S. mortality data
                providing baseline life expectancy by age and sex
              </li>
              <li>
                <strong className="text-foreground">Global Burden of Disease (GBD) 2019</strong> —
                Risk factor relative risks and population attributable fractions
              </li>
              <li>
                <strong className="text-foreground">Published Meta-Analyses and Trials</strong> —
                Peer-reviewed studies on interventions and health outcomes
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Statistical Methods</h2>
            <p className="text-muted-foreground leading-relaxed">
              Optiqal estimates the incremental health impact of interventions
              against your profile rather than presenting a generic score. We
              use simulation to propagate uncertainty through the model and show
              the limits of current research. Weak evidence is handled with
              priors and shrinkage rather than hard buckets, so fragile claims
              move closer to zero and carry wider tails instead of being given
              false precision.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-3">
              <strong className="text-foreground">Not medical advice.</strong>{" "}
              Our estimates are statistical, not clinical. They show what
              research suggests for someone with your profile but cannot account
              for your complete medical history. Discuss health decisions with
              your doctor.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Open Source</h2>
            <p className="text-muted-foreground leading-relaxed">
              Optiqal is open source. You can view the code, methodology, and contribute on{" "}
              <a
                href="https://github.com/maxghenis/optiqal-ai"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                GitHub
              </a>
              . We welcome feedback, bug reports, and contributions from the community.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
