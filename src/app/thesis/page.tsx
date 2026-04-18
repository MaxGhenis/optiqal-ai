"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Activity, ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

const sections = [
  { id: "problem", label: "Problem" },
  { id: "wedge", label: "Wedge" },
  { id: "product", label: "Product" },
  { id: "model", label: "Model" },
  { id: "market", label: "Market" },
  { id: "gtm", label: "GTM" },
  { id: "traction", label: "Traction" },
  { id: "team", label: "Team" },
  { id: "risks", label: "Risks" },
  { id: "vision", label: "Vision" },
] as const;

type Section = (typeof sections)[number]["id"];

interface Source {
  id: number;
  author?: string;
  title: string;
  year: number;
  url: string;
}

const sources: Source[] = [
  {
    id: 1,
    author: "Murray et al.",
    title: "Global Burden of Disease 2019: A systematic analysis",
    year: 2020,
    url: "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(20)30925-9/fulltext",
  },
  {
    id: 4,
    author: "Grand View Research",
    title: "Digital Health Market Size Report 2024-2030",
    year: 2024,
    url: "https://www.grandviewresearch.com/industry-analysis/digital-health-market",
  },
  {
    id: 5,
    author: "McKinsey",
    title: "The era of exponential improvement in healthcare?",
    year: 2024,
    url: "https://www.mckinsey.com/industries/healthcare/our-insights/the-era-of-exponential-improvement-in-healthcare",
  },
  {
    id: 10,
    author: "ICER",
    title: "Value Assessment Framework 2020-2023",
    year: 2023,
    url: "https://icer.org/our-approach/methods-process/value-assessment-framework/",
  },
  {
    id: 11,
    author: "Neumann et al.",
    title: "Cost-Effectiveness in Health and Medicine (Second Edition)",
    year: 2016,
    url: "https://global.oup.com/academic/product/cost-effectiveness-in-health-and-medicine-9780190492939",
  },
];

function Cite({ id }: { id: number }) {
  const [showCard, setShowCard] = useState(false);
  const source = sources.find((s) => s.id === id);
  if (!source) return null;

  return (
    <span className="relative inline">
      <sup
        className="text-primary cursor-pointer font-mono text-[0.7em] ml-0.5 transition-colors hover:text-primary/70"
        onMouseEnter={() => setShowCard(true)}
        onMouseLeave={() => setShowCard(false)}
        onClick={() => window.open(source.url, "_blank")}
      >
        [{id}]
      </sup>
      {showCard && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 bg-card border border-border rounded-lg p-4 min-w-[280px] max-w-[350px] z-50 shadow-2xl animate-in fade-in slide-in-from-bottom-2 duration-150">
          <div className="font-medium text-sm text-foreground mb-1 leading-snug">
            {source.title}
          </div>
          {source.author && (
            <div className="text-xs text-muted-foreground mb-2">
              {source.author}, {source.year}
            </div>
          )}
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary hover:underline"
          >
            View source →
          </a>
        </div>
      )}
    </span>
  );
}

function SectionTitle({
  number,
  title,
  subtitle,
}: {
  number: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-8">
      <p className="text-xs uppercase tracking-[0.25em] text-primary mb-3">
        {number}
      </p>
      <h2 className="font-serif text-4xl font-bold mb-3">{title}</h2>
      {subtitle && (
        <p className="text-lg text-muted-foreground leading-relaxed">
          {subtitle}
        </p>
      )}
    </div>
  );
}

