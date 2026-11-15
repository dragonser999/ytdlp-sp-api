from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx
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

# 1. Track / Playlist വിവരങ്ങളും Direct Download URL-ഉം ലഭിക്കാൻ
@app.get("/info")
async def get_spotify_info(url: str = Query(..., description="Spotify Track or Playlist URL")):
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Failed to fetch from upstream")
        
        data = res.json().get("data", {})
        
        # Single track ആണെങ്കിൽ full download URL കൂടെ ചേർക്കുന്നു
        if "track" in data and data["track"].get("downloadUrl"):
            rel_path = data["track"]["downloadUrl"]
            filename = f"{data['track']['artist']} - {data['track']['title']}.mp3"
            data["track"]["fullAudioUrl"] = f"{BASE_URL}{rel_path}?filename={quote(filename)}"
            
        return data

# 2. നേരിട്ട് MP3 ഫയൽ സ്ട്രീം / ഡൗൺലോഡ് ചെയ്യാൻ
@app.get("/download")
async def download_spotify_track(url: str = Query(..., description="Spotify Track URL")):
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Upstream API error")
        
        track = res.json().get("data", {}).get("track")
        if not track or not track.get("downloadUrl"):
            raise HTTPException(status_code=400, detail="Only single track URLs are supported for direct download")
        
        filename = f"{track['artist']} - {track['title']}.mp3"
        audio_url = f"{BASE_URL}{track['downloadUrl']}?filename={quote(filename)}"
        
        audio_res = await client.get(audio_url, headers={"User-Agent": HEADERS["User-Agent"], "Referer": f"{BASE_URL}/"})
        if audio_res.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch audio stream")
            
        return StreamingResponse(
            iter([audio_res.content]),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'}
        )
