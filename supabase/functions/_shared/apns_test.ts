import { assert, assertEquals, assertNotEquals } from "jsr:@std/assert@1.0.14";
import {
  apnsHost,
  type ApnsConfig,
  base64url,
  isDeadToken,
  makeApnsJwt,
  makeApnsSender,
  readApnsConfig,
} from "./apns.ts";

async function testKey(): Promise<{ pem: string; publicKey: CryptoKey }> {
  const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  const der = new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey));
  const body = btoa(String.fromCharCode(...der)).match(/.{1,64}/g)!.join("\n");
  return { pem: `-----BEGIN PRIVATE KEY-----\n${body}\n-----END PRIVATE KEY-----`, publicKey: pair.publicKey };
}

function decode(part: string): Record<string, unknown> {
  return JSON.parse(atob(part.replaceAll("-", "+").replaceAll("_", "/").padEnd(Math.ceil(part.length / 4) * 4, "=")));
}

Deno.test("APNs settings need all four secrets", () => {
  assertEquals(readApnsConfig({}), null);
  assertEquals(readApnsConfig({ APNS_KEY_ID: "K", APNS_TEAM_ID: "T", APNS_PRIVATE_KEY: "P" }), null);
  const config = readApnsConfig({
    APNS_KEY_ID: " K ",
    APNS_TEAM_ID: "T",
    APNS_PRIVATE_KEY: "line1\\nline2",
    APNS_BUNDLE_ID: "net.nctson.awareapp",
    APNS_USE_SANDBOX: "TRUE",
  });
  assertEquals(config, { keyId: "K", teamId: "T", privateKey: "line1\nline2", bundleId: "net.nctson.awareapp", useSandbox: true });
  assertEquals(readApnsConfig({ APNS_KEY_ID: "K", APNS_TEAM_ID: "T", APNS_PRIVATE_KEY: "P", APNS_BUNDLE_ID: "B" })?.useSandbox, false);
});

Deno.test("the JWT is signed with the .p8 key and carries the key and team", async () => {
  const { pem, publicKey } = await testKey();
  const config: ApnsConfig = { keyId: "ABC123DEFG", teamId: "TEAM123456", privateKey: pem, bundleId: "b", useSandbox: false };
  const jwt = await makeApnsJwt(config, 1_790_000_000);
  const [header, claims, signature] = jwt.split(".");
  assertEquals(decode(header), { alg: "ES256", kid: "ABC123DEFG" });
  assertEquals(decode(claims), { iss: "TEAM123456", iat: 1_790_000_000 });
  const raw = Uint8Array.from(atob(signature.replaceAll("-", "+").replaceAll("_", "/").padEnd(88, "=")), (c) => c.charCodeAt(0));
  assertEquals(raw.length, 64);
  const valid = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, publicKey, raw,
    new TextEncoder().encode(`${header}.${claims}`));
  assert(valid, "the signature verifies with the public key");
});

Deno.test("sandbox tokens and the sandbox setting use Apple's development server", () => {
  const config: ApnsConfig = { keyId: "K", teamId: "T", privateKey: "", bundleId: "b", useSandbox: false };
  const production = { token: "aa", user_id: "u", environment: "production" as const };
  const sandbox = { token: "bb", user_id: "u", environment: "sandbox" as const };
  assertEquals(apnsHost(config, production), "api.push.apple.com");
  assertEquals(apnsHost(config, sandbox), "api.sandbox.push.apple.com");
  assertEquals(apnsHost({ ...config, useSandbox: true }, production), "api.sandbox.push.apple.com");
});

Deno.test("the sender posts to APNs with the right headers and reuses its JWT", async () => {
  const { pem } = await testKey();
  const config: ApnsConfig = { keyId: "K", teamId: "T", privateKey: pem, bundleId: "net.nctson.awareapp", useSandbox: false };
  const calls: { url: string; init: RequestInit }[] = [];
  const fakeFetch = ((url: string, init: RequestInit) => {
    calls.push({ url, init });
    return Promise.resolve(calls.length === 3
      ? new Response(JSON.stringify({ reason: "BadDeviceToken" }), { status: 400 })
      : new Response(null, { status: 200 }));
  }) as unknown as typeof fetch;
  let now = 1_790_000_000_000;
  const send = makeApnsSender(config, fakeFetch, () => now);
  const device = { token: "abcd", user_id: "u", environment: "production" as const };

  assertEquals(await send(device, { aps: { alert: { title: "Hi", body: "There" } } }), { status: 200, reason: undefined });
  assertEquals(calls[0].url, "https://api.push.apple.com/3/device/abcd");
  const headers = calls[0].init.headers as Record<string, string>;
  assertEquals(headers["apns-topic"], "net.nctson.awareapp");
  assertEquals(headers["apns-push-type"], "alert");
  assert(headers.authorization.startsWith("bearer "));
  assertEquals(JSON.parse(calls[0].init.body as string).aps.alert.title, "Hi");

  now += 10 * 60 * 1000;
  await send(device, {});
  assertEquals((calls[1].init.headers as Record<string, string>).authorization, headers.authorization,
    "the JWT is reused for a while");
  now += 45 * 60 * 1000;
  assertEquals(await send(device, {}), { status: 400, reason: "BadDeviceToken" });
  assertNotEquals((calls[2].init.headers as Record<string, string>).authorization, headers.authorization,
    "and renewed after 40 minutes");
});

Deno.test("dead tokens are recognised", () => {
  assert(isDeadToken({ status: 410, reason: "Unregistered" }));
  assert(isDeadToken({ status: 400, reason: "BadDeviceToken" }));
  assert(!isDeadToken({ status: 400, reason: "PayloadTooLarge" }));
  assert(!isDeadToken({ status: 500 }));
});

Deno.test("base64url has no padding or URL-unsafe characters", () => {
  assertEquals(base64url(new Uint8Array([251, 255, 191])), "-_-_");
});
