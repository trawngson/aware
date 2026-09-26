// Who is calling an Edge Function.

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const part = token.split(".")[1];
  if (!part) return null;
  try {
    const json = atob(part.replaceAll("-", "+").replaceAll("_", "/").padEnd(Math.ceil(part.length / 4) * 4, "="));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** The bearer token of an Authorization header, or null. */
export function bearerToken(header: string | null): string | null {
  const match = header?.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : null;
}

/**
 * True when the request carries the service-role key (the scheduled job that
 * drains the outbox), never for a signed-in user. The platform has already
 * checked the JWT's signature before the function runs.
 */
export function isServiceRequest(header: string | null, serviceKey: string | undefined): boolean {
  const token = bearerToken(header);
  if (!token) return false;
  if (serviceKey && token === serviceKey) return true;
  return decodeJwtPayload(token)?.role === "service_role";
}
