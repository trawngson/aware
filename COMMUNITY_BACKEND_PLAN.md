# Community backend plan

The plan for giving AWARE a real backend: accounts, synced scans and points, a
leaderboard, a community Gallery, a recycling map, push notifications, and an
admin web page. The owner (Nguyen Truong Son) approved every decision below on
2026-09-26. The work runs unattended in a cloud Claude Code session on branch
`community-backend`, so this file carries everything the session needs. Keep
the **Progress log** at the bottom up to date: it is how the work resumes after
a context reset and how the owner reads the result in the morning.

## 1. Rules (non-negotiable)

1. **Git identity and naming.** Work only on branch `community-backend`. Never
   create a branch whose name contains `claude`, `ai`, `codex`, or any other
   assistant name. Before the first commit, run
   `git config user.name "Nguyen Truong Son"` and
   `git config user.email "sonntt.az@gmail.com"`. Commits, the PR title, and
   the PR body must not mention Claude, Anthropic, or AI: no `Co-Authored-By`
   trailer, no "Generated with" footer. Before every push, check
   `git log --format='%an <%ae>%n%B' origin/community-backend..HEAD`. If
   pushing to `community-backend` is refused, stop and say so in the
   Progress log. Do not push to a differently named branch instead.
2. **Never merge, force-push, rebase shared history, or touch `main` or
   `liquid-glass-redesign`.** Open one draft PR from `community-backend` into
   `liquid-glass-redesign` (PR #9 is not merged yet) and keep pushing to it.
3. **Secrets.** The repo is public. Never commit a service-role key, database
   password, access token, APNs key, or any `.env` file. The Supabase anon
   (publishable) key and URL are public by design, and only the owner adds real
   ones. The service-role key must never be in the iOS app or the admin page.
4. **Leave the ML project alone.** Do not change `backend/` (the dataset and
   training pipeline), `records/`, `test_set/`, `aware.mlpackage`,
   `UltralyticsYOLO/`, `PAPER.md`, or the benchmark code in `awareapp/Benchmark/`.
   Never try to reach the VAST GPU server in any way.
5. **Keep the iOS project safe.** The deployment target stays iOS 18.4 (the
   paper's demo phone is an iPhone XR on iOS 18). Do not change
   `DEVELOPMENT_TEAM` or other signing settings. Keep `NSCameraUsageDescription`.
   New Swift files under `awareapp/` join the target automatically
   (filesystem-synchronized groups), so `project.pbxproj` changes should be
   limited to what a new Swift package or Info.plist key needs. Copy the
   pattern of the existing package references (YOLO, OnboardingKit, Expandable).
6. **No questions overnight.** Nobody will answer. When something is unclear,
   pick the option that is simplest and safe, note it in the Progress log under
   "Decisions made during the run", and carry on.

## 2. What the owner decided

| Topic | Decision |
|---|---|
| Scope | Everything that needs a server: accounts and synced scans/points, leaderboard, community Gallery (posts, replies, likes, saves, photos), recycling map, push notifications, admin web page. |
| Platform | Supabase: Postgres, Auth, Storage, Edge Functions, row-level security (RLS). The hosted project will be in Singapore (`ap-southeast-1`). The owner creates it later; this run never deploys. |
| Sign-in | A guest (anonymous) account on first launch, so scanning works with no sign-up. Adding **Sign in with Apple** later keeps the guest's scans, points, posts and name. The owner doesn't have the paid Apple Developer Program yet, so Apple sign-in and APNs are built but can't be tested on a device. |
| Age | No age limit and no age question (owner's decision). Mention once in the final report that Vietnam's personal-data rules require a parent's consent for under-16s. |
| Samples | The app's current hard-coded content (people in `Community/Community.swift`, `GalleryPost.sample`, the map spots and clusters in `RecyclingMapData`, the chart data in `InsightModels`) stays in the app. It is **mixed in with real content without a badge** (owner's decision; mention the App Review risk under guidelines 2.3 and 5.x once in the final report). A server setting `show_samples`, toggled on the admin page, shows or hides it. The app caches the last value. If it has never fetched one, or no backend is configured, samples show. |
| Personal stats | Home cards, goal and insights come from the user's real scans. While samples are on and the user has no scans yet, show today's sample numbers so a fresh demo looks the same as now. |
| Points | Server-authoritative. The app cannot write points. A database function records each scan event once (by its UUID), takes the point value from a versioned reward table (today: 20 points for a recyclable result under policy `hanoi-2026.1`, 0 otherwise, which matches `RecyclingPolicy`), and caps points per user per day (default 200, editable by the admin). This must keep `backend/SPECIFICATION.md` §5.3: detector, policy and reward stay separate layers, points only after an accepted, confirmed detection, and at most once per scan event. |
| Map | Post locations are stored rounded to about 500 m (a 0.005° grid). The database does the rounding so clients can't skip it. The app asks for "While Using" location permission only when the user taps a control that needs it, and works without it by falling back to today's fixed point at Hoan Kiem Lake. |
| Moderation | Users can report posts, replies and users, and block users (the blocker no longer sees their content). A post or reply hides itself after 3 distinct reports until the admin reviews it. A basic English/Vietnamese word filter runs on the server. Banned users can't post, reply or like. Users accept short community terms before their first post or reply (App Store guideline 1.2). |
| Notifications | Push for replies and likes on your posts, and admin announcements to everyone, sent by an Edge Function through APNs. Weekly goal and streak reminders are local notifications scheduled by the app. The existing Notifications switch in settings controls all of them. Ask for notification permission only when the user turns it on. |
| Admin page | A separate static web page in `admin/`: plain HTML and JavaScript using `@supabase/supabase-js` from jsDelivr (pinned exact version), no build step, hostable on GitHub Pages. Only accounts with the admin role can use it; the database enforces this, not the page. It covers the samples switch, reports queue, hide/restore/delete content, ban/unban, daily point cap, sending announcements, and simple counts. |
| Offline | The app fully works offline. Scans, points and history are saved on the phone and synced when back online. The last-fetched community content is cached, samples show offline, and the model runs on-device as now. Posting may need a connection; show a friendly message instead of failing silently. |
| Account deletion | In-app "Delete account" (App Store guideline 5.1.1(v)): removes the auth user, their rows and their stored photos. |

## 3. Architecture

```
awareapp/ (SwiftUI) ──supabase-swift──▶ Supabase: Auth · PostgREST (tables, RPCs) · Storage · Edge Functions ──▶ APNs
admin/ (static web) ──supabase-js────▶ same project, admin role only
```

- **`supabase/`**: `config.toml` (already there: project `aware`, guest sign-in
  on, local analytics off), `migrations/` (SQL, one file per step, never edit a
  migration after it is pushed; add a new one), `seed.sql` (local test data
  only, never samples for production), `functions/` (Edge Functions in
  TypeScript/Deno), and `tests/database/` (pgTAP; `harness.test.sql` is there).
- **Database, in outline.** Design the details yourself; these behaviors are
  required:
  - `profiles`: one row per auth user, holding the display name (guests get a
    friendly generated one, e.g. "Recycler 4821", editable), avatar initials
    and colors, admin flag or role, `banned_at`, and `terms_accepted_at`.
    Created by a trigger on sign-up.
  - `reward_rules` (label and policy version → points and eligibility,
    versioned, seeded with today's values) and `scan_events` (the scan event
    UUID as a unique key, user, canonical label, policy version, confirmed,
    points awarded, reward state, reason code, `scanned_at`). The RPC
    `award_scan(...)` is the only way to add points. It returns the spec's
    reward output: state (`eligible`, `ineligible`, `already_awarded`,
    `confirmation_required`), points, reason code, and scan event ID. Clamp a
    client-supplied `scanned_at` to the last 7 days, and apply the daily cap by
    Vietnam day (`Asia/Ho_Chi_Minh`).
  - Leaderboard RPCs for this month (Vietnam time) and all time. Each returns
    the top N plus the caller's own rank, and excludes banned users.
  - `posts` (text, optional title, material tag `plastic|paper|glass|metal`,
    optional image path, optional rounded location, hidden and removed state,
    timestamps), `replies` (optional image), `likes`, `saves`, `reports`,
    `blocks`. Counts come from the database, not the client.
  - Map RPCs: posts with a location inside a region, and "nearby" counts
    within 2 km of a point.
  - `app_settings`: a single row holding `show_samples`, the daily point cap
    and the report threshold. Anyone can read it; only admins can write it.
  - `device_tokens`, `announcements`, and a `notification_outbox` filled by
    triggers (reply, like) and by announcements, then drained by an Edge
    Function.
  - Storage: a `post-images` bucket that users can upload to only under their
    own `<user id>/` folder, images only, 5 MB limit. Removing a post removes
    its images.
  - **RLS on every table**, with pgTAP tests proving that a user can't read
    another user's private rows or write another user's rows, that guests
    can't act as admins, and that banned users can't post.
- **Edge Functions:** `send-push` (drains the outbox, signs an APNs JWT from
  secrets `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_PRIVATE_KEY`, `APNS_BUNDLE_ID`
  = `net.nctson.awareapp`, `APNS_USE_SANDBOX`, and skips cleanly when they are
  missing) and `delete-account`. Put logic in plain functions with Deno unit
  tests that mock APNs; never call Apple from tests.
- **iOS app:**
  - A backend layer behind a protocol, with a Supabase implementation and an
    offline/no-backend implementation.
  - Backend URL and anon key are read from a config file or build setting.
    Empty means no backend: the app behaves exactly as today.
  - Local persistence with SwiftData for scans, points and the sync queue.
    `RewardLedger` and `GalleryStore` become backed by it.
  - Repositories that merge real content with samples when `show_samples` is
    on.
  - Guest sign-in, with Sign in with Apple linking in settings.
  - Real Gallery with report, block and terms; real map and leaderboard.
  - Home stats from real scans.
  - Notifications and local reminders.
  - Settings gets an account section (name, Sign in with Apple, delete
    account).
  - Prefer the official `supabase-swift` package, pinned to an exact version.
    If Xcode on CI can't resolve it after two honest attempts, write a thin
    `URLSession` client for the Auth, REST, RPC and Storage calls instead.
- **Info.plist and privacy:** add `NSLocationWhenInUseUsageDescription` and
  `NSPhotoLibraryAddUsageDescription` (sharing a scan photo offers "Save Image",
  which crashes without it). Add a `PrivacyInfo.xcprivacy` declaring the
  UserDefaults required-reason API and the data the app now collects. Add no
  analytics or tracking SDKs.

## 4. App style (keep what's there)

- Follow the Liquid Glass design system in `awareapp/DesignSystem/` (`Glass.swift`,
  `Theme.swift`). Use native SwiftUI controls wherever they match: navigation
  bars, `List`, `Toggle`, sheets, `PhotosPicker`, `ShareLink`, the
  `SignInWithAppleButton`. Build custom views only for content (cards, chips,
  pins).
- A vertical scroll view that sits under the tab bar must be a `TabScrollView`
  (`DesignSystem/DeviceAppearance.swift`); it keeps the tab bar in the device's
  Light/Dark style.
- Friendly, casual wording. Legal and policy details go only on a separate info
  screen. Never tell users to check with their ward.
- Every new user-facing string goes into `awareapp/Localizable.xcstrings` with
  an English and a Vietnamese translation.

## 5. How to check work without a Mac

This session runs on Linux: no Xcode, no simulator, and possibly no Docker.
Everything is checked by GitHub Actions.

- **Access check, first thing.** Confirm you can push to `community-backend` and
  read Actions results (the `gh` CLI or GitHub tools): list the runs for this
  branch. If you can't read CI results, still build everything in the order
  below, but write in the Progress log that nothing was verified.
- **Database:** every push that touches `supabase/**` or `admin/**` runs
  `.github/workflows/supabase-checks.yml`: it starts local Supabase on a Linux
  runner, applies all migrations, and runs `supabase test db`. It takes about 2
  minutes (verified green on 2026-09-26, run 36250920338). Extend that
  workflow with new jobs as needed: Deno tests for functions, and Playwright
  tests for `admin/` against the same local stack, with `npm` dependencies
  pinned. If Docker works in this session, you may also run
  `npx supabase@2.118.0 start` locally for faster loops.
- **iOS:** the PR runs `.github/workflows/ios-render-check.yml` (Xcode 27,
  iPhone 18 Pro, iOS 27), which builds the app and screenshots a tour in Light
  and Dark. Build errors are in the failed log (`gh run view <id> --log-failed`).
  Download only the small `render-previews` artifact and look at the
  screenshots. A run takes 15–20 minutes, and **a new push to the PR cancels the
  running check**, so batch iOS changes and push them together. Do DB work while
  you wait instead of polling. You may add a step or job that runs the
  `awareappTests` unit tests on the same runner.
- **The render tour must keep passing.** With no backend configured, the screens
  must look as they do today. No permission prompt, sign-in sheet or terms
  sheet may appear on its own along the tour's path (launch, Home, Waste Saved,
  Recycling Map, Leaderboard, More, Gallery, a post, New Post, Scan). The tour's
  steps are in `awareappUITests/RenderCheckUITests.swift`.

## 6. Order of work

Finish, push and get CI green on each phase before starting the next, so
whatever exists in the morning works. Update the Progress log after each phase.

1. **Setup:** access check, git identity, open the draft PR (title
   "Community backend"; body: what it adds, how to test, owner steps), and
   confirm the Supabase checks workflow is green on the branch.
2. **Core schema:** profiles, reward rules, scan events, `award_scan`,
   app settings, and leaderboard RPCs. RLS on all of them, with pgTAP tests.
3. **iOS foundation:** backend config, SwiftData store, the sync queue for scans
   and points, guest sign-in, and the `show_samples` fetch and cache. Home stats
   come from real scans. No-backend mode stays identical to today.
4. **Leaderboard in the app**, with real data merged with samples.
5. **Gallery:** posts, replies, likes, saves, photo upload, moderation
   (reports, blocks, auto-hide, word filter, bans), and terms acceptance, with
   DB tests first and then the app.
6. **Map:** rounded locations, map and nearby RPCs, and the app on real posts
   with an opt-in location button.
7. **Admin page** in `admin/`, with Playwright tests in CI.
8. **Notifications:** device tokens, outbox triggers, the `send-push` function
   with mocked tests, app registration, and local goal reminders behind the
   settings switch.
9. **Accounts:** Sign in with Apple linking that keeps the guest's data, and
   `delete-account` plus the in-app button.
10. **Privacy and polish:** the Info.plist keys, the privacy manifest,
    Vietnamese strings, and draft privacy policy and community terms in `docs/`
    (EN and VI, clearly marked as drafts for the owner to review).
11. **Owner guide:** `supabase/README.md` with numbered steps a high-school
    senior can follow: create the Singapore project, set the admin account,
    add GitHub secrets, deploy with a manual `supabase-deploy.yml` workflow
    (write it, don't run it; `workflow_dispatch` only works once it is on
    `main`), fill in the app and admin config, publish `admin/` on GitHub
    Pages, and later the Apple steps (Sign in with Apple capability, APNs key).
    Give each step its expected result.

If time runs out, stop at a green phase boundary rather than leaving a phase
half done.

## 7. Done means

- The Supabase checks and the iOS render check are both green on the PR's
  latest commit.
- Every table has RLS, and the pgTAP tests cover the rules in §3.
- With no backend configured, the render screenshots match today's app.
- No secrets in the repo, no assistant names in commits or the PR, and nothing
  outside the allowed folders changed.
- The Progress log ends with a **final report**:
  - what works;
  - what was built but couldn't be tested (Apple sign-in and APNs, which need
    the paid program);
  - decisions made during the run;
  - the owner's next steps;
  - the risks: unlabeled samples (App Review), no age limit (Vietnam's
    under-16 consent rule), and the Ultralytics AGPL-3.0 licence still
    unresolved (`backend/WORKFLOW_CHECKLIST.md`).

