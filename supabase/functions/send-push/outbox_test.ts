import { assertEquals } from "jsr:@std/assert@1.0.14";
import type { DeviceToken } from "../_shared/apns.ts";
import { drainOutbox, type OutboxRow, type OutboxStore, payloadFor } from "./outbox.ts";

function memoryStore(rows: OutboxRow[], tokens: DeviceToken[]) {
  const state = { sent: [] as number[], failed: [] as { id: number; error: string }[], removed: [] as string[] };
  const store: OutboxStore = {
    pending: (limit) => Promise.resolve(rows.slice(0, limit)),
    tokensFor: (row) => Promise.resolve(tokens.filter((t) => row.recipient_id === null || t.user_id === row.recipient_id)),
    markSent: (id) => { state.sent.push(id); return Promise.resolve(); },
    markFailed: (row, error) => { state.failed.push({ id: row.id, error }); return Promise.resolve(); },
    removeToken: (token) => { state.removed.push(token); return Promise.resolve(); },
  };
  return { store, state };
}

const row = (id: number, recipient: string | null, kind: OutboxRow["kind"] = "reply"): OutboxRow =>
  ({ id, kind, recipient_id: recipient, title: "New reply", body: "Binh: So cool", post_id: "p1", attempts: 0 });
const token = (value: string, user: string): DeviceToken => ({ token: value, user_id: user, environment: "production" });

Deno.test("messages go to the recipient's phones, dead tokens are dropped", async () => {
  const { store, state } = memoryStore(
    [row(1, "ana"), row(2, "binh", "like"), row(3, null, "announcement"), row(4, "chi")],
    [token("ana-phone", "ana"), token("ana-ipad", "ana"), token("dead", "dung"), token("chi-phone", "chi")],
  );
  const sent: string[] = [];
  const summary = await drainOutbox(store, (device) => {
    sent.push(device.token);
    if (device.token === "dead") return Promise.resolve({ status: 410, reason: "Unregistered" });
    if (device.token === "chi-phone") return Promise.resolve({ status: 503, reason: "ServiceUnavailable" });
    return Promise.resolve({ status: 200 });
  });

  assertEquals(summary, { messages: 4, delivered: 4, failed: 1, removedTokens: 1 });
  // Ana's reply on both her devices, nothing for Binh (no phone), the
  // announcement to everyone, Chi's reply failed.
  assertEquals(sent, ["ana-phone", "ana-ipad", "ana-phone", "ana-ipad", "dead", "chi-phone", "chi-phone"]);
  assertEquals(state.sent, [1, 2, 3]);
  assertEquals(state.failed, [{ id: 4, error: "503 ServiceUnavailable" }]);
  assertEquals(state.removed, ["dead"]);
});

Deno.test("a network error counts as a failure to retry", async () => {
  const { store, state } = memoryStore([row(1, "ana")], [token("ana-phone", "ana")]);
  const summary = await drainOutbox(store, () => Promise.reject(new Error("connection reset")));
  assertEquals(summary.failed, 1);
  assertEquals(state.failed, [{ id: 1, error: "connection reset" }]);
});

Deno.test("the payload has the alert, the kind and the post", () => {
  assertEquals(payloadFor(row(1, "ana")), {
    aps: { alert: { title: "New reply", body: "Binh: So cool" }, sound: "default" },
    kind: "reply",
    post_id: "p1",
  });
  assertEquals(payloadFor({ ...row(2, null, "announcement"), post_id: null }).post_id, undefined);
});
