import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Terms of Service — Optiqal",
  description: "Terms of service for using Optiqal",
};

export default function TermsPage() {
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

        <h1 className="text-3xl font-bold mb-8">Terms of Service</h1>
        <p className="text-sm text-muted-foreground mb-8">
          Last updated: December 25, 2024
        </p>

        <div className="prose prose-invert prose-sm max-w-none space-y-6">
          <section>
            <h2 className="text-xl font-semibold mb-3">1. Acceptance of Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              By accessing or using Optiqal (&quot;the Service&quot;), you agree to be bound by these
              Terms of Service. If you do not agree to these terms, please do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">2. Educational Purpose Only</h2>
            <p className="text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Optiqal is strictly for educational and informational purposes.</strong>{" "}
              The Service provides estimates and visualizations based on published research and actuarial
              data to help you understand how lifestyle factors may affect life expectancy and quality
              of life at a population level.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-3">
              The Service does NOT provide:
            </p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>Medical advice, diagnosis, or treatment</li>
              <li>Individual health predictions or prognoses</li>
              <li>Recommendations for specific health decisions</li>
              <li>A substitute for professional medical consultation</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">3. No Medical Advice Disclaimer</h2>
            <p className="text-muted-foreground leading-relaxed">
              <strong className="text-foreground">
                Always consult a qualified healthcare professional before making any health-related decisions.
              </strong>{" "}
              The estimates provided by Optiqal are based on population-level statistics and cannot
              predict individual outcomes. Your personal health situation may differ significantly
              from population averages due to genetics, medical conditions, environment, and other
              factors not captured in our models.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">4. Limitation of Liability</h2>
            <p className="text-muted-foreground leading-relaxed">
              To the maximum extent permitted by law, Optiqal and its creators shall not be liable
              for any direct, indirect, incidental, special, consequential, or punitive damages
              arising from your use of or inability to use the Service. This includes, but is not
              limited to, any decisions made based on information provided by the Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">5. Accuracy of Information</h2>
            <p className="text-muted-foreground leading-relaxed">
              While we strive to base our estimates on peer-reviewed research and official data
              sources (such as CDC life tables), we make no warranties or representations about
              the accuracy, reliability, or completeness of any information provided. Scientific
              understanding evolves, and our models may not reflect the most current research.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">6. Privacy and Data</h2>
            <p className="text-muted-foreground leading-relaxed">
              Your use of the Service is also governed by our{" "}
              <Link href="/privacy" className="text-primary hover:underline">
                Privacy Policy
              </Link>
              . By using the Service, you consent to the collection and use of information as
              described in the Privacy Policy.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">7. Changes to Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              We reserve the right to modify these Terms at any time. Changes will be effective
              immediately upon posting. Your continued use of the Service after any changes
              constitutes acceptance of the new Terms.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">8. Contact</h2>
            <p className="text-muted-foreground leading-relaxed">
              For questions about these Terms, please contact us through the project&apos;s GitHub
              repository.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
