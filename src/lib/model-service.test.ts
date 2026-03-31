import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { getRemoteModelBaseUrl, getRemoteModelHeaders } from "@/lib/model-service";

describe("model service helpers", () => {
  beforeEach(() => {
    delete process.env.MODEL_URL;
    delete process.env.OPTIQAL_MODEL_URL;
    delete process.env.NEXT_PUBLIC_MODEL_URL;
    delete process.env.VERCEL;
    delete process.env.VERCEL_AUTOMATION_BYPASS_SECRET;
    delete process.env.MODEL_PROTECTION_BYPASS_SECRET;
    delete process.env.OPTIQAL_MODEL_BYPASS_SECRET;
  });

  afterEach(() => {
    delete process.env.MODEL_URL;
    delete process.env.OPTIQAL_MODEL_URL;
    delete process.env.NEXT_PUBLIC_MODEL_URL;
    delete process.env.VERCEL;
    delete process.env.VERCEL_AUTOMATION_BYPASS_SECRET;
    delete process.env.MODEL_PROTECTION_BYPASS_SECRET;
    delete process.env.OPTIQAL_MODEL_BYPASS_SECRET;
  });

  it("prefers configured model service urls", () => {
    process.env.MODEL_URL = "https://model.example/svc/model";

    expect(getRemoteModelBaseUrl("https://optiqal.ai")).toBe("https://model.example/svc/model");
  });

  it("builds a same-origin service url when an explicit public route prefix is configured", () => {
    process.env.NEXT_PUBLIC_MODEL_URL = "/svc/model";

    expect(getRemoteModelBaseUrl("https://preview.vercel.app")).toBe(
      "https://preview.vercel.app/svc/model"
    );
  });

  it("forwards incoming protection headers and cookies", () => {
    const headers = new Headers({
      cookie: "foo=bar",
      "x-vercel-protection-bypass": "request-secret",
      "x-vercel-set-bypass-cookie": "true",
    });

    expect(getRemoteModelHeaders(headers)).toEqual({
      cookie: "foo=bar",
      "x-vercel-protection-bypass": "request-secret",
      "x-vercel-set-bypass-cookie": "true",
    });
  });

  it("falls back to the automation bypass secret when no request header is present", () => {
    process.env.VERCEL_AUTOMATION_BYPASS_SECRET = "automation-secret";

    expect(getRemoteModelHeaders(new Headers())).toEqual({
      cookie: undefined,
      "x-vercel-protection-bypass": "automation-secret",
      "x-vercel-set-bypass-cookie": undefined,
    });
  });

  it("requires a dedicated bypass secret for cross-project vercel model services", () => {
    expect(() =>
      getRemoteModelHeaders(new Headers(), {
        remoteBaseUrl: "https://optiqal-model-preview.vercel.app",
        requestOrigin: "https://optiqal-preview.vercel.app",
      })
    ).toThrow("MODEL_PROTECTION_BYPASS_SECRET");
  });

  it("uses the dedicated model bypass secret for cross-project vercel model services", () => {
    process.env.MODEL_PROTECTION_BYPASS_SECRET = "model-secret";

    expect(
      getRemoteModelHeaders(
        new Headers({
          cookie: "foo=bar",
          "x-vercel-protection-bypass": "frontend-secret",
          "x-vercel-set-bypass-cookie": "true",
        }),
        {
          remoteBaseUrl: "https://optiqal-model-preview.vercel.app",
          requestOrigin: "https://optiqal-preview.vercel.app",
        }
      )
    ).toEqual({
      cookie: "foo=bar",
      "x-vercel-protection-bypass": "model-secret",
      "x-vercel-set-bypass-cookie": undefined,
    });
  });
});
