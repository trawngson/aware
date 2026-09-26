// End-to-end tests for the admin page against a local Supabase stack.
//
// Needs SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY from
// `supabase status` (the local stack's keys; never a real project's). The
// service-role key is only used here, to create test users and data; the page
// itself only gets the anon key. SUPABASE_JS_PATH, when set, serves the page's
// supabase-js from that local file instead of the CDN.
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { createClient } from "@supabase/supabase-js";

const url = process.env.SUPABASE_URL ?? "http://127.0.0.1:54321";
const anonKey = process.env.SUPABASE_ANON_KEY;
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const localSupabaseJs = process.env.SUPABASE_JS_PATH;

const service = createClient(url, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } });
const tag = Date.now().toString(36);
const password = "correct horse battery staple";
const adminEmail = `admin-${tag}@example.com`;
const memberEmail = `member-${tag}@example.com`;
const memberName = `Member ${tag}`;
let memberId;
let reportedPostId;
let quietPostId;

async function createUser(email) {
  const { data, error } = await service.auth.admin.createUser({ email, password, email_confirm: true });
  if (error) throw error;
  return data.user.id;
}

async function check(promise) {
  const { data, error } = await promise;
  if (error) throw error;
  return data;
}

test.beforeAll(async () => {
  const adminId = await createUser(adminEmail);
  memberId = await createUser(memberEmail);
  await check(service.from("profiles").update({ role: "admin" }).eq("id", adminId));
  await check(service.from("profiles")
    .update({ display_name: memberName, terms_accepted_at: new Date().toISOString() }).eq("id", memberId));
  reportedPostId = (await check(service.from("posts")
    .insert({ author_id: memberId, body: `Reported post ${tag}` }).select("id").single())).id;
  quietPostId = (await check(service.from("posts")
    .insert({ author_id: memberId, body: `Quiet post ${tag}` }).select("id").single())).id;
  for (let i = 0; i < 3; i++) {
    const reporter = await createUser(`reporter-${i}-${tag}@example.com`);
    await check(service.from("reports").insert({ reporter_id: reporter, post_id: reportedPostId, reason: "spam" }));
  }
});

test.afterAll(async () => {
  // Leave the settings as the app expects them.
  await check(service.from("app_settings").update({ show_samples: true, daily_point_cap: 200 }).eq("id", true));
});

async function openPage(page) {
  page.on("dialog", (dialog) => dialog.accept());
  await page.route("**/config.js", (route) => route.fulfill({
    contentType: "application/javascript",
    body: `window.AWARE_ADMIN_CONFIG = ${JSON.stringify({ supabaseUrl: url, supabaseAnonKey: anonKey })};`,
  }));
  if (localSupabaseJs) {
    await page.route("https://cdn.jsdelivr.net/**", (route) => route.fulfill({
      contentType: "application/javascript",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: readFileSync(localSupabaseJs),
    }));
  }
  await page.goto("/index.html");
}

async function signIn(page, email) {
  await openPage(page);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("the page asks to be set up when config.js is empty", async ({ page }) => {
  if (localSupabaseJs) {
    await page.route("https://cdn.jsdelivr.net/**", (route) => route.fulfill({
      contentType: "application/javascript",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: readFileSync(localSupabaseJs),
    }));
  }
  await page.goto("/index.html");
  await expect(page.getByRole("heading", { name: "Not set up yet" })).toBeVisible();
});

test("an account that isn't an admin can't use the page", async ({ page }) => {
  await signIn(page, memberEmail);
  await expect(page.locator("#notice")).toHaveText("This account isn't an admin.");
  await expect(page.locator("#dashboard")).toBeHidden();
});

test("an admin sees the counts and changes the settings", async ({ page }) => {
  await signIn(page, adminEmail);
  await expect(page.locator("#dashboard")).toBeVisible();
  await expect(page.getByTestId("count-open_reports").locator("dd")).not.toHaveText("0");
  await expect(page.getByTestId("show-samples")).toBeChecked();

  await page.getByTestId("show-samples").uncheck();
  await page.getByTestId("daily-cap").fill("150");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.locator("#notice")).toContainText("Settings saved");
  const settings = await check(service.from("app_settings").select("show_samples, daily_point_cap").single());
  expect(settings).toEqual({ show_samples: false, daily_point_cap: 150 });
});

