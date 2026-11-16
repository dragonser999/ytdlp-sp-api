import re
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from curl_cffi.requests import AsyncSession

app = FastAPI(title="Spotify Full Song & Playlist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MF_URL = "https://musicfab.io"
MF_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": MF_URL,
    "Referer": f"{MF_URL}/",
}

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


async def get_musicfab_data(url: str):
    async with AsyncSession(impersonate="chrome", timeout=35.0) as s:
        r = await s.post(f"{MF_URL}/api/spotify", json={"url": url}, headers=MF_HEADERS)
        if r.status_code != 200:
            return None, f"Upstream HTTP {r.status_code}"
        return r.json().get("data", {}), None


async def resolve_full_track(track_url: str):
    enc = quote(track_url, safe="")
    async with AsyncSession(impersonate="chrome", timeout=45.0) as s:
        # 1. Nexray API
        try:
            r = await s.get(f"https://api.nexray.eu.cc/downloader/spotify?url={enc}", headers=WEB_HEADERS)
            if r.status_code == 200:
                j = r.json()
                res = j.get("result") or {}
                if j.get("status") and str(res.get("url", "")).startswith("http"):
                    return {
                        "title": res.get("title"),
                        "artist": res.get("artist"),
                        "thumbnail": res.get("thumbnail") or res.get("cover"),
                        "downloadUrl": res["url"],
                        "sourceApi": "Nexray",
                    }, None
        except Exception:
            pass

        # 2. NexaDev API
        try:
            r = await s.get(f"https://api.nexadev.my.id/api/spotify?url={enc}", headers=WEB_HEADERS)
            if r.status_code == 200:
                j = r.json()
                d = j.get("data") or {}
                if j.get("status") and str(d.get("url", "")).startswith("http"):
                    return {
                        "title": d.get("title"),
                        "artist": d.get("artist"),
                        "thumbnail": d.get("thumbnail"),
                        "downloadUrl": d["url"],
                        "sourceApi": "NexaDev",
                    }, None
        except Exception:
            pass

        # 3. Zelora API
        try:
            r = await s.get(f"https://zelora-api.vercel.app/download/spotify?url={enc}", headers=WEB_HEADERS)
            if r.status_code == 200:
                j = r.json()
                res = j.get("result") or {}
                dls = res.get("downloads") or []
                if j.get("status") and dls and str(dls[0].get("url", "")).startswith("http"):
                    raw = res.get("title", "")
                    art, tit = raw.split(" - ", 1) if " - " in raw else ("Unknown Artist", raw)
                    return {
                        "title": tit.strip(),
                        "artist": art.strip(),
                        "thumbnail": res.get("thumbnail"),
                        "downloadUrl": dls[0]["url"],
                        "sourceApi": "Zelora",
                    }, None
        except Exception:
            pass

    return None, "All 3 APIs failed to resolve download link"


@app.get("/")
async def home():
    return {
        "status": True,
        "message": "Spotify Multi-API Service is Running",
        "endpoints": {
            "track_json": "/track?url=SPOTIFY_TRACK_URL",
            "direct_mp3": "/download?url=SPOTIFY_TRACK_URL",
            "playlist": "/playlist?url=SPOTIFY_PLAYLIST_URL",
        },
    }


@app.get("/track")
async def get_track_info(url: str = Query(..., description="Spotify Track URL")):
    match = re.search(r"(https?://open\.spotify\.com/track/[a-zA-Z0-9]+)", url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Spotify Track URL")

    clean_url = match.group(1)
    track_data, err = await resolve_full_track(clean_url)
    if err or not track_data:
        raise HTTPException(status_code=502, detail=err or "Failed to fetch track")

    # Fallback to musicfab for high-res cover if missing
    if not track_data.get("thumbnail"):
        mf, _ = await get_musicfab_data(clean_url)
        if mf and "track" in mf:
            track_data["thumbnail"] = mf["track"].get("cover")

    return {
        "status": True,
        "sourceUrl": clean_url,
        "result": track_data,
    }


@app.get("/download")
async def download_track_mp3(url: str = Query(..., description="Spotify Track URL")):
    match = re.search(r"(https?://open\.spotify\.com/track/[a-zA-Z0-9]+)", url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Spotify Track URL")

    clean_url = match.group(1)
    track_data, err = await resolve_full_track(clean_url)
    if err or not track_data:
        raise HTTPException(status_code=502, detail=err or "Failed to resolve track")

    title = track_data.get("title") or "Song"
    artist = track_data.get("artist") or "Artist"
    safe_filename = re.sub(r'[\\/*?:"<>|]', "_", f"{artist} - {title}.mp3")

    async with AsyncSession(impersonate="chrome", timeout=90.0) as s:
        res = await s.get(track_data["downloadUrl"], headers=WEB_HEADERS, allow_redirects=True)
        if res.status_code != 200 or not res.content:
            raise HTTPException(status_code=502, detail="Failed to download MP3 stream")

        return StreamingResponse(
            iter([res.content]),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="{quote(safe_filename)}"'
            },
        )


@app.get("/playlist")
async def get_playlist_info(request: Request, url: str = Query(..., description="Spotify Playlist URL")):
    match = re.search(r"(https?://open\.spotify\.com/playlist/[a-zA-Z0-9]+)", url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Spotify Playlist URL")

    clean_url = match.group(1)
    data, err = await get_musicfab_data(clean_url)
    if err or not data or "collection" not in data:
        raise HTTPException(status_code=502, detail=err or "Failed to load playlist")

    col = data["collection"]
    raw_tracks = col.get("tracks", [])
    base_api = str(request.base_url).rstrip("/")

    formatted_tracks = []
    for idx, t in enumerate(raw_tracks, start=1):
        src = t.get("sourceUrl")
        if not src:
            continue
        enc_src = quote(src, safe="")
        formatted_tracks.append({
            "index": idx,
            "id": t.get("id"),
            "title": t.get("title"),
            "artist": t.get("artist"),
            "duration": t.get("duration"),
            "cover": t.get("cover"),
            "sourceUrl": src,
            "trackApiUrl": f"{base_api}/track?url={enc_src}",
            "directMp3Url": f"{base_api}/download?url={enc_src}",
        })

    return {
        "status": True,
        "type": col.get("type", "playlist"),
        "title": col.get("title"),
        "cover": col.get("cover"),
        "total": len(formatted_tracks),
        "tracks": formatted_tracks,
    }
