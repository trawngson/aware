import { assert, assertEquals } from "jsr:@std/assert@1.0.14";
import { bearerToken, isServiceRequest } from "./auth.ts";

function jwt(payload: Record<string, unknown>): string {
  const part = (value: unknown) => btoa(JSON.stringify(value)).replaceAll("=", "").replaceAll("+", "-").replaceAll("/", "_");
  return `${part({ alg: "HS256" })}.${part(payload)}.signature`;
}

Deno.test("only the service role may drain the outbox", () => {
  assert(isServiceRequest("Bearer secret-key", "secret-key"));
  assert(isServiceRequest(`Bearer ${jwt({ role: "service_role" })}`, "other"));
  assert(!isServiceRequest(`Bearer ${jwt({ role: "authenticated", sub: "u" })}`, "secret-key"));
  assert(!isServiceRequest(`Bearer ${jwt({ role: "anon" })}`, "secret-key"));
  assert(!isServiceRequest(null, "secret-key"));
  assert(!isServiceRequest("Bearer not-a-jwt", undefined));
});

Deno.test("bearer tokens are read from the header", () => {
  assertEquals(bearerToken("Bearer abc"), "abc");
  assertEquals(bearerToken("bearer   abc "), "abc");
  assertEquals(bearerToken("Basic abc"), null);
});
