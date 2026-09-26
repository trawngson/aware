// send-push: delivers the notification outbox through APNs. Run it on a
// schedule (see supabase/README.md) with the service-role key. Without the
// APNs secrets it does nothing and reports how many messages are waiting.
import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.117.2";
import { type DeviceToken, makeApnsSender, readApnsConfig } from "../_shared/apns.ts";
import { isServiceRequest } from "../_shared/auth.ts";
import { drainOutbox, type OutboxRow, type OutboxStore } from "./outbox.ts";

const MAX_ATTEMPTS = 5;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

export function supabaseOutboxStore(db: SupabaseClient): OutboxStore {
  const check = <T>({ data, error }: { data: T; error: { message: string } | null }): T => {
    if (error) throw new Error(error.message);
    return data;
  };
  return {
    async pending(limit) {
      return check(await db.from("notification_outbox")
        .select("id, kind, recipient_id, title, body, post_id, attempts")
        .is("sent_at", null).lt("attempts", MAX_ATTEMPTS)
        .order("id").limit(limit)) as OutboxRow[];
    },
    async tokensFor(row) {
      let query = db.from("device_tokens").select("token, user_id, environment");
      if (row.recipient_id) query = query.eq("user_id", row.recipient_id);
      return check(await query.limit(10_000)) as DeviceToken[];
    },
    async markSent(id) {
      check(await db.from("notification_outbox").update({ sent_at: new Date().toISOString() }).eq("id", id));
    },
    async markFailed(row, error) {
      check(await db.from("notification_outbox")
        .update({ attempts: row.attempts + 1, last_error: error.slice(0, 500) }).eq("id", row.id));
    },
    async removeToken(token) {
      check(await db.from("device_tokens").delete().eq("token", token));
    },
  };
}

Deno.serve(async (request) => {
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!isServiceRequest(request.headers.get("Authorization"), serviceKey)) {
    return json({ error: "Only the scheduled job may send notifications." }, 403);
  }
  const db = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey!, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const config = readApnsConfig(Deno.env.toObject());
  if (!config) {
    const { count } = await db.from("notification_outbox").select("id", { count: "exact", head: true })
      .is("sent_at", null);
    return json({ skipped: "APNs secrets are not set", pending: count ?? 0 });
  }
  try {
    return json(await drainOutbox(supabaseOutboxStore(db), makeApnsSender(config)));
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : String(error) }, 500);
  }
});
