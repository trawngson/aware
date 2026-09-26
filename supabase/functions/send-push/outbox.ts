// Draining the notification outbox: for each pending message, send it to
// its recipient's phones (or everyone's, for announcements) and record the
// outcome. Storage and sending are passed in, so tests use fakes.
import { type ApnsResult, type DeviceToken, isDeadToken } from "../_shared/apns.ts";

export interface OutboxRow {
  id: number;
  kind: "reply" | "like" | "announcement";
  recipient_id: string | null;
  title: string;
  body: string;
  post_id: string | null;
  attempts: number;
}

export interface OutboxStore {
  pending(limit: number): Promise<OutboxRow[]>;
  tokensFor(row: OutboxRow): Promise<DeviceToken[]>;
  markSent(id: number): Promise<void>;
  markFailed(row: OutboxRow, error: string): Promise<void>;
  removeToken(token: string): Promise<void>;
}

export type Sender = (device: DeviceToken, payload: unknown) => Promise<ApnsResult>;

export interface DrainSummary {
  messages: number;
  delivered: number;
  failed: number;
  removedTokens: number;
}

/** The notification as the app receives it. */
export function payloadFor(row: OutboxRow): Record<string, unknown> {
  return {
    aps: { alert: { title: row.title, body: row.body }, sound: "default" },
    kind: row.kind,
    ...(row.post_id ? { post_id: row.post_id } : {}),
  };
}

export async function drainOutbox(store: OutboxStore, send: Sender, limit = 100): Promise<DrainSummary> {
  const summary: DrainSummary = { messages: 0, delivered: 0, failed: 0, removedTokens: 0 };
  for (const row of await store.pending(limit)) {
    summary.messages += 1;
    const devices = await store.tokensFor(row);
    const errors: string[] = [];
    for (const device of devices) {
      try {
        const result = await send(device, payloadFor(row));
        if (result.status === 200) {
          summary.delivered += 1;
        } else if (isDeadToken(result)) {
          await store.removeToken(device.token);
          summary.removedTokens += 1;
        } else {
          errors.push(`${result.status} ${result.reason ?? ""}`.trim());
        }
      } catch (error) {
        errors.push(error instanceof Error ? error.message : String(error));
      }
    }
    // Done when nothing failed, or when some phones got it (a retry would
    // send those a duplicate). A message with nobody to send to is done too.
    if (errors.length === 0 || errors.length < devices.length) {
      await store.markSent(row.id);
    } else {
      summary.failed += 1;
      await store.markFailed(row, errors.slice(0, 3).join("; "));
    }
  }
  return summary;
}
