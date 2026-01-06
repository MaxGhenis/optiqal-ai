import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Check } from "lucide-react";

export const metadata = {
  title: "Design system — Optiqal",
  description: "Optiqal's Clinical-Organic Futurism design system",
};

function ColorSwatch({
  name,
  value,
  hex,
  className,
  textClass = "text-foreground",
}: {
  name: string;
  value: string;
  hex: string;
  className?: string;
  textClass?: string;
}) {
  return (
    <div className="space-y-3">
      <div
        className={`h-24 rounded-xl border border-border/30 ${className}`}
        style={{ backgroundColor: value }}
      />
      <div>
        <p className={`font-medium ${textClass}`}>{name}</p>
        <p className="text-sm font-mono text-muted-foreground">{hex}</p>
      </div>
    </div>
  );
}

function TypographySample({
  name,
  fontClass,
  sample,
  description,
}: {
  name: string;
  fontClass: string;
  sample: string;
  description: string;
}) {
  return (
    <div className="space-y-2">
      <p className={`text-4xl ${fontClass}`}>{sample}</p>
      <div>
        <p className="font-medium">{name}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export default function DesignPage() {
  return (
    <div className="max-w-5xl mx-auto px-6">
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
          Design system
        </p>
        <h1 className="font-serif text-4xl md:text-5xl font-medium mb-4">
          Clinical-Organic <span className="gradient-text">Futurism</span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
          Optiqal's visual language balances medical precision with organic
          warmth. Dark, sophisticated backgrounds paired with vibrant cyan and
          coral accents create an aesthetic that feels both clinical and
          approachable.
        </p>
      </div>

      {/* Color Palette */}
      <section className="mb-20 opacity-0 animate-slide-up delay-100">
        <h2 className="font-serif text-2xl font-medium mb-6">Color palette</h2>

        {/* Primary Colors */}
        <div className="mb-8">
          <h3 className="text-sm uppercase tracking-wider text-muted-foreground mb-4">
            Primary colors
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <ColorSwatch
              name="Cyan (primary)"
              value="hsl(174, 72%, 56%)"
              hex="#56c4bf"
              className="glow-primary"
            />
            <ColorSwatch
              name="Cyan glow"
              value="hsl(174, 80%, 65%)"
              hex="#6ed4cf"
            />
            <ColorSwatch
              name="Coral (accent)"
              value="hsl(12, 80%, 65%)"
              hex="#e08a73"
              className="glow-coral"
            />
            <ColorSwatch
              name="Coral soft"
              value="hsl(12, 60%, 75%)"
              hex="#dba99b"
            />
          </div>
        </div>

        {/* Background Colors */}
        <div className="mb-8">
          <h3 className="text-sm uppercase tracking-wider text-muted-foreground mb-4">
            Backgrounds
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <ColorSwatch
              name="Midnight (background)"
              value="hsl(220, 25%, 4%)"
              hex="#080a10"
              className="border-2"
            />
            <ColorSwatch
              name="Card"
              value="hsl(220, 20%, 8%)"
              hex="#111318"
              className="border-2"
            />
            <ColorSwatch
              name="Slate (muted)"
              value="hsl(220, 15%, 12%)"
              hex="#191c22"
            />
            <ColorSwatch
              name="Border"
              value="hsl(220, 15%, 18%)"
              hex="#272b33"
            />
          </div>
        </div>

        {/* Text Colors */}
        <div>
          <h3 className="text-sm uppercase tracking-wider text-muted-foreground mb-4">
            Text colors
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            <ColorSwatch
              name="Foreground"
              value="hsl(210, 20%, 95%)"
              hex="#f0f2f5"
            />
            <ColorSwatch
              name="Muted foreground"
              value="hsl(210, 10%, 55%)"
              hex="#838991"
            />
            <ColorSwatch
              name="Primary foreground"
              value="hsl(220, 25%, 4%)"
              hex="#080a10"
              className="border-2"
            />
          </div>
        </div>
      </section>

      {/* Gradients */}
      <section className="mb-20 opacity-0 animate-slide-up delay-200">
        <h2 className="font-serif text-2xl font-medium mb-6">Gradients</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <Card className="overflow-hidden border-border/50">
            <div className="h-32 bg-gradient-to-br from-primary via-[hsl(174,80%,65%)] to-accent" />
            <CardContent className="p-4">
              <p className="font-medium">Brand gradient</p>
              <p className="text-sm text-muted-foreground font-mono">
                from-primary via-cyan-glow to-coral
              </p>
            </CardContent>
          </Card>
          <Card className="overflow-hidden border-border/50">
            <div className="h-32 mesh-gradient" />
            <CardContent className="p-4">
              <p className="font-medium">Mesh gradient background</p>
              <p className="text-sm text-muted-foreground font-mono">
                .mesh-gradient
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Typography */}
      <section className="mb-20 opacity-0 animate-slide-up delay-300">
        <h2 className="font-serif text-2xl font-medium mb-6">Typography</h2>
        <div className="grid md:grid-cols-3 gap-8">
          <TypographySample
            name="Playfair Display"
            fontClass="font-serif"
            sample="Aa Bb Cc"
            description="Elegant serif for headings and display text"
          />
          <TypographySample
            name="DM Sans"
            fontClass="font-sans"
            sample="Aa Bb Cc"
            description="Clean sans-serif for body text and UI"
          />
          <TypographySample
            name="JetBrains Mono"
            fontClass="font-mono"
            sample="01234"
            description="Monospace for code and data"
          />
        </div>

        <div className="mt-8 p-6 rounded-xl bg-card/50 border border-border/50">
          <h3 className="text-sm uppercase tracking-wider text-muted-foreground mb-4">
            Type scale examples
          </h3>
          <div className="space-y-4">
            <p className="font-serif text-5xl font-medium">
              Predict your <span className="gradient-text">life expectancy</span>
            </p>
            <p className="font-serif text-3xl">Section heading</p>
            <p className="font-serif text-xl">Card title</p>
            <p className="text-lg text-muted-foreground">
              Body text for descriptions and paragraphs
            </p>
            <p className="text-sm text-muted-foreground">
              Small text for captions and meta information
            </p>
            <p className="text-xs uppercase tracking-[0.25em] text-primary">
              Label or category
            </p>
          </div>
        </div>
      </section>

      {/* Components */}
      <section className="mb-20 opacity-0 animate-slide-up delay-400">
        <h2 className="font-serif text-2xl font-medium mb-6">Components</h2>

        {/* Buttons */}
        <div className="mb-8">
          <h3 className="text-sm uppercase tracking-wider text-muted-foreground mb-4">
            Buttons
          </h3>
          <div className="flex flex-wrap gap-4">
            <Button className="btn-glow bg-primary text-primary-foreground hover:bg-primary/90">
              Primary button
            </Button>
            <Button variant="outline" className="border-border/50 hover:border-primary/50 hover:bg-primary/5">
              Outline button
            </Button>
            <Button variant="ghost" className="text-muted-foreground hover:text-foreground">
              Ghost button
            </Button>
          </div>
        </div>

        {/* Cards */}
        <div className="mb-8">
          <h3 className="text-sm uppercase tracking-wider text-muted-foreground mb-4">
            Cards
          </h3>
          <div className="grid md:grid-cols-2 gap-6">
            <Card className="mesh-gradient-card border-border/50 card-highlight hover-lift">
              <CardContent className="p-6">
                <h4 className="font-serif text-xl font-medium mb-2">
                  Feature card
                </h4>
                <p className="text-muted-foreground">
                  Cards with mesh gradient backgrounds and subtle highlight
                  borders create depth and visual interest.
                </p>
              </CardContent>
            </Card>
            <Card className="bg-card/50 border-border/50 glass">
              <CardContent className="p-6">
                <h4 className="font-serif text-xl font-medium mb-2">
                  Glass card
                </h4>
                <p className="text-muted-foreground">
                  Glass morphism effect with backdrop blur for overlays and
                  floating elements.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Tags */}
        <div>
          <h3 className="text-sm uppercase tracking-wider text-muted-foreground mb-4">
            Tags and badges
          </h3>
          <div className="flex flex-wrap gap-3">
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-primary text-sm font-medium">
              <Check className="h-3.5 w-3.5" />
              Active tag
            </span>
            <span className="px-4 py-1.5 rounded-full border border-border/50 bg-card/50 text-sm">
              Neutral tag
            </span>
            <span className="px-4 py-1.5 rounded-full border border-accent/30 bg-accent/5 text-accent text-sm">
              Accent tag
            </span>
          </div>
        </div>
      </section>

      {/* Effects */}
      <section className="mb-20 opacity-0 animate-slide-up delay-500">
        <h2 className="font-serif text-2xl font-medium mb-6">Effects</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="p-6 rounded-xl bg-card/50 border border-border/50 text-center">
            <div className="text-4xl font-serif font-medium gradient-text text-glow mb-4">
              42 years
            </div>
            <p className="text-sm text-muted-foreground font-mono">.gradient-text .text-glow</p>
          </div>
          <div className="p-6 rounded-xl bg-card/50 border border-border/50 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-primary glow-primary" />
            <p className="text-sm text-muted-foreground font-mono">.glow-primary</p>
          </div>
          <div className="p-6 rounded-xl bg-card/50 border border-border/50 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-primary/20 animate-pulse-glow" />
            <p className="text-sm text-muted-foreground font-mono">.animate-pulse-glow</p>
          </div>
        </div>
      </section>

      {/* Spacing */}
      <section className="opacity-0 animate-slide-up delay-600">
        <h2 className="font-serif text-2xl font-medium mb-6">Spacing</h2>
        <div className="p-6 rounded-xl bg-card/50 border border-border/50">
          <p className="text-muted-foreground mb-4">
            Use Tailwind's default spacing scale. Common patterns:
          </p>
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-3">
              <span className="w-24 font-mono text-muted-foreground">gap-6</span>
              <span>Between grid items and cards</span>
            </li>
            <li className="flex items-center gap-3">
              <span className="w-24 font-mono text-muted-foreground">p-6, p-8</span>
              <span>Card content padding</span>
            </li>
            <li className="flex items-center gap-3">
              <span className="w-24 font-mono text-muted-foreground">mb-16</span>
              <span>Section spacing</span>
            </li>
            <li className="flex items-center gap-3">
              <span className="w-24 font-mono text-muted-foreground">py-24</span>
              <span>Large section vertical padding</span>
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
