import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft, Check, X, AlertTriangle, Info } from "lucide-react";

export const metadata = {
  title: "Writing guide — Optiqal",
  description: "Editorial standards for communicating health research with precision and clarity",
};

function Example({
  correct,
  children,
}: {
  correct: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-lg border ${
        correct
          ? "border-primary/30 bg-primary/5"
          : "border-destructive/30 bg-destructive/5"
      }`}
    >
      <div
        className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center mt-0.5 ${
          correct ? "bg-primary/20 text-primary" : "bg-destructive/20 text-destructive"
        }`}
      >
        {correct ? (
          <Check className="h-3 w-3" />
        ) : (
          <X className="h-3 w-3" />
        )}
      </div>
      <p className={correct ? "text-foreground" : "text-muted-foreground"}>
        {children}
      </p>
    </div>
  );
}

function Principle({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-12">
      <h3 className="font-serif text-xl font-medium mb-2">{title}</h3>
      <p className="text-muted-foreground mb-4 leading-relaxed">{description}</p>
      {children}
    </div>
  );
}

export default function WritingPage() {
  return (
    <div className="max-w-4xl mx-auto px-6">
      {/* Back link */}
      <Link
        href="/brand"
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-8 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to brand
      </Link>

      {/* Header */}
      <div className="mb-16 opacity-0 animate-slide-up">
        <p className="text-xs uppercase tracking-[0.25em] text-primary mb-3">
          Writing guide
        </p>
        <h1 className="font-serif text-4xl md:text-5xl font-medium mb-4">
          Voice and <span className="gradient-text">standards</span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
          Optiqal communicates complex health research with precision, clarity,
          and appropriate epistemic humility. We present evidence
          dispassionately while remaining accessible to non-specialists.
        </p>
      </div>

      {/* Disclaimer Box */}
      <Card className="mb-16 border-accent/30 bg-accent/5 opacity-0 animate-slide-up delay-100">
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <AlertTriangle className="h-6 w-6 text-accent flex-shrink-0 mt-0.5" />
            <div>
              <h2 className="font-medium text-lg mb-2">Required disclaimer</h2>
              <p className="text-muted-foreground text-sm leading-relaxed">
                All Optiqal content must include appropriate disclaimers. Our
                predictions are statistical estimates based on population-level
                research, not individual medical advice. Users should consult
                healthcare professionals for personal health decisions.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Core Principles */}
      <section className="mb-16 opacity-0 animate-slide-up delay-200">
        <h2 className="font-serif text-2xl font-medium mb-8">Core principles</h2>

        <Principle
          title="Sentence case for headings"
          description="Use sentence case (only first word capitalized) for all headings, following the modern standard used by Apple, Google, and major tech companies. Proper nouns and acronyms remain capitalized."
        >
          <div className="space-y-2">
            <Example correct>How it works</Example>
            <Example correct={false}>How It Works</Example>
            <Example correct>What QALYs tell us about healthspan</Example>
            <Example correct={false}>What QALYs Tell Us About Healthspan</Example>
          </div>
        </Principle>

        <Principle
          title="Active voice"
          description="Prefer active voice for clarity and directness. Passive voice obscures agency and weakens statements."
        >
          <div className="space-y-2">
            <Example correct>
              Optiqal estimates your remaining life expectancy using CDC life
              tables.
            </Example>
            <Example correct={false}>
              Your remaining life expectancy is estimated by Optiqal using CDC
              life tables.
            </Example>
            <Example correct>
              Meta-analyses suggest that regular exercise extends lifespan.
            </Example>
            <Example correct={false}>
              It has been suggested by meta-analyses that lifespan is extended
              by regular exercise.
            </Example>
          </div>
        </Principle>

        <Principle
          title="Precise health terminology"
          description="Use correct epidemiological and statistical terms. Define acronyms on first use. Avoid oversimplifying in ways that distort meaning."
        >
          <div className="space-y-2">
            <Example correct>
              Quality-Adjusted Life Years (QALYs) weight years of life by health
              quality, where 1.0 represents perfect health.
            </Example>
            <Example correct={false}>
              QALYs measure how good your life is.
            </Example>
            <Example correct>
              The hazard ratio for all-cause mortality was 0.85 (95% CI:
              0.78-0.92).
            </Example>
            <Example correct={false}>
              Your death risk goes down by 15%.
            </Example>
          </div>
        </Principle>

        <Principle
          title="Quantify uncertainty"
          description="Always present confidence intervals, prediction intervals, or ranges. Point estimates alone create false precision. Make uncertainty visible and meaningful."
        >
          <div className="space-y-2">
            <Example correct>
              Remaining life expectancy: 25 years (90% prediction interval:
              7-39 years)
            </Example>
            <Example correct={false}>
              You will live another 25 years.
            </Example>
            <Example correct>
              Adding more profile details narrows your prediction interval from
              +/-16 years to +/-8 years.
            </Example>
            <Example correct={false}>
              More details make your prediction more accurate.
            </Example>
          </div>
        </Principle>

        <Principle
          title="Dispassionate presentation"
          description="Present evidence neutrally without editorializing or moralizing. Let data speak for itself. Avoid language that could induce anxiety or false hope."
        >
          <div className="space-y-2">
            <Example correct>
              Research associates smoking with a 2.3x higher mortality rate.
            </Example>
            <Example correct={false}>
              Smoking is terrible for you and dramatically shortens your life.
            </Example>
            <Example correct>
              Exercise is associated with improved cardiovascular outcomes in
              observational studies.
            </Example>
            <Example correct={false}>
              Exercise is the best thing you can do for your heart!
            </Example>
          </div>
        </Principle>

        <Principle
          title="Acknowledge limitations"
          description="Be explicit about what models can and cannot capture. Genetics, rare conditions, and individual variation may substantially affect outcomes."
        >
          <div className="space-y-2">
            <Example correct>
              These estimates are based on population-level data and may not
              reflect your individual circumstances.
            </Example>
            <Example correct={false}>This is your personalized prediction.</Example>
            <Example correct>
              The model does not account for genetic factors, which can
              significantly influence health outcomes.
            </Example>
            <Example correct={false}>
              We consider all relevant health factors.
            </Example>
          </div>
        </Principle>
      </section>

      {/* Terminology */}
      <section className="mb-16 opacity-0 animate-slide-up delay-300">
        <h2 className="font-serif text-2xl font-medium mb-6">Key terminology</h2>
        <Card className="border-border/50 bg-card/50">
          <CardContent className="p-6">
            <div className="grid gap-4">
              {[
                {
                  term: "QALY",
                  definition:
                    "Quality-Adjusted Life Year. A measure that weights years of life by health quality (0-1 scale). Always define on first use.",
                },
                {
                  term: "Hazard ratio (HR)",
                  definition:
                    "The ratio of hazard rates between exposed and unexposed groups. HR < 1 indicates reduced risk; HR > 1 indicates increased risk.",
                },
                {
                  term: "Confidence interval (CI)",
                  definition:
                    "A range of values that likely contains the true parameter. A 95% CI means 95% of such intervals would contain the true value.",
                },
                {
                  term: "Prediction interval",
                  definition:
                    "A range likely to contain a future individual observation. Wider than confidence intervals because they account for individual variation.",
                },
                {
                  term: "Meta-analysis",
                  definition:
                    "A statistical method combining results from multiple studies to arrive at pooled estimates.",
                },
                {
                  term: "RCT",
                  definition:
                    "Randomized Controlled Trial. The gold standard for establishing causal effects, though not always feasible for long-term health outcomes.",
                },
                {
                  term: "Observational study",
                  definition:
                    "Research where exposure is not assigned by researchers. Can establish associations but not necessarily causation.",
                },
                {
                  term: "Life table",
                  definition:
                    "Actuarial table showing mortality rates and life expectancy by age. Optiqal uses CDC period life tables as baseline.",
                },
              ].map((item) => (
                <div key={item.term} className="flex gap-4">
                  <span className="font-mono text-primary font-medium min-w-32">
                    {item.term}
                  </span>
                  <span className="text-muted-foreground text-sm leading-relaxed">
                    {item.definition}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Tone Guidelines */}
      <section className="mb-16 opacity-0 animate-slide-up delay-400">
        <h2 className="font-serif text-2xl font-medium mb-6">Tone guidelines</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <Card className="border-primary/30 bg-primary/5">
            <CardContent className="p-6">
              <h3 className="font-medium mb-4 flex items-center gap-2">
                <Check className="h-4 w-4 text-primary" />
                What we are
              </h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Precise and quantitative</li>
                <li>Transparent about methodology</li>
                <li>Appropriately uncertain</li>
                <li>Educational and informative</li>
                <li>Accessible without dumbing down</li>
                <li>Calm and measured</li>
              </ul>
            </CardContent>
          </Card>
          <Card className="border-destructive/30 bg-destructive/5">
            <CardContent className="p-6">
              <h3 className="font-medium mb-4 flex items-center gap-2">
                <X className="h-4 w-4 text-destructive" />
                What we avoid
              </h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Alarmist or anxiety-inducing</li>
                <li>Overly confident or deterministic</li>
                <li>Moralizing about lifestyle choices</li>
                <li>Medical advice or diagnoses</li>
                <li>Promising specific outcomes</li>
                <li>Emotional manipulation</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Standard Disclaimers */}
      <section className="opacity-0 animate-slide-up delay-500">
        <h2 className="font-serif text-2xl font-medium mb-6">
          Standard disclaimers
        </h2>
        <div className="space-y-4">
          <Card className="border-border/50 bg-card/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3 mb-3">
                <Info className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <h3 className="font-medium">Full disclaimer (footer/about page)</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed ml-8">
                Optiqal generates personalized predictions by applying hazard
                ratios from peer-reviewed meta-analyses to CDC life tables.
                Prediction intervals reflect uncertainty in the underlying
                research. Your actual outcomes may differ due to genetics and
                other unmodeled factors. Not medical advice—consult a healthcare
                professional for health decisions.
              </p>
            </CardContent>
          </Card>
          <Card className="border-border/50 bg-card/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3 mb-3">
                <Info className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <h3 className="font-medium">Short disclaimer (inline)</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed ml-8">
                These are statistical estimates, not medical advice. Consult your
                doctor for health decisions.
              </p>
            </CardContent>
          </Card>
          <Card className="border-border/50 bg-card/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3 mb-3">
                <Info className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <h3 className="font-medium">Uncertainty reminder</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed ml-8">
                Add more details to narrow your prediction interval. The uncertainty
                bounds are just as important as the point estimate.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
