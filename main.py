from fastapi import FastAPI, HTTPException, Query
from curl_cffi.requests import AsyncSession
import asyncio
from urllib.parse import quote

app = FastAPI()

BASE_URL = "https://musicfab.io"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}

async def get_track_download_data(session: AsyncSession, track_url: str, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            res = await session.post(f"{BASE_URL}/api/spotify", json={"url": track_url}, headers=HEADERS)
            if res.status_code != 200:
                return None

            track = res.json().get("data", {}).get("track")
            if not track or not track.get("downloadUrl"):
                return None

            filename = f"{track['artist']} - {track['title']}.mp3".replace("/", "_")
            full_download_url = f"{BASE_URL}{track['downloadUrl']}?filename={quote(filename)}"

            return {
                "id": track.get("id"),
                "title": track.get("title"),
                "artist": track.get("artist"),
                "duration": track.get("duration"),
                "cover": track.get("cover"),
                "sourceUrl": track.get("sourceUrl"),
                "downloadUrl": full_download_url
            }
        except Exception:
            return None

@app.get("/playlist")
@app.get("/download")
async def get_playlist_links(url: str = Query(..., description="Spotify Playlist or Track URL")):
    async with AsyncSession(impersonate="chrome", timeout=60.0) as session:
        res = await session.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Blocked/Failed ({res.status_code}): {res.text[:200]}"
            )

        data = res.json().get("data", {})

        # 1. Single Track ആണെങ്കിൽ അതിന്റെ downloadUrl നൽകുന്നു
        if "track" in data:
            track = data["track"]
            filename = f"{track['artist']} - {track['title']}.mp3".replace("/", "_")
            full_download_url = f"{BASE_URL}{track['downloadUrl']}?filename={quote(filename)}"
            return {
                "type": "track",
                "title": track.get("title"),
                "artist": track.get("artist"),
                "cover": track.get("cover"),
                "downloadUrl": full_download_url
            }

        # 2. Playlist / Album ആണെങ്കിൽ എല്ലാ പാട്ടുകളുടെയും downloadUrl ലിസ്റ്റ് ആയി നൽകുന്നു
        if "collection" in data:
            collection = data["collection"]
            raw_tracks = collection.get("tracks", [])
            if not raw_tracks:
                raise HTTPException(status_code=404, detail="No tracks found in playlist")

            semaphore = asyncio.Semaphore(5)  # ഒരേസമയം 5 റിക്വസ്റ്റുകൾ വീതം
            tasks = [
                get_track_download_data(session, t["sourceUrl"], semaphore)
                for t in raw_tracks if t.get("sourceUrl")
            ]
            results = await asyncio.gather(*tasks)
            valid_tracks = [item for item in results if item is not None]

            return {
                "type": collection.get("type", "playlist"),
                "title": collection.get("title"),
                "cover": collection.get("cover"),
                "total": len(valid_tracks),
                "tracks": valid_tracks
            }

        raise HTTPException(status_code=400, detail="Invalid Spotify URL")
