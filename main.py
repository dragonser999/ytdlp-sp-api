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

async def get_track_download_data(session: AsyncSession, raw_track: dict, semaphore: asyncio.Semaphore):
    track_url = raw_track.get("sourceUrl")
    async with semaphore:
        await asyncio.sleep(0.5)  # Rate limit ഒഴിവാക്കാൻ ചെറിയ ഇടവേള
        try:
            res = await session.post(f"{BASE_URL}/api/spotify", json={"url": track_url}, headers=HEADERS)
            if res.status_code != 200:
                return {
                    "id": raw_track.get("id"),
                    "title": raw_track.get("title"),
                    "artist": raw_track.get("artist"),
                    "sourceUrl": track_url,
                    "downloadUrl": None,
                    "error": f"HTTP {res.status_code}"
                }

            track = res.json().get("data", {}).get("track")
            if not track or not track.get("downloadUrl"):
                return {
                    "id": raw_track.get("id"),
                    "title": raw_track.get("title"),
                    "artist": raw_track.get("artist"),
                    "sourceUrl": track_url,
                    "downloadUrl": None,
                    "error": "No downloadUrl in response"
                }

            filename = f"{track['artist']} - {track['title']}.mp3".replace("/", "_")
            full_download_url = f"{BASE_URL}{track['downloadUrl']}?filename={quote(filename)}"

            return {
                "id": track.get("id"),
                "title": track.get("title"),
                "artist": track.get("artist"),
                "duration": track.get("duration"),
                "cover": track.get("cover"),
                "sourceUrl": track_url,
                "downloadUrl": full_download_url
            }
        except Exception as e:
            return {
                "id": raw_track.get("id"),
                "title": raw_track.get("title"),
                "sourceUrl": track_url,
                "downloadUrl": None,
                "error": str(e)
            }

@app.get("/playlist")
@app.get("/download")
async def get_playlist_links(
    url: str = Query(..., description="Spotify Playlist or Track URL"),
    limit: int = Query(10, description="ഒരു തവണ ഫെച്ച് ചെയ്യേണ്ട പാട്ടുകളുടെ എണ്ണം (Max 30)")
):
    async with AsyncSession(impersonate="chrome", timeout=90.0) as session:
        res = await session.post(f"{BASE_URL}/api/spotify", json={"url": url}, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Blocked/Failed ({res.status_code}): {res.text[:200]}"
            )

        data = res.json().get("data", {})

        # 1. Single Track
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

        # 2. Playlist / Album
        if "collection" in data:
            collection = data["collection"]
            raw_tracks = collection.get("tracks", [])[:limit]
            if not raw_tracks:
                raise HTTPException(status_code=404, detail="No tracks found in playlist")

            semaphore = asyncio.Semaphore(2)  # ഒരേസമയം 2 റിക്വസ്റ്റുകൾ മാത്രം
            tasks = [
                get_track_download_data(session, t, semaphore)
                for t in raw_tracks if t.get("sourceUrl")
            ]
            tracks_result = await asyncio.gather(*tasks)

            return {
                "type": collection.get("type", "playlist"),
                "title": collection.get("title"),
                "cover": collection.get("cover"),
                "total": len(tracks_result),
                "tracks": tracks_result
            }

        raise HTTPException(status_code=400, detail="Invalid Spotify URL")
