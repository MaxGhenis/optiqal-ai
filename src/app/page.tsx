import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Activity,
  Check,
  Clock,
  Heart,
  Search,
  TrendingUp,
  BookOpen,
  ArrowRight,
  Sparkles,
  Zap,
} from "lucide-react";

function LifeMeter() {
  return (
    <div className="relative w-72 h-72 mx-auto">
      {/* Outer glow */}
      <div className="absolute inset-0 rounded-full bg-primary/20 blur-3xl animate-pulse-glow" />

      {/* Decorative orbiting elements */}
      <div
        className="absolute inset-0 animate-orbit"
        style={{ animationDuration: "25s" }}
      >
        <div className="w-3 h-3 rounded-full bg-primary/60 blur-sm" />
      </div>
      <div
        className="absolute inset-0 animate-orbit"
        style={{ animationDuration: "35s", animationDirection: "reverse" }}
      >
        <div className="w-2 h-2 rounded-full bg-accent/60 blur-sm" />
      </div>

      {/* Main SVG ring */}
      <svg
        className="w-full h-full -rotate-90 animate-breathe"
        viewBox="0 0 160 160"
      >
        {/* Background ring */}
        <circle
          cx="80"
          cy="80"
          r="70"
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth="4"
          opacity="0.3"
        />
        {/* Progress ring */}
        <circle
          cx="80"
          cy="80"
          r="70"
          fill="none"
          stroke="url(#lifeGradient)"
          strokeWidth="6"
          strokeLinecap="round"
          className="life-ring"
        />
        {/* Gradient definition */}
        <defs>
          <linearGradient id="lifeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="hsl(var(--primary))" />
            <stop offset="50%" stopColor="hsl(var(--cyan-glow))" />
            <stop offset="100%" stopColor="hsl(var(--coral))" />
          </linearGradient>
        </defs>
      </svg>

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-center space-y-1">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Your potential
          </p>
          <p className="text-5xl font-serif font-semibold gradient-text text-glow">
            +2.3
          </p>
          <p className="text-sm text-muted-foreground">quality-adjusted years</p>
        </div>
      </div>
    </div>
  );
}

function FloatingParticle({
  className,
  delay,
  duration,
}: {
  className?: string;
  delay?: string;
  duration?: string;
}) {
  return (
    <div
      className={`absolute w-1 h-1 rounded-full bg-primary/30 animate-float ${className}`}
      style={{ animationDelay: delay, animationDuration: duration }}
    />
  );
}

