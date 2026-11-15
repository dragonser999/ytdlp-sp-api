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
        # Downloads folder ഉണ്ടാക്കുന്നു
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)
        
        # spotdl കമാൻഡ് റൺ ചെയ്യുന്നു
        cmd = ["spotdl", url, "--output", f"{output_dir}/{{title}}.{{ext}}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"error": "Download failed", "details": result.stderr}
        
        # ഡൗൺലോഡ് ചെയ്ത ഫയലുകൾ കണ്ടെത്തുന്നു
        files = glob.glob(f"{output_dir}/*")
        if not files:
            raise HTTPException(status_code=404, detail="No files found after download")
        
        # ഏറ്റവും ഒടുവിൽ ഡൗൺലോഡ് ചെയ്ത ഫയലിന്റെ പാസ് കൊടുക്കുന്നു
        latest_file = max(files, key=os.path.getctime)
        
        return {
            "success": True,
            "message": "Downloaded successfully!",
            "file_name": os.path.basename(latest_file),
            "file_path": latest_file
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
