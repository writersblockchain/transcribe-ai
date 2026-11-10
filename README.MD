# Cadence

Turn YouTube podcasts into searchable, timestamped transcripts organized by speaker. Create an account, save conversations, rename speakers, and export transcripts as text.

**Live app:** https://cadence-transcribe-tau.vercel.app

## Run locally

Requires Python 3.10+, Node.js 22+, and ffmpeg.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your AssemblyAI key to `.env`:

```env
ASSEMBLYAI_API_KEY=your_key_here
```

Start the app:

```sh
python -m uvicorn app:app --reload
```

Open http://127.0.0.1:8000. **Try a sample** works without an API key. Real transcription uses your AssemblyAI account and may incur charges.

## Storage

Each account has a private conversation library. Transcripts save automatically; click **Save title and speaker names** after editing.

- **Local:** SQLite database at `data/cadence.sqlite3`.
- **Production:** SQLite on a persistent Railway volume at `/data/cadence.sqlite3`.
- Local and production data are separate. To back up local data, stop the server and copy `data/`. Manage production volume backups in Railway.

Never commit `.env`, database files, or backups. Account passwords are hashed; transcript data is not encrypted at rest.

## Deployment

The frontend runs on **Vercel**; the FastAPI backend runs on **Railway**. Audio is downloaded with yt-dlp and transcribed by AssemblyAI.

| Service | Configuration |
| --- | --- |
| Vercel | Project `cadence-transcribe`; root directory `static/` |
| Railway | Project `cadence-transcribe`; service `backend`; one replica and worker |
| Railway volume | Mount at `/data` |
| Health check | `/api/health` |

Set these Railway environment variables:

- `ASSEMBLYAI_API_KEY`: your private API key.
- `CADENCE_DB`: `/data/cadence.sqlite3`.
- `APP_ORIGINS`: `https://cadence-transcribe-tau.vercel.app`.

`static/vercel.json` proxies API requests to Railway. If changing domains, update that configuration and `APP_ORIGINS`.

With the official CLIs installed, signed in, and linked:

```sh
railway up --service backend
vercel deploy --prod --cwd static
```

Wait for active transcriptions to finish before deploying. Railway has announced that `railway.json` needs migration to its new IaC format before December 1, 2026; use `railway config migrate` to review the migration.

## Limits

- One transcription at a time; videos up to two hours and audio up to 200 MB.
- YouTube may block cloud downloads. Accuracy varies; speaker labels are not verified identities.
- Restarting the backend interrupts unfinished jobs. Completed conversations remain saved.
- Email verification, password reset, and per-user usage quotas are not implemented.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
```

Tests cover authentication, private libraries, persistence, URL validation, deployment checks, and a mocked transcription pipeline.
