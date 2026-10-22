"""Local podcast transcription prototype. Run one Uvicorn worker."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI()
jobs = {}
lock = threading.Lock()
API = "https://api.assemblyai.com/v2"


def youtube_url(value):
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.port:
        raise ValueError("Paste a valid YouTube video link.")
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        video = parsed.path.strip("/")
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            video = parse_qs(parsed.query).get("v", [""])[0]
        elif re.fullmatch(r"/(shorts|live|embed)/[^/]+/?", parsed.path):
            video = parsed.path.strip("/").split("/")[1]
        else:
            video = ""
    else:
        video = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
        raise ValueError("Paste a YouTube video link, rather than a playlist or channel.")
    return f"https://www.youtube.com/watch?v={video}"


class Submission(BaseModel):
    url: str = Field(max_length=2048)


def update(job_id, **values):
    with lock:
        jobs[job_id].update(values)


def transcribe(job_id, url, key):
    try:
        update(job_id, status="downloading")
        with tempfile.TemporaryDirectory() as folder:
            # Fixed canonical URL and argument array: never execute user shell input.
            result = subprocess.run([
                sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist",
                *(["--js-runtimes", "node"] if shutil.which("node") else []),
                "--no-progress", "--max-filesize", "200M", "--socket-timeout", "30",
                "--match-filter", "!is_live & duration <= 7200",
                "-f", "bestaudio[ext=m4a]/bestaudio", "-o", f"{folder}/audio.%(ext)s", url,
            ], capture_output=True, text=True, timeout=600)
            files = [p for p in Path(folder).glob("audio.*") if p.suffix not in (".part", ".ytdl")]
            if result.returncode or not files:
                raise ValueError("Could not download this video. Try a public, non-live video under 2 hours. YouTube may restrict automated downloads.")
            audio = files[0]
            if audio.stat().st_size > 200 * 1024 * 1024:
                raise ValueError("This video's audio exceeds the 200 MB limit.")
            headers = {"authorization": key}
            update(job_id, status="uploading")
            with audio.open("rb") as stream:
                response = requests.post(f"{API}/upload", headers=headers, data=stream, timeout=300)
            response.raise_for_status()
            response = requests.post(f"{API}/transcript", headers=headers, json={
                "audio_url": response.json()["upload_url"],
                "speaker_labels": True, "language_detection": True,
            }, timeout=30)
            response.raise_for_status()
            transcript_id = response.json()["id"]
        update(job_id, status="transcribing")
        deadline = time.monotonic() + 7200
        while time.monotonic() < deadline:
            response = requests.get(f"{API}/transcript/{transcript_id}", headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data["status"] == "error":
                raise ValueError("The transcription service could not process this audio. Try another video.")
            if data["status"] == "completed":
                utterances = [{"speaker": u.get("speaker") or "Unknown", "start": u["start"],
                               "end": u["end"], "text": u["text"]} for u in data.get("utterances") or []]
                update(job_id, status="completed", utterances=utterances)
                return
            time.sleep(4)
        raise ValueError("Transcription timed out. Please try again later.")
    except requests.HTTPError as exc:
        code = exc.response.status_code
        message = "Check your AssemblyAI API key and account balance." if code in (401, 402, 403) else "The transcription service is unavailable. Please try again later."
        update(job_id, status="error", error=message)
    except ValueError as exc:
        update(job_id, status="error", error=str(exc))
    except Exception:
        update(job_id, status="error", error="Processing failed or the connection timed out. Please try again.")


@app.get("/api/config")
def config():
    return {"configured": bool(os.getenv("ASSEMBLYAI_API_KEY"))}


@app.post("/api/transcripts", status_code=202)
def create(body: Submission, background: BackgroundTasks):
    try:
        url = youtube_url(body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    key = os.getenv("ASSEMBLYAI_API_KEY")
    if not key:
        raise HTTPException(503, "Add ASSEMBLYAI_API_KEY to .env and restart the server. You can try the demo meanwhile.")
    with lock:
        if any(j["status"] not in ("completed", "error") for j in jobs.values()):
            raise HTTPException(429, "A transcript is already processing. Please wait for it to finish.")
        # Bound memory for this local prototype.
        while len(jobs) >= 20:
            del jobs[next(iter(jobs))]
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"id": job_id, "url": url, "status": "queued"}
    background.add_task(transcribe, job_id, url, key)
    return {"id": job_id}


@app.get("/api/transcripts/{job_id}")
def get_job(job_id: str):
    with lock:
        if job_id not in jobs:
            raise HTTPException(404, "Transcript not found. The server may have restarted.")
        return dict(jobs[job_id])


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="web")
