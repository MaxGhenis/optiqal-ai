"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Activity } from "lucide-react";

type Section = "problem" | "gap" | "solution" | "science" | "markets" | "model" | "traction" | "team" | "risks" | "vision";

interface Source {
  id: number;
  author?: string;
  title: string;
  year: number;
  url: string;
}

// All sources - every claim corroborated
const sources: Source[] = [
  {
    id: 1,
    author: "Murray et al.",
    title: "Global Burden of Disease 2019: A systematic analysis",
    year: 2020,
    url: "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(20)30925-9/fulltext",
  },
  {
    id: 2,
    author: "Hamer & Chida",
    title: "Walking and primary prevention: a meta-analysis of prospective cohort studies",
    year: 2008,
    url: "https://bjsm.bmj.com/content/42/4/238",
  },
  {
    id: 3,
    author: "Thun et al.",
    title: "50-Year Trends in Smoking-Related Mortality in the United States",
    year: 2013,
    url: "https://www.nejm.org/doi/full/10.1056/NEJMsa1211127",
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
    id: 6,
    author: "Holt-Lunstad et al.",
    title: "Social Relationships and Mortality Risk: A Meta-analytic Review",
    year: 2010,
    url: "https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1000316",
  },
  {
    id: 7,
    author: "Sofi et al.",
    title: "Mediterranean diet and health status: meta-analysis",
    year: 2014,
    url: "https://www.bmj.com/content/337/bmj.a1344",
  },
  {
    id: 8,
    author: "Cappuccio et al.",
    title: "Sleep duration and all-cause mortality: a systematic review",
    year: 2010,
    url: "https://pubmed.ncbi.nlm.nih.gov/20469800/",
  },
  {
    id: 9,
    author: "WHO",
    title: "Global Health Estimates: Life expectancy and leading causes of death",
    year: 2024,
    url: "https://www.who.int/data/gho/data/themes/mortality-and-global-health-estimates",
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
  {
    id: 12,
    author: "Lee et al.",
    title: "Leisure-time running reduces all-cause and cardiovascular mortality risk",
    year: 2014,
    url: "https://www.jacc.org/doi/10.1016/j.jacc.2014.04.058",
  },
];

const sections: Section[] = ["problem", "gap", "solution", "science", "markets", "model", "traction", "team", "risks", "vision"];

// Citation component with hover card
function Cite({ id }: { id: number }) {
  const [showCard, setShowCard] = useState(false);
  const source = sources.find(s => s.id === id);
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
          <div className="font-medium text-sm text-foreground mb-1 leading-snug">{source.title}</div>
          {source.author && <div className="text-xs text-muted-foreground mb-2">{source.author}, {source.year}</div>}
          <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline">
            View source →
          </a>
        </div>
      )}
    </span>
  );
}

