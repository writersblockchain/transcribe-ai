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

## Included

- Public YouTube video links, including short, Shorts, and live-recording URL forms.
- Audio download, upload, transcription, and completion/error states.
- [Speaker diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers), automatic language detection, timestamps, and links back to video moments.
- Editable speaker names, transcript search, and plain-text export.
- Layouts for desktop and mobile browsers; this is not yet a native iOS or Android app.

## Architecture and limits

FastAPI serves the static HTML/CSS/JavaScript interface and API. A background task downloads audio using yt-dlp, uploads it to AssemblyAI, and polls for a speaker-labeled transcript. Temporary downloaded audio is removed after submission or failure. Audio is sent to AssemblyAI; its service retention policy applies.

This is a **local, single-user prototype**, with no authentication. Do not expose it directly to the public internet. Use one server worker. Jobs live in memory (maximum 20), and restart clears them. The browser remembers the active job ID to resume polling after refresh; speaker renames are temporary, so export before refreshing. One transcription runs at a time, with a two-hour video limit and 200 MB audio limit. Downloading times out after ten minutes and transcription polling after two hours; a provider job may still continue after a local timeout.

YouTube may block automated downloads or require sign-in for some videos. Use public content you have permission to process. For a public launch, add an authenticated media upload fallback, durable storage, a persistent job queue, per-user access controls, quotas, deletion controls, and monitoring. A hosted backend must support Python subprocesses and long-running jobs.

Speakers receive labels such as A and B, not verified personal identities. Rename them after reviewing the transcript. Accuracy varies with overlapping speech, noise, accents, and recording quality. **99% accuracy is a goal to evaluate, not a measured guarantee.**

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
```

Tests cover URL restrictions, API errors, concurrency limits, and the pipeline with mocked external services. A real YouTube-to-transcript run requires a configured API key and network access.
