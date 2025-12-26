"use client";

import Link from "next/link";
import { ArrowLeft, ChevronDown } from "lucide-react";
import { useState } from "react";

const faqs = [
  {
    question: "What is a QALY?",
    answer:
      "A QALY (Quality-Adjusted Life Year) is a measure that combines both the quantity and quality of life. One QALY equals one year of life in perfect health. A year spent in less-than-perfect health is worth less than one QALY, reflecting reduced quality of life.",
  },
  {
    question: "How accurate are these estimates?",
    answer:
      "Our estimates are based on population-level research and actuarial data, not individual predictions. They show average effects observed in large studies, but your personal outcomes may vary significantly based on genetics, environment, and factors not captured in our models.",
  },
  {
    question: "Where does the data come from?",
    answer:
      "We use peer-reviewed research, CDC life tables, and published epidemiological studies. Each estimate is derived from meta-analyses and large cohort studies that examine how lifestyle factors affect mortality and quality of life at the population level.",
  },
  {
    question: "Is this medical advice?",
    answer:
      "No. Optiqal is strictly for educational purposes. The information provided is not medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional before making any health-related decisions.",
  },
  {
    question: "How is my data handled?",
    answer:
      "All calculations happen in your browser. We do not collect, store, or transmit your personal health information. See our Privacy Policy for complete details on our data practices.",
  },
  {
    question: "What lifestyle factors are included?",
    answer:
      "We currently model factors with strong research backing including smoking, alcohol consumption, exercise, diet, sleep, and BMI. We continually evaluate new research to expand our coverage while maintaining scientific rigor.",
  },
  {
    question: "Can I trust these numbers for my personal decisions?",
    answer:
      "Use these estimates as one input among many, not as definitive predictions. They illustrate general patterns from research but cannot account for your unique circumstances. Discuss any health decisions with your doctor.",
  },
];

function FAQItem({
  question,
  answer,
  isOpen,
  onToggle,
}: {
  question: string;
  answer: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-border">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between py-4 text-left hover:text-primary transition-colors"
      >
        <span className="text-lg font-medium">{question}</span>
        <ChevronDown
          className={`w-5 h-5 text-muted-foreground transition-transform duration-200 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>
      <div
        className={`overflow-hidden transition-all duration-200 ${
          isOpen ? "max-h-48 pb-4" : "max-h-0"
        }`}
      >
        <p className="text-muted-foreground leading-relaxed">{answer}</p>
      </div>
    </div>
  );
}

export default function FAQPage() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

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

        <h1 className="text-3xl font-bold mb-8">Frequently Asked Questions</h1>

        <div className="space-y-0">
          {faqs.map((faq, index) => (
            <FAQItem
              key={index}
              question={faq.question}
              answer={faq.answer}
              isOpen={openIndex === index}
              onToggle={() => setOpenIndex(openIndex === index ? null : index)}
            />
          ))}
        </div>

        <div className="mt-12 p-6 bg-muted/30 rounded-lg">
          <p className="text-muted-foreground text-sm">
            Have more questions? Check out our{" "}
            <Link href="/terms" className="text-primary hover:underline">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="text-primary hover:underline">
              Privacy Policy
            </Link>{" "}
            for additional information.
          </p>
        </div>
      </div>
    </main>
  );
}