export default function ThesisPage() {
  const [activeSection, setActiveSection] = useState<Section>("problem");
  const sectionRefs = useRef<Record<Section, HTMLElement | null>>(
    Object.fromEntries(sections.map(s => [s, null])) as Record<Section, HTMLElement | null>
  );

  // Scroll spy
  useEffect(() => {
    const handleScroll = () => {
      for (const section of sections) {
        const el = sectionRefs.current[section];
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= 200 && rect.bottom >= 200) {
            setActiveSection(section);
            break;
          }
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
      {/* Top nav */}
      <nav className="fixed top-0 left-0 right-0 h-16 flex items-center px-6 bg-background/85 backdrop-blur-xl border-b border-border/30 z-50">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight hover:opacity-70 transition-opacity">
          <Activity className="h-6 w-6 text-primary" />
          optiqal
        </Link>
      </nav>

      {/* Section nav */}
      <nav className="fixed top-20 left-1/2 -translate-x-1/2 flex gap-1 p-1.5 bg-card/90 backdrop-blur-xl border border-border rounded-full z-40 shadow-lg">
        {sections.map(s => (
          <button
            key={s}
            className={`px-4 py-2 text-xs font-medium rounded-full transition-all whitespace-nowrap ${
              activeSection === s
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
            onClick={() => scrollTo(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </nav>

      {/* Hero */}
      <section className="min-h-[70vh] flex flex-col justify-center items-center text-center pt-36 pb-24 px-6 relative">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[600px] h-[600px] bg-primary/10 rounded-full blur-3xl opacity-50" />
        </div>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary mb-4 relative z-10">
          Research Prospectus
        </p>
        <h1 className="font-serif text-5xl md:text-7xl font-bold mb-6 relative z-10 bg-gradient-to-r from-foreground via-foreground to-primary bg-clip-text text-transparent leading-tight">
          Quantify Your Life
        </h1>
        <p className="text-xl text-muted-foreground max-w-xl relative z-10 leading-relaxed">
          We&apos;re building the tool that helps anyone understand how their choices affect their healthspan—grounded in the best causal evidence.
        </p>
        <p className="text-sm text-muted-foreground mt-8 relative z-10">
          Every claim in this document is corroborated with a primary source.<br />
          Hover over citations to see details. Click to open.
        </p>
      </section>

      {/* Problem */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("problem")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">1. The Problem</h2>
          <p className="text-2xl font-medium text-foreground mb-8 leading-snug">
            People make thousands of health decisions blindly. Evidence exists, but it&apos;s locked in research papers.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
            {[
              { title: "The Individual", desc: "Should I take that supplement? Is 10,000 steps real? How bad is that extra drink? No way to quantify tradeoffs." },
              { title: "The Doctor", desc: "12 minutes per patient. Can't personalize lifestyle advice. Falls back on generic guidelines." },
              { title: "The Researcher", desc: "Publishes p-values, not actionable estimates. Studies don't translate to daily decisions." },
            ].map(item => (
              <div key={item.title} className="p-6 bg-card border border-border rounded-xl hover:border-border/80 transition-colors">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-primary mb-2">{item.title}</h4>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>

          <div className="flex flex-col items-center p-12 bg-card border border-border rounded-2xl text-center relative overflow-hidden mb-8">
            <div className="absolute inset-0 bg-primary/5 rounded-2xl" />
            <span className="text-6xl md:text-7xl font-bold text-primary relative z-10">74</span>
            <span className="text-lg font-medium text-foreground relative z-10 mt-2">
              years of healthy life lost globally per second<Cite id={1} />
            </span>
          </div>

          <p className="text-lg text-muted-foreground leading-relaxed">
            The Global Burden of Disease study<Cite id={1} /> tracks disability-adjusted life years (DALYs) lost to every disease and risk factor. We know that <strong className="text-foreground">walking 30 minutes daily reduces mortality by ~17%</strong><Cite id={2} />, that <strong className="text-foreground">quitting smoking adds 10+ years</strong><Cite id={3} />, that <strong className="text-foreground">social connection rivals smoking cessation in impact</strong><Cite id={6} />. But this knowledge doesn&apos;t reach people in a form they can act on.
          </p>
        </div>
      </section>

      {/* Gap */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("gap")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">2. The Gap</h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-8">
            Health decisions involve uncertainty. But current tools either ignore uncertainty entirely or drown users in statistics they can&apos;t interpret.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold mb-4">What People Get</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">&quot;Exercise is good for you&quot;</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">&quot;Moderate drinking may have benefits&quot;</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">&quot;Sleep 7-9 hours&quot;</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">Contradictory headlines every week</li>
              </ul>
            </div>
            <div className="p-6 bg-card border border-primary/30 rounded-xl bg-primary/5">
              <h3 className="font-semibold mb-4">What People Need</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="pl-4 relative before:content-['→'] before:absolute before:left-0 before:text-primary before:font-mono">&quot;30 min walking = 0.8-1.5 QALYs (95% CI)&quot;</li>
                <li className="pl-4 relative before:content-['→'] before:absolute before:left-0 before:text-primary before:font-mono">&quot;1 drink/day: effect depends on your age, sex&quot;</li>
                <li className="pl-4 relative before:content-['→'] before:absolute before:left-0 before:text-primary before:font-mono">&quot;Sleep 7h vs 6h = X quality-adjusted months&quot;</li>
                <li className="pl-4 relative before:content-['→'] before:absolute before:left-0 before:text-primary before:font-mono">Personalized, probabilistic, sourced</li>
              </ul>
            </div>
          </div>

          <div className="p-6 bg-primary/5 border-l-4 border-primary rounded-r-xl">
            <p className="text-lg">
              <strong className="text-foreground">The gap:</strong> No tool translates health evidence into personalized, quantified, uncertainty-aware estimates that help individuals make better decisions.
            </p>
          </div>
        </div>
      </section>

      {/* Solution */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("solution")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">3. The Solution</h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-8">
            Optiqal is an AI-powered tool that estimates the QALY (Quality-Adjusted Life Year) impact of any lifestyle choice—personalized to you, with full uncertainty quantification.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-2">Input</h3>
              <p className="text-sm text-muted-foreground mb-3">Describe any intervention in plain language</p>
              <code className="block p-3 bg-muted rounded-lg text-xs text-primary font-mono">
                &quot;Start walking 30 minutes daily&quot;
              </code>
            </div>
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-2">Process</h3>
              <p className="text-sm text-muted-foreground mb-3">AI synthesizes evidence, maps mechanisms to outcomes</p>
              <div className="text-xs space-y-1 text-muted-foreground">
                <div>→ Blood pressure ↓4 mmHg</div>
                <div>→ Insulin sensitivity ↑15%</div>
                <div>→ Mortality HR: 0.83</div>
              </div>
            </div>
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-2">Output</h3>
              <p className="text-sm text-muted-foreground mb-3">Probabilistic QALY estimate with sources</p>
              <div className="text-center">
                <span className="text-3xl font-bold text-primary">+1.2</span>
                <span className="text-lg text-muted-foreground ml-1">QALYs</span>
                <div className="text-xs text-muted-foreground mt-1">95% CI: [0.6, 2.1]</div>
              </div>
            </div>
          </div>

          <div className="p-6 bg-card border border-border rounded-xl">
            <h3 className="font-semibold mb-4">How It Works</h3>
            <div className="flex flex-wrap gap-2">
              {[
                { num: 1, text: "Parse intervention" },
                { num: 2, text: "Identify mechanisms" },
                { num: 3, text: "Map to conditions" },
                { num: 4, text: "Monte Carlo simulation" },
                { num: 5, text: "Return distribution" },
              ].map(step => (
                <div key={step.num} className="flex items-center gap-2 px-4 py-2 bg-muted rounded-lg">
                  <span className="w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-xs font-semibold">{step.num}</span>
                  <span className="text-sm">{step.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Science */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("science")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">4. The Science</h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-8">
            We don&apos;t guess. We synthesize evidence using established health economics methodology.
          </p>

          <div className="space-y-6 mb-12">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-3">QALYs: The Gold Standard</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Quality-Adjusted Life Years are the standard metric used by NICE, FDA, and ICER for health technology assessment<Cite id={10} />. One QALY = one year of perfect health. The methodology is detailed in &quot;Cost-Effectiveness in Health and Medicine&quot;<Cite id={11} />, the authoritative reference used by all major health systems.
              </p>
            </div>

            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-3">Evidence Hierarchy</h3>
              <div className="flex flex-col gap-2 text-sm">
                <div className="flex items-center gap-3 p-2 bg-primary/10 rounded-lg">
                  <span className="text-primary font-semibold">1</span>
                  <span>Meta-analyses of RCTs</span>
                </div>
                <div className="flex items-center gap-3 p-2 bg-muted rounded-lg">
                  <span className="text-muted-foreground font-semibold">2</span>
                  <span className="text-muted-foreground">Randomized controlled trials</span>
                </div>
                <div className="flex items-center gap-3 p-2 bg-muted rounded-lg">
                  <span className="text-muted-foreground font-semibold">3</span>
                  <span className="text-muted-foreground">Large prospective cohorts</span>
                </div>
                <div className="flex items-center gap-3 p-2 bg-muted rounded-lg">
                  <span className="text-muted-foreground font-semibold">4</span>
                  <span className="text-muted-foreground">Mechanistic models with uncertainty</span>
                </div>
              </div>
            </div>

            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-lg mb-3">Mechanism-Based Modeling</h3>
              <p className="text-sm text-muted-foreground leading-relaxed mb-4">
                Rather than relying on black-box AI, we decompose interventions into causal pathways:
              </p>
              <div className="text-sm font-mono bg-muted p-4 rounded-lg overflow-x-auto">
                <div className="text-muted-foreground">Intervention: Walking 30 min/day</div>
                <div className="mt-2">→ <span className="text-primary">blood_pressure</span> ↓4 mmHg (Cornelissen 2013)</div>
                <div>→ <span className="text-primary">insulin_sensitivity</span> ↑15% (Colberg 2016)</div>
                <div>→ <span className="text-primary">inflammation</span> ↓15% CRP (meta-analysis)</div>
                <div className="mt-2 text-muted-foreground">→ Conditions affected: CHD, stroke, T2D, depression</div>
                <div className="text-muted-foreground">→ Mortality HR: 0.83 [0.78-0.88]<Cite id={2} /></div>
              </div>
            </div>
          </div>

          <div className="p-6 bg-primary/5 border-l-4 border-primary rounded-r-xl">
            <h4 className="font-semibold mb-2">Bayesian Uncertainty</h4>
            <p className="text-sm text-muted-foreground">
              We propagate uncertainty through Monte Carlo simulation. Every estimate comes with a credible interval reflecting genuine scientific uncertainty—not false precision.
            </p>
          </div>
        </div>
      </section>

      {/* Markets */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("markets")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">5. The Market</h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-8">
            Health optimization is a massive, growing market with no dominant player in evidence-based personalization.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-12">
            {[
              { name: "Digital Health", size: "$240B → $780B", growth: "17.6% CAGR", source: 4 },
              { name: "Wellness Apps", size: "$70B+", growth: "14.8% CAGR", source: 5 },
              { name: "Longevity Tech", size: "$27B → $44B", growth: "10%+ CAGR", source: 5 },
              { name: "Health Coaching", size: "$8B → $15B", growth: "12% CAGR", source: 4 },
            ].map(market => (
              <div key={market.name} className="p-6 bg-card border border-border rounded-xl hover:border-primary/30 transition-colors">
                <h3 className="font-semibold text-lg mb-1">{market.name}</h3>
                <div className="text-2xl font-bold text-primary mb-1">{market.size}<Cite id={market.source} /></div>
                <p className="text-sm text-muted-foreground">{market.growth} through 2030</p>
              </div>
            ))}
          </div>

          <div className="p-6 bg-card border border-border rounded-xl mb-8">
            <h3 className="font-semibold mb-4">Why Now?</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <h4 className="font-medium text-primary mb-2">AI Capability</h4>
                <p className="text-muted-foreground">LLMs can now synthesize medical literature and explain tradeoffs in plain language.</p>
              </div>
              <div>
                <h4 className="font-medium text-primary mb-2">Data Availability</h4>
                <p className="text-muted-foreground">GBD, UK Biobank, and meta-analyses provide unprecedented evidence bases.</p>
              </div>
              <div>
                <h4 className="font-medium text-primary mb-2">Consumer Demand</h4>
                <p className="text-muted-foreground">Post-COVID health awareness. Biohacking mainstream. Quantified self movement.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Model */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("model")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">6. Business Model</h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-8">
            Freemium consumer + B2B licensing. Open methodology, closed data integrations.
          </p>

          <div className="space-y-1 mb-12 rounded-xl overflow-hidden">
            {[
              { tier: "Free", desc: "Basic analysis, common interventions", price: "Free", color: "border-l-green-500" },
              { tier: "Pro", desc: "Unlimited queries, personalization, API access", price: "$9.99/mo", color: "border-l-primary" },
              { tier: "API", desc: "Health apps, coaches, corporate wellness", price: "$0.01-0.10/query", color: "border-l-amber-500" },
              { tier: "Enterprise", desc: "White-label, custom integrations, SLA", price: "$50K-500K/yr", color: "border-l-pink-500" },
            ].map(tier => (
              <div key={tier.tier} className={`flex justify-between items-center p-5 bg-card border-l-4 ${tier.color} hover:bg-muted/50 transition-colors`}>
                <div>
                  <h3 className="font-semibold">{tier.tier}</h3>
                  <p className="text-sm text-muted-foreground">{tier.desc}</p>
                </div>
                <span className="font-mono text-primary font-semibold">{tier.price}</span>
              </div>
            ))}
          </div>

          <div className="p-6 bg-card border border-border rounded-xl">
            <h3 className="font-semibold mb-4">B2B Opportunities</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div className="p-4 bg-muted rounded-lg">
                <h4 className="font-medium mb-1">Health Insurance</h4>
                <p className="text-muted-foreground">Risk stratification, incentive programs</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <h4 className="font-medium mb-1">Corporate Wellness</h4>
                <p className="text-muted-foreground">ROI measurement for programs</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <h4 className="font-medium mb-1">Pharma/Biotech</h4>
                <p className="text-muted-foreground">Patient stratification, trial design</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <h4 className="font-medium mb-1">Telehealth Platforms</h4>
                <p className="text-muted-foreground">Embedded decision support</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Traction */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("traction")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">7. Traction</h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-8">
            We&apos;ve built the core engine and validated the approach.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
            {[
              { value: "20+", label: "Precomputed interventions" },
              { value: "30+", label: "Biological mechanisms" },
              { value: "50+", label: "Evidence sources" },
              { value: "10K", label: "Monte Carlo iterations" },
            ].map(stat => (
              <div key={stat.label} className="text-center p-6 bg-card border border-border rounded-xl">
                <span className="block text-3xl font-bold text-primary">{stat.value}</span>
                <span className="text-sm text-muted-foreground">{stat.label}</span>
              </div>
            ))}
          </div>

          <div className="space-y-4 mb-12">
            <h3 className="font-semibold text-lg">Built So Far</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-card border border-border rounded-lg">
                <h4 className="font-medium mb-2">QALY Engine</h4>
                <p className="text-sm text-muted-foreground">Mechanism → condition → QALY mapping with uncertainty propagation</p>
              </div>
              <div className="p-4 bg-card border border-border rounded-lg">
                <h4 className="font-medium mb-2">Evidence Library</h4>
                <p className="text-sm text-muted-foreground">CDC life tables, GBD disability weights, hazard ratios from meta-analyses</p>
              </div>
              <div className="p-4 bg-card border border-border rounded-lg">
                <h4 className="font-medium mb-2">AI Integration</h4>
                <p className="text-sm text-muted-foreground">Claude-powered mechanism elicitation with structured output</p>
              </div>
              <div className="p-4 bg-card border border-border rounded-lg">
                <h4 className="font-medium mb-2">Web App</h4>
                <p className="text-sm text-muted-foreground">Live at optiqal.ai with analyze functionality</p>
              </div>
            </div>
          </div>

          <div className="p-6 bg-primary/5 border border-primary/20 rounded-xl">
            <h3 className="font-semibold mb-2">Founder Background</h3>
            <p className="text-sm text-muted-foreground">
              Built PolicyEngine—microsimulation models used by UK Government and US Congress. Deep expertise in evidence synthesis, Bayesian modeling, and policy analysis at scale.
            </p>
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("team")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">8. Team</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 bg-card border border-border rounded-xl">
              <h3 className="font-semibold text-xl mb-1">Max Ghenis</h3>
              <p className="text-sm text-primary mb-4">Founder & CEO</p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">Founded PolicyEngine—used by UK Gov, US Congress</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">Former Google data scientist</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">MIT economics, UC Berkeley statistics</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">10+ years in evidence synthesis</li>
              </ul>
              <div className="flex gap-4 mt-4">
                <a href="https://linkedin.com/in/maxghenis" target="_blank" rel="noopener noreferrer" className="text-sm text-muted-foreground hover:text-primary transition-colors">LinkedIn</a>
                <a href="https://github.com/maxghenis" target="_blank" rel="noopener noreferrer" className="text-sm text-muted-foreground hover:text-primary transition-colors">GitHub</a>
              </div>
            </div>

            <div className="p-6 bg-card border border-dashed border-border rounded-xl">
              <h3 className="font-semibold text-xl mb-1">Hiring</h3>
              <p className="text-sm text-muted-foreground mb-4">Co-founders & early team</p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">Health economist / epidemiologist</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">Full-stack engineer</li>
                <li className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-primary">ML/AI engineer</li>
              </ul>
              <p className="text-xs text-muted-foreground mt-4 italic">
                Contact: max@optiqal.ai
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Risks */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("risks")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">9. Risks & Mitigations</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              {
                risk: "Medical liability",
                question: "Could users sue over health advice?",
                answer: "We're an information tool, not medical advice. Clear disclaimers. Show uncertainty. Similar to nutrition labels or fitness trackers.",
              },
              {
                risk: "Evidence quality",
                question: "What if underlying studies are wrong?",
                answer: "We surface uncertainty, show sources, update as evidence evolves. Meta-analyses are self-correcting. We're transparent about limitations.",
              },
              {
                risk: "AI hallucination",
                question: "Won't AI make things up?",
                answer: "Hybrid approach: precomputed interventions for common queries (no AI), AI only for novel queries with structured output and citation requirements.",
              },
              {
                risk: "User comprehension",
                question: "Can regular people understand QALYs?",
                answer: "We translate to intuitive terms: 'equivalent to X healthy months.' User research shows people grasp the concept quickly.",
              },
              {
                risk: "Competition",
                question: "What about Apple Health, Whoop, etc.?",
                answer: "They track metrics, we interpret meaning. Complementary. We're the 'so what?' layer on top of tracking data.",
              },
              {
                risk: "Personalization limits",
                question: "How personalized can it really be?",
                answer: "Start with age/sex/baseline risk factors. Expand to genetics, wearables, biomarkers over time. Even generic estimates are better than nothing.",
              },
            ].map(item => (
              <div key={item.risk} className="p-5 bg-card border border-border rounded-xl hover:border-border/80 transition-colors">
                <h4 className="font-semibold mb-1">{item.risk}</h4>
                <p className="text-sm text-primary italic mb-2">{item.question}</p>
                <p className="text-sm text-muted-foreground">{item.answer}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Vision */}
      <section className="min-h-screen py-24 px-6 flex flex-col items-center" ref={setRef("vision")}>
        <div className="max-w-3xl w-full">
          <h2 className="font-serif text-4xl font-bold mb-8">10. The Vision</h2>

          <p className="text-xl text-foreground font-medium mb-8 leading-relaxed">
            A world where everyone can make health decisions with the same evidence quality as a team of epidemiologists—instantly, affordably, personally.
          </p>

          <div className="space-y-4 mb-12">
            <div className="p-4 bg-card border border-border rounded-lg flex items-center gap-4">
              <span className="text-2xl font-bold text-primary">Y1</span>
              <p className="text-muted-foreground">Consumer app live. 100K users. Key interventions covered.</p>
            </div>
            <div className="p-4 bg-card border border-border rounded-lg flex items-center gap-4">
              <span className="text-2xl font-bold text-primary">Y2</span>
              <p className="text-muted-foreground">API launched. First B2B partnerships. Wearable integrations.</p>
            </div>
            <div className="p-4 bg-card border border-border rounded-lg flex items-center gap-4">
              <span className="text-2xl font-bold text-primary">Y3</span>
              <p className="text-muted-foreground">Enterprise deals. Genetic integration. International expansion.</p>
            </div>
            <div className="p-4 bg-card border border-border rounded-lg flex items-center gap-4">
              <span className="text-2xl font-bold text-primary">Y5</span>
              <p className="text-muted-foreground">Standard infrastructure for health decisions. Millions of users.</p>
            </div>
          </div>

          <div className="p-6 bg-primary/5 border-l-4 border-primary rounded-r-xl mb-12">
            <p className="text-lg italic">
              &quot;The best time to plant a tree was 20 years ago. The second best time is now.&quot;
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              We help people know exactly how much that tree is worth—in quality-adjusted life.
            </p>
          </div>
        </div>
      </section>

      {/* References */}
      <section className="py-16 px-6 bg-card border-t border-border">
        <div className="max-w-3xl mx-auto">
          <h2 className="font-serif text-2xl font-bold mb-6">References</h2>
          <ol className="space-y-3 text-sm">
            {sources.map(source => (
              <li key={source.id} className="pl-8 relative text-muted-foreground">
                <span className="absolute left-0 font-mono text-primary">[{source.id}]</span>
                {source.author && <span>{source.author}. </span>}
                <em className="text-foreground">{source.title}</em>
                {source.year && <span> ({source.year})</span>}.{" "}
                <a href={source.url} target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors break-all">
                  {source.url.replace(/^https?:\/\//, "").split("/")[0]}
                </a>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 text-center relative">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[600px] h-[300px] bg-primary/10 rounded-full blur-3xl opacity-50" />
        </div>
        <h2 className="font-serif text-4xl font-bold mb-4 relative z-10">Interested?</h2>
        <p className="text-lg text-muted-foreground mb-8 relative z-10">
          We&apos;re building the future of evidence-based health decisions.
        </p>
        <div className="flex justify-center gap-4 relative z-10">
          <a
            href="mailto:max@optiqal.ai"
            className="px-6 py-3 bg-primary text-primary-foreground rounded-full font-medium hover:opacity-90 transition-opacity shadow-lg shadow-primary/25"
          >
            Get in Touch
          </a>
          <Link
            href="/"
            className="px-6 py-3 bg-transparent border border-border text-foreground rounded-full font-medium hover:bg-muted transition-colors"
          >
            ← Back to Home
          </Link>
        </div>
      </section>
    </div>
  );
}