test("an admin works through the report queue", async ({ page }) => {
  await signIn(page, adminEmail);
  const report = page.locator(`[data-testid="report"][data-target="${reportedPostId}"]`);
  await expect(report).toContainText(`Reported post ${tag}`);
  await expect(report).toContainText("3 reports");
  await expect(report).toContainText("hidden");

  await report.getByRole("button", { name: "Restore" }).click();
  await expect(page.locator("#notice")).toHaveText("Restored.");
  await expect(report).toHaveCount(0);
  let post = await check(service.from("posts").select("hidden_at, removed_at").eq("id", reportedPostId).single());
  expect(post.hidden_at).toBeNull();

  const quiet = page.locator(`[data-testid="post"][data-target="${quietPostId}"]`);
  await quiet.getByRole("button", { name: "Hide" }).click();
  await expect(page.locator("#notice")).toHaveText("Hidden.");
  post = await check(service.from("posts").select("hidden_at").eq("id", quietPostId).single());
  expect(post.hidden_at).not.toBeNull();

  await quiet.getByRole("button", { name: "Remove" }).click();
  await expect(page.locator("#notice")).toHaveText("Removed.");
  await expect(quiet).toContainText("removed");
  post = await check(service.from("posts").select("removed_at").eq("id", quietPostId).single());
  expect(post.removed_at).not.toBeNull();
});

test("an admin bans and unbans someone", async ({ page }) => {
  await signIn(page, adminEmail);
  await page.getByTestId("user-query").fill(memberName);
  await page.getByRole("button", { name: "Search" }).click();
  const found = page.getByTestId("user-results").locator(`[data-user="${memberId}"]`);
  await found.getByRole("button", { name: "Ban" }).click();
  await expect(page.locator("#notice")).toHaveText(`${memberName} is banned.`);
  await expect(page.getByTestId("banned").locator(`[data-user="${memberId}"]`)).toBeVisible();
  let profile = await check(service.from("profiles").select("banned_at").eq("id", memberId).single());
  expect(profile.banned_at).not.toBeNull();

  await page.getByTestId("banned").locator(`[data-user="${memberId}"]`).getByRole("button", { name: "Unban" }).click();
  await expect(page.locator("#notice")).toHaveText(`${memberName} can take part again.`);
  profile = await check(service.from("profiles").select("banned_at").eq("id", memberId).single());
  expect(profile.banned_at).toBeNull();
});

test("an admin sends an announcement", async ({ page }) => {
  await signIn(page, adminEmail);
  await page.getByTestId("announce-title").fill(`Recycling day ${tag}`);
  await page.getByTestId("announce-body").fill("Bring your cans to the lake on Sunday!");
  await page.getByRole("button", { name: "Send announcement" }).click();
  await expect(page.locator("#notice")).toHaveText("Announcement sent.");
  await expect(page.getByTestId("announcements")).toContainText(`Recycling day ${tag}`);
  const rows = await check(service.from("announcements").select("id").eq("title", `Recycling day ${tag}`));
  expect(rows).toHaveLength(1);
});

test("user content is shown as text, never as HTML", async ({ page }) => {
  await check(service.from("posts").insert({ author_id: memberId, body: `<img src=x onerror="window.pwned=1"> ${tag}` }));
  await signIn(page, adminEmail);
  await expect(page.getByTestId("posts")).toContainText(`<img src=x onerror="window.pwned=1"> ${tag}`);
  expect(await page.evaluate(() => window.pwned)).toBeUndefined();
});
