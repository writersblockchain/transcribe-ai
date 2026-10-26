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
import sqlite3
from contextlib import asynccontextmanager
import storage
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()
@asynccontextmanager
async def lifespan(app):
    storage.initialize()
    yield

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def same_origin(request: Request, call_next):
    if request.method in ("POST", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin != str(request.base_url).rstrip("/")):
            return JSONResponse({"detail":"Cross-origin requests are not allowed."}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def require_user(request: Request):
    user = storage.session_user(request.cookies.get("cadence_session"))
    if not user:
        raise HTTPException(401, "Please sign in to view your conversations.")
    return user


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)


auth_attempts = {}
auth_lock = threading.Lock()


def check_attempts(request):
    key = request.client.host if request.client else "local"
    now = time.monotonic()
    with auth_lock:
        for host in list(auth_attempts):
            auth_attempts[host] = [t for t in auth_attempts[host] if t > now-900]
            if not auth_attempts[host]:
                del auth_attempts[host]
        attempts = auth_attempts.setdefault(key, [])
        if len(attempts) >= 20:
            raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
        attempts.append(now)


def login_response(response, request, user):
    response.set_cookie("cadence_session", storage.session(user['id']), httponly=True,
                        samesite="strict", secure=request.url.scheme == "https", max_age=604800)
    return user


@app.post("/api/auth/register", status_code=201)
def register(body: Credentials, request: Request, response: Response):
    check_attempts(request)
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(400, "Enter a valid email address.")
    try:
        user = storage.register(email, body.password)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This email is already registered. Please sign in.")
    return login_response(response, request, user)


@app.post("/api/auth/login")
def login(body: Credentials, request: Request, response: Response):
    check_attempts(request)
    user = storage.authenticate(body.email.strip().lower(), body.password)
    if not user:
        raise HTTPException(401, "Email or password is incorrect.")
    return login_response(response, request, user)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    storage.logout(request.cookies.get("cadence_session", ""))
    response.delete_cookie("cadence_session")
    return {"ok":True}


@app.get("/api/auth/me")
def me(user=Depends(require_user)):
    return user

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
        storage.save(jobs[job_id], jobs[job_id]["owner"])


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
def create(body: Submission, background: BackgroundTasks, user=Depends(require_user)):
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
        jobs[job_id] = {"id": job_id, "url": url, "status": "queued", "owner": user["id"],
                        "title": "YouTube conversation", "names": {}}
        storage.save(jobs[job_id], user["id"])
    background.add_task(transcribe, job_id, url, key)
    return {"id": job_id}


@app.get("/api/transcripts")
def history(user=Depends(require_user)):
    return storage.history(user["id"])


@app.get("/api/transcripts/{job_id}")
def get_job(job_id: str, user=Depends(require_user)):
    data = storage.get(job_id, user["id"])
    if not data:
        raise HTTPException(404, "Conversation not found.")
    return {k:v for k,v in data.items() if k != "owner"}


class Changes(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    names: dict[str, str] = Field(default_factory=dict, max_length=100)
    url: str = Field(default="", max_length=2048)


@app.patch("/api/transcripts/{job_id}")
def edit_job(job_id: str, body: Changes, user=Depends(require_user)):
    with lock:
        data = storage.get(job_id, user["id"])
        if not data:
            raise HTTPException(404, "Conversation not found.")
        if data['status'] != 'completed':
            raise HTTPException(409, "Wait for transcription to finish before editing.")
        speakers = {u['speaker'] for u in data.get('utterances', [])}
        if any(key not in speakers or len(value)>80 for key,value in body.names.items()) or not body.title.strip():
            raise HTTPException(400, "Use a title and speaker names of at most 80 characters.")
        try:
            url = youtube_url(body.url) if body.url else ""
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        data.update(title=body.title.strip(), names=body.names, url=url)
        storage.save(data, user['id'])
        if job_id in jobs:
            jobs[job_id] = data
    return {"ok":True}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="web")
