// AWARE admin page. Plain JavaScript, no build step. It signs in with the
// Supabase anon key and the admin's own account; the database decides what
// that account may do (is_admin(), row-level security, admin_* functions),
// so nothing here is trusted for security. User content is only ever written
// with textContent, never as HTML.

const config = window.AWARE_ADMIN_CONFIG || {};
const IMAGE_BUCKET = "post-images";
let client = null;

const $ = (selector) => document.querySelector(selector);

function show(id, visible = true) {
  const element = $(id);
  if (element) element.hidden = !visible;
}

function notify(message, isError = false) {
  const notice = $("#notice");
  notice.textContent = message;
  notice.className = isError ? "error" : "ok";
  notice.hidden = false;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => { notice.hidden = true; }, 6000);
}

// Builds an element: el("button", { type: "button", onclick }, "Text", child).
function el(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === undefined || value === null || value === false) continue;
    if (key.startsWith("on")) element.addEventListener(key.slice(2), value);
    else if (key === "className") element.className = value;
    else element.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return element;
}

function when(isoDate) {
  return new Date(isoDate).toLocaleString();
}

// Runs a Supabase call and reports its error. Returns the data, or undefined.
async function run(label, call) {
  const { data, error } = await call;
  if (error) {
    notify(`${label}: ${error.message}`, true);
    return undefined;
  }
  return data;
}

// ---------------------------------------------------------------------------
// Signing in
// ---------------------------------------------------------------------------

async function start() {
  if (!config.supabaseUrl || !config.supabaseAnonKey) {
    show("#not-configured");
    return;
  }
  client = window.supabase.createClient(config.supabaseUrl, config.supabaseAnonKey);
  $("#sign-in-form").addEventListener("submit", signIn);
  $("#sign-out").addEventListener("click", signOut);
  $("#settings-form").addEventListener("submit", saveSettings);
  $("#announce-form").addEventListener("submit", announce);
  $("#user-search").addEventListener("submit", searchUsers);

  const { data } = await client.auth.getSession();
  if (data.session) await enter();
  else show("#sign-in");
}

async function signIn(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const { error } = await client.auth.signInWithPassword({
    email: String(form.get("email")),
    password: String(form.get("password")),
  });
  if (error) {
    notify(`Couldn't sign in: ${error.message}`, true);
    return;
  }
  await enter();
}

async function signOut() {
  await client.auth.signOut();
  show("#dashboard", false);
  show("#account", false);
  show("#sign-in");
}

async function enter() {
  const { data: isAdmin, error } = await client.rpc("is_admin");
  if (error || !isAdmin) {
    await client.auth.signOut();
    show("#dashboard", false);
    show("#sign-in");
    notify("This account isn't an admin.", true);
    return;
  }
  const { data } = await client.auth.getUser();
  $("#account-email").textContent = data.user?.email ?? "";
  show("#sign-in", false);
  show("#account");
  show("#dashboard");
  await refreshAll();
}

async function refreshAll() {
  await Promise.all([loadCounts(), loadSettings(), loadReports(), loadPosts(), loadBanned(), loadAnnouncements()]);
}

// ---------------------------------------------------------------------------
// Overview and settings
// ---------------------------------------------------------------------------

const COUNT_LABELS = {
  users: "People",
  guests: "Of them guests",
  banned: "Banned",
  scans_today: "Scans today",
  points_today: "Leaves today",
  scans_total: "Scans in total",
  posts: "Posts",
  hidden_posts: "Hidden posts",
  replies: "Replies",
  open_reports: "Open reports",
};

async function loadCounts() {
  const counts = await run("Counts", client.rpc("admin_counts"));
  if (!counts) return;
  const list = $("#counts");
  list.replaceChildren();
  for (const [key, label] of Object.entries(COUNT_LABELS)) {
    list.append(el("div", { "data-testid": `count-${key}` }, el("dt", {}, label), el("dd", {}, counts[key] ?? 0)));
  }
}

