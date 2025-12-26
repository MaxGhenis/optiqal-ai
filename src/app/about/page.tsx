import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "About — Optiqal",
  description: "Learn about Optiqal and how it estimates quality-adjusted life years",
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
              Optiqal is an educational tool that estimates Quality-Adjusted Life Years (QALYs)
              to help you understand how lifestyle factors may affect your healthspan. By combining
              actuarial life expectancy data with health-related quality of life research, Optiqal
              provides a more complete picture of healthy life expectancy than mortality statistics alone.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-3">
              QALYs weight years of life by health quality, where 1 QALY represents one year lived
              in perfect health. This framework helps illustrate the potential impact of various
              risk factors on both how long you might live and how well you might live.
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
                <strong className="text-foreground">Published Meta-Analyses</strong> —
                Peer-reviewed studies on lifestyle factors and health outcomes
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Educational Purpose</h2>
            <p className="text-muted-foreground leading-relaxed">
              <strong className="text-foreground">
                Optiqal is for educational and informational purposes only.
              </strong>{" "}
              It does not provide medical advice, diagnosis, or treatment. The estimates shown are
              based on population-level statistics and cannot predict individual outcomes. Always
              consult a qualified healthcare professional before making health-related decisions.
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
