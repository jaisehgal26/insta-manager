# insta-manager

Free, self-hosted CLI for managing and publishing to **multiple Instagram Business/Creator accounts** you own, using Meta’s **official Instagram Graph API** and **Facebook Login for Business** (Page access tokens on `graph.facebook.com`).

No browser automation, scraping, or unofficial libraries.

## Features & limitations

| Feature | Supported | Notes |
|--------|-----------|--------|
| Multiple accounts | Yes | Registry in `~/.insta-manager/accounts.json` (mode `0600`) |
| Facebook Login for Business | Yes | `auth login` or `auth exchange` |
| Single image post | Yes | Public `image_url` or upload via pluggable host |
| Carousel (2–10) | Yes | Mixed image + video children; **no Reels in carousels** |
| Reel | Yes | Resumable upload; `cover_url` or `thumb_offset`; `share_to_feed` |
| Story (image/video ≤60s) | Yes | No stickers/captions via API |
| Caption, alt text, location, user tags, collaborators | Yes | Where Graph API allows for your account type |
| Resumable video upload | Yes | `rupload.facebook.com` — no public video URL required |
| Container status polling | Yes | Waits for `FINISHED`; errors on `ERROR` / `EXPIRED` |
| First comment after publish | Yes | **Pinning not available** via API; links in comments are **not clickable** |
| Comment list/reply/hide/delete | Yes | |
| Enable/disable comments on post | Yes | |
| Delete published post | Yes | `DELETE /{ig-media-id}` |
| Insights (account & media) | Yes | Configurable `--metrics` |
| Local scheduling | Yes | SQLite queue + `schedule run-due` / `daemon` (containers created at run time; expire ~24h) |
| Rate limit guard | Yes | `content_publishing_limit` before publish |
| JSON output & dry-run | Yes | For agents and CI |
| Native IG scheduling | No | Use local scheduler only |
| Comment link clicks / pin | No | Platform limitation |
| Story stickers | No | API limitation |

**API version:** set `INSTA_MANAGER_API_VERSION` (default `v21.0`). Update when Meta ships newer versions (e.g. v27.x).

## Requirements

- Linux (or any OS with Python 3.10+)
- Instagram **Business** or **Creator** account linked to a Facebook **Page**
- Meta Developer app with **Instagram Graph API** + **Facebook Login for Business**

## Meta app setup (first time)