## Progress log

_Update after each phase: date/time, phase, what changed, CI run links and
results, and anything left over._

**2026-09-26 15:35 UTC, access check.** Checked out `community-backend`
(tracking `origin/community-backend` at `e44803e`) and set the git identity to
Nguyen Truong Son <sonntt.az@gmail.com>. GitHub Actions results for the branch
are readable: the one run so far is Supabase checks
[36250920338](https://github.com/trawngson/aware/actions/runs/36250920338),
success. PR #9 (`liquid-glass-redesign` into `main`) is open and not merged. The
session has no `gh` CLI; CI is read through the GitHub tools instead. Docker
starts in this session, so local Supabase can be tried for faster loops. Push
access is confirmed by this commit reaching `origin/community-backend`.

**2026-09-26 15:40 UTC, phase 1 (setup) done.** Draft PR
[#10](https://github.com/trawngson/aware/pull/10) "Community backend" opened
from `community-backend` into `liquid-glass-redesign`. Supabase checks run by
hand on the branch head: [36252366974](https://github.com/trawngson/aware/actions/runs/36252366974),
success. Local Supabase also starts in this session (Docker Hub images, because
the default ECR image host is blocked here), so migrations and pgTAP tests are
tried locally before each push.

**2026-09-26 15:50 UTC, phase 2 (core schema) pushed.** Migration
`20260926160000_core_schema.sql`: `profiles` (made by a sign-up trigger with a
"Recycler 1234" name and an avatar gradient from the app's palette; users can
edit only their name), `app_settings` (one row: `show_samples`, daily cap 200,
report threshold 3; anyone reads, only admins write), versioned `reward_rules`
seeded for `hanoi-2026.1`, `scan_events`, `award_scan()` (the only way to earn
points; returns state, points, reason code and scan event ID; clamps
`scanned_at` to the last 7 days; daily cap by Vietnam day; each event earns at
most once), `is_admin()` (never true for guests or banned users) and
`leaderboard(period, limit)` for `month` (Vietnam time) and `all`, top N plus
the caller's rank, banned users left out. RLS is on for every table. pgTAP:
`profiles`, `rewards`, `settings`, `leaderboard` and an `rls` guard that fails
if any public table lacks RLS or the anon role can write anywhere (88 tests).
CI: Supabase checks [36252982560](https://github.com/trawngson/aware/actions/runs/36252982560),
success.

**2026-09-26 16:30 UTC, phase 3 (iOS foundation) done.** iOS render check
[36254249515](https://github.com/trawngson/aware/actions/runs/36254249515),
success: build 325 s (first build with supabase-swift), unit tests 63 s, 10
screenshots in each appearance. The screenshots couldn't be looked at here:
this session's network blocks the artifact download host, so the next push
adds a CI step that compares each screen with the last green run on
`liquid-glass-redesign` and prints the differences in the job log. New in the
app:
- `Backend/`: `BackendConfig` (reads `BackendConfig.plist`, committed empty;
  `-AWAREBackendDisabled YES` ignores it), the `CommunityBackend` protocol with
  `SupabaseBackend` (supabase-swift 2.55.2, exact) and `NoBackend`,
  `ScanSync` (sends pending scans oldest first, keeps the server's points,
  restores history after a reinstall) and `AppSession` (guest sign-in with no
  UI, `show_samples`/profile cache in UserDefaults, sync on launch, on
  foreground, when the network comes back and after each scan).
- `Persistence/`: SwiftData `ScanRecord` store; `RewardLedger` now saves
  awarded scans there and is the sync queue (`pending` records).
- `Stats/`: `PersonalStats` (points, waste and CO₂ saved from ImpactFactors,
  streaks, weeks, months, categories) and `MyStats` (sample numbers while
  samples are on and there are no scans). Home cards and both insight screens
  take real numbers; their sample code paths are unchanged.
- `RecyclingPolicy`'s result now carries the user's answer (`choiceID`), which
  the server needs to pick the reward rule.
- The render tour launches with `-AWAREBackendDisabled YES`, and the render
  check script also runs `awareappTests` once per full tour.

Checked before pushing: the Foundation-only files (config, models, backend,
sync, stats, policy) compile on Linux against supabase-swift 2.55.2 and pass
11 tests there, 4 of them against a local Supabase stack (guest session reuse,
rename, awards, sync, history restore, leaderboard, offline). The SwiftUI and
SwiftData parts can only be compiled by the render check.

**2026-09-26 16:45 UTC, phase 4 (leaderboard) done.** Supabase checks
[36255370503](https://github.com/trawngson/aware/actions/runs/36255370503) and
iOS render check [36255373256](https://github.com/trawngson/aware/actions/runs/36255373256),
both success. The new comparison with `liquid-glass-redesign` (run
36248867850): 16 of 20 screens are pixel-identical; the others differ only
where every run differs (the scan screen's video, map tiles, the keyboard's
suggestion bar on New Post). Migration
`20260926170000_community_stats.sql` adds `community_stats()` (people with
points and recycled items per label, banned users left out; pgTAP
`community_stats`). In the app, `LeaderboardStore` fetches this month's and
all-time rankings and the community totals (cached for offline use), and
`Community.standings(for:)` merges the user, real people and, while samples
are on, the sample people. The leaderboard gets a This Month / All Time
switch, shown only with a backend. Home's impact card adds the real community
to the sample totals. The backend layer also gains the Gallery calls for the
next phase (tested live in the Linux harness, not used by the app yet).

**2026-09-26 17:00 UTC, phase 5 (Gallery) pushed.** Migration
`20260926180000_gallery.sql`: `posts`, `replies`, `likes`, `saves`, `reports`,
`blocks`, counts kept by triggers, auto-hide after `report_threshold` distinct
reports, an English/Vietnamese word filter (posts, replies and names), bans,
`accept_terms()`, admin tools (`admin_moderate`, `admin_set_banned`,
`admin_dismiss_reports`, `admin_report_queue`) and the `post-images` bucket
(images only, 5 MB, uploads only into the user's own folder). pgTAP:
`gallery`, `moderation`, `storage`. In the app: `GalleryStore` shows real
posts (newest first, cached with SwiftData for offline use) followed by the
samples while they show; posting and replying upload photos and ask for the
community terms first; the post menu reports, blocks or deletes; replies can
be reported, blocked or deleted with a long press; More gets Community
guidelines and Blocked people (only with a backend). The Linux harness runs
the whole flow against local Supabase (terms, upload, like, save, reply,
word filter, report, block, delete with photos).

**2026-09-26 17:00 UTC, phase 5 (Gallery) done.** Supabase checks
[36256497510](https://github.com/trawngson/aware/actions/runs/36256497510) and
iOS render check [36256500839](https://github.com/trawngson/aware/actions/runs/36256500839),
both success (unit tests included). Compared with `liquid-glass-redesign` (run
36248867850): 16 of 20 screens pixel-identical; the rest are the scan video,
map tiles and the keyboard area on New Post, as in phase 4.

**2026-09-26 17:00 UTC, phase 6 (map) pushed.** Migration
`20260926190000_map.sql`: posts get an optional latitude/longitude that a
trigger rounds to a 0.005° grid (about 500 m) whatever the client sends,
`map_posts(bounds, material)` (visible located posts in a region, blocked
authors left out) and `nearby_count(point, radius, material)`. pgTAP `map`
(13 tests). In the app: `MapStore` fetches real posts around the user (or Hoan
Kiem Lake) and the nearby counts; the map shows them with their photos next to
the sample spots, and the sample clusters only while samples show. A "locate
me" button (only with a backend) asks for While Using location the first time
it is tapped; if location is off, an alert explains and the map keeps working
from Hoan Kiem Lake. The composer gets an "On the map" chip (only with a
backend, off by default) that attaches the rounded location. Tapping a real
spot opens its post. Home's map card shows the real nearby count.
`NSLocationWhenInUseUsageDescription` is added to the build settings. The
backend layer also carries the calls that phases 8 and 9 use (device tokens,
Apple sign-in, account deletion), unused until then. Checked locally: pgTAP
with the migrations up to this one (179 tests) and the Linux harness (14
tests, including a live map test).

**2026-09-26 17:20 UTC, phase 6 (map) done.** Supabase checks
[36257493090](https://github.com/trawngson/aware/actions/runs/36257493090) and
iOS render check [36257496516](https://github.com/trawngson/aware/actions/runs/36257496516),
both success. Compared with `liquid-glass-redesign`: 17 of 20 screens
pixel-identical; the others are the scan video, map tiles and 0.13% on the
dark leaderboard (a screen this phase doesn't touch; below the level the
comparison maps).

**2026-09-26 17:12 UTC, PR description fixed.** The tool that opened the
draft PR had appended a footer naming the coding assistant to its
description, against rule 1. It is removed; the PR has no comments. Later PR
updates are checked the same way.

**2026-09-26 17:22 UTC, phase 7 (admin page) pushed.** A static page in
`admin/` (plain HTML, CSS and JavaScript, no build step) using supabase-js
2.117.2 from jsDelivr, pinned with a subresource-integrity hash. Admins sign
in with email and password; everyone else sees "This account isn't an admin."
It shows counts (people, guests, scans and points today, posts, open
reports), the settings (samples switch, daily cap, report threshold), the
report queue (hide, restore, remove, "looks fine", ban the author), the
latest posts (hide, restore, remove), a people search
with ban/unban and the banned list, and announcements. User content is only
ever inserted as text. `admin/config.js` is committed empty; the page asks to
be set up until it is filled in. Migration `20260926200000_admin.sql` adds
`announcements` (admins write, signed-in users read) and `admin_counts()`;
pgTAP `admin` (9 tests). The Supabase checks workflow now also runs 7
Playwright tests against the same local stack (`admin/tests`, npm packages
pinned by `package-lock.json`): setup screen, non-admin refused, settings
saved, report queue, hide/remove, ban/unban, announcement, and a script-in-a-
post test. All 7 pass locally.

**2026-09-26 17:33 UTC, phase 7 (admin page) done.** Supabase checks
[36258644318](https://github.com/trawngson/aware/actions/runs/36258644318)
(pgTAP, then all 7 Playwright tests, with supabase-js loaded from jsDelivr
and its integrity hash checked) and iOS render check
[36258646834](https://github.com/trawngson/aware/actions/runs/36258646834),
both success; 17 of 20 screens pixel-identical to the base branch (the rest:
scan video, map tiles, keyboard bar).

**2026-09-26 17:35 UTC, phase 8 (notifications) pushed.** Migration
`20260926210000_notifications.sql`: `device_tokens` (each user sees and
removes only their own; `register_device()` moves a token to whoever signs
in on that phone), and a `notification_outbox` with no client access at all,
filled by triggers on replies, likes (one pending per post) and
announcements, skipping your own actions and people you blocked. pgTAP
`notifications` (14 tests). Edge Function `send-push` drains the outbox
through APNs with an ES256 token made from the `APNS_*` secrets, per-token
sandbox or production host, drops tokens Apple says are dead, retries
failures up to 5 times, only answers the service role, and skips cleanly
(reporting the queue length) when the secrets are missing. Its logic is in
plain functions with Deno tests using a fake APNs (`supabase/functions/**/
*_test.ts`); the Supabase checks workflow gains a job that type-checks and
runs them. `delete-account` is also here (used in phase 9), with its own
tests. In the app: `NotificationManager` behind the existing switch in
More. Turning it on asks for permission (turned back off, with an alert
offering Settings, if declined); with permission it schedules the streak and
weekly goal reminders and, with a backend, registers for push and uploads
the token (after sign-in if it arrives earlier). Turning it off cancels the
reminders and removes the token from the server. An app delegate receives
the token and shows notifications while the app is open; tapping a reply,
like or announcement opens the Gallery. Checked locally: pgTAP (202 tests),
Deno (15 tests), and the Linux harness registering, moving and removing a
token against local Supabase.

### Decisions made during the run

1. **Other waste earns 10 points, not 0.** The plan says "20 points for a
   recyclable result, 0 otherwise, which matches `RecyclingPolicy`", but
   `RecyclingPolicy` gives 10 points for other waste (`otherWastePoints`), and
   the app's tests check that. The server's `reward_rules` copy the app exactly
   (recyclable 20, other waste 10) so the "+10" the app shows is what the user
   gets. To change it, add rows for a new policy version.
2. **Answers decide the group.** Labels whose group depends on the user's
   answer (cup material, clean or soiled cardboard) have one reward rule per
   answer. Without a known answer, `award_scan` returns
   `confirmation_required` and the same scan event can be sent again with the
   answer.
3. **The daily cap is all or nothing per scan.** A scan that would push the
   day's total past the cap earns 0 (`daily_cap_reached`); a smaller one that
   still fits counts.
4. **Settled scan events are final.** Once a scan event is `eligible` or
   `ineligible`, repeating it returns the stored result; only events still
   waiting for confirmation are evaluated again.
5. **Names from sign-in providers are ignored.** Every account starts as
   "Recycler 1234" and the user picks a name, so nothing personal (such as a
   name shared by Apple) appears publicly by default.
6. **Profiles are public inside the app.** Any signed-in user can read every
   profile row (name, avatar, role, ban and terms dates); only the owner can
   change the name, and nothing else. Private data (scans, saves, blocks,
   reports, device tokens) is in separate tables limited to its owner.
7. **Points are still awarded on "Add to Gallery".** That's when the app
   awarded them before (the button is disabled until any question is
   answered), so it counts as the user's explicit confirmation. Only rewarded
   scans are saved and synced; the server gets `confirmed = true`.
8. **After the first real scan, Home shows only the user's own numbers.**
   While samples are on and nothing has been scanned, Home shows today's
   sample numbers (24,100 leaves, 6,700 g, …), as the plan says. From the
   first scan, all personal numbers are the user's own (the sample numbers are
   not added to them), so a demo's numbers drop after its first scan.
9. **The monthly goal is 500 leaves** (25 recyclables). The sample card's
   "70%, 2,000 to go" had no real goal behind it.
10. **Only sourced impact figures in real mode.** Waste saved uses the typical
    masses from `CO2_IMPACT_NOTES.md` (bottle 10 g, can 13 g, jar 350 g, small
    box 200 g; cups and foam have none) and counts recycled items only; CO₂
    uses `ImpactFactors`. The CO₂ screen's "km not driven", "liters water"
    and "kWh" tiles have no source, so real mode shows trees (22 kg a year,
    as the screen already says), items recycled, streak and leaves instead.
11. **The phone applies the cached daily cap too**, only when a backend is
    configured, so offline scans don't promise points the server will refuse.
    Without a backend there is no cap, as before.
12. **The render tour always runs without a backend**
    (`-AWAREBackendDisabled YES`), so CI never creates guest accounts on the
    real project once the owner fills in `BackendConfig.plist`.
13. **Screens are checked by a pixel comparison in CI.** Artifact downloads
    are blocked here, so the render check now compares each preview with the
    last green run on the PR's base branch and prints how much changed, with a
    rough map of where (`.github/scripts/compare-renders.py`). It only
    reports; it never fails the job.
14. **The leaderboard's All Time view uses the samples' points too.** Sample
    people have one number, used for both periods.
15. **Photos are public by URL.** The `post-images` bucket is public, so the
    app shows photos without signed URLs. Paths are random, but a hidden
    post's photo stays reachable by its URL until it is removed.
16. **Photos are deleted through the Storage API, not by the database.** This
    Supabase version blocks deleting files from SQL. The app deletes a post's
    photos (its own and its replies') when the author deletes it, the admin
    page deletes the photo when an admin removes a post, and `delete-account`
    removes a user's folder.
17. **Liking needs no terms.** Only posting and replying ask for the community
    terms; banned users still can't like.
18. **Real posts come first, then the samples**, rather than mixing them by
    date (the samples have fixed ages like "2d").
19. **"Add to Gallery" on a scan result opens the composer** with the photo
    and text filled in when there is a backend, instead of posting publicly
    straight away. Without a backend it adds the post at once, as before.
20. **Reporting or blocking sample content only hides it on the phone**
    (samples aren't on the server).
21. **Admin "Remove" keeps the row.** It marks the post or reply removed,
    closes its reports and deletes its photo; authors deleting their own post
    delete the row.
22. **Local runs use Docker Hub images.** This session can't download from the
   default image host (public.ecr.aws), so local Supabase runs with
   `SUPABASE_INTERNAL_IMAGE_REGISTRY=docker.io`. CI is unchanged.
23. **A post goes on the map only when its author turns on "On the map"**
    (off by default, shown only with a backend). Distances and "nearby"
    counts are measured from Hoan Kiem Lake until the user taps the locate
    button; the phone's own location is never sent to the server.
24. **Admins sign in with email and password.** The owner creates the admin
    account in the Supabase dashboard (see `supabase/README.md`), so no email
    sending has to be set up. Anonymous (guest) accounts can never be admins.
25. **The admin page's tests can swap in a local supabase-js.** This session
    can't reach jsDelivr, so locally the tests serve the same pinned version
    from `node_modules` (`SUPABASE_JS_PATH`); CI loads it from the CDN with
    the integrity hash, like the real page.
26. **The Notifications switch stays on by default, and permission is asked
    only when the user turns it on.** Changing its default would change the
    More screen, and asking at launch is against the plan. The catch: on a
    fresh install the switch shows on, but nothing is scheduled or registered
    until the user turns it off and on again. The owner
    may prefer the switch off by default; that is a one-word change in
    `UserOptionsView` and `NotificationManager`, and changes the More screen.
27. **Push tokens carry their APNs environment.** Debug builds (run from
    Xcode) register as `sandbox`, release builds as `production`, and
    `send-push` picks Apple's server per token, so one project serves both.
28. **Reminders are local only**: a streak reminder at 19:00 on days without
    a scan yet, and a weekly goal nudge on Sundays at 18:00 (phone's time).
    They are rescheduled each time the app opens.
29. **One pending like notification per post**, so a popular post doesn't buzz
    its author for every like; nothing is sent to someone who blocked the
    actor, or for your own replies and likes.
30. **Deno comes from npm in CI** (`npx deno@2.9.6`), pinned, instead of a
    separate setup action.
31. **No Push Notifications or Sign in with Apple capability in the Xcode
    project.** Both need the paid Apple Developer Program, and adding them now
    would break signing with the free team (rule 5). The code is in place and
    fails quietly until the owner adds them (`supabase/README.md`, Part D).
