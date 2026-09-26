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

**2026-09-26 16:30 UTC, phase 3 (iOS foundation) pushed, waiting for the
render check.** New in the app:
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
13. **Local runs use Docker Hub images.** This session can't download from the
   default image host (public.ecr.aws), so local Supabase runs with
   `SUPABASE_INTERNAL_IMAGE_REGISTRY=docker.io`. CI is unchanged.
