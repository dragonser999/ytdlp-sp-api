from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from curl_cffi.requests import AsyncSession
import zipfile
import io
from urllib.parse import quote

app = FastAPI()

BASE_URL = "https://musicfab.io"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}

async def fetch_single_audio(session: AsyncSession, track_url: str):
    res = await session.post(f"{BASE_URL}/api/spotify", json={"url": track_url}, headers=HEADERS)
    if res.status_code != 200:
        return None, None
    track = res.json().get("data", {}).get("track")
    if not track or not track.get("downloadUrl"):
        return None, None

    filename = f"{track['artist']} - {track['title']}.mp3".replace("/", "_")
    audio_url = f"{BASE_URL}{track['downloadUrl']}?filename={quote(filename)}"
    audio_res = await session.get(audio_url, headers={"Referer": f"{BASE_URL}/"})

    if audio_res.status_code == 200:
        return filename, audio_res.content
    return None, None

@app.get("/info")
async def get_spotify_info(url: str = Query(...)):
    async with AsyncSession(impersonate="chrome", timeout=30.0) as session:
        res = await session.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Blocked/Failed ({res.status_code}): {res.text[:200]}"
            )
        return res.json().get("data", {})

@app.get("/download")
async def download_spotify(url: str = Query(...)):
    async with AsyncSession(impersonate="chrome", timeout=60.0) as session:
        res = await session.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Blocked/Failed ({res.status_code}): {res.text[:200]}"
            )

        data = res.json().get("data", {})

        # 1. Single Track
        if "track" in data:
            filename, content = await fetch_single_audio(session, url)
            if not content:
                raise HTTPException(status_code=502, detail="Failed to download audio file")
            return StreamingResponse(
                iter([content]),
                media_type="audio/mpeg",
                headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'}
            )

        # 2. Playlist / Album (ZIP)
        if "collection" in data:
            tracks = data["collection"].get("tracks", [])
            if not tracks:
                raise HTTPException(status_code=404, detail="No tracks found")

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for t in tracks:
                    src = t.get("sourceUrl")
                    if src:
                        fname, content = await fetch_single_audio(session, src)
                        if fname and content:
                            zip_file.writestr(fname, content)

            zip_buffer.seek(0)
            zip_name = f"{data['collection'].get('title', 'playlist')}.zip".replace("/", "_")
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{quote(zip_name)}"'}
            )

        raise HTTPException(status_code=400, detail="Invalid Spotify URL")