async function loadSettings() {
  const settings = await run("Settings",
    client.from("app_settings").select("show_samples, daily_point_cap, report_threshold").single());
  if (!settings) return;
  const form = $("#settings-form");
  form.show_samples.checked = settings.show_samples;
  form.daily_point_cap.value = settings.daily_point_cap;
  form.report_threshold.value = settings.report_threshold;
}

async function saveSettings(event) {
  event.preventDefault();
  const form = event.target;
  const changes = {
    show_samples: form.show_samples.checked,
    daily_point_cap: Number(form.daily_point_cap.value),
    report_threshold: Number(form.report_threshold.value),
  };
  const saved = await run("Saving settings",
    client.from("app_settings").update(changes).eq("id", true).select("show_samples"));
  if (saved === undefined) return;
  if (saved.length === 0) {
    notify("The settings weren't saved: this account can't change them.", true);
    return;
  }
  notify("Settings saved. Phones pick them up the next time they open the app.");
}

// ---------------------------------------------------------------------------
// Moderation
// ---------------------------------------------------------------------------

function imageLink(path) {
  if (!path) return null;
  const { data } = client.storage.from(IMAGE_BUCKET).getPublicUrl(path);
  return el("a", { href: data.publicUrl, target: "_blank", rel: "noopener" }, "Photo");
}

async function moderate(kind, id, action) {
  if (action === "remove" && !confirm(`Remove this ${kind} for everyone? Its photo is deleted.`)) return;
  const photo = await run("Moderating", client.rpc("admin_moderate", { p_kind: kind, p_id: id, p_action: action }));
  if (photo === undefined) return;
  if (photo) {
    await run("Deleting the photo", client.storage.from(IMAGE_BUCKET).remove([photo]));
  }
  notify(action === "hide" ? "Hidden." : action === "restore" ? "Restored." : "Removed.");
  await refreshAll();
}

async function dismiss(kind, id) {
  const done = await run("Closing reports", client.rpc("admin_dismiss_reports", { p_kind: kind, p_id: id }));
  if (done === undefined) return;
  notify("Reports closed.");
  await refreshAll();
}

async function setBanned(userId, banned, name) {
  if (banned && !confirm(`Ban ${name}? They can't post, reply or like, and their content stops showing.`)) return;
  const done = await run(banned ? "Banning" : "Unbanning",
    client.rpc("admin_set_banned", { p_user: userId, p_banned: banned }));
  if (done === undefined) return;
  notify(banned ? `${name} is banned.` : `${name} can take part again.`);
  await refreshAll();
}

async function loadReports() {
  const queue = await run("Reports", client.rpc("admin_report_queue"));
  const box = $("#reports");
  box.replaceChildren();
  if (!queue) return;
  if (queue.length === 0) {
    box.append(el("p", { className: "hint" }, "No open reports."));
    return;
  }
  for (const item of queue) {
    const state = [item.hidden && "hidden", item.removed && "removed", item.author_banned && "author banned"]
      .filter(Boolean).join(", ");
    const actions = item.kind === "user"
      ? [
          el("button", { type: "button", onclick: () => setBanned(item.target_id, true, item.author_name) }, "Ban"),
          el("button", { type: "button", onclick: () => dismiss("user", item.target_id) }, "Looks fine"),
        ]
      : [
          el("button", { type: "button", onclick: () => moderate(item.kind, item.target_id, "hide") }, "Hide"),
          el("button", { type: "button", onclick: () => moderate(item.kind, item.target_id, "restore") }, "Restore"),
          el("button", { type: "button", className: "danger", onclick: () => moderate(item.kind, item.target_id, "remove") }, "Remove"),
          el("button", { type: "button", onclick: () => dismiss(item.kind, item.target_id) }, "Looks fine"),
          el("button", { type: "button", onclick: () => setBanned(item.author_id, true, item.author_name) }, "Ban author"),
        ];
    box.append(el("article", { className: "card", "data-testid": "report", "data-target": item.target_id },
      el("header", {},
        el("strong", {}, `${item.kind} by ${item.author_name ?? "someone"}`),
        el("span", { className: "badge" }, `${item.reports} report${item.reports === 1 ? "" : "s"}`),
        state && el("span", { className: "state" }, state)),
      item.title && el("p", { className: "title" }, item.title),
      item.body && el("p", {}, item.body),
      imageLink(item.image_path),
      item.reasons?.length > 0 && el("p", { className: "hint" }, `Reasons: ${item.reasons.join(", ")}`),
      el("div", { className: "actions" }, actions)));
  }
}

