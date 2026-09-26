// delete-account: deletes the calling user's account and everything in it.
// The app calls it with the user's own session; the service-role key never
// leaves the server.
import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.117.2";
import { bearerToken } from "../_shared/auth.ts";
import { type AccountStore, deleteAccount } from "./account.ts";

const BUCKET = "post-images";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

export function supabaseAccountStore(admin: SupabaseClient): AccountStore {
  return {
    async listOwnPhotos(userId) {
      const paths: string[] = [];
      for (let offset = 0; ; offset += 1000) {
        const { data, error } = await admin.storage.from(BUCKET).list(userId, { limit: 1000, offset });
        if (error) throw new Error(error.message);
        paths.push(...data.map((file) => `${userId}/${file.name}`));
        if (data.length < 1000) return paths;
      }
    },
    async replyPhotosOnPostsOf(userId) {
      const { data: posts, error } = await admin.from("posts").select("id").eq("author_id", userId);
      if (error) throw new Error(error.message);
      if (posts.length === 0) return [];
      const { data: replies, error: replyError } = await admin.from("replies").select("image_path")
        .in("post_id", posts.map((post) => post.id)).not("image_path", "is", null);
      if (replyError) throw new Error(replyError.message);
      return replies.map((reply) => reply.image_path as string);
    },
    async removePhotos(paths) {
      const { error } = await admin.storage.from(BUCKET).remove(paths);
      if (error) throw new Error(error.message);
    },
    async deleteUser(userId) {
      const { error } = await admin.auth.admin.deleteUser(userId);
      if (error) throw new Error(error.message);
    },
  };
}

Deno.serve(async (request) => {
  if (request.method !== "POST") return json({ error: "Use POST." }, 405);
  const token = bearerToken(request.headers.get("Authorization"));
  if (!token) return json({ error: "Sign in first." }, 401);
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await admin.auth.getUser(token);
  if (error || !data.user) return json({ error: "Sign in first." }, 401);
  try {
    const removedPhotos = await deleteAccount(data.user.id, supabaseAccountStore(admin));
    return json({ deleted: true, removedPhotos });
  } catch (failure) {
    return json({ error: failure instanceof Error ? failure.message : String(failure) }, 500);
  }
});
