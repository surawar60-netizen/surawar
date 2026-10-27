import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="LinkMedia Converter API", version="0.1.0")
allowed = os.getenv("FRONTEND_ORIGIN", "https://linkmedia-converter.higgsfield.app")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in allowed.split(",") if x.strip()], allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])
OUT = Path(os.getenv("OUTPUT_DIR", "/tmp/linkmedia"))
OUT.mkdir(parents=True, exist_ok=True)
MAX_AGE_SECONDS = int(os.getenv("FILE_TTL_SECONDS", "1800"))

class ConvertRequest(BaseModel):
    url: HttpUrl
    format: str

def clean_old_files():
    cutoff = time.time() - MAX_AGE_SECONDS
    for p in OUT.iterdir():
        try:
            if p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
        except OSError:
            pass

def validate_url(url: str):
    host = (urlparse(url).hostname or "").lower()
    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}:
        raise HTTPException(400, "YouTube URL만 지원합니다.")
    if not url.startswith(("https://", "http://")):
        raise HTTPException(400, "유효한 URL이 아닙니다.")

@app.get("/health")
def health():
    return {"ok": True, "service": "linkmedia-converter"}

@app.post("/api/convert")
def convert(req: ConvertRequest):
    fmt = req.format.lower().strip()
    if fmt not in {"mp3", "wav", "mp4"}:
        raise HTTPException(400, "지원 형식은 MP3, WAV, MP4입니다.")
    url = str(req.url)
    validate_url(url)
    clean_old_files()
    work = OUT / next(tempfile._get_candidate_names())
    work.mkdir(parents=True, exist_ok=False)
    template = str(work / "source.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--restrict-filenames", "-o", template]
    if fmt == "mp4":
        cmd += ["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4"]
    else:
        cmd += ["-f", "bestaudio/best"]
    cmd += [url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "yt-dlp failed")[-1000:])
        sources = [p for p in work.iterdir() if p.is_file()]
        if not sources:
            raise RuntimeError("다운로드 파일을 찾을 수 없습니다.")
        source = max(sources, key=lambda p: p.stat().st_size)
        output = work / f"converted.{fmt}"
        if fmt == "mp4":
            if source.suffix.lower() == ".mp4":
                output = source
            else:
                subprocess.run(["ffmpeg", "-y", "-i", str(source), "-c", "copy", str(output)], check=True, capture_output=True, timeout=240)
        else:
            codec = ["-vn", "-codec:a", "libmp3lame", "-q:a", "2"] if fmt == "mp3" else ["-vn", "-codec:a", "pcm_s16le"]
            subprocess.run(["ffmpeg", "-y", "-i", str(source), *codec, str(output)], check=True, capture_output=True, timeout=240)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("변환 결과 파일이 비어 있습니다.")
        media_type = {"mp3": "audio/mpeg", "wav": "audio/wav", "mp4": "video/mp4"}[fmt]
        return FileResponse(path=output, media_type=media_type, filename=f"linkmedia.{fmt}")
    except subprocess.TimeoutExpired:
        shutil.rmtree(work, ignore_errors=True)
        raise HTTPException(504, "변환 시간이 초과됐습니다. 더 짧은 영상으로 다시 시도하세요.")
    except HTTPException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(work, ignore_errors=True)
        detail = str(e)
        if "Sign in" in detail or "bot" in detail.lower():
            detail = "YouTube가 이 요청을 차단했습니다. 로그인 우회나 보호 회피는 지원하지 않습니다."
        raise HTTPException(502, f"변환 실패: {detail[:500]}")
