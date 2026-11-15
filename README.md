# insta-manager

A free, self-hosted command-line tool for publishing to **multiple Instagram Business accounts you own**, using Meta’s **official Instagram Graph API** and **Facebook Login for Business**.

It talks only to `graph.facebook.com` (and `rupload.facebook.com` for video). There is no browser automation, no scraping, and no unofficial Instagram library. You connect each account once with a long-lived Page access token, then publish from the CLI (or from an AI agent that runs the CLI) without logging in or out of Instagram.

- **Repo:** https://github.com/jaisehgal26/insta-manager
- **CLI:** `insta-manager` (version 0.1.0)
- **Default Graph API version:** `v21.0` (override with `INSTA_MANAGER_API_VERSION`)

---

## Table of contents

1. [Why this tool exists](#why-this-tool-exists)
2. [What it can and cannot do](#what-it-can-and-cannot-do)
3. [Prerequisites](#prerequisites)
4. [Install](#install)
5. [Step-by-step setup](#step-by-step-setup)
   - [Step 1. Switch each Instagram account to Business](#step-1-switch-each-instagram-account-to-a-professional-business-account)
   - [Step 2. Create a Facebook Page and link it](#step-2-create-a-facebook-page-for-each-account-and-link-them)
   - [Step 3. Business portfolios](#step-3-put-each-facebook-page-in-a-business-portfolio-you-admin)
   - [Step 4. Create a Meta developer app](#step-4-create-a-free-meta-developer-app)
   - [Step 5. Add the required permissions](#step-5-add-the-required-permissions-scopes)
   - [Step 6. Put the App ID and secret in `.env`](#step-6-put-the-app-id-and-app-secret-in-env)
   - [Step 7. Get a user token from Graph API Explorer](#step-7-get-a-short-lived-user-token-from-graph-api-explorer)
   - [Step 8. Exchange it for long-lived Page tokens](#step-8-exchange-the-token-and-register-every-account)
   - [Step 9. Check tokens and do a dry-run](#step-9-check-tokens-and-do-a-dry-run-before-the-first-live-post)
6. [CLI reference](#cli-reference)
7. [Connecting Instagram to an AI agent (Grok Bot)](#connecting-instagram-to-an-ai-agent-grok-bot)
8. [Renewing tokens (~60 days)](#renewing-tokens-about-60-days)
9. [Image hosting](#image-hosting-for-image_url)
10. [FAQ (questions we actually asked and answered)](#faq-questions-we-actually-asked-and-answered)
11. [Troubleshooting](#troubleshooting)
12. [Security](#security)
13. [Development](#development)
14. [License](#license)

---

## Why this tool exists

Instagram can flag accounts that are logged in and out of the website repeatedly, especially from unfamiliar cloud-computer IP addresses. A previous account was flagged for exactly that reason.

The safe official alternative is:

1. Switch each Instagram account to a **Professional Business** account.
2. Link each one to its own **Facebook Page**.
3. Create a free **Meta developer app**.
4. Connect once with **Facebook Login for Business**.
5. Store **long-lived Page tokens** and publish through the Graph API.

Nothing in this workflow logs into Instagram in a browser. That rule is strict: **never log into Instagram through a browser on a cloud machine** (including this tool’s host). Do Instagram account changes, the AI label, and any in-app settings from your own phone or your own computer.

This project was built as a free replacement for paid schedulers (for example PostOnce): same official API, no subscription, support for multiple accounts, Reels, Stories, comments, insights, and a local scheduler.

---

## What it can and cannot do

These limits were checked against Meta’s official Instagram Graph API docs (November 2026) and are implemented in the CLI.

| Feature | Supported | Notes |
|--------|-----------|--------|
| Multiple accounts | Yes | Registry in `~/.insta-manager/accounts.json` (file mode `0600`) |
| Facebook Login for Business | Yes | `auth login` (local OAuth) or `auth exchange` (Graph API Explorer token) |
| Single image post | Yes | Needs a public `image_url`, or a local file uploaded via the configured host |
| Carousel (2–10 items) | Yes | Mixed image + video children; **Reels are not allowed inside a carousel** |
| Reel | Yes | Resumable upload from a local file; `cover_url` or `thumb_offset` (milliseconds); `share_to_feed` (on by default) |
| Story (image or video ≤ 60s) | Yes | No stickers, polls, music, link stickers, or captions via the API |
| Caption, alt text, location | Yes | Where Graph API allows it for your account type |
| Resumable video upload | Yes | `rupload.facebook.com` — no public video URL required |
| Container status polling | Yes | Waits for `FINISHED`; errors on `ERROR` / `EXPIRED` |
| First comment after publish | Yes | Useful for “link in bio”. **Pinning is not available** via the API. Links in comments are **not clickable**. |
| Comment list / reply / hide / delete | Yes | |
| Enable or disable comments on a post | Yes | `comment toggle --enabled` / `--disabled` |
| Delete a published post | Yes | `DELETE /{ig-media-id}` |
| Insights (account and media) | Yes | Configurable `--metrics` |
| Local scheduling | Yes | SQLite queue + `schedule run-due` / `daemon`. Containers are created at run time and expire in about 24 hours. |
| Rate-limit guard | Yes | Checks `content_publishing_limit` before publish |
| JSON output and dry-run | Yes | For agents and CI |
| List recent media | Not in the CLI | Use the Graph API `/{ig-user-id}/media` endpoint directly (see [Troubleshooting](#troubleshooting)) |
| Native Instagram scheduling | No | Use the local scheduler only |
| Clickable links in captions or comments | No | Platform limitation — use the profile bio link |
| Pin a comment | No | Pin it yourself in the Instagram app on your phone |
| Story stickers, polls, music | No | API limitation |
| Edit a caption after publish | No | API limitation |
| Instagram’s native “Add AI label” toggle | Not via this CLI | Turn it on in the Instagram app. Put a short “created with AI” line on screen and in the caption as well. |

**Daily publish cap:** typically 50 or 100 pieces per account per day (Meta’s current limit). Check with `insta-manager publish limit --account ALIAS --json`.

**API version:** set `INSTA_MANAGER_API_VERSION` (default `v21.0`). Update this when you move to a newer Graph API version (for example `v22.0` or later).

Official docs: [Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/) and [Instagram Graph API](https://developers.facebook.com/docs/instagram-api/).

---

## Prerequisites

You need:

- **Linux** (or any OS with **Python 3.10+**)
- One or more **Instagram accounts you own**
- A **Facebook account** that will admin the Pages and the Meta app
- Willingness to do the one-time Meta setup below on **your own phone and computer** (not on a cloud browser logged into Instagram)

You do **not** need:

- A paid Meta or Instagram product
- App Review, if you only post to accounts you own and the app stays in **Development mode**
- A public video host (videos upload directly)
- To give the CLI your Instagram password

---

## Install

```bash
git clone https://github.com/jaisehgal26/insta-manager.git
cd insta-manager

# If you are installing from the still-open feature branch (until it is merged to main):
# git checkout cursor/insta-manager-graph-api-1f17

cp .env.example .env
# Fill META_APP_ID and META_APP_SECRET in .env (see Step 6). Never commit .env.
chmod 600 .env

pip install -e ".[dev]"
# or: ./install.sh
```

After install, `insta-manager --help` should print the command list, and `insta-manager --version` should print `0.1.0`.

Local state (tokens and the scheduler database) lives in **`~/.insta-manager/`** (override with `INSTA_MANAGER_HOME`). That directory is created with mode `0700`. Never commit it.

The CLI also reads a `.env` file from the **current working directory**. The reliable way to load credentials, especially for agents, is:

```bash
cd /path/to/insta-manager
set -a
. ./.env
set +a
```

---

## Step-by-step setup

Do these steps in order. Each step says what you should see when it worked. All Instagram taps happen on **your phone or your own computer**, never in a cloud browser.

### Step 1. Switch each Instagram account to a Professional Business account

The Graph API only works with **Professional** accounts (Business or Creator). For brand / shop-style pages and a clean Facebook Page link, use **Business**.

On your phone, in the Instagram app, for **each** account:

1. Open the profile, then **Settings and activity**.
2. Open **Account type and tools** (wording can vary slightly: “Account type”, “Switch to professional account”).
3. Choose **Professional**, then **Business** (not Creator).
4. When Instagram asks for a category, pick **Shopping & Retail** (or the closest shop category if that exact label is missing).
5. Finish the prompts. You can skip filling every optional business detail.

**What you should see:** the profile is a Professional account. Settings show options such as professional dashboard, category, and “Linked accounts” / “Page”. The account is **not** still a personal account.

**Why Business, not Creator?** Creator is also valid for the API, but Business is the better fit for a shop or brand page and for linking a Facebook Page cleanly. This is the path we used.

Repeat for every Instagram account you want the tool to publish to.

### Step 2. Create a Facebook Page for each account and link them

Each Instagram Business account must be linked to **its own Facebook Page**. One Page per Instagram account. You will admin every Page with the same Facebook user that owns the Meta app.

1. On your own computer or phone, open [Facebook Pages](https://www.facebook.com/pages/create) or Meta Business Suite and **create a Page** for that brand (name it after the Instagram account or the character / shop).
2. Make sure your Facebook user is an **admin** of the Page.
3. In the **Instagram app** (or in Meta Business Suite): **Settings → Linked accounts / Page**, and connect that Instagram account to **that** Facebook Page.
4. Confirm the same Page is not already tied to a different Instagram account.

**What you should see:** Instagram’s Linked accounts screen shows the Facebook Page. In Meta Business Suite, the Page and the Instagram account appear as a connected pair. If the link fails, see [Troubleshooting](#troubleshooting) (the usual causes are “already linked to another Page”, the account is still personal, or a portfolio / permission issue).

### Step 3. Put each Facebook Page in a business portfolio you admin

Meta groups Pages into **business portfolios** (sometimes called a Business Manager / business portfolio). During a real multi-account setup, **each Facebook Page ended up in its own business portfolio**. That is OK, and it avoided linking conflicts.

For each Page:

1. Open [Meta Business Suite](https://business.facebook.com/) and open the portfolio that should hold that Page, or create a new portfolio if Meta asks you to.
2. Confirm **you** (the same Facebook user) are **admin** of that portfolio and of the Page.
3. Confirm the Instagram account is still connected to that Page after any portfolio move.

**What you should see:** each Page is visible under a portfolio you admin, and the Instagram account is still listed as connected. If a later `auth exchange` finds some Pages but not others, come back here: the missing Page is usually in a portfolio your user cannot see, or the Instagram account is not actually linked.

### Step 4. Create a free Meta developer app

1. Go to [Meta for Developers](https://developers.facebook.com/) and sign in with the **same Facebook user** that admins the Pages.
2. Click **My Apps → Create App**.
3. Choose a type suitable for business (for example **Business**).
4. Give it a name you will recognize (any clear name is fine). You do not need a company website to start.
5. Create the app. It will start in **Development mode**. Leave it there if you are only posting to accounts you own. Development mode / Standard Access is typically enough and **does not require App Review**.
6. In the app dashboard, add these products if they are not already added:
   - **Instagram Graph API** (sometimes listed under Instagram)
   - **Facebook Login for Business** (or Facebook Login configured for Business)
7. Open **App settings → Basic**. Copy the **App ID** and the **App Secret**. Treat the App Secret like a password.

**What you should see:** an app dashboard with an App ID (a number) and an App Secret, plus the two products above listed as added. The mode badge says **Development**.

If you later use `insta-manager auth login` on a machine with a browser, also open **Facebook Login → Settings** and add this exact OAuth redirect URI (it must match `INSTA_MANAGER_OAUTH_REDIRECT_URI`):

```text
http://127.0.0.1:8765/callback
```

The recommended path on a headless computer is **Graph API Explorer + `auth exchange`** (Step 7–8), so you may not need the redirect URI at all.

### Step 5. Add the required permissions (scopes)

In the app’s permission / Graph API Explorer permissions list, you need:

| Permission | Why it is needed |
|------------|------------------|
| `instagram_basic` | Read basic Instagram account info |
| `instagram_content_publish` | Create posts, Reels, carousels, and Stories |
| `instagram_manage_comments` | List, reply, hide, and delete comments |
| `instagram_manage_insights` | Account and media insights |
| `instagram_manage_contents` | Manage existing content (including delete) |
| `pages_show_list` | List Facebook Pages you admin (`/me/accounts`) |
| `pages_read_engagement` | Read Page-linked Instagram data |
| `business_management` | Access Pages that live in a business portfolio |

**What you should see:** those eight scopes are available to request when you generate a token. For your own assets in Development mode you usually do **not** need to submit App Review.

### Step 6. Put the App ID and App Secret in `.env`

On the machine that will run `insta-manager` (for an agent, that is the tool’s install directory):

```bash
cd /path/to/insta-manager
cp -n .env.example .env
chmod 600 .env
```

Edit `.env` so it contains:

```bash
# Meta app credentials (Developer Console → your app → Settings → Basic)
META_APP_ID=<APP_ID>
META_APP_SECRET=<APP_SECRET>

# Optional: default Graph API version (e.g. v21.0, v22.0)
INSTA_MANAGER_API_VERSION=v21.0

# Local data directory (default: ~/.insta-manager/)
# INSTA_MANAGER_HOME=~/.insta-manager

# Default image uploader plugin: direct | catbox | s3
INSTA_MANAGER_IMAGE_UPLOADER=catbox

# S3-compatible (R2, MinIO, AWS) — only if using s3 uploader
# S3_ENDPOINT_URL=
# S3_BUCKET=
# S3_ACCESS_KEY_ID=
# S3_SECRET_ACCESS_KEY=
# S3_PUBLIC_BASE_URL=

# OAuth local redirect (auth login command)
# INSTA_MANAGER_OAUTH_REDIRECT_URI=http://127.0.0.1:8765/callback
```

Replace `<APP_ID>` and `<APP_SECRET>` with the values from App settings → Basic.

**Rules:**

- `.env` is gitignored. Never commit it.
- **Never paste the App Secret into a chat, a ticket, a screenshot, or a README.**
- Prefer `chmod 600 .env` so only your user can read it.

**What you should see:** `ls -l .env` shows mode `-rw-------`. `insta-manager` commands that need the secret no longer fail with a missing `META_APP_ID` / `META_APP_SECRET` once the file is sourced (see Step 8).

### Step 7. Get a short-lived user token from Graph API Explorer

Do this on **your own computer**, signed into Facebook as the Page admin. This is a Facebook / Meta Developers login, not an Instagram website login.

1. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer).
2. In the **Meta App** dropdown, select **the app you just created** (not “Graph API Explorer” or some other app).
3. Set the token type to a **User token** (not a Page token yet). The tool will exchange this user token and then discover Page tokens itself.
4. Click **Permissions** / **Add a permission** and add all eight scopes from Step 5.
5. Click **Generate Access Token**. Approve the Facebook Login dialog. When it asks which Pages to grant, select **all** of the Pages you linked in Step 2.
6. You should now see a long access-token string in the Explorer. Copy it somewhere private and temporary (a password manager, or paste it once into a terminal on the machine that runs the CLI). **Do not paste it into a group chat or a public ticket.**

**What you should see:** Graph API Explorer shows your app name, the permissions listed, and a token. A quick test in Explorer, `GET /me/accounts?fields=id,name,instagram_business_account`, should list each Page and a nested `instagram_business_account` with an `id` and `username`. If a Page is missing the Instagram object, that account is not linked yet — go back to Step 2.

Short-lived user tokens typically last about **1–2 hours**. You do not need to rush, but do Step 8 in the same sitting.

### Step 8. Exchange the token and register every account

On the machine where `insta-manager` is installed:

```bash
cd /path/to/insta-manager
set -a
. ./.env
set +a

# Replace the placeholder. Do not log or screenshot the real token.
insta-manager auth exchange --token "<short-lived-user-token>" --json
```

What this command does:

1. Calls Meta’s `fb_exchange_token` grant to turn the short-lived **user** token into a **long-lived user** token (usually about **60 days**).
2. Calls `GET /me/accounts` and finds every Page that has an `instagram_business_account`.
3. Stores a **long-lived Page token** for each one in `~/.insta-manager/accounts.json` (mode `0600`).
4. Picks an **alias** from the Instagram username (or the Page name), lowercased, with characters other than letters, numbers, `-` and `_` turned into `-`.

  For example, Instagram `@rex.wristpicks` becomes the alias `rex-wristpicks`. That alias is what you pass to `--account` later.

Optional alternative, only on a machine that has a display: `insta-manager auth login --json`. This opens a Facebook OAuth window, listens on `http://127.0.0.1:8765/callback`, and then does the same exchange. It is Facebook Login, not an Instagram website login. On a headless agent computer, prefer Graph API Explorer + `auth exchange`.

Then list what was saved (tokens are redacted):

```bash
insta-manager account list --json
insta-manager auth check-tokens --json
```

**What you should see:**

- `auth exchange` prints one record per linked Instagram account (alias, `ig_user_id`, `page_id`, `page_name`). It should not print the full token.
- `account list` shows the same aliases. `access_token` is redacted to a short prefix plus `…`.
- `auth check-tokens` shows `"valid": true` for each alias, and an `expires_at` around 60 days out when Meta reports one.

If an account is missing, that Page was not returned by `/me/accounts` with an `instagram_business_account`. Recheck the Page link, portfolio admin, and that you granted that Page in the Facebook Login dialog, then run `auth exchange` again with a fresh user token.

You can also add or remove a record by hand (only if you already have a long-lived **Page** token):

```bash
insta-manager account add --alias shop --ig-user-id 1784... --page-id 109... --token "<PAGE_TOKEN>"
insta-manager account remove --alias shop
```

### Step 9. Check tokens and do a dry-run before the first live post

```bash
insta-manager auth check-tokens --json
insta-manager publish limit --account YOUR_ALIAS --json

insta-manager publish image --account YOUR_ALIAS \
  --image-url https://example.com/photo.jpg \
  --caption "Hello" \
  --dry-run --json
```

**What you should see:** `check-tokens` is valid, `publish limit` returns the remaining quota, and the dry-run prints the payload **without** creating a post on Instagram.

When you are ready for a real post:

```bash
insta-manager publish image --account YOUR_ALIAS \
  --image-file ./photo.jpg \
  --caption "Hello" \
  --json
```

For a Reel (the most common path for this project):

```bash
insta-manager publish reel --account YOUR_ALIAS \
  --video-file ./reel.mp4 \
  --caption "$(cat caption.txt)" \
  --share-to-feed \
  --thumb-offset 2000 \
  --json
```

`--thumb-offset` is in **milliseconds** (2000 = the frame at 2 seconds). `--share-to-feed` is the default; use `--no-share-to-feed` if you do not want the Reel on the main grid.

**What you should see:** JSON with a media id and, once Instagram finishes processing, the post on that account. Reels can take a little while to appear while the container moves from in-progress to `FINISHED`.

---

## CLI reference

Global patterns:

- `--account ALIAS` on publish, comment, and insights commands
- `--json` for machine-readable output (use this from an agent)
- `--dry-run` where supported (prints what would be sent; does not publish)

Command groups: `account`, `auth`, `publish`, `comment`, `insights`, `schedule`.

Note the singular names: it is `account` and `comment`, not `accounts` / `comments`. There is no `token` command group; token work is under `auth`. There is no `publish photo` command; use `publish image`.

### Accounts

```bash
insta-manager account list
insta-manager account list --json
insta-manager account add --alias shop --ig-user-id 1784... --page-id 109... --token "<PAGE_TOKEN>" [--page-name "Shop"]
insta-manager account remove --alias shop
```

### Auth

```bash
insta-manager auth login [--json] [--dry-run]
insta-manager auth exchange --token "USER_TOKEN" [--json] [--dry-run]
insta-manager auth check-tokens [--json]
```

`auth check-tokens` reports whether each stored Page token is valid and updates the stored `expires_at` from Meta’s `debug_token` endpoint. It does **not** mint a new token. When a token is close to expiry or invalid, run `auth exchange` again with a fresh Graph API Explorer user token (see [Renewing tokens](#renewing-tokens-about-60-days)).

### Publish

```bash
insta-manager publish limit --account shop --json

insta-manager publish image --account shop \
  --image-file ./a.jpg \
  --caption "Hi" \
  --alt-text "..." \
  --location-id LOCATION_ID \
  --first-comment "Link in bio" \
  [--image-url https://example.com/a.jpg] \
  [--dry-run] [--json]

insta-manager publish carousel --account shop \
  --items "./1.jpg,./2.mp4,./3.png" \
  --caption "Carousel" \
  [--location-id LOCATION_ID] \
  [--first-comment "..."] \
  [--dry-run] [--json]

insta-manager publish reel --account shop \
  --video-file ./reel.mp4 \
  [--caption "..."] \
  [--share-to-feed | --no-share-to-feed] \
  [--cover-url https://example.com/cover.jpg] \
  [--thumb-offset 2000] \
  [--first-comment "..."] \
  [--dry-run] [--json]

insta-manager publish story --account shop --image-file ./story.jpg [--json] [--dry-run]
insta-manager publish story --account shop --image-url https://example.com/story.jpg
insta-manager publish story --account shop --video-file ./story.mp4

insta-manager publish container-status --account shop --container-id CONTAINER_ID [--json]
insta-manager publish delete --account shop --media-id MEDIA_ID [--json] [--dry-run]
```

`--share-to-feed` is on by default for Reels. `--thumb-offset` is milliseconds from the start of the video and chooses the cover frame if you do not pass `--cover-url`.

### Comments

```bash
insta-manager comment list --account shop --media-id MEDIA_ID --json
insta-manager comment add --account shop --media-id MEDIA_ID --message "Thanks!"
insta-manager comment reply --account shop --comment-id COMMENT_ID --message "..."
insta-manager comment hide --account shop --comment-id COMMENT_ID
insta-manager comment unhide --account shop --comment-id COMMENT_ID
insta-manager comment delete --account shop --comment-id COMMENT_ID
insta-manager comment toggle --account shop --media-id MEDIA_ID --enabled
insta-manager comment toggle --account shop --media-id MEDIA_ID --disabled
```

### Insights

```bash
insta-manager insights account --account shop --period day [--metrics impressions,reach] [--json]
insta-manager insights media --account shop --media-id MEDIA_ID [--metrics ...] [--json]
```

`--period` defaults to `day`. `--metrics` is an optional comma-separated list.

### Scheduling (local)

The Graph API has no native “schedule this post” endpoint. The tool keeps a local SQLite queue at `~/.insta-manager/scheduler.sqlite`. **Create containers at run time**, not a day early — publish containers expire in about 24 hours.

`--type` is `image` or `reel`. `--payload` is a JSON object with paths, URLs, and caption. `--run-at` is an ISO 8601 datetime (UTC recommended).

```bash
insta-manager schedule add --account shop \
  --run-at 2026-11-14T15:00:00+00:00 \
  --type image \
  --payload '{"image_path":"/path/photo.jpg","caption":"Scheduled"}' \
  --json

insta-manager schedule list [--account shop] [--status STATUS] [--json]
insta-manager schedule run-due [--json] [--dry-run]
insta-manager schedule daemon --interval 60 [--dry-run]
```

`schedule daemon --interval` is the poll period in seconds (default `30`).

Cron example:

```cron
*/5 * * * * INSTA_MANAGER_HOME=/home/you/.insta-manager /usr/local/bin/insta-manager schedule run-due --json >> /var/log/insta-manager.log 2>&1
```

If you also need `META_APP_ID` / `META_APP_SECRET` for token checks at run time, export them in the cron environment or source `.env` in a small wrapper script. Do not put the App Secret in the crontab file.

---

## Connecting Instagram to an AI agent (Grok Bot)

This is how an agent on the same computer as the CLI is meant to use Insta Manager. The pattern was built so the agent never opens Instagram in a browser and never needs your Instagram password.

### Install location and aliases

A typical install on the agent’s computer:

- Code: `/workspace/tools/insta-manager` (or wherever you cloned the repo)
- CLI on `PATH`: `insta-manager` (for example `~/.local/bin/insta-manager`)
- App credentials: `/workspace/tools/insta-manager/.env` (mode `600`)
- Account tokens: `~/.insta-manager/accounts.json` (mode `600`, shape `{"accounts":[...]}`)

Each registry record has an `alias`, an `ig_user_id`, a `page_id`, and an `access_token` (the long-lived Page token). The alias usually comes from the Instagram username, for example `@torque.carfinds` → `torque-carfinds`. Always confirm with `insta-manager account list --json` rather than guessing.

### Every command starts by loading `.env`

```bash
cd /workspace/tools/insta-manager   # or your clone path
set -a
. ./.env
set +a
```

Without this, `auth exchange` and `auth check-tokens` fail because `META_APP_ID` / `META_APP_SECRET` are missing. Settings also load a `.env` from the current working directory, so run commands from the repo directory when possible.

### Publish from the agent

Example: publish a Reel that was already prepared locally, share it to the feed, and pick a cover frame at 2 seconds:

```bash
insta-manager publish reel \
  --account rex-wristpicks \
  --video-file /path/to/reel.mp4 \
  --caption "$(cat /path/to/caption.txt)" \
  --share-to-feed \
  --thumb-offset 2000 \
  --json
```

Use `--dry-run --json` first when you are checking a payload. Parse the JSON for the media id. Instagram permalinks often appear once the media is finished processing.

To check remaining quota or token health before a batch:

```bash
insta-manager auth check-tokens --json
insta-manager publish limit --account rex-wristpicks --json
```

### Listing recent media (not a CLI command)

The CLI does not have a “list media” command. The agent can call the Graph API with the stored Page token (and must not print that token):

```text
GET https://graph.facebook.com/v21.0/{ig-user-id}/media?fields=id,media_type,timestamp,permalink,caption
```

Use the `ig_user_id` and `access_token` from the registry. When writing scripts, read `access_token` from `accounts.json` — do not hard-code it, and do not echo it.

### Safety rules the agent must follow

1. **Never log into Instagram through a browser**, including a cloud-computer browser. An account was previously flagged after bot logins from a cloud IP. The official Graph API via this CLI is the only posting path.
2. **Never print, chat, or commit the Meta App Secret or access tokens.** Redact them in logs, screenshots, and pull requests. `account list` already redacts tokens; do not bypass that by dumping `accounts.json` or `.env`.
3. **The user approves posts** (or gives a clear, standing instruction such as handing a scheduled batch to the agent). Draft, dry-run, and wait when approval is required.
4. **Do Instagram-only UI tasks on the user’s own phone:** switching to Business, linking a Page, turning on the AI label, pinning a comment, or clearing an Instagram checkpoint. The agent must not do those in a browser session.
5. If Meta returns **“API access blocked”** (see [Troubleshooting](#the-api-access-blocked--subcode-5258005)), **stop posting**, tell the user, and wait until they have cleared the block in the Meta developer dashboard. Do not keep retrying, and do not try to “fix” it by logging into Instagram.

### What the user does vs what the agent does

| The user (on their phone / computer) | The agent (on the box, via this CLI) |
|--------------------------------------|--------------------------------------|
| Creates Instagram accounts, switches them to Business, links Pages | Never opens Instagram in a browser |
| Creates the Meta app, copies App ID / secret into `.env` (or pastes the secret once into a private local file, not into chat) | Reads `.env`, never prints the secret |
| Generates a Graph API Explorer user token and hands it over once (or pastes it into a local command) | Runs `auth exchange`, stores Page tokens |
| Approves captions and videos, turns on the AI label in the app | Publishes with `insta-manager publish … --json` |
| Renews the user token about every 60 days | Reminds the user, then runs `auth exchange` again |
| Fixes a Meta “API access blocked” alert in the developer dashboard | Pauses posting and reports the error |

---

## Renewing tokens (about 60 days)

Long-lived tokens from this flow last about **60 days**. `auth check-tokens` will show `expires_at` and `valid`.

When expiry is close, or if a publish fails with an invalid-token error:

1. On your own computer, open [Graph API Explorer](https://developers.facebook.com/tools/explorer).
2. Select the **same Meta app**, add the same eight permissions, and generate a **new User token**. Grant all of the Pages again.
3. On the machine that runs the CLI:

```bash
cd /path/to/insta-manager
set -a
. ./.env
set +a
insta-manager auth exchange --token "<new-short-lived-user-token>" --json
insta-manager auth check-tokens --json
```

This overwrites the stored Page tokens for every discovered account. You should see `valid: true` and a new `expires_at` about 60 days out.

Set a reminder a few days before expiry. `auth check-tokens` alone will **not** extend the token.

---

## Image hosting (for `image_url`)

Instagram requires a **public HTTPS URL** for images. Videos use resumable upload and do not.

| Uploader | Env | Trade-offs |
|----------|-----|------------|
| `catbox` (default) | `INSTA_MANAGER_IMAGE_UPLOADER=catbox` | Free, anonymous; files are public; retention is not guaranteed; third-party host |
| `s3` | `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_PUBLIC_BASE_URL` | Your bucket (R2, MinIO, AWS); you control retention and ACL |
| `direct` | `INSTA_MANAGER_IMAGE_UPLOADER=direct` | Use `--image-url` only; the CLI will not upload the file for you |

Always pass `--image-url` if you already host the file.

---

## FAQ (questions we actually asked and answered)

These are real questions from the design and setup of this tool, with the answers we settled on.

### “Instagram is targeting multiple login and logout. Is there a way to manage several accounts without logging in and out?”

Yes. Stop using the Instagram website for posting. Switch each account to Business, link it to a Facebook Page, and publish through the official Graph API with long-lived Page tokens. Instagram then does not see a fresh browser login from a new place every time you post. That is exactly what Insta Manager does.

The official route cannot add story polls, music, or stickers, but it can post Reels, feed posts, carousels, and plain Stories.

### “Can we build something free that does this, instead of a paid scheduler?”

Yes. That is this repo. Paid connectors (for example PostOnce) also use the official API, but they charge after a trial and often cannot post Stories or manage comments. Insta Manager is self-hosted, free, and covers posts, carousels, Reels, plain Stories, a first comment, comment tools, delete, insights, and a local scheduler.

### “Can you add links in comments and pin them?”

You can post a comment (including right after publish, with `--first-comment`). Instagram will show a URL in that comment as **plain text**, not as a tappable link. The API **cannot pin** a comment. If you need the comment pinned, open the Instagram app on your phone and pin it there. For a clickable link, use the profile bio.

### “Instagram login or Facebook login — which should we use?”

**Facebook Login for Business.** Instagram-login style tokens are simpler and do not need a Facebook Page, but every file has to be on a public URL first, and you cannot delete posts with that path. Facebook Login needs each Instagram account linked to a Page, and in return the tool can upload video straight from the computer (resumable upload) and can delete posts. We chose Facebook Login for those reasons.

### “What features are actually available on the official API?”

See [What it can and cannot do](#what-it-can-and-cannot-do). Short version: image posts, carousels (up to 10), Reels from 3 seconds to 15 minutes with a cover and share-to-feed, plain Stories up to 60 seconds, first comment, comment moderation, delete, insights, alt text and tags, many of your own accounts in one Development-mode app. Not available: pin comment, clickable comment links, story stickers / polls / music, editing a caption after publish, native Instagram scheduling.

### “Do I need Meta App Review?”

Not if you only publish to **your own** accounts and keep the app in **Development mode** (Standard Access). That is the intended setup. App Review is for apps that will act on other people’s accounts or go into Live / production mode for third-party users.

### “Business or Creator? Which category?”

Use **Business**, not Creator, for a brand or shop page and a clean Page link. Preferred category in the setup we used: **Shopping & Retail**.

### “Why is each Facebook Page in its own business portfolio?”

Meta organizes Pages inside business portfolios. When several brand Pages are created, they may each land in (or may need) their own portfolio. That happened in a real four-account setup and is fine. What matters is that **your Facebook user is admin of the Page and of the portfolio that holds it**. If `auth exchange` or `/me/accounts` is missing an account, check portfolio admin rights and the Instagram ↔ Page link before creating a new app or new tokens.

### “How do I get a token, and is Graph API Explorer safe?”

Yes, if you do it on your own computer, select **your** Meta app, add the permissions in Step 5, and generate a **User** token. Then run `insta-manager auth exchange --token …` on the machine that hosts the CLI. Do not paste the token into a public chat. Short-lived user tokens last about one to two hours; the exchange turns them into long-lived Page tokens of about 60 days.

### “How long do tokens last, and how do I renew them?”

About **60 days**. Check with `insta-manager auth check-tokens --json`. Renew by generating a fresh Graph API Explorer user token and running `auth exchange` again. `check-tokens` does not itself issue a new token.

### “Can the app stay in Development mode?”

Yes, and it should, for this use. Development mode is enough for the app admin to post to assets they own. Going Live is a different, heavier process and is not required here.

### “What is the Instagram AI label? Can Insta Manager turn it on?”

Instagram has an **AI info** label for AI-generated or AI-altered content, and (for some profiles) an **AI-generated profile** toggle in Edit profile. Those controls live in the **Instagram app**. This CLI cannot reliably set the native “Add AI label” field. Put a short disclosure on screen and in the caption, and turn the label on from your phone. Keep characters stylized so they are obviously not real footage, and still switch the label on when the content is AI-generated.

### “Can the agent log into Instagram if the API is down?”

No. Never. If the API is blocked or a token is bad, fix the Meta app or renew the token. Do not fall back to a browser login.

### “Do I have to approve every post?”

The intended workflow is: the agent prepares the Reel or image and the caption, and publishes only after you approve — or after you give a clear standing instruction (for example “post this week’s already-approved batch at 7 PM”). Use `--dry-run` until then.

### “What does `--thumb-offset` and `--share-to-feed` mean on a Reel?”

`--share-to-feed` (the default) also puts the Reel on the main profile grid. `--no-share-to-feed` keeps it out of the grid. `--thumb-offset` is the cover frame, in **milliseconds** from the start (for example `2000` is two seconds). You can pass `--cover-url` instead if you have a public image for the cover.

### “Why did a command fail until we sourced `.env`?”

`META_APP_ID` and `META_APP_SECRET` must be in the process environment (or in a `.env` in the current working directory). Agents should always `cd` to the install directory and run `set -a; . ./.env; set +a` before `auth` commands.

---

## Troubleshooting

### `auth exchange` or `auth check-tokens` says the App ID or secret is missing

Source `.env` from the install directory, as in Step 8. Confirm `.env` has `META_APP_ID` and `META_APP_SECRET` and is not empty. Do not print the secret while debugging.

### `auth exchange` finishes but an account is missing

That Instagram account was not on `/me/accounts` with an `instagram_business_account`. Check, in order:

1. The Instagram account is Professional **Business**, not personal.
2. It is linked to a Facebook Page you admin.
3. Your Facebook user is admin of the **business portfolio** that holds that Page.
4. When you generated the token, you granted **that** Page in the Facebook Login dialog.
5. In Graph API Explorer (your app, your user token), `GET /me/accounts?fields=id,name,instagram_business_account` shows that Page and a nested Instagram id.

Then run `auth exchange` again with a **fresh** user token.

### “This Page is already linked to another Instagram account”

Unlink the old Instagram account in Meta Business Suite or Instagram’s Linked accounts screen (from your phone), then link the correct one. Each Page can only connect to one Instagram account.

### Facebook Login or Graph API Explorer keeps asking for permissions you already added

Make sure the Explorer’s **Meta App** dropdown is **your** app, not a default or sample app. Add the scopes again, generate a new token, and approve all Pages.

### Invalid OAuth token / token expired / `(#190)` style errors

The stored Page token is dead or past its ~60-day window. Renew it with [Step 7–8](#step-7-get-a-short-lived-user-token-from-graph-api-explorer). Do not try to log into Instagram in a browser to “refresh the session”.

### The “API access blocked” error (subcode `5258005`)

This is a real failure we hit with a Development-mode app while publishing.

**What it looks like:** Graph API calls fail with an `OAuthException`, HTTP / code `200`, subcode **`5258005`**, and a message like **“API access blocked”**. Account list and publish both fail. The stored tokens may still be *valid* according to `debug_token`; the block is on the **app**, not necessarily on the token.

**What to do:**

1. **Stop posting.** Do not keep retrying, and do not log into Instagram in a browser.
2. Open the [Meta developer app dashboard](https://developers.facebook.com/apps/) for this app (the app admin does this). Look for a banner, alert, “app restrictions”, or a disabled API-access notice.
3. Clear whatever Meta is asking for there (this is a Meta-side block; it is not fixed by creating a new token alone).
4. When the dashboard looks clear, retry a harmless call first (`auth check-tokens` or `publish limit`). If that works, resume publishing.

In the incident we saw, the app owner fixed it in Meta’s dashboard the same day and the same tokens started working again. There was no need to rebuild the app or change aliases.

If the block comes back, pause again and go back to the dashboard rather than looping retries.

### Reel is created but not visible yet / container `IN_PROGRESS`

Wait and poll `insta-manager publish container-status --account ALIAS --container-id ID --json`. The CLI already waits for `FINISHED` on a normal `publish reel`. `ERROR` or `EXPIRED` means you need to publish again (containers expire in about 24 hours).

### Image publish fails with a URL or download error

Instagram has to fetch a **public HTTPS** image URL. If you passed a local file, check `INSTA_MANAGER_IMAGE_UPLOADER`. Try `--image-url` with a URL you can open in a private browser window. Or switch to the `s3` uploader. Videos should not need this.

### `publish carousel` rejects the items

You need **2–10** files, images and/or videos, comma-separated in `--items`. **Do not include Reels** as carousel children. Use `publish reel` for a Reel.

### Links in the first comment do not open

That is an Instagram limitation, not a bug in this tool. Put the clickable URL in the profile bio, and use the comment for “link in bio” text.

### I need to list recent posts and permalinks

There is no `insta-manager media list` command. Call:

```text
GET https://graph.facebook.com/v21.0/{ig-user-id}/media?fields=id,media_type,timestamp,permalink,caption
```

using that account’s Page token. Do not print the token.

### `auth login` does nothing useful on a headless server

Expected. `auth login` opens a browser and listens on `127.0.0.1:8765`. Use Graph API Explorer on your computer and `auth exchange` on the server instead.

### Instagram shows a checkpoint or “confirm your email” when I open the app

That is an Instagram account-security prompt. Clear it **on your phone** in the official app. Do not complete it in a cloud browser. It is separate from Graph API tokens, but it can still affect how the account appears in the app.

---

## Security

- **Never log into Instagram in a browser on the machine that runs this tool.** Use only the official Graph API.
- **Page tokens** live only under `~/.insta-manager/` (`accounts.json` is mode `0600`; the directory is `0700`).
- **`.env` is gitignored.** Use `.env.example` as the template. Mode `600` is recommended.
- **Never commit, paste, or log** `META_APP_SECRET`, user tokens, or Page tokens. If a secret leaks, rotate the App Secret in the Meta dashboard and run `auth exchange` again with a new user token.
- `account list` redacts tokens. Do not “debug” by printing `.env` or `accounts.json` into a chat.
- Prefer Graph API Explorer + `auth exchange` so Facebook Login happens on a computer **you** control.
- Delete old Instagram website logins from any password vault yourself if they are no longer needed. This tool does not need them.
- Tokens last about 60 days. Re-run `auth exchange` before they expire. `auth check-tokens` only reports expiry; it does not extend the token by itself.
- This tool is for **accounts you own**. Do not use it to access anyone else’s Instagram account.

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests use **respx** to mock all Graph API HTTP calls. Do not point tests at a live app or real tokens.

Package layout:

- `insta_manager/cli.py` — Typer CLI
- `insta_manager/auth.py` — token exchange, OAuth login, `check-tokens`
- `insta_manager/registry.py` — `~/.insta-manager/accounts.json`
- `insta_manager/api/` — Graph client, publishing, comments, insights, tokens
- `insta_manager/scheduler/` — local SQLite queue
- `insta_manager/uploaders/` — `catbox`, `s3`, `direct`

---

## License

MIT — see [LICENSE](LICENSE).
