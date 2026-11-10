# Cadence · Transcribe podcasts by speaker

A local first version of a responsive web app for desktop and mobile browsers. Paste a public YouTube video link, transcribe its audio, and read timestamped passages labeled by speaker.

## Run locally

Requires Python 3.10+ and internet access. Node.js 22+ is recommended for YouTube extraction; some videos may also require ffmpeg or a supported JavaScript runtime such as Deno. See [yt-dlp installation](https://github.com/yt-dlp/yt-dlp/wiki/Installation).

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set ASSEMBLYAI_API_KEY in .env, then:
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. **Try a sample** works without credentials and uses a labeled fictional conversation. Real transcription requires your own [AssemblyAI API key](https://www.assemblyai.com/dashboard) and may incur provider charges. Keep the key in `.env`, never frontend code.

## Accounts and saved conversations

1. Refresh the app and choose **Create account** using your email and a password of at least 10 characters.
2. The first account on this local installation receives any backed-up conversations in `data/recovery/`. Create your own account first. Subsequent accounts have separate libraries.
3. New transcripts are saved automatically. Open **Past conversations** to return to them after refreshing or restarting.
4. Edit the title, speaker names, or optional YouTube source link, then click **Save title and speaker names**. Unsaved edits are flagged.

Accounts, hashed passwords, sessions, and transcripts are stored in `data/cadence.sqlite3` on this Mac. They are not synced to the cloud. Session cookies expire after seven days; signing out revokes the session. Emails are account identifiers; email verification and password reset are not implemented. Keep your password safe.

**Backups:** stop the server, then copy the entire `data/` folder to a safe location. Keep it with the project if moving the folder again. It contains private transcripts and account data; do not commit or share it. Both `data/` and `.env` are ignored by Git. Database records are not encrypted at rest; anyone with filesystem access may read them.

The existing transcript was backed up from AssemblyAI before enabling storage. Recovery imports are idempotent and never overwrite later edits. Browser-only speaker names and the source YouTube link are not available from the provider; add them in the saved conversation if needed.

## Included

- Public YouTube video links, including short, Shorts, and live-recording URL forms.
- Audio download, upload, transcription, and completion/error states.
- [Speaker diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers), automatic language detection, timestamps, and links back to video moments.
- Editable speaker names, transcript search, and plain-text export.
- Layouts for desktop and mobile browsers; this is not yet a native iOS or Android app.

## Architecture and limits

FastAPI serves the static HTML/CSS/JavaScript interface and API. A background task downloads audio using yt-dlp, uploads it to AssemblyAI, and polls for a speaker-labeled transcript. Temporary downloaded audio is removed after submission or failure. Audio is sent to AssemblyAI; its service retention policy applies.

This is a **local prototype with separate password-protected accounts**. Use one server worker. Conversations persist in SQLite; a maximum of 20 jobs are cached in memory, without deleting saved records. Server restart marks unfinished work as interrupted; completed transcripts remain available. The browser remembers the active job ID per account to resume polling after refresh. One transcription runs at a time, with a two-hour video limit and 200 MB audio limit. Downloading times out after ten minutes and transcription polling after two hours; a provider job may still continue after a local timeout.

YouTube may block automated downloads or require sign-in for some videos. Use public content you have permission to process. Before a public launch, configure HTTPS, email verification/password reset, an authenticated media upload fallback, a persistent job queue, per-user quotas, deletion controls, backups, and monitoring. Sign-in attempts have a basic in-process limit; it resets when the server restarts. Keep the server on loopback for local use. Accounts isolate API access, but this is not yet a production identity service. A hosted backend must support Python subprocesses and long-running jobs.

Speakers receive labels such as A and B, not verified personal identities. Rename them after reviewing the transcript. Accuracy varies with overlapping speech, noise, accents, and recording quality. **99% accuracy is a goal to evaluate, not a measured guarantee.**

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
```

Tests cover URL restrictions, API errors, concurrency limits, the pipeline with mocked external services, authentication, cross-account isolation, session revocation/expiry, recovery ownership, and persistence across restart. A real YouTube-to-transcript run requires a configured API key and network access.


## Railway backend deployment

The Dockerfile includes Python, Node.js (for YouTube extraction), and ffmpeg.
Deploy one service with **one replica and one Uvicorn worker**. Attach a Railway
volume at `/data` and set `CADENCE_DB=/data/cadence.sqlite3`. Startup refuses to
run on Railway without a persistent database mount. Configure
`ASSEMBLYAI_API_KEY` as a Railway secret, never in the image or Git.
`/api/health` checks database access. The service uses Railway's `PORT`.

Before the first public deployment, migrate a consistent SQLite backup to the
volume (never overwrite a running production database). Existing password hashes
and conversation ownership carry over. Remove sessions from the migration copy
so users sign in again. Keep the original local database intact. Configure volume
backups in Railway. Do not scale this SQLite backend to multiple replicas.

For the Vercel frontend, publish `static/` and proxy `/api/:path*` to the Railway
HTTPS origin. Add the exact Vercel production origin to Railway's `APP_ORIGINS`;
never use `*`. The browser then uses same-origin HTTP-only session cookies.
Railway can also serve the existing frontend directly while Vercel is configured.
Do not enable arbitrary preview origins. `.railwayignore` and `.dockerignore`
exclude local credentials, databases, virtual environments, and backups.

Deployments interrupt active transcription jobs; wait for them to finish before
releasing changes. YouTube may restrict downloads from cloud IPs even when the
same video works locally; verify a real video after deployment.


### Deployed production services

- Website: https://cadence-transcribe-tau.vercel.app
- Backend: https://backend-production-64fc9491.up.railway.app
- Railway project: `cadence-transcribe`, service: `backend`, volume mount: `/data`.
- Vercel project: `cadence-transcribe` in `sean-2133s-projects`; deploy from `static/`.
- The local account and two conversations were migrated with record-by-record
  verification. Local and production databases are independent from now on.
- Railway `APP_ORIGINS` permits the exact production website origin. Sessions
  use secure HTTP-only cookies. Environment keys remain in Railway variables.

Future releases: deploy the backend from the repository root with `railway up`,
then the frontend with `vercel deploy --prod --cwd static`. CLI logins and project
links are machine-local. Wait for active transcriptions before redeploying.
Railway currently warns that `railway.json` must migrate to its new IaC format
before December 1, 2026; use `railway config migrate` to plan that migration.
