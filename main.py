from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx
import asyncio
import zipfile
import io
from urllib.parse import quote

app = FastAPI()

BASE_URL = "https://musicfab.io"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}

async def fetch_single_audio(client: httpx.AsyncClient, track_url: str):
    res = await client.post(f"{BASE_URL}/api/spotify", json={"url": track_url}, headers=HEADERS)
    if res.status_code != 200:
        return None, None
    track = res.json().get("data", {}).get("track")
    if not track or not track.get("downloadUrl"):
        return None, None
    
    filename = f"{track['artist']} - {track['title']}.mp3".replace("/", "_")
    audio_url = f"{BASE_URL}{track['downloadUrl']}?filename={quote(filename)}"
    audio_res = await client.get(audio_url, headers={"User-Agent": HEADERS["User-Agent"], "Referer": f"{BASE_URL}/"})
    
    if audio_res.status_code == 200:
        return filename, audio_res.content
    return None, None

@app.get("/info")
async def get_spotify_info(url: str = Query(...)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Upstream error")
        return res.json().get("data", {})

@app.get("/download")
async def download_spotify(url: str = Query(...)):
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Upstream error")
        
        data = res.json().get("data", {})

        # 1. Single Track ആണെങ്കിൽ നേരിട്ട് MP3 നൽകുന്നു
        if "track" in data:
            filename, content = await fetch_single_audio(client, url)
            if not content:
                raise HTTPException(status_code=502, detail="Failed to download track")
            return StreamingResponse(
                iter([content]),
                media_type="audio/mpeg",
                headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'}
            )

        # 2. Playlist / Album ആണെങ്കിൽ ZIP ഫയലായി നൽകുന്നു
        if "collection" in data:
            collection = data["collection"]
            tracks = collection.get("tracks", [])
            if not tracks:
                raise HTTPException(status_code=404, detail="No tracks found")

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for t in tracks:
                    src = t.get("sourceUrl")
                    if src:
                        fname, content = await fetch_single_audio(client, src)
                        if fname and content:
                            zip_file.writestr(fname, content)

            zip_buffer.seek(0)
            zip_name = f"{collection.get('title', 'playlist')}.zip".replace("/", "_")
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{quote(zip_name)}"'}
            )

        raise HTTPException(status_code=400, detail="Invalid Spotify URL")
