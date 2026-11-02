# Heatmapify

Runs on your own Windows or Mac for free. Paste a YouTube link, get the **most** and **least engaging moments** of the video, with a
dashboard that shows exactly why.

- Uses YouTube's own **"Most replayed"** data when the video has it.
- Otherwise builds a clearly labelled **estimate** from four signals: comments, captions, audio and visuals.
- Never makes numbers up: if nothing usable exists, you get a clear error.

**Dashboard:** https://heatmapify.onrender.com  Host your own copy: [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/velvetthunder15/heatmapify)

**Quick start:** [Windows](#quick-start-windows-about-5-minutes) · [macOS](#quick-start-macos-about-5-minutes)

| Source | When | Confidence |
|---|---|---|
| `official` | YouTube publishes "Most replayed" data | `high` |
| `estimated` | No official data, so comments, captions, audio and visuals are scored | `high` / `medium` / `low` |
| error | Nothing usable | `no_data_available` (never fabricated) |

---

## Quick start (Windows, about 5 minutes)

You need Windows 10 or 11 and nothing else. No Docker, no WSL, no Redis, no paid hosting.

### 1. Get the code

Either clone it:

```bat
git clone https://github.com/velvetthunder15/heatmapify.git
cd heatmapify
```

or [**download the latest release (.zip)**](https://github.com/velvetthunder15/heatmapify/releases/latest/download/Heatmapify.zip) and extract it anywhere (for example `Documents\Heatmapify`).

### 2. Start the server

Double-click **`start-windows.bat`**.

The first run takes a few minutes. It sets everything up inside the project folder:

| Step | What happens |
|---|---|
| Python | Uses Python 3.10 to 3.12 if you have it, otherwise installs 3.11 with `winget` (one time) |
| `.venv\` | A private Python environment with the dependencies |
| `.tools\` | Portable `ffmpeg`, `deno` and `cloudflared` (nothing installed system-wide) |
| `.env` | Settings file, created once (local mode, `REDIS_URL=memory://`, `CORS_ORIGINS=*`) |
| `secrets\api_key.txt` | Your **permanent** API key, created once and reused every start |
| Tunnel | A free Cloudflare quick tunnel that gives your laptop a public `https://` URL |

Later starts take a few seconds.

### 3. Copy your URL and key

When it's ready, the window prints something like:

```
================ Heatmapify ================
Local docs:  http://127.0.0.1:8000/docs
Public docs: https://random-words-here.trycloudflare.com/docs
API URL:     https://random-words-here.trycloudflare.com   (paste this into the dashboard)
API key:     yhx_xxxxxxxxxxxxxxxx   (also saved in secrets\api_key.txt)
```

- **API URL**: the `API URL` line. A `trycloudflare.com` URL **changes every time you restart**. Set up a permanent one in step 6 and it shows your fixed `workers.dev` URL instead.
- **API key**: stays the same forever (it's in `secrets\api_key.txt`).

**Keep this window open.** Closing it or pressing Ctrl+C stops the server.

### 4. Open the dashboard

1. Go to **https://heatmapify.onrender.com**
2. Tap **Connection**, paste the **API URL** and **API key**, then tap **Test connection**. You should see a green *Connected*.
3. Leave **Remember on this device** ticked so you only paste the key once. With the quick tunnel, update the URL after each restart. With a permanent URL, you never have to.

### 5. Analyze a video

1. Paste any YouTube link (`watch?v=`, `youtu.be/`, `shorts/` all work) and tap **Analyze**.
2. Official data comes back instantly. An estimate takes a few minutes; the progress bar shows each stage (comments → captions → audio → visuals → scoring).
3. Results are cached, so opening the same video again is instant. Your last 5 videos are under **Recent**.

Want to see it first? Tap **View a sample result** on the dashboard.

### 6. (Recommended) Get a permanent URL

By default you get a free **quick tunnel**: an anonymous `https://<random>.trycloudflare.com` address,
with no account, which **changes every restart**. To get a URL that never changes, connect **your own
free Cloudflare account** once. Close the server window, double-click **`setup-permanent-url.bat`** (on a Mac: `bash setup-permanent-url.command`), and pick:

#### Option 1: free `workers.dev` URL (no domain, about 3 minutes) [recommended]

You get `https://yt-heatmap-api.<your-subdomain>.workers.dev`, free on Cloudflare's free plan.

1. Sign up or sign in at **https://dash.cloudflare.com** (free).
2. Go to **https://dash.cloudflare.com/profile/api-tokens** → **Create Token** → template **Edit Cloudflare Workers** → **Continue to summary** → **Create Token**. Copy it.
3. In `setup-permanent-url.bat` choose **1** and paste the token.
4. It prints your URL. Double-click **`start-windows.bat`**. It shows `API URL: https://yt-heatmap-api.….workers.dev`.
5. Paste that URL into the dashboard **once**.

How it works: setup deploys a tiny Worker (`worker/proxy.js`) and a KV store to your account. Each time
`start-windows.bat` starts, it opens a quick tunnel as usual and saves its address in KV. The Worker forwards
every request on your permanent URL to it. After a restart the URL can take **up to a minute** to switch over.
While your laptop is off it answers `503 server_offline`. Free plan limit: 100,000 requests/day.

#### Option 2: your own domain (named tunnel)

For `https://api.yourdomain.com`, you need a domain added to your Cloudflare account (status **Active**).

1. **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel** → **Cloudflared**, and name it.
2. Pick **Windows** and **copy the install command** (contains `eyJ...`). Don't run it.
3. Add a **public hostname** (*Published application routes* in newer dashboards): subdomain `api`, your domain, service **HTTP** → **`127.0.0.1:8000`**. Save.
4. In `setup-permanent-url.bat` choose **2**, paste the command, and type the hostname.
5. Start `start-windows.bat`. It runs your named tunnel directly, with no quick tunnel and no Worker.

**Switching back:** `setup-permanent-url.bat -Remove` returns to random quick-tunnel URLs.
**Secrets:** the Cloudflare token is stored only in your `.env`, which git ignores. Don't share it. If it
leaks, delete it in Cloudflare (API Tokens or the tunnel) and run setup again.

### 7. (Optional) Run it in the background, with no window

A permanent URL is just a fixed address. The actual work (downloading the video, scoring audio and
frames) still happens **on your computer**, so something has to keep running there. Background mode
means you never have to keep a window open for it:

1. Run `start-windows.bat` once so it's set up, then close it.
2. Double-click **`install-background.bat`**. It prints your API URL and key, and that's it.

From then on the server runs **hidden**, **starts by itself every time you log in**, restarts itself if
it crashes, reconnects the tunnel if your network drops, and keeps the PC from idle-sleeping while it runs.

| File | What it does |
|---|---|
| `background-status.bat` | Is it running? Shows the current API URL and key |
| `uninstall-background.bat` | Stop it and remove it from login |
| `rotate-key.bat` | Replace your API key if it ever leaks (restart the server after) |
| `logs\server.log` | What it's doing (errors show up here) |

It still stops when the computer is **shut down, asleep (lid closed) or offline**. With a workers.dev URL
the API then answers `503 server_offline` until it's back. For true 24/7 you'd need a machine that's
always on (an old laptop, a Raspberry Pi-class mini PC). Cloud servers usually get blocked by YouTube, which is why this runs at home.

### Updating

[Re-download the latest release](https://github.com/velvetthunder15/heatmapify/releases/latest/download/Heatmapify.zip) and extract it over the folder (or `git pull`), then run `start-windows.bat` again.
Your `.env` and API key are kept.

---

## Quick start (macOS, about 5 minutes)

Works on Apple Silicon (M1–M4) and Intel Macs running macOS 12 or later. No Docker, no Homebrew, no admin password.

### 1. Get the code

Open **Terminal** (Spotlight → "Terminal") and run:

```bash
git clone https://github.com/velvetthunder15/heatmapify.git
cd heatmapify
```

No git? [Download the latest release (.zip)](https://github.com/velvetthunder15/heatmapify/releases/latest/download/Heatmapify.zip), double-click it in Downloads, then in Terminal move it to your home folder (macOS blocks background mode in Desktop, Documents and Downloads):

```bash
mv ~/Downloads/Heatmapify ~
cd ~/Heatmapify
```

(If macOS asks to install the *command line developer tools* when you run `git`, click Install, or use the ZIP.)

### 2. Start the server

```bash
bash start-mac.command
```

You can also double-click `start-mac.command` in Finder. The first time, macOS may block it because it was downloaded:
right-click it → **Open** → **Open**, or just use the Terminal command above, which always works.

The first run takes a few minutes and keeps everything inside the project folder:

| Step | What happens |
|---|---|
| Python | Uses Python 3.10 to 3.13 if you have it. macOS's built-in `python3` is usually too old, so otherwise it downloads a private Python 3.12 into `.tools/` using `uv` |
| `.venv/` | A private Python environment with the dependencies |
| `.tools/` | Portable `ffmpeg`, `ffprobe`, `deno` and `cloudflared` for your Mac's chip |
| `.env`, `secrets/api_key.txt` | Same as Windows: local mode settings and your **permanent** API key |
| Tunnel | A free Cloudflare quick tunnel, or your permanent URL if you set one up |

### 3. Everything else is the same as Windows

The window prints the same `API URL` and `API key` lines. Continue with **steps 3–7 above**, using these Mac equivalents:

| Windows | macOS |
|---|---|
| `start-windows.bat` | `bash start-mac.command` |
| `setup-permanent-url.bat` | `bash setup-permanent-url.command` |
| `setup-permanent-url.bat -Remove` | `bash setup-permanent-url.command --remove` |
| `secrets\api_key.txt` | `secrets/api_key.txt` (`cat secrets/api_key.txt`) |
| Close the window | Press **Ctrl+C** in Terminal |
| `install-background.bat` | `bash install-background.command` (move the folder out of Desktop/Documents/Downloads first, since macOS blocks background jobs there) |
| `background-status.bat` | `bash install-background.command --status` |
| `uninstall-background.bat` | `bash install-background.command --uninstall` |
| `rotate-key.bat` | `bash rotate-key.command` (restarts background mode for you) |

Keep the Terminal window open while you use the API, or use background mode (step 7) to run it as a hidden
login service via launchd that also keeps the Mac awake.

**Updating:** run `git pull` (or re-download the ZIP over the folder), then start it again.

---

## The dashboard

| Panel | What it shows |
|---|---|
| **Overview** | Thumbnail, title, *Official* or *Estimated* badge, confidence and why, length, disclaimer |
| **Key numbers** | Peak moment, biggest drop-off, average engagement, % of hot segments (score ≥ 0.6), signals used. Tap a time to play it |
| **Engagement over time** | Heat strip plus the score curve. Green bands are peaks (numbered), red bands are drop-offs, the dashed line is the average. Hover for each signal's value, click to play from there |
| **Player** | Embedded YouTube player that jumps to any moment you tap |
| **Top moments / Least engaging** | Ranked ranges with score and the signals that drove them, plus a *YouTube ↗* link at that timestamp |
| **Engagement by part of the video** | Average score for each fifth: Intro, Early, Middle, Late, Ending |
| **Signals over time** | Each signal's own curve. Tap the chips to show or hide signals |
| **Signal weights** | How much each signal counts, and any signal that was skipped with the reason |
| **What drove the score** | Each signal's share of the total weighted score |
| **Agreement with final score** | Correlation (−1 to 1) between each signal and the combined score |
| **Score distribution** | How many segments fall in each 0.1 score band |
| **Data** | Download JSON or CSV, copy JSON, view the raw response |
| **About** | Plain-English version of the section below |

The dashboard is a static site in `dashboard/` (plain HTML, CSS and JS, no build step). Your URL and key
are saved only in your browser's local storage and sent only to your own API.

---

## Understanding the results

### Segments

Every video is cut into equal **segments**, 10 seconds by default (5 to 60 s, set with the
dashboard's *Segment size* or the `window` parameter). Everything is scored per segment.

### Score

A number from **0 to 1** for each segment, **relative to the rest of the same video**: 1.00 is
this video's most engaging moment and 0.00 its least. It's a ranking within one video, not a grade,
so 0.8 on one video doesn't mean the same as 0.8 on another.

- **Official** scores are YouTube's relative replay intensity. They are **not** view counts.
- **Estimated** scores are a heuristic, not viewing data. Every estimated response has `"is_estimate": true` and a `disclaimer`.

### Signals

A **signal** is one independent measurement taken for every segment. Each one is min-max scaled to
0–1 within the video (strongest segment = 1, weakest = 0) so they can be blended fairly.

| Signal | Weight | How it's measured |
|---|---|---|
| **Comments** | 0.35 | Finds timestamps people write in comments (`3:42`, `1:02:10`). Each mention is spread over ±5 s, and liked comments count more (weight `1 + ln(1 + likes)`). Up to 2,000 comments. Skipped if fewer than 10 timestamped comments. Uses the YouTube Data API when `YT_API_KEY` is set, else yt-dlp scraping |
| **Captions** (`transcript`) | 0.25 | Transcript text per segment, scored on hook phrases ("watch this", "here's why"), emphasis words ("insane", "biggest"), questions, numbers and claims, topic shifts versus the previous segment, and speech density. Optional LLM rating blended in when `LLM_API_KEY` is set |
| **Audio** | 0.25 | 16 kHz mono audio. **Audio events** from [YAMNet](https://huggingface.co/audiomagic/yamnet-onnx) (Google's AudioSet classifier, 521 sounds, run locally with ONNX Runtime): each window's *reaction* score is the strongest of laughter, applause/cheering, crowd noise and shouting/gasps. Audio = `0.5 × reaction + 0.3 × loudness (RMS dB) + 0.2 × onset rate`. A trained head is used instead: the bundled default (trained on 20 videos with official data), or your own if you train one (below) and it beats zero-shot on unseen videos. If the model can't load, it falls back to `0.5 × loudness + 0.3 × onset rate + 0.2 × loud noise-like bursts`. Past the end of the audio counts as silence |
| **Visuals** | 0.15 | A ≤360p video-only stream decoded by ffmpeg to 64×36 grayscale frames at 2 fps (AV1, VP9 and H.264 all work): `0.6 × cut density + 0.4 × motion`. A cut is a frame jump far above the video's usual change (median + 6 × MAD, at least 25) |

### How the final score is calculated

1. **Split** the video into segments.
2. **Measure** each signal for every segment.
3. **Scale** each signal to 0–1 within the video.
4. **Blend**: `0.35 × comments + 0.25 × captions + 0.25 × audio + 0.15 × visuals`.
5. **Rescale** the blend to 0–1 again, so the top segment is always 1.00.
6. **Shape**: a power curve `score^k` pulls ordinary segments down so the median lands at
   `ESTIMATE_MEDIAN_TARGET` (default 0.12). YouTube's real replay data is mostly near zero with a few
   spikes, while an average of four signals hovers around 0.5. Order is unchanged, so peaks and
   drop-offs stay the same; only the scale now looks like official data. Set it to `0` to turn it off.

A trailing piece of half a segment or less is merged into the previous segment, so the last few seconds
aren't flagged as a drop-off just because they're short.

#### Calibrating against official data

The weights are reasonable defaults, not truths. To fit them to the videos you analyse, list 10+
videos that **do** have YouTube's "Most replayed" graph in `calibration/videos.txt` (one per line) and
double-click `calibrate.bat` (Windows) or `calibrate.command` (Mac). Or run
`python -m scripts.calibrate --file calibration/videos.txt`. It runs both modes on each video, reports
how well the estimate's ranking matches (Spearman) and how many of the real top-5 moments it found, then
searches for the best weights and shape. Add `--apply` to save them to `.env`, then restart the server.

#### Training the audio model on your own videos

The audio signal can learn what engagement *sounds like* in the videos you analyse. Put videos that have
the "Most replayed" graph in `calibration/videos.txt` (the same file calibrate uses; 15+ is best, 5 is the
minimum) and double-click `train-audio.bat` (Windows) or `train-audio.command` (Mac), or run
`python -m scripts.train_audio --file calibration/videos.txt`.

For each video it downloads the audio once, runs YAMNet, and lines up the sound features (laughter,
applause, crowd, shouting, impacts, music, speech, silence, loudness, change in loudness, speech rate, plus
YAMNet's 1024-number embedding) with YouTube's official curve. It then fits a small ridge regression on top
of the frozen YAMNet features (transfer learning: YAMNet itself isn't retrained, which would need far more
data) and tests it with **leave-one-video-out cross-validation**, so every number it prints is for a video
the model never saw. It compares three things: the old loudness-only signal, YAMNet zero-shot, and the
trained head. The head is saved to `models/audio_head.json` and switched on only if it beats zero-shot (a head of yours always overrides the bundled default, which was trained on 20 YTMR500 videos: ρ 0.16 vs 0.04 zero-shot on unseen videos, see `benchmarks/audio/v1.5`);
restart the server to use it. Features are cached in `calibration/audio/`, so adding videos later is quick.

Cost: the model is 16 MB, downloaded once on first use (checked against a pinned SHA-256) into `models/`.
It runs on the CPU in roughly 2 to 5 seconds per 10 minutes of audio and about 300 MB of RAM, only for
estimates. Set `AUDIO_EVENTS=false` in `.env` to switch it off.

If a signal can't be measured (comments off, no captions, a download fails), it's dropped and the
remaining weights are scaled up to add to 1. It's listed in `signals_skipped` with the reason, for example
`{"visual": "DownloadError: ..."}`, and the dashboard shows it under *Signal weights*.

### Peaks and drop-offs

The highest-scoring segments seed **top moments** and the lowest seed **drop-offs**. Each seed grows over
neighbouring segments within 0.05 of its score (`MERGE_TOLERANCE`) into one range, and peaks never overlap
drop-offs. For a peak, `signals` lists the signals that contributed at least 20% of its weighted score, with
their `share`.

### Confidence

| Level | Rule (estimated) |
|---|---|
| **high** | Comments with ≥ 50 timestamped comments **plus** ≥ 2 other signals |
| **medium** | Comments plus 1 other signal, **or** captions plus 2 others |
| **low** | Anything thinner |

Official data is always `high`. Estimates are best on videos with lots of timestamped comments and captions.
They find moments that look and sound engaging; they can't see real watch time.

---

## Using the API directly

```bash
export KEY=yhx_your_key
export API=http://localhost:8000
```

**Fast path:** official or cached data comes back immediately with `200`.

```bash
curl -s -H "X-API-Key: $KEY" \
  "$API/v1/heatmap?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&top=5&bottom=5"
```

If the video has no official heatmap, the same call queues an estimate and returns `202`:

```json
{"job_id": "5f0c...", "status": "queued", "status_url": "http://localhost:8000/v1/jobs/5f0c...",
 "message": "No official heatmap is available; an estimate is being computed."}
```

**Slow path:** queue explicitly (optionally with a webhook):

```bash
curl -s -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"url":"https://youtu.be/VIDEO_ID","top":5,"bottom":5,"window":10,
       "force_estimate":false,"webhook_url":"https://example.com/hooks/heatmap"}' \
  "$API/v1/jobs"

curl -s -H "X-API-Key: $KEY" "$API/v1/jobs/JOB_ID"
# {"job_id":"...","status":"processing","progress":0.55,"stage":"analysing audio","result":null}
```

Statuses: `queued | processing | done | failed`. Jobs are private to the key that created
them. Webhooks receive `{"job_id", "status", "result"}` or `{"job_id", "status", "error"}`.
They must be public `https://` URLs (private/loopback addresses are rejected).

### Response

```json
{
  "video_id": "abc123XYZ_0",
  "title": "...",
  "duration": 612,
  "source": "estimated",
  "is_estimate": true,
  "confidence": "medium",
  "confidence_reason": "3 signals available (comments, transcript, audio), 23 timestamped comments.",
  "signals_used": ["comments", "transcript", "audio"],
  "signals_skipped": {"visual": "DownloadError: ..."},
  "weights": {"comments": 0.412, "transcript": 0.294, "audio": 0.294},
  "window_seconds": 10,
  "most_engaging": [
    {"start": 220, "end": 250, "start_hms": "00:03:40", "end_hms": "00:04:10", "score": 1.0,
     "type": "peak", "link": "https://youtu.be/abc123XYZ_0?t=220",
     "signals": [{"name": "comments", "value": 0.97, "share": 0.61}, {"name": "audio", "value": 0.8, "share": 0.25}]}
  ],
  "least_engaging": [
    {"start": 480, "end": 510, "start_hms": "00:08:00", "end_hms": "00:08:30", "score": 0.0,
     "type": "drop-off", "link": "https://youtu.be/abc123XYZ_0?t=480",
     "signals": [{"name": "comments", "value": 0.0}, {"name": "audio", "value": 0.05}]}
  ],
  "full_heatmap": [{"start": 0, "end": 10, "score": 0.31, "signals": {"comments": 0.2, "audio": 0.5}}],
  "disclaimer": "Estimated from comments, captions, audio and visuals. This is a heuristic, not real viewer data.",
  "cached": false
}
```

### Errors

Always `{"error": {"code": "...", "message": "..."}}`:

| HTTP | code | meaning |
|---|---|---|
| 400 | `invalid_url` | not a YouTube video URL / ID |
| 401 | `unauthorized` | missing or invalid `X-API-Key` |
| 403 | `video_private`, `video_members_only`, `video_premium_only`, `video_needs_sign_in`, `video_age_restricted` | can't be analysed: only videos anyone can watch work, public or unlisted (age-restricted works with cookies) |
| 404 | `video_unavailable`, `job_not_found` | removed video, unknown/expired job |
| 422 | `video_live`, `video_too_long`, `no_data_available`, `validation_error` | |
| 429 | `rate_limited`, `quota_exceeded` | per-minute limit / daily quota (has `Retry-After`) |
| 502 | `upstream_blocked` | YouTube blocked this server; configure a proxy or cookies |

Common dashboard messages:

| Message | Fix |
|---|---|
| *Couldn't reach the API* | The server window was closed, or (quick tunnel) the URL changed on restart, so paste the new one. A permanent URL avoids this. On an old version, update so CORS is on |
| *Error 401* | Wrong key. Copy it again from `secrets\api_key.txt` |
| *Error 530 / 502* | The tunnel can't reach your server. Restart `start-windows.bat` |
| `server_offline` (503) | Your permanent URL works but the server is off. Start `start-windows.bat`, then wait up to a minute after it starts |
| `upstream_blocked` | YouTube is blocking the request. See *Reliability* below |

---

## Advanced

### How local mode works

`start-windows.bat` runs `scripts/local-windows.ps1`, which runs `python -m app.local`: uvicorn and an RQ
`SimpleWorker` in one process on an in-memory `fakeredis` (`REDIS_URL=memory://`). Cache and job history
reset when you close the window; the API key stays because only its HMAC hash is stored in `API_KEY_HASHES`
in `.env`. Requests leave from your own internet connection, so YouTube rarely blocks them.

### Permanent URL: how it works

`setup-permanent-url.bat` → `scripts/setup-tunnel.ps1`:

- **workers.dev:** `scripts/cf_worker.py setup` uses your API token to read your account, claim your
  workers.dev subdomain if you don't have one yet, create the KV namespace `yt-heatmap-api`, upload
  `worker/proxy.js` as the Worker `yt-heatmap-api`, and enable it on workers.dev. It saves `CF_API_TOKEN`, `CF_ACCOUNT_ID`,
  `CF_KV_NAMESPACE_ID`, `CF_WORKER_URL` and `PUBLIC_BASE_URL` in `.env`. On each start the runner calls
  `cf_worker set-target <quick-tunnel-url>`.
- **Own domain:** writes `CLOUDFLARE_TUNNEL_TOKEN` and `PUBLIC_BASE_URL`. The runner then runs
  `cloudflared tunnel run --token ...` instead of a quick tunnel. The Docker path reads the same two values.

### Free self-hosting with Docker (your own computer + Cloudflare Tunnel)

Costs nothing, and because requests leave from your home/college internet (not a datacenter IP),
YouTube is far less likely to block extraction, so no proxy is needed. The API is online only
while your computer is on and Docker is running.

1. Install [Docker Desktop](https://docs.docker.com/get-docker/) and start it.
2. `git clone https://github.com/velvetthunder15/heatmapify.git && cd heatmapify`
3. Run one command:
   - macOS / Linux / WSL: `./scripts/selfhost.sh`
   - Windows PowerShell: `powershell -ExecutionPolicy Bypass -File .\scripts\selfhost.ps1`

It creates `.env` (random pepper, laptop-sized concurrency), builds and starts API + worker +
Redis + a Cloudflare quick tunnel, waits for `/health`, and prints your public
`https://<random>.trycloudflare.com` URL plus your first API key (shown once).

Other commands: `selfhost.sh url` (current URL), `selfhost.sh key NAME` (new key),
`selfhost.sh stop`.

**Stable URL with Docker:** the quick-tunnel URL changes on every restart. The free workers.dev option is built into
the Windows runner. With Docker, after each start you can run `python -m scripts.cf_worker set-target <url>` yourself, or for a fixed
URL on your own domain, add a domain to a free Cloudflare account, create a tunnel in Zero Trust → Networks → Tunnels
pointing to `http://api:8000`, then put `CLOUDFLARE_TUNNEL_TOKEN=...` and
`PUBLIC_BASE_URL=https://your.host` in `.env`. The script switches to the named tunnel automatically.

### Paid / cloud deployment

Needs long-running workers and ffmpeg, so it is **not suited to serverless** (Lambda, Vercel,
Cloud Functions). Use a container host:

- **Render**: a *Web Service* (Dockerfile, default CMD) + a *Background Worker* (same repo,
  start command `python -m app.worker`) + *Render Key Value* (Redis). Set env vars from
  `.env.example`; set `PUBLIC_BASE_URL`.
- **Railway**: deploy the repo twice (api / worker with start command `python -m app.worker`)
  and add the Redis plugin; reference `${{Redis.REDIS_URL}}`.
- **Fly.io**: `fly launch`, then define `[processes] app = "gunicorn ..."`,
  `worker = "python -m app.worker"`, and attach Upstash Redis (`fly redis create`).
- **VPS**: `docker compose up -d` behind Caddy or nginx with TLS. Give the worker 2+ GB RAM
  (librosa).

Then create keys with `scripts.manage_keys` inside the API container.

### Reliability: YouTube blocking

YouTube routinely blocks datacenter IPs ("Sign in to confirm you're not a bot"). You will
almost certainly need one of:

- `YT_PROXY=http://user:pass@host:port`: a **residential** proxy works best.
- `YT_COOKIES_FILE=/secrets/cookies.txt`: Netscape-format cookies from a throwaway account,
  mounted via `./secrets`. This also unlocks age-restricted videos.

All yt-dlp calls retry with exponential backoff and surface `upstream_blocked` instead of
failing silently. The image includes Deno, which current yt-dlp needs to solve YouTube's
player challenges.

**Upgrading yt-dlp** (do this whenever extraction breaks):

```bash
make bump-ytdlp V=2026.11.01
# or without editing requirements: docker compose build --build-arg YTDLP_VERSION=2026.11.01
```

### API keys

- Keys look like `yhx_...` and are stored only as `HMAC-SHA256(API_KEY_PEPPER, key)`.
- `python -m scripts.manage_keys create --name NAME [--rate N] [--quota N]`, `list`, `revoke HASH`.
- Static keys without Redis records: `python -m scripts.manage_keys hash yhx_...` and put the
  hash in `API_KEY_HASHES`.
- Rate limit is per minute; daily quota resets 00:00 UTC. Polling `/v1/jobs/{id}` counts toward
  the rate limit but not the daily quota.
- Local mode's key lives in `secrets/api_key.txt`. `rotate-key.bat` / `rotate-key.command`
  (`python -m scripts.local_setup --rotate-key`) replaces it and removes the old hash.
- `CORS_ORIGINS` lists the websites allowed to call the API from a browser (default: the two
  Heatmapify dashboards). Pages on `localhost` are always allowed (`CORS_ALLOW_LOCALHOST=false` to turn off).

### Multi-user safety

- Strict URL validation: YouTube hosts only; only the 11-char ID is used downstream (SSRF-safe).
- Cache by video ID: official 24 h, estimated 7 days. One analysis serves any `top`/`bottom`.
- Estimated mode limited to `MAX_ESTIMATE_DURATION` (60 min). Concurrency: `WORKER_CONCURRENCY`
  processes per worker container, plus a cluster-wide `GLOBAL_MAX_JOBS` Redis semaphore.
- Temp audio/video lives in a per-job directory that is deleted in a `finally` block (and the
  temp root is wiped when a worker starts).
- Identical in-flight requests join the same job instead of re-processing.
- Structured JSON logs; no request bodies or keys are logged; nothing is stored beyond the cache
  and job results (which expire).

### Tests

No network, ffmpeg or audio libraries needed:

```bash
pip install -r requirements-dev.txt
pytest -q
```

### Project layout

```
app/
  main.py         FastAPI routes, CORS, error handlers, auth dependency
  local.py        single-process local mode (uvicorn + RQ SimpleWorker on fakeredis)
  config.py       all settings (env vars)
  urls.py         strict YouTube URL parsing
  auth.py         hashed API keys, rate limits, quotas
  cache.py        Redis connection + heatmap cache
  jobs.py         RQ jobs, progress, global semaphore, webhooks
  pipeline.py     fallback chain, confidence, signals_skipped, response rendering
  scoring.py      windows, normalisation, weighting, peak/drop-off merging
  ytdl.py         yt-dlp options, per-download temp folders, proxy/cookies, retry/backoff
  worker.py       multi-process RQ worker entrypoint (Docker mode)
  sources/        official.py comments.py transcript.py audio.py visual.py
dashboard/        static web dashboard: index.html (connect + analyze), about.html (how it works), styles.css, app.js, sample.json
scripts/
  local-windows.ps1  Windows runner behind start-windows.bat
  local-mac.sh       macOS runner behind start-mac.command
  background-windows.ps1 / run-hidden.vbs / background-install.ps1   Windows background mode
  background-mac.sh  macOS background mode (launchd LaunchAgent)
  setup-tunnel.sh    macOS twin of setup-tunnel.ps1
  local_setup.py     creates .env, CORS and the permanent API key
  setup-tunnel.ps1   behind setup-permanent-url.bat
  cf_worker.py       deploys the Worker + KV and updates its target
  manage_keys.py     create / list / revoke keys (Docker mode)
  selfhost.sh/.ps1   Docker + tunnel self-hosting
start-windows.bat
setup-permanent-url.bat   permanent URL via your Cloudflare account (workers.dev or own domain)
start-mac.command         macOS one-command start
install-background.bat / uninstall-background.bat / background-status.bat   Windows background mode
install-background.command   macOS background mode
rotate-key.bat / rotate-key.command   replace the API key
calibrate.bat / calibrate.command     tune estimate weights against official data
train-audio.bat / train-audio.command train the YAMNet audio model on official data
setup-permanent-url.command   macOS permanent-URL setup
worker/proxy.js           the workers.dev forwarding Worker
render.yaml       deploys dashboard/ to Render (main dashboard, auto-deploys on push)
SECURITY.md       how keys are protected, and how to report a problem
tests/
```

## Terms of Service

This project scrapes YouTube pages and media outside the official Data API. That can
conflict with [YouTube's Terms of Service](https://www.youtube.com/t/terms). **Review them
(and get legal advice) before running this publicly or as a paid service.** Prefer the
official API where it covers your needs, cache aggressively, and respect rate limits.

## Security

- **Your API key never leaves your browser except to your own server.** The dashboard is a static page with no backend. The key is sent only as an `X-API-Key` header to the API URL you entered, and only over https (plain http is refused except for `localhost`).
- **Where it's stored:** only in this browser. By default it lasts until you close the tab. Tick *Remember on this device* to keep it, and use *Forget key* to wipe it. The key box isn't a password field, so browsers won't offer to save it as a login.
- **Shared links can't steal it:** opening a link with someone else's `?api=` never sends them your saved key.
- **The page is locked down:** a strict Content-Security-Policy (no inline or third-party scripts), no framing, and only the bare site origin is sent as a referrer (YouTube's embedded player refuses to play without it; calls to your API send no referrer at all). Results from the server are validated before they're shown.
- **On the server:** keys are stored only as HMAC-SHA256 hashes, every key is rate-limited, and browsers may call the API only from the Heatmapify dashboard or pages on your own computer (`CORS_ORIGINS`). API responses are marked `no-store`.
- **If your key leaks:** double-click `rotate-key.bat` (Windows) or `rotate-key.command` (Mac). It prints a new key, the old one stops working once the server restarts, and you paste the new key into the dashboard.

## License

[MIT](LICENSE) © 2026 Chirag Rasane. The license covers this code only. It doesn't grant any rights to YouTube content or override YouTube's Terms of Service.