async function loadPosts() {
  const posts = await run("Posts", client.from("posts")
    .select("id, title, body, image_path, hidden_at, removed_at, created_at, author:profiles!author_id(id, display_name, banned_at)")
    .order("created_at", { ascending: false })
    .limit(20));
  const box = $("#posts");
  box.replaceChildren();
  if (!posts) return;
  if (posts.length === 0) {
    box.append(el("p", { className: "hint" }, "No posts yet."));
    return;
  }
  for (const post of posts) {
    const state = post.removed_at ? "removed" : post.hidden_at ? "hidden" : "";
    box.append(el("article", { className: "card", "data-testid": "post", "data-target": post.id },
      el("header", {},
        el("strong", {}, post.author?.display_name ?? "someone"),
        el("span", { className: "hint" }, when(post.created_at)),
        state && el("span", { className: "state" }, state)),
      post.title && el("p", { className: "title" }, post.title),
      post.body && el("p", {}, post.body),
      imageLink(post.image_path),
      !post.removed_at && el("div", { className: "actions" },
        post.hidden_at
          ? el("button", { type: "button", onclick: () => moderate("post", post.id, "restore") }, "Restore")
          : el("button", { type: "button", onclick: () => moderate("post", post.id, "hide") }, "Hide"),
        el("button", { type: "button", className: "danger", onclick: () => moderate("post", post.id, "remove") }, "Remove"))));
  }
}

function personRow(person) {
  const banned = Boolean(person.banned_at);
  return el("li", { "data-testid": "person", "data-user": person.id },
    el("span", {}, person.display_name),
    person.role === "admin" && el("span", { className: "badge" }, "admin"),
    banned && el("span", { className: "state" }, "banned"),
    el("button", { type: "button", onclick: () => setBanned(person.id, !banned, person.display_name) },
      banned ? "Unban" : "Ban"));
}

async function searchUsers(event) {
  event.preventDefault();
  const query = String(new FormData(event.target).get("query") ?? "").trim();
  const box = $("#user-results");
  box.replaceChildren();
  if (!query) return;
  const pattern = `%${query.replace(/[%_\\]/g, (c) => `\\${c}`)}%`;
  const people = await run("Search", client.from("profiles")
    .select("id, display_name, role, banned_at").ilike("display_name", pattern).limit(20));
  if (!people) return;
  box.append(people.length ? el("ul", {}, people.map(personRow)) : el("p", { className: "hint" }, "Nobody by that name."));
}

async function loadBanned() {
  const people = await run("Banned people", client.from("profiles")
    .select("id, display_name, role, banned_at").not("banned_at", "is", null).order("banned_at", { ascending: false }));
  const box = $("#banned");
  box.replaceChildren();
  if (!people) return;
  box.append(people.length ? el("ul", {}, people.map(personRow)) : el("p", { className: "hint" }, "Nobody is banned."));
}

// ---------------------------------------------------------------------------
// Announcements
// ---------------------------------------------------------------------------

async function announce(event) {
  event.preventDefault();
  const form = event.target;
  const title = form.title.value.trim();
  const body = form.body.value.trim();
  if (!confirm(`Send "${title}" to everyone?`)) return;
  const done = await run("Sending", client.from("announcements").insert({ title, body }));
  if (done === undefined) return;
  form.reset();
  notify("Announcement sent.");
  await loadAnnouncements();
}

async function loadAnnouncements() {
  const items = await run("Announcements", client.from("announcements")
    .select("id, title, body, created_at").order("created_at", { ascending: false }).limit(10));
  const list = $("#announcements");
  list.replaceChildren();
  if (!items) return;
  for (const item of items) {
    list.append(el("li", { "data-testid": "announcement" },
      el("strong", {}, item.title), " ", el("span", {}, item.body), " ",
      el("span", { className: "hint" }, when(item.created_at))));
  }
}

start();
