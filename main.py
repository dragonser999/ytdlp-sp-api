from fastapi import FastAPI, HTTPException
import subprocess
import os
import glob
from fastapi.responses import FileResponse

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Spotify Downloader API is running smoothly!"}

@app.get("/download")
def download_audio(url: str):
    try:
        # കറന്റ് ഫോൾഡറിൽ തന്നെ ഡൗൺലോഡ് ചെയ്യുന്നു
        cmd = ["spotdl", url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"error": "Download failed", "details": result.stderr}
        
        # ഡൗൺലോഡ് ചെയ്ത ഓഡിയോ ഫയലുകൾ (mp3/m4a) തപ്പുന്നു
        files = glob.glob("*.mp3") + glob.glob("*.m4a")
        if not files:
            raise HTTPException(status_code=404, detail="No files found after download")
        
        # ഏറ്റവും പുതിയ ഫയൽ എടുക്കുന്നു
        latest_file = max(files, key=os.path.getctime)
        file_path = os.path.abspath(latest_file)
        
        # ഫയൽ നേരിട്ട് യൂസറുടെ ബ്രൗസറിലേക്ക് ഡൗൺലോഡ് ആയി പോരാൻ
        return FileResponse(file_path, media_type="audio/mpeg", filename=os.path.basename(file_path))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