1. Go to [Meta for Developers](https://developers.facebook.com/) → **Create App** → type suitable for business (e.g. Business).
2. Add products:
   - **Instagram Graph API**
   - **Facebook Login for Business** (or Facebook Login configured for Business)
3. **App settings → Basic:** note **App ID** and **App Secret**.
4. **Facebook Login → Settings:** add valid OAuth redirect, e.g. `http://127.0.0.1:8765/callback` (must match `INSTA_MANAGER_OAUTH_REDIRECT_URI`).
5. Request these permissions (for **your own** assets, Development mode / Standard Access typically works without App Review):
   - `instagram_basic`
   - `instagram_content_publish`
   - `instagram_manage_comments`
   - `instagram_manage_insights`
   - `instagram_manage_contents`
   - `pages_show_list`
   - `pages_read_engagement`
   - `business_management`
6. On Instagram: switch account to **Professional** (Business or Creator) and **link to your Facebook Page** (Instagram app → Account → Linked accounts, or Meta Business Suite).
7. Generate a token:
   - **Graph API Explorer:** choose your app, add the permissions above, generate User token, then run `insta-manager auth exchange --token …`, **or**
   - `insta-manager auth login` (opens browser OAuth on the machine with a display).
8. The tool exchanges for a **long-lived user token**, calls `/me/accounts`, and stores **long-lived Page tokens** with `instagram_business_account`.

See Meta’s [Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/) and [Instagram Graph API](https://developers.facebook.com/docs/instagram-api/) documentation for current limits.

## Install

```bash
git clone https://github.com/jaisehgal26/insta-manager.git
cd insta-manager
cp .env.example .env   # fill META_APP_ID, META_APP_SECRET
pip install -e ".[dev]"
# or: ./install.sh
```

## First run

```bash
# 1) Configure secrets (repo never stores tokens)
export $(grep -v '^#' .env | xargs)   # or use dotenv in your shell

# 2) Authenticate and register all Pages that have IG Business accounts
insta-manager auth login
# or: insta-manager auth exchange --token "<short-lived-user-token>"

# 3) List accounts (tokens redacted)
insta-manager account list --json

# 4) Check token validity / expiry
insta-manager auth check-tokens --json

# 5) Publish a test image (dry-run)
insta-manager publish image --account YOUR_ALIAS --image-url https://example.com/photo.jpg --dry-run --json

# 6) Real publish
insta-manager publish image --account YOUR_ALIAS --image-file ./photo.jpg --caption "Hello" --json
```

Local state directory: **`~/.insta-manager/`** (override with `INSTA_MANAGER_HOME`). Never commit this directory.

## Image hosting (for `image_url`)

Instagram requires a **public HTTPS URL** for images. Videos use resumable upload and do not.

| Uploader | Env | Trade-offs |
|----------|-----|------------|
| `catbox` (default) | `INSTA_MANAGER_IMAGE_UPLOADER=catbox` | Free, anonymous; public files; retention not guaranteed; third-party |
| `s3` | `S3_*` variables | Your bucket (R2, MinIO, AWS); you control retention and ACL |
| `direct` | — | Use `--image-url` only |

Always pass `--image-url` if you already host the file.

## CLI reference

Global patterns:

- `--account ALIAS` on publish/comment/insights commands
- `--json` for machine-readable output
- `--dry-run` where supported

### Accounts

```bash
insta-manager account list
insta-manager account add --alias shop --ig-user-id 1784... --page-id 109... --token EAA...
insta-manager account remove --alias shop
```

### Auth

```bash
insta-manager auth login
insta-manager auth exchange --token "USER_TOKEN"
insta-manager auth check-tokens --json
```

### Publish

```bash
insta-manager publish limit --account shop --json
insta-manager publish image --account shop --image-file ./a.jpg --caption "Hi" --alt-text "..." --first-comment "https://example.com"
insta-manager publish carousel --account shop --items "./1.jpg,./2.mp4,./3.png" --caption "Carousel"
insta-manager publish reel --account shop --video-file ./reel.mp4 --share-to-feed --thumb-offset 3000
insta-manager publish story --account shop --image-file ./story.jpg
insta-manager publish story --account shop --video-file ./story.mp4
insta-manager publish container-status --account shop --container-id CONTAINER_ID
insta-manager publish delete --account shop --media-id MEDIA_ID
```

### Comments

```bash
insta-manager comment list --account shop --media-id MEDIA_ID --json
insta-manager comment add --account shop --media-id MEDIA_ID --message "Thanks!"
insta-manager comment reply --account shop --comment-id COMMENT_ID --message "..."
insta-manager comment hide --account shop --comment-id COMMENT_ID
insta-manager comment unhide --account shop --comment-id COMMENT_ID
insta-manager comment delete --account shop --comment-id COMMENT_ID
insta-manager comment toggle --account shop --media-id MEDIA_ID --enabled/--disabled
```

### Insights

```bash
insta-manager insights account --account shop --period day --metrics impressions,reach
insta-manager insights media --account shop --media-id MEDIA_ID
```

### Scheduling (local)

Containers expire in ~24 hours — jobs should create media shortly before `run_at`.

```bash
insta-manager schedule add --account shop --run-at 2026-11-14T15:00:00+00:00 \
  --type image --payload '{"image_path":"/path/photo.jpg","caption":"Scheduled"}' --json

insta-manager schedule list --account shop
insta-manager schedule run-due --json    # cron: */5 * * * * insta-manager schedule run-due --json
insta-manager schedule daemon --interval 60
```

## Cron example

```cron
*/5 * * * * INSTA_MANAGER_HOME=/home/you/.insta-manager /usr/local/bin/insta-manager schedule run-due --json >> /var/log/insta-manager.log 2>&1
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests use **respx** to mock all Graph API HTTP calls.

## Security

- Page tokens live only under `~/.insta-manager/`
- `.env` is gitignored; use `.env.example` as a template
- Prefer long-lived Page tokens; re-run `auth login` / `auth exchange` when Page tokens approach expiry (Page tokens from long-lived users can be effectively non-expiring in many setups — verify with `auth check-tokens`)

## License

MIT — see [LICENSE](LICENSE).
