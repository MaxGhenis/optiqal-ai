import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Shared medical disclaimer surfaced on every results page and persistently in
 * the app footer. The copy is intentionally identical everywhere so the safety
 * message reads the same regardless of where a user lands.
 */
export const MEDICAL_DISCLAIMER_TEXT =
  "Statistical estimates, not medical advice. Prescription items require a clinician. Consult a healthcare professional before acting.";

interface MedicalDisclaimerProps {
  /**
   * "banner" renders a full-width card for the top of a results surface.
   * "compact" renders a single muted line for the persistent layout footer.
   */
  variant?: "banner" | "compact";
  className?: string;
}

export function MedicalDisclaimer({
  variant = "banner",
  className,
}: MedicalDisclaimerProps) {
  if (variant === "compact") {
    return (
      <p
        role="note"
        aria-label="Medical disclaimer"
        className={cn(
          "flex items-start justify-center gap-2 px-4 py-3 text-center text-xs text-muted-foreground",
          className
        )}
      >
        <ShieldAlert
          aria-hidden="true"
          className="mt-px h-3.5 w-3.5 shrink-0 text-highlight"
        />
        <span>{MEDICAL_DISCLAIMER_TEXT}</span>
      </p>
    );
  }

  return (
    <div
      role="note"
      aria-label="Medical disclaimer"
      className={cn(
        "flex items-start gap-3 rounded-2xl border border-highlight/30 bg-highlight/5 px-4 py-3",
        className
      )}
    >
      <ShieldAlert
        aria-hidden="true"
        className="mt-0.5 h-5 w-5 shrink-0 text-highlight"
      />
      <p className="text-sm leading-relaxed text-text-soft">
        {MEDICAL_DISCLAIMER_TEXT}
      </p>
    </div>
  );
}
