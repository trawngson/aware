// Apple Push Notification service (APNs) helpers: the token-based JWT, the
// request, and reading the settings from the function's secrets. Plain
// functions, so tests can run them with a fake `fetch` and never call Apple.

export interface ApnsConfig {
  keyId: string;
  teamId: string;
  /** The .p8 key's contents (PKCS#8 PEM). */
  privateKey: string;
  bundleId: string;
  /** Send everything to the development (sandbox) server. */
  useSandbox: boolean;
}

export interface DeviceToken {
  token: string;
  user_id: string;
  environment: "sandbox" | "production";
}

export interface ApnsResult {
  status: number;
  reason?: string;
}

/** The APNs settings, or null when any required secret is missing. */
export function readApnsConfig(env: Record<string, string | undefined>): ApnsConfig | null {
  const keyId = env.APNS_KEY_ID?.trim();
  const teamId = env.APNS_TEAM_ID?.trim();
  const privateKey = env.APNS_PRIVATE_KEY?.trim();
  const bundleId = env.APNS_BUNDLE_ID?.trim();
  if (!keyId || !teamId || !privateKey || !bundleId) return null;
  return {
    keyId,
    teamId,
    // Secrets set on one line keep their line breaks as "\n".
    privateKey: privateKey.replaceAll("\\n", "\n"),
    bundleId,
    useSandbox: env.APNS_USE_SANDBOX?.trim().toLowerCase() === "true",
  };
}

export function base64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function pemToDer(pem: string): ArrayBuffer {
  const body = pem.replace(/-----(BEGIN|END) [A-Z ]+-----/g, "").replace(/\s+/g, "");
  const bytes = Uint8Array.from(atob(body), (c) => c.charCodeAt(0));
  return bytes.buffer as ArrayBuffer;
}

/** The ES256 JWT APNs expects: {alg, kid} and {iss: team, iat: seconds}. */
export async function makeApnsJwt(config: ApnsConfig, nowSeconds: number): Promise<string> {
  const encode = (value: unknown) => base64url(new TextEncoder().encode(JSON.stringify(value)));
  const signingInput = `${encode({ alg: "ES256", kid: config.keyId })}.${encode({ iss: config.teamId, iat: nowSeconds })}`;
  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToDer(config.privateKey),
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["sign"],
  );
  // Web Crypto returns the raw r||s signature JWTs use.
  const signature = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, new TextEncoder().encode(signingInput));
  return `${signingInput}.${base64url(new Uint8Array(signature))}`;
}

export function apnsHost(config: ApnsConfig, device: DeviceToken): string {
  return config.useSandbox || device.environment === "sandbox"
    ? "api.sandbox.push.apple.com"
    : "api.push.apple.com";
}

/** True when APNs says the token will never work again. */
export function isDeadToken(result: ApnsResult): boolean {
  return result.status === 410 ||
    (result.status === 400 && ["BadDeviceToken", "DeviceTokenNotForTopic"].includes(result.reason ?? ""));
}

/**
 * Returns a function that sends one notification. The JWT is reused for 40
 * minutes (APNs wants a new one at most hourly, and not more than every 20).
 */
export function makeApnsSender(
  config: ApnsConfig,
  fetchFn: typeof fetch = fetch,
  now: () => number = () => Date.now(),
): (device: DeviceToken, payload: unknown) => Promise<ApnsResult> {
  let cached: { jwt: string; issuedAt: number } | null = null;
  return async (device, payload) => {
    const current = now();
    if (!cached || current - cached.issuedAt > 40 * 60 * 1000) {
      cached = { jwt: await makeApnsJwt(config, Math.floor(current / 1000)), issuedAt: current };
    }
    const response = await fetchFn(`https://${apnsHost(config, device)}/3/device/${device.token}`, {
      method: "POST",
      headers: {
        authorization: `bearer ${cached.jwt}`,
        "apns-topic": config.bundleId,
        "apns-push-type": "alert",
        "apns-priority": "10",
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    let reason: string | undefined;
    if (!response.ok) {
      try {
        reason = (await response.json()).reason;
      } catch {
        reason = undefined;
      }
    } else {
      await response.body?.cancel();
    }
    return { status: response.status, reason };
  };
}
