# AWARE community backend: owner guide

This folder is AWARE's server: a [Supabase](https://supabase.com) project with a
Postgres database, sign-in, photo storage and two small server functions.
Until you finish the steps below, the app runs on its own exactly as before
(the backend settings are empty), so nothing here is urgent.

Follow the steps in order. Each one says what you should see when it worked.
Keep a password manager open: you'll create a few secrets on the way.

**Never put these in the repository** (it is public): the database password,
the access token, the `service_role` (secret) key, and the APNs `.p8` key. The
project URL and the anon (publishable) key are public by design and are the
only values that go into the app and the admin page.

What's here:

| Path | What it is |
|---|---|
| `migrations/` | The database, one SQL file per step, applied in order. Never edit one that was deployed; add a new file instead. |
| `tests/database/` | Database tests (pgTAP), run by the "Supabase checks" workflow on every push. |
| `functions/send-push/` | Sends queued push notifications (replies, likes, announcements) through Apple. |
| `functions/delete-account/` | Deletes the calling user's account, rows and photos (More → Account → Delete account). |
| `config.toml` | Settings for the local test stack. The hosted project is set up by hand below. |

---

## Part A: create the project (once, about 20 minutes)

### 1. Create the Supabase project

1. Sign up or log in at [supabase.com](https://supabase.com/dashboard).
2. **New project**. Name: `aware`. Region: **Southeast Asia (Singapore)**.
3. Click **Generate a password**, copy it into your password manager as
   "AWARE database password", then **Create new project**.

**Expected:** after a minute or two the project dashboard says the project is
ready.

### 2. Write down the project's three values

- **Project Settings → General → Project ID** (the "reference ID", 20 letters).
- **Project Settings → Data API → Project URL** (`https://<reference ID>.supabase.co`).
- **Project Settings → API Keys**: the **anon / publishable** key.

**Expected:** you have the reference ID, the URL and the anon key in your notes.

### 3. Turn on guest sign-in and account linking

**Authentication → Sign In / Providers**:

1. Turn on **Allow anonymous sign-ins** (every phone starts as a guest).
2. Turn on **Allow manual linking** (lets a guest add Sign in with Apple later
   and keep everything).
3. **Save**.

**Expected:** both switches stay on after reloading the page.

Tip: **Authentication → Rate Limits** limits new guests per IP address per
hour. If a whole class installs AWARE on one school Wi-Fi at the same time,
raise that number for the day.

### 4. Make a Supabase access token for GitHub

1. Open [supabase.com/dashboard/account/tokens](https://supabase.com/dashboard/account/tokens).
2. **Generate new token**, name it `aware-github`, copy it (it starts with `sbp_`
   and is shown only once).

**Expected:** the token is in your password manager.

### 5. Add the GitHub secrets

On GitHub: **Settings → Secrets and variables → Actions → New repository
secret**, three times:

| Name | Value |
|---|---|
| `SUPABASE_ACCESS_TOKEN` | the token from step 4 |
| `SUPABASE_PROJECT_REF` | the reference ID from step 2 |
| `SUPABASE_DB_PASSWORD` | the database password from step 1 |

**Expected:** the three names are listed under "Repository secrets".

### 6. Deploy the database and functions

The **Supabase deploy** workflow (`.github/workflows/supabase-deploy.yml`) can
only be started once it is on the `main` branch, so do this after the
community-backend pull request has reached `main`.

1. **Actions → Supabase deploy → Run workflow**, branch `main`, keep "Also
   deploy the Edge Functions" ticked, **Run workflow**.
2. Wait for it to finish (2–3 minutes).

**Expected:** a green run. In Supabase, **Table Editor** lists `profiles`,
`scan_events`, `posts`, `replies` and the other tables; **Storage** has a
`post-images` bucket; **Edge Functions** lists `send-push` and
`delete-account`.

Run the same workflow again whenever new files appear in `migrations/` or
`functions/`. It only applies what the project doesn't have yet.

<details>
<summary>Without GitHub Actions (from your own computer)</summary>

With Node.js installed, from the repository folder:

```sh
npx supabase@2.118.0 login
npx supabase@2.118.0 link --project-ref <reference ID>   # asks for the database password
npx supabase@2.118.0 db push
npx supabase@2.118.0 functions deploy send-push delete-account
```
</details>

### 7. Create your admin account

1. **Authentication → Users → Add user → Create new user**. Enter your email and
   a strong password, tick **Auto Confirm User**, **Create user**.
2. **SQL Editor → New query**, paste this with your email, and **Run**:

   ```sql
   update public.profiles
   set role = 'admin'
   where id = (select id from auth.users where email = 'you@example.com');
   ```

**Expected:** "Success. 1 row affected" (0 rows means the email doesn't match
the user you created).

### 8. Schedule the push sender

Push notifications wait in a queue until the `send-push` function sends them.
Run it every minute:

1. **Integrations → Cron → Enable** (and **Database → Extensions**: make sure
   `pg_cron` and `pg_net` are on).
2. Copy the **service_role** key: **Project Settings → API Keys → Legacy API
   keys → service_role → Reveal**. It must stay secret.
3. **SQL Editor → New query**, replace the two `<...>` parts, and **Run**:

   ```sql
   -- Keeps the key in the encrypted Vault, not in the job's text.
   select vault.create_secret('<service_role key>', 'aware_service_role_key');

   select cron.schedule(
     'aware-send-push',
     '* * * * *',
     $$
     select net.http_post(
       url := 'https://<reference ID>.supabase.co/functions/v1/send-push',
       headers := jsonb_build_object(
         'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets
                                        where name = 'aware_service_role_key'),
         'Content-Type', 'application/json'),
       body := '{}'::jsonb
     );
     $$
   );
   ```

**Expected:** `select jobname, schedule from cron.job;` shows
`aware-send-push`. A minute later, **Edge Functions → send-push → Logs** shows
calls. Until Part D is done they answer
`{"skipped":"APNs secrets are not set","pending":0}`, which is fine.

---

## Part B: connect the app

### 9. Fill in the app's backend settings

Open `awareapp/Backend/BackendConfig.plist` and fill in:

- `SupabaseURL`: the project URL from step 2
- `SupabaseAnonKey`: the anon key from step 2

Both are public by design, so committing them is fine. Never put the
service_role key here: this file ships inside the app.

**Expected:** build and run the app. Nothing new is asked on launch. In
Supabase, **Authentication → Users** shows a new anonymous user, and the app's
More screen now has **Account** and **Community** sections.

The render check in CI starts the app with `-AWAREBackendDisabled YES`, so it
never talks to the real project.

### 10. Try it

1. Scan something and add it.
   **Expected:** **Table Editor → scan_events** has a row with its points.
2. In the Gallery, tap **+**, agree to the community rules, and post.
   **Expected:** the post shows in the app and in **Table Editor → posts**.
3. Open the Leaderboard. **Expected:** you appear under "This Month".

---

## Part C: the admin page

### 11. Fill in and try the admin page

1. Put the same URL and anon key into `admin/config.js`.
2. On your computer, in the repository folder: `cd admin` then
   `python3 -m http.server 8000`, and open <http://localhost:8000>.
3. Sign in with the admin email and password from step 7.

**Expected:** Overview counts, Settings, Reports, Latest posts, People and
Announcements. An account that isn't an admin sees "This account isn't an
admin." (the database enforces this, not the page).

### 12. Publish the admin page and the policies on GitHub Pages

1. Commit `admin/config.js` (the URL and anon key are public by design).
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions → Publish web pages → Run workflow** (on `main`).

**Expected:** a green run, then:
- `https://<your GitHub name>.github.io/aware/admin/`: the admin sign-in page.
- `https://<your GitHub name>.github.io/aware/privacy-policy.html`: the privacy
  policy (review the drafts in `docs/` first).

### 13. Day-to-day moderation

- **Reports:** a post or reply reported by 3 different people hides itself
  until you **Restore** or **Remove** it. Check the page daily; App Review
  expects reports to be handled quickly (about 24 hours).
- **Samples:** "Show the sample people, posts and map spots in the app" hides
  the built-in demo content once there is enough real content. Phones pick it
  up the next time they refresh.
- **Ban** stops someone from posting, replying and liking; **Unban** undoes it.
- **Announcements** go to everyone who turned notifications on (after Part D).

---

## Part D: Apple features (after joining the Apple Developer Program)

Both need the paid program. Until then the app handles their failures quietly:
Sign in with Apple shows "Couldn't sign in with Apple", and notifications are
limited to the phone's own streak and goal reminders.

### 14. Sign in with Apple

1. In Xcode: target **awareapp → Signing & Capabilities → + Capability → Sign
   in with Apple**.
2. In Supabase: **Authentication → Sign In / Providers → Apple → Enable**.
   Under **Client IDs** enter `net.nctson.awareapp`. The iOS app signs in
   natively, so the secret key fields can stay empty. **Save**.

**Expected:** More → Account → **Sign in with Apple** opens Apple's sheet.
Afterwards the row says "Apple ID", and in **Authentication → Users** the same
user (same ID as the guest) now shows the Apple provider: the scans, points and
posts stayed. Signing in on a second phone offers "Switch account".

### 15. Push notifications

1. In Xcode: **+ Capability → Push Notifications**.
2. [developer.apple.com](https://developer.apple.com/account) → **Certificates,
   Identifiers & Profiles → Keys → +**, name "AWARE push", tick **Apple Push
   Notifications service (APNs)**, **Continue → Register → Download**. The
   `.p8` file downloads only once: keep it in your password manager. Note the
   **Key ID**, and your **Team ID** (top right, or Membership details).
3. Add three more GitHub secrets: `APNS_KEY_ID`, `APNS_TEAM_ID`, and
   `APNS_PRIVATE_KEY` (open the `.p8` in a text editor and paste all of it,
   including the BEGIN and END lines).
4. Run **Actions → Supabase deploy** again (step 6).

**Expected:** on a phone, More → **Notifications** on → Allow. **Table Editor →
device_tokens** gets a row. Reply to your own post from another account: the
push arrives within about a minute, and the send-push logs show
`{"sent":1,...}`.

---

## Part E: before the App Store

16. Review the drafts in `docs/` (privacy policy and community terms, English
    and Vietnamese), fill in the [bracketed] parts, publish them (step 12), and
    use the privacy policy link in App Store Connect.
17. Answer App Store Connect's **App Privacy** questions to match
    `awareapp/PrivacyInfo.xcprivacy`: User ID, Name, Photos, Other User
    Content, Coarse Location, Product Interaction and Device ID, all linked to
    the user, used for App Functionality, never for tracking.
18. Read the risks in the final report in `COMMUNITY_BACKEND_PLAN.md`
    (unlabeled sample content, no minimum age, the Ultralytics licence).

---

## Working on the backend locally

Needs Docker and Node.js.

```sh
npx supabase@2.118.0 start          # local stack; prints its URL and keys
npx supabase@2.118.0 db reset       # re-applies every migration
npx supabase@2.118.0 test db        # database tests
(cd admin/tests && npm ci && npx playwright install chromium && \
  SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_SERVICE_ROLE_KEY=... npx playwright test)
(cd supabase/functions && npx --yes deno@2.9.6 test --allow-env)
npx supabase@2.118.0 stop
```

To point a development build at the local stack, put `http://127.0.0.1:54321`
and the local anon key into `BackendConfig.plist` (don't commit that).

## Troubleshooting

| Problem | Fix |
|---|---|
| Deploy fails at "Link the project" | Check `SUPABASE_ACCESS_TOKEN` and `SUPABASE_PROJECT_REF`. |
| Deploy fails at "Apply database migrations" with a password error | `SUPABASE_DB_PASSWORD` is wrong; reset it under Project Settings → Database and update the secret. |
| The app never shows Account/Community in More | `BackendConfig.plist` is empty or the URL doesn't start with `https://`. |
| New phones fail to sign in | Anonymous sign-ins are off (step 3) or the rate limit was hit. |
| The admin page says "This account isn't an admin." | Run the SQL in step 7 for that email. |
| send-push answers 403 | The cron job's key isn't the service_role key (step 8). |
