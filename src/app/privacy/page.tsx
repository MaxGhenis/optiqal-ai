import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Privacy Policy — Optiqal",
  description: "Privacy policy for Optiqal",
};

export default function PrivacyPage() {
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

        <h1 className="text-3xl font-bold mb-8">Privacy Policy</h1>
        <p className="text-sm text-muted-foreground mb-8">
          Last updated: December 25, 2024
        </p>

        <div className="prose prose-invert prose-sm max-w-none space-y-6">
          <section>
            <h2 className="text-xl font-semibold mb-3">Overview</h2>
            <p className="text-muted-foreground leading-relaxed">
              Optiqal is designed with privacy in mind. We minimize data collection and do not
              sell or share your personal information with third parties for marketing purposes.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Information We Collect</h2>

            <h3 className="text-lg font-medium mt-4 mb-2">Profile Data You Provide</h3>
            <p className="text-muted-foreground leading-relaxed">
              When you use Optiqal, you may enter personal information such as age, sex, height,
              weight, and lifestyle factors. This data is:
            </p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>Processed locally in your browser for calculations</li>
              <li>Optionally saved to your browser&apos;s local storage for convenience</li>
              <li>Not transmitted to our servers unless you explicitly choose to share results</li>
            </ul>

            <h3 className="text-lg font-medium mt-4 mb-2">Sharing Feature</h3>
            <p className="text-muted-foreground leading-relaxed">
              If you use the sharing feature to create a shareable link, your profile data is
              encoded in the URL. This data is not stored on our servers; the URL contains all
              the information needed to reproduce your results. Anyone with the link can view
              the shared results.
            </p>

            <h3 className="text-lg font-medium mt-4 mb-2">Analytics</h3>
            <p className="text-muted-foreground leading-relaxed">
              We may use privacy-respecting analytics to understand how the Service is used.
              This may include aggregate data such as page views, feature usage, and general
              geographic regions. We do not use analytics that track individual users across
              websites or create advertising profiles.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">How We Use Information</h2>
            <p className="text-muted-foreground leading-relaxed">
              Information you provide is used solely to:
            </p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>Calculate and display your personalized estimates</li>
              <li>Save your preferences for future visits (if you choose)</li>
              <li>Generate shareable links (if you use the sharing feature)</li>
              <li>Improve the Service based on aggregate usage patterns</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Data Storage</h2>
            <p className="text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Local Storage:</strong> Your profile data may be
              stored in your browser&apos;s local storage. This data remains on your device and can
              be cleared through your browser settings.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-3">
              <strong className="text-foreground">No Server-Side Storage:</strong> We do not maintain
              a database of user profiles. Your health information is not stored on our servers.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Third-Party Services</h2>
            <p className="text-muted-foreground leading-relaxed">
              The Service is hosted on Vercel. Please refer to{" "}
              <a
                href="https://vercel.com/legal/privacy-policy"
                className="text-primary hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Vercel&apos;s Privacy Policy
              </a>{" "}
              for information about their data practices.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Your Rights</h2>
            <p className="text-muted-foreground leading-relaxed">
              You have the right to:
            </p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>Clear your locally stored data at any time through your browser settings</li>
              <li>Use the Service without providing accurate personal information</li>
              <li>Request information about what data we may have collected</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Children&apos;s Privacy</h2>
            <p className="text-muted-foreground leading-relaxed">
              The Service is not intended for use by individuals under 18 years of age. We do
              not knowingly collect information from children.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Changes to This Policy</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may update this Privacy Policy from time to time. Changes will be posted on
              this page with an updated effective date.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">Contact</h2>
            <p className="text-muted-foreground leading-relaxed">
              For privacy-related questions or concerns, please contact us through the project&apos;s
              GitHub repository.
            </p>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-border">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/terms" className="text-primary hover:underline">
              Terms of Service
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
