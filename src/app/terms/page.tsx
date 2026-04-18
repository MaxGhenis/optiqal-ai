import Link from "next/link";

export default function TermsPage() {
  return (
    <main className="min-h-screen mesh-gradient paper-grid px-6 py-20">
      <div className="noise-overlay fixed inset-0 pointer-events-none" />
      <div className="relative z-10 mx-auto max-w-3xl">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div>
            <p className="section-chip">Legal</p>
            <h1 className="mt-4 font-serif text-4xl font-semibold tracking-[-0.04em]">
              Terms of Use
            </h1>
          </div>
          <Link
            href="/"
            className="data-pill text-sm transition-colors hover:text-foreground"
          >
            Back home
          </Link>
        </div>

        <div className="decision-card space-y-8 p-8">
          <section className="space-y-3">
            <h2 className="font-serif text-2xl font-semibold">Scope</h2>
            <p className="text-text-soft leading-relaxed">
              Optiqal provides decision-support estimates for health
              interventions. It is an informational tool, not medical advice,
              diagnosis, or treatment.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-2xl font-semibold">Use of Results</h2>
            <p className="text-text-soft leading-relaxed">
              You are responsible for how you interpret and act on outputs.
              Bayesian estimates, uncertainty intervals, and rankings are model
              outputs built from assumptions and evidence that may be incomplete
              or wrong for your situation.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-2xl font-semibold">No Warranty</h2>
            <p className="text-text-soft leading-relaxed">
              The service is provided on an as-is basis without warranties of
              accuracy, fitness for a particular purpose, or uninterrupted
              availability.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-2xl font-semibold">Contact</h2>
            <p className="text-text-soft leading-relaxed">
              Questions about these terms can be directed through the contact
              information published on optiqal.ai.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
