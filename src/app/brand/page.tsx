import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Palette, FileText } from "lucide-react";
import { LogoLockup } from "@/components/brand/logo";

export default function BrandPage() {
  const cards = [
    {
      href: "/brand/design",
      icon: Palette,
      title: "Design system",
      description:
        "Color palette, typography, spacing, and visual components that define Optiqal's Clinical-Organic Futurism aesthetic.",
      delay: "delay-100",
    },
    {
      href: "/brand/writing",
      icon: FileText,
      title: "Writing guide",
      description:
        "Voice, tone, and editorial standards for communicating health research with precision and clarity.",
      delay: "delay-200",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto px-6">
      {/* Hero */}
      <div className="text-center mb-16 opacity-0 animate-slide-up">
        <div className="inline-flex items-center mb-6">
          <LogoLockup
            size="lg"
            descriptor="Clinical-organic futurism"
            nameClassName="text-[2.2rem]"
            descriptorClassName="text-[0.74rem]"
          />
        </div>
        <h1 className="font-serif text-4xl md:text-5xl lg:text-6xl font-medium mb-6">
          Brand <span className="gradient-text">guidelines</span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          Clinical-Organic Futurism: medical precision meets organic warmth.
          These guidelines ensure consistent, trustworthy communication across
          all Optiqal touchpoints.
        </p>
      </div>

      {/* Cards */}
      <div className="grid md:grid-cols-2 gap-6">
        {cards.map((card) => (
          <Link key={card.href} href={card.href} className="block group">
            <Card
              className={`h-full mesh-gradient-card border-border/50 card-highlight hover-lift opacity-0 animate-slide-up ${card.delay}`}
            >
              <CardContent className="p-8 space-y-5">
                <div className="relative w-14 h-14">
                  <div className="absolute inset-0 rounded-2xl bg-primary/20 blur-xl animate-pulse-glow" />
                  <div className="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/20 to-transparent border border-primary/30 flex items-center justify-center group-hover:border-primary/50 transition-colors">
                    <card.icon className="h-6 w-6 text-primary" />
                  </div>
                </div>
                <div>
                  <h2 className="font-serif text-2xl font-medium mb-2 group-hover:text-primary transition-colors">
                    {card.title}
                  </h2>
                  <p className="text-muted-foreground leading-relaxed">
                    {card.description}
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Quick reference */}
      <div className="mt-16 pt-12 border-t border-border/30 opacity-0 animate-slide-up delay-300">
        <h2 className="font-serif text-2xl font-medium mb-6 text-center">
          Quick reference
        </h2>
        <div className="grid sm:grid-cols-3 gap-6 text-center">
          <div className="space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-primary mx-auto" />
            <p className="text-sm font-mono text-muted-foreground">#56c4bf</p>
            <p className="text-sm">Primary cyan</p>
          </div>
          <div className="space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-accent mx-auto" />
            <p className="text-sm font-mono text-muted-foreground">#e08a73</p>
            <p className="text-sm">Accent coral</p>
          </div>
          <div className="space-y-2">
            <p className="font-serif text-3xl font-medium">Aa</p>
            <p className="text-sm text-muted-foreground">Playfair Display</p>
            <p className="text-sm">Serif headings</p>
          </div>
        </div>
      </div>
    </div>
  );
}
