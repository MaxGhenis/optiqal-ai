import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  MEDICAL_DISCLAIMER_TEXT,
  MedicalDisclaimer,
} from "@/components/medical-disclaimer";

describe("MedicalDisclaimer", () => {
  afterEach(cleanup);

  it("uses the exact required copy", () => {
    expect(MEDICAL_DISCLAIMER_TEXT).toBe(
      "Statistical estimates, not medical advice. Prescription items require a clinician. Consult a healthcare professional before acting."
    );
  });

  it("renders the full copy in the default banner variant", () => {
    render(<MedicalDisclaimer />);
    const note = screen.getByRole("note", { name: /medical disclaimer/i });
    expect(note).toHaveTextContent(MEDICAL_DISCLAIMER_TEXT);
  });

  it("renders the full copy in the compact variant used by the footer", () => {
    render(<MedicalDisclaimer variant="compact" />);
    const note = screen.getByRole("note", { name: /medical disclaimer/i });
    expect(note).toHaveTextContent(MEDICAL_DISCLAIMER_TEXT);
  });
});
