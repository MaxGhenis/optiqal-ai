const DEFAULT_REMOTE_MODEL_ROUTE_PREFIX = "/svc/model";

function getConfiguredModelBaseUrl(): string | undefined {
  return process.env.OPTIQAL_MODEL_URL ?? process.env.MODEL_URL ?? undefined;
}

function getConfiguredModelBypassSecret(): string | undefined {
  return (
    process.env.OPTIQAL_MODEL_BYPASS_SECRET ??
    process.env.MODEL_PROTECTION_BYPASS_SECRET ??
    undefined
  );
}

function getConfiguredModelCookie(): string | undefined {
  return (
    process.env.OPTIQAL_MODEL_COOKIE ??
    process.env.MODEL_SERVICE_COOKIE ??
    undefined
  );
}

function isCrossOriginService(remoteBaseUrl: string, requestOrigin: string): boolean {
  try {
    const remoteUrl = new URL(remoteBaseUrl);
    const originUrl = new URL(requestOrigin);
    return remoteUrl.origin !== originUrl.origin;
  } catch {
    // Fail closed: malformed origin metadata must never cause request cookies
    // or deployment-protection credentials to be forwarded elsewhere.
    return true;
  }
}

export function getRemoteModelBaseUrl(origin: string): string | undefined {
  const configuredUrl = getConfiguredModelBaseUrl();
  if (configuredUrl) {
    return configuredUrl;
  }

  if (!process.env.NEXT_PUBLIC_MODEL_URL) {
    return undefined;
  }

  const routePrefix = process.env.NEXT_PUBLIC_MODEL_URL ?? DEFAULT_REMOTE_MODEL_ROUTE_PREFIX;
  return new URL(routePrefix, origin).toString();
}

export function getRemoteModelHeaders(
  headers: Headers,
  options?: {
    remoteBaseUrl?: string;
    requestOrigin?: string;
  }
): Record<string, string | undefined> {
  const bypassSecret = getConfiguredModelBypassSecret();
  const configuredCookie = getConfiguredModelCookie();
  const needsDedicatedBypass =
    options?.remoteBaseUrl &&
    options?.requestOrigin &&
    isCrossOriginService(options.remoteBaseUrl, options.requestOrigin);

  return {
    cookie:
      needsDedicatedBypass
        ? configuredCookie ?? undefined
        : headers.get("cookie") ?? undefined,
    "x-vercel-protection-bypass":
      needsDedicatedBypass
        ? bypassSecret ?? undefined
        : headers.get("x-vercel-protection-bypass") ??
          process.env.VERCEL_AUTOMATION_BYPASS_SECRET ??
          bypassSecret ??
          undefined,
    "x-vercel-set-bypass-cookie":
      needsDedicatedBypass ? undefined : headers.get("x-vercel-set-bypass-cookie") ?? undefined,
  };
}