export default function Home() {
  return (
    <div className="min-h-screen mesh-gradient relative overflow-hidden">
      {/* Noise texture */}
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      {/* Floating particles */}
      <FloatingParticle className="top-1/4 left-1/4" delay="0s" duration="8s" />
      <FloatingParticle
        className="top-1/3 right-1/3"
        delay="2s"
        duration="10s"
      />
      <FloatingParticle
        className="bottom-1/4 left-1/3"
        delay="4s"
        duration="7s"
      />
      <FloatingParticle
        className="top-1/2 right-1/4"
        delay="1s"
        duration="9s"
      />

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="relative">
              <Activity className="h-7 w-7 text-primary transition-transform group-hover:scale-110" />
              <div className="absolute inset-0 bg-primary/30 blur-lg opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <span className="text-xl font-semibold tracking-tight">optiqal</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Button
              variant="ghost"
              className="text-muted-foreground hover:text-foreground transition-colors"
              asChild
            >
              <Link href="#how-it-works">How it works</Link>
            </Button>
            <Button
              className="btn-glow bg-primary text-primary-foreground hover:bg-primary/90"
              asChild
            >
              <Link href="/analyze">
                Try it free
                <Sparkles className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Text content */}
            <div className="space-y-8 opacity-0 animate-slide-up">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-primary text-sm font-medium">
                <Zap className="h-3.5 w-3.5" />
                AI-powered QALY estimation
              </div>

              <h1 className="font-serif text-5xl md:text-6xl lg:text-7xl font-medium leading-[1.1] tracking-tight">
                Predict your
                <br />
                <span className="gradient-text">healthspan</span>
              </h1>

              <p className="text-lg text-muted-foreground max-w-lg leading-relaxed">
                Optiqal estimates how lifestyle factors like exercise, diet, and
                smoking affect life expectancy and quality of life, based on
                published research and actuarial data.
              </p>

              <div className="flex flex-wrap gap-4 pt-2">
                <Button
                  size="lg"
                  className="btn-glow bg-primary text-primary-foreground hover:bg-primary/90 h-12 px-8 text-base"
                  asChild
                >
                  <Link href="/analyze">
                    Explore now
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  className="h-12 px-8 text-base border-border/50 hover:border-primary/50 hover:bg-primary/5"
                  asChild
                >
                  <Link href="#how-it-works">Learn more</Link>
                </Button>
              </div>
            </div>

            {/* Life meter visualization */}
            <div className="opacity-0 animate-scale-in delay-300">
              <LifeMeter />
            </div>
          </div>
        </div>
      </section>

      {/* Example Section */}
      <section className="py-24 px-6 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-muted/30 to-transparent" />
        <div className="max-w-4xl mx-auto relative">
          <div className="text-center mb-12 opacity-0 animate-slide-up">
            <p className="text-xs uppercase tracking-[0.25em] text-primary mb-3">
              Example result
            </p>
            <h2 className="font-serif text-3xl md:text-4xl font-medium">
              &ldquo;Add 30 minutes of walking daily&rdquo;
            </h2>
          </div>

          <Card className="max-w-2xl mx-auto mesh-gradient-card border-border/50 card-highlight hover-lift opacity-0 animate-scale-in delay-200">
            <CardContent className="p-8">
              <div className="text-center space-y-6">
                <p className="text-sm text-muted-foreground uppercase tracking-wider">
                  Estimated impact
                </p>
                <div className="space-y-2">
                  <div className="text-6xl font-serif font-semibold gradient-text text-glow">
                    +2 years, 3 months
                  </div>
                  <p className="text-muted-foreground">of quality-adjusted life</p>
                </div>

                <div className="flex justify-center gap-12 pt-6 border-t border-border/50">
                  <div className="text-center group">
                    <div className="flex items-center justify-center gap-2 text-muted-foreground mb-2">
                      <Clock className="h-4 w-4 group-hover:text-primary transition-colors" />
                      <span className="text-xs uppercase tracking-wider">
                        Longevity
                      </span>
                    </div>
                    <p className="text-2xl font-semibold text-primary">
                      +1.8 years
                    </p>
                  </div>
                  <div className="text-center group">
                    <div className="flex items-center justify-center gap-2 text-muted-foreground mb-2">
                      <Heart className="h-4 w-4 group-hover:text-accent transition-colors" />
                      <span className="text-xs uppercase tracking-wider">
                        Quality
                      </span>
                    </div>
                    <p className="text-2xl font-semibold text-accent">
                      +0.5 years
                    </p>
                  </div>
                </div>

                <div className="pt-4">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                    High confidence
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* How it Works */}
      <section id="how-it-works" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16 opacity-0 animate-slide-up">
            <p className="text-xs uppercase tracking-[0.25em] text-primary mb-3">
              The process
            </p>
            <h2 className="font-serif text-4xl md:text-5xl font-medium">
              How it works
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: Search,
                title: "Enter your profile",
                description:
                  "Provide basic info like age, sex, BMI, and lifestyle factors such as smoking status and activity level.",
                delay: "delay-100",
              },
              {
                icon: BookOpen,
                title: "We search the research",
                description:
                  "Optiqal synthesizes data from CDC life tables, meta-analyses, and cohort studies to estimate effects.",
                delay: "delay-200",
              },
              {
                icon: TrendingUp,
                title: "See the estimates",
                description:
                  "View life expectancy and QALY projections based on your profile—with uncertainty ranges.",
                delay: "delay-300",
              },
            ].map((step, index) => (
              <Card
                key={step.title}
                className={`mesh-gradient-card border-border/50 card-highlight hover-lift opacity-0 animate-slide-up ${step.delay}`}
              >
                <CardContent className="p-8 space-y-5">
                  <div className="relative w-14 h-14">
                    <div className="absolute inset-0 rounded-2xl bg-primary/20 blur-xl animate-pulse-glow" />
                    <div className="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/20 to-transparent border border-primary/30 flex items-center justify-center">
                      <step.icon className="h-6 w-6 text-primary" />
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-muted-foreground">
                      0{index + 1}
                    </span>
                    <h3 className="font-serif text-xl font-medium">
                      {step.title}
                    </h3>
                  </div>
                  <p className="text-muted-foreground leading-relaxed">
                    {step.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-6 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-muted/30 to-transparent" />
        <div className="max-w-6xl mx-auto relative">
          <div className="text-center mb-16 opacity-0 animate-slide-up">
            <p className="text-xs uppercase tracking-[0.25em] text-primary mb-3">
              Capabilities
            </p>
            <h2 className="font-serif text-4xl md:text-5xl font-medium">
              Features
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-4 max-w-4xl mx-auto">
            {[
              "Results in hours, days, or weeks—not abstract QALY fractions",
              "Separate longevity vs. quality-of-life breakdowns",
              "Confidence intervals reflecting evidence strength",
              "Personalized to your age, health conditions, and lifestyle",
              "Citations to specific studies and meta-analyses",
              "Caveats and limitations clearly explained",
              "Compare multiple choices side-by-side",
              "Powered by Claude AI for nuanced evidence synthesis",
            ].map((feature, index) => (
              <div
                key={feature}
                className={`flex items-start gap-4 p-4 rounded-xl hover:bg-muted/30 transition-colors opacity-0 animate-slide-up`}
                style={{ animationDelay: `${100 + index * 50}ms` }}
              >
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center mt-0.5">
                  <Check className="h-3.5 w-3.5 text-primary" />
                </div>
                <span className="text-foreground/90">{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Example choices */}
      <section className="py-24 px-6">
        <div className="max-w-5xl mx-auto text-center">
          <div className="mb-12 opacity-0 animate-slide-up">
            <p className="text-xs uppercase tracking-[0.25em] text-primary mb-3">
              Get started
            </p>
            <h2 className="font-serif text-4xl md:text-5xl font-medium mb-4">
              Explore different scenarios
            </h2>
            <p className="text-muted-foreground text-lg">
              See how different factors affect life expectancy estimates
            </p>
          </div>

          <div className="flex flex-wrap justify-center gap-3 opacity-0 animate-scale-in delay-200">
            {[
              "Cut out dairy",
              "Switch to a standing desk",
              "Take vitamin D supplements",
              "Reduce alcohol to weekends",
              "Start meditating 10 min/day",
              "Bike instead of drive",
              "Get a temperature-controlled mattress",
              "Use plastic-free detergent",
              "Add strength training 2x/week",
              "Intermittent fasting",
            ].map((choice) => (
              <Link
                key={choice}
                href={`/analyze?q=${encodeURIComponent(choice)}`}
                className="px-5 py-2.5 rounded-full border border-border/50 bg-card/50 hover:border-primary/50 hover:bg-primary/5 hover:text-primary transition-all duration-300 text-sm"
              >
                {choice}
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-32 px-6 relative">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-gradient-to-t from-primary/10 via-transparent to-transparent" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px]" />
        </div>
        <div className="max-w-2xl mx-auto text-center relative">
          <div className="space-y-8 opacity-0 animate-slide-up">
            <h2 className="font-serif text-4xl md:text-5xl lg:text-6xl font-medium leading-tight">
              Ready to predict
              <br />
              <span className="gradient-text">your healthspan?</span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-md mx-auto">
              See how lifestyle factors affect your life expectancy based on
              published research.
            </p>
            <Button
              size="lg"
              className="btn-glow bg-primary text-primary-foreground hover:bg-primary/90 h-14 px-10 text-lg"
              asChild
            >
              <Link href="/analyze">
                Get your prediction
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-border/30">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-6">
            <div className="flex items-center gap-3">
              <Activity className="h-5 w-5 text-primary" />
              <span className="text-sm text-muted-foreground">
                &copy; {new Date().getFullYear()} optiqal
              </span>
            </div>
            <div className="flex items-center gap-4 sm:gap-6 flex-wrap justify-center">
              <Link
                href="/about"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                About
              </Link>
              <Link
                href="/faq"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                FAQ
              </Link>
              <Link
                href="/terms"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Terms
              </Link>
              <Link
                href="/privacy"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Privacy
              </Link>
            </div>
          </div>
          <p className="text-xs text-muted-foreground max-w-2xl mx-auto text-center leading-relaxed">
            <strong>For educational purposes only.</strong> Optiqal provides statistical estimates
            based on population averages from published research. This is not medical advice and
            cannot predict individual outcomes. Always consult healthcare professionals for
            personal health decisions.
          </p>
        </div>
      </footer>
    </div>
  );
}