export default function ThesisPage() {
  const [activeSection, setActiveSection] = useState<Section>("problem");
  const [showStickyBar, setShowStickyBar] = useState(false);
  const sectionRefs = useRef<Record<Section, HTMLElement | null>>(
    Object.fromEntries(sections.map((s) => [s.id, null])) as Record<
      Section,
      HTMLElement | null
    >,
  );

  useEffect(() => {
    const handleScroll = () => {
      setShowStickyBar(window.scrollY > window.innerHeight * 0.7);

      for (const section of sections) {
        const el = sectionRefs.current[section.id];
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.top <= 200 && rect.bottom >= 200) {
          setActiveSection(section.id);
          break;
        }
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (section: Section) => {
    sectionRefs.current[section]?.scrollIntoView({ behavior: "smooth" });
  };

  const setRef = (section: Section) => (el: HTMLElement | null) => {
    sectionRefs.current[section] = el;
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav className="fixed top-0 left-0 right-0 h-16 flex items-center px-6 bg-background/85 backdrop-blur-xl border-b border-border/30 z-50">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight hover:opacity-70 transition-opacity"
        >
          <Activity className="h-6 w-6 text-primary" />
          Optiqal
        </Link>
      </nav>

      <nav className="fixed top-20 left-1/2 -translate-x-1/2 flex gap-1 p-1.5 bg-card/90 backdrop-blur-xl border border-border rounded-full z-40 shadow-lg">
        {sections.map((section) => (
          <button
            key={section.id}
            className={`px-4 py-2 text-xs font-medium rounded-full transition-all whitespace-nowrap ${
              activeSection === section.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
            onClick={() => scrollTo(section.id)}
          >
            {section.label}
          </button>
        ))}
      </nav>

      <section className="min-h-[70vh] flex flex-col justify-center items-center text-center pt-36 pb-24 px-6 relative">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[600px] h-[600px] bg-primary/10 rounded-full blur-3xl opacity-50" />
        </div>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary mb-4 relative z-10">
          Internal business plan
        </p>
        <h1 className="font-serif text-5xl md:text-7xl font-bold mb-6 relative z-10 bg-gradient-to-r from-foreground via-foreground to-primary bg-clip-text text-transparent leading-tight">
          The Optiqal thesis
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl relative z-10 leading-relaxed">
          The paper and docs should carry the research argument. This page is
          the commercial thesis: who Optiqal is for, what product wedge it
          owns, why the Bayesian model matters, and how it becomes a business.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-4 relative z-10">
          <Button
            size="lg"
            className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/25 h-12 px-8"
            asChild
          >
            <Link href="/analyze">
              Open analyzer
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button variant="outline" size="lg" className="h-12 px-8" asChild>
            <a href="mailto:max@optiqal.ai">Share draft</a>
          </Button>
        </div>
        <p className="text-sm text-muted-foreground mt-6 relative z-10">
          Hidden route for strategy work. Not meant to duplicate the paper.
        </p>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("problem")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="1"
            title="The problem"
            subtitle="Health consumers spend money and effort across labs, wearables, food, skincare, supplements, and prescriptions without a common decision benchmark."
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            {[
              {
                title: "Too many choices",
                desc: "Extra sleep, ApoB lowering, creatine, sunscreen, alcohol reduction, therapy, meal quality, supplements.",
              },
              {
                title: "No common unit",
                desc: "Most tools show biomarkers, scores, or habits. They do not compare unlike interventions on one scale.",
              },
              {
                title: "Bad capital allocation",
                desc: "People overinvest in low-value, legible actions while underinvesting in high-value boring ones.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="p-6 bg-card border border-border rounded-xl"
              >
                <h3 className="font-semibold text-lg mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>

          <div className="p-6 bg-primary/5 border-l-4 border-primary rounded-r-xl">
            <p className="text-lg leading-relaxed">
              Healthcare already uses QALY-style reasoning to compare
              interventions and resource allocation
              <Cite id={10} />
              <Cite id={11} />. Consumers do not have an equivalent tool for
              everyday health decisions, despite the scale of disease burden and
              preventable loss documented in GBD
              <Cite id={1} />.
            </p>
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("wedge")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="2"
            title="The wedge"
            subtitle="Most of the market offers scores, dashboards, or protocols. Optiqal should own the decision-engine layer."
          />

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
            {[
              {
                title: "Scores",
                desc: "Biological age, readiness, or pace-of-aging summaries.",
              },
              {
                title: "Dashboards",
                desc: "Labs, wearables, trends, and health record aggregation.",
              },
              {
                title: "Protocols",
                desc: "Stacks, longevity routines, supplement bundles, coaching.",
              },
              {
                title: "Optiqal",
                desc: "What is most worth doing next, given what I already do?",
              },
            ].map((item, index) => (
              <div
                key={item.title}
                className={`p-6 rounded-xl border ${
                  index === 3
                    ? "bg-primary/10 border-primary/40"
                    : "bg-card border-border"
                }`}
              >
                <h3 className="font-semibold text-lg mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold mb-3">Core user question</h3>
              <p className="text-xl font-medium leading-relaxed">
                What are the top additions, removals, or swaps most likely to
                improve my healthspan from here?
              </p>
            </div>
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold mb-3">Positioning line</h3>
              <p className="text-xl font-medium leading-relaxed">
                Optiqal tells you what is most worth doing next.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("product")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="3"
            title="The product"
            subtitle="The unit of value is not a score. It is a decision card that turns unlike interventions into comparable bets."
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-3">Inputs</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Profile, habits, conditions, lab context, and current stack.
              </p>
            </div>
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-3">Decision object</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Add, remove, or swap an intervention and compare the net change.
              </p>
            </div>
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-3">Outputs</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Expected benefit, probability of benefit, downside risk, burden,
                and cost.
              </p>
            </div>
          </div>

          <div className="p-8 bg-card border border-primary/30 rounded-2xl mb-8">
            <div className="flex items-center justify-between gap-4 mb-6">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-primary mb-2">
                  Example decision card
                </p>
                <h3 className="font-serif text-3xl font-semibold">
                  Extend sleep by 45 minutes
                </h3>
              </div>
              <div className="text-right">
                <div className="text-4xl font-serif font-semibold text-primary">
                  +0.18
                </div>
                <div className="text-sm text-muted-foreground">net QALYs</div>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-muted-foreground mb-1">P(net &gt; 0)</div>
                <div className="font-semibold text-lg">72%</div>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-muted-foreground mb-1">Downside tail</div>
                <div className="font-semibold text-lg">9%</div>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-muted-foreground mb-1">Burden</div>
                <div className="font-semibold text-lg">Moderate</div>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-muted-foreground mb-1">Cost</div>
                <div className="font-semibold text-lg">$0</div>
              </div>
            </div>
          </div>

          <div className="p-6 bg-primary/5 border-l-4 border-primary rounded-r-xl">
            <p className="text-lg leading-relaxed">
              Optiqal should not use hand-authored strong-versus-speculative
              buckets. Weak evidence should show up as more shrinkage, wider
              tails, and higher sensitivity to priors.
            </p>
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("model")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="4"
            title="The model"
            subtitle="The technical differentiator is a continuous Bayesian decision model, not another recommendation engine with hidden heuristics."
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
            {[
              {
                title: "Effect-size priors",
                desc: "Different intervention families start with different causal priors instead of sharing one naive evidence template.",
              },
              {
                title: "Bias and confounding shrinkage",
                desc: "Observational, publication, and healthy-user effects shrink claims toward zero when the evidence is fragile.",
              },
              {
                title: "External validity",
                desc: "Posterior estimates adjust to age, sex, baseline risk, and current stack instead of pretending population averages are fully portable.",
              },
              {
                title: "Harms and reversibility",
                desc: "Every action gets a net distribution, not just a benefit story. Downside risk is part of the ranking.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="p-6 bg-card border border-border rounded-xl"
              >
                <h3 className="font-semibold text-lg mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>

          <div className="p-6 bg-card border border-border rounded-xl mb-8">
            <h3 className="font-semibold text-lg mb-4">User-facing outputs</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-muted-foreground">
              <div className="p-4 bg-muted rounded-lg">Expected net QALY delta</div>
              <div className="p-4 bg-muted rounded-lg">Probability of net benefit</div>
              <div className="p-4 bg-muted rounded-lg">Probability of clearing a meaningful threshold</div>
              <div className="p-4 bg-muted rounded-lg">Downside tail risk and burden-adjusted utility</div>
            </div>
          </div>

          <p className="text-lg text-muted-foreground leading-relaxed">
            QALYs are already the canonical cross-intervention comparison unit in
            health economics
            <Cite id={10} />
            <Cite id={11} />. Optiqal applies that logic to personal decision
            support with explicit uncertainty instead of hiding it behind a
            score.
          </p>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("market")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="5"
            title="The market"
            subtitle="The top-down market is large, but the more important point is that quantified-self and longevity users already spend heavily without a ranking layer."
          />

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
            {[
              { name: "Digital Health", size: "$240B to $780B", source: 4 },
              { name: "Wellness Apps", size: "$70B+", source: 5 },
              { name: "Longevity Tech", size: "$27B to $44B", source: 5 },
              { name: "Health Coaching", size: "$8B to $15B", source: 4 },
            ].map((item) => (
              <div
                key={item.name}
                className="p-6 bg-card border border-border rounded-xl"
              >
                <h3 className="font-semibold text-lg mb-2">{item.name}</h3>
                <div className="text-2xl font-bold text-primary mb-1">
                  {item.size}
                  <Cite id={item.source} />
                </div>
                <p className="text-sm text-muted-foreground">through 2030</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold mb-3">Initial ICP</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>High-agency quantified-self users</li>
                <li>Longevity and Bryan Johnson-adjacent consumers</li>
                <li>People already paying for labs, wearables, and supplements</li>
                <li>Users trying to simplify an overgrown stack</li>
              </ul>
            </div>
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold mb-3">Why now</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Consumers have more data but not better prioritization</li>
                <li>LLMs make evidence synthesis and explanation cheaper</li>
                <li>Long-tail health spending is already mainstream</li>
                <li>People increasingly want skeptical, source-aware guidance</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("gtm")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="6"
            title="Go-to-market"
            subtitle="Start with a consumer wedge that proves the ranking problem is real, then move outward into coaches, clinics, and API distribution."
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            {[
              {
                title: "Phase 1: consumer wedge",
                desc: "Public-facing analyzer, stack teardowns, and high-signal case studies for quantified-self and longevity users.",
              },
              {
                title: "Phase 2: pros and coaches",
                desc: "Shared plans, client reports, and repeat ranking workflows for health coaches and performance-minded practitioners.",
              },
              {
                title: "Phase 3: platform",
                desc: "API and white-label decision support inside lab, telehealth, or wellness products.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="p-6 bg-card border border-border rounded-xl"
              >
                <h3 className="font-semibold text-lg mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>

          <div className="space-y-4">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold mb-3">Channels that fit the product</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-muted-foreground">
                <div className="p-4 bg-muted rounded-lg">Public comparisons: sleep vs supplements vs lipids</div>
                <div className="p-4 bg-muted rounded-lg">Personal stack analyses and before/after case studies</div>
                <div className="p-4 bg-muted rounded-lg">Methodology transparency to attract skeptical power users</div>
                <div className="p-4 bg-muted rounded-lg">Lab and wearable integrations as retention hooks</div>
              </div>
            </div>
            <div className="p-6 bg-primary/5 border-l-4 border-primary rounded-r-xl">
              <p className="text-lg leading-relaxed">
                The best early outcome is not “users love their score.” It is
                “users stopped wasting money and attention on low-value health
                actions.”
              </p>
            </div>
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("traction")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="7"
            title="Traction"
            subtitle="The project is no longer an idea. There is already a functioning engine, app surface, manuscript, and test suite."
          />

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
            {[
              { value: "10", label: "modeled interventions" },
              { value: "450", label: "TypeScript tests passing" },
              { value: "121", label: "Python tests passing" },
              { value: "1", label: "paper draft in repo" },
            ].map((stat) => (
              <div
                key={stat.label}
                className="text-center p-6 bg-card border border-border rounded-xl"
              >
                <span className="block text-3xl font-bold text-primary">
                  {stat.value}
                </span>
                <span className="text-sm text-muted-foreground">
                  {stat.label}
                </span>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              {
                title: "Live product surface",
                desc: "Working app with profile input, intervention comparison, combination calculator, and optimizer flow.",
              },
              {
                title: "Bayesian simulation core",
                desc: "Python and TypeScript simulation paths, precomputed profiles, and uncertainty-aware outputs.",
              },
              {
                title: "Manuscript and docs",
                desc: "Paper draft and methodology docs already exist, which helps separate scientific claims from product claims.",
              },
              {
                title: "Founder-product fit",
                desc: "Built by someone already using the tool for personal stack decisions and with a history of building policy simulation systems.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="p-6 bg-card border border-border rounded-xl"
              >
                <h3 className="font-semibold text-lg mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("team")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="8"
            title="Team"
            subtitle="This starts founder-led, but the next hires should strengthen health credibility, product execution, and data integrations."
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-xl mb-1">Max Ghenis</h3>
              <p className="text-sm text-primary mb-4">Founder</p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Founded PolicyEngine and built large-scale simulation infrastructure</li>
                <li>Former Google data scientist</li>
                <li>MIT economics, UC Berkeley statistics</li>
                <li>Strong fit for evidence synthesis, product framing, and probabilistic modeling</li>
              </ul>
            </div>
            <div className="p-6 bg-card border border-dashed border-border rounded-xl">
              <h3 className="font-semibold text-xl mb-1">Next hires</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Sequence matters more than headcount.
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Health economist or epidemiologist with causal-inference instincts</li>
                <li>Product-minded full-stack engineer</li>
                <li>Later: data integration engineer for labs and wearables</li>
              </ul>
              <p className="text-xs text-muted-foreground mt-4 italic">
                Contact: max@optiqal.ai
              </p>
            </div>
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("risks")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="9"
            title="Risks"
            subtitle="The main product risk is not competition. It is losing trust through false precision or confusing UX."
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              {
                risk: "False precision",
                answer:
                  "Mitigation: show posteriors, downside tails, and prior sensitivity instead of brittle single-number rankings.",
              },
              {
                risk: "Medical trust and liability",
                answer:
                  "Mitigation: keep the product in decision-support territory, not diagnosis, and make assumptions legible.",
              },
              {
                risk: "Weak retention",
                answer:
                  "Mitigation: make the product about stack changes over time, not one-off curiosity checks.",
              },
              {
                risk: "Speculative long tail",
                answer:
                  "Mitigation: do not lead the product or marketing with fragile supplement claims before the core engine is trusted.",
              },
              {
                risk: "Data integration messiness",
                answer:
                  "Mitigation: begin with clean manual inputs, then add imports where they materially change ranking quality.",
              },
              {
                risk: "Model drift across surfaces",
                answer:
                  "Mitigation: make one engine canonical and parity-test every user-facing path against it.",
              },
            ].map((item) => (
              <div
                key={item.risk}
                className="p-5 bg-card border border-border rounded-xl"
              >
                <h4 className="font-semibold mb-2">{item.risk}</h4>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {item.answer}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section
        className="min-h-screen py-24 px-6 flex flex-col items-center"
        ref={setRef("vision")}
      >
        <div className="max-w-4xl w-full">
          <SectionTitle
            number="10"
            title="The vision"
            subtitle="Optiqal becomes the default benchmark layer for personal health decisions."
          />

          <div className="space-y-4 mb-10">
            {[
              {
                year: "Y1",
                desc: "A credible consumer analyzer with strong early retention among quantified-self and longevity users.",
              },
              {
                year: "Y2",
                desc: "Lab and wearable integrations, repeat stack workflows, and early coach or practitioner adoption.",
              },
              {
                year: "Y3",
                desc: "API and white-label partnerships that embed the ranking engine into other health products.",
              },
              {
                year: "Y5",
                desc: "Optiqal is the default answer to “what is most worth doing next for my health?”",
              },
            ].map((item) => (
              <div
                key={item.year}
                className="p-5 bg-card border border-border rounded-xl flex items-center gap-4"
              >
                <span className="text-2xl font-bold text-primary min-w-12">
                  {item.year}
                </span>
                <p className="text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>

          <div className="p-6 bg-primary/5 border-l-4 border-primary rounded-r-xl">
            <p className="text-lg italic leading-relaxed">
              The ambition is not to become another health dashboard. It is to
              become the layer that tells every health dashboard, protocol, and
              supplement stack what is actually worth doing next.
            </p>
          </div>
        </div>
      </section>

      <section className="py-16 px-6 bg-card border-t border-border">
        <div className="max-w-3xl mx-auto">
          <h2 className="font-serif text-2xl font-bold mb-6">References</h2>
          <ol className="space-y-3 text-sm">
            {sources.map((source) => (
              <li
                key={source.id}
                className="pl-8 relative text-muted-foreground"
              >
                <span className="absolute left-0 font-mono text-primary">
                  [{source.id}]
                </span>
                {source.author && <span>{source.author}. </span>}
                <em className="text-foreground">{source.title}</em>
                <span> ({source.year}). </span>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-primary transition-colors break-all"
                >
                  {source.url.replace(/^https?:\/\//, "").split("/")[0]}
                </a>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="py-24 px-6 text-center relative">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[600px] h-[300px] bg-primary/10 rounded-full blur-3xl opacity-50" />
        </div>
        <h2 className="font-serif text-4xl font-bold mb-4 relative z-10">
          Ready to pressure test it?
        </h2>
        <p className="text-lg text-muted-foreground mb-8 relative z-10">
          Use the live analyzer for product feel, and keep the paper separate
          for scientific claims.
        </p>
        <div className="flex flex-wrap justify-center gap-4 relative z-10">
          <Button
            size="lg"
            className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/25 h-12 px-8"
            asChild
          >
            <Link href="/analyze">
              Try Optiqal free
              <Sparkles className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button variant="ghost" size="lg" className="h-12 px-8" asChild>
            <Link href="/">Back to home</Link>
          </Button>
        </div>
      </section>

      <div
        className={`fixed bottom-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-xl border-t border-border shadow-2xl transition-transform duration-300 ${
          showStickyBar ? "translate-y-0" : "translate-y-full"
        }`}
      >
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div className="hidden sm:block">
            <p className="text-sm font-medium">Optiqal business thesis</p>
            <p className="text-xs text-muted-foreground">
              Bayesian decision engine for health interventions
            </p>
          </div>
          <Button
            size="lg"
            className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/25 h-11 px-6 sm:px-8"
            asChild
          >
            <Link href="/analyze">
              Open analyzer
              <Sparkles className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
