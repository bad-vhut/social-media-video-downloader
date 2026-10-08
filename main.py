import os
import uuid
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
from dotenv import load_dotenv

# =========================
# Load Environment
# =========================

load_dotenv()

PORT = int(
    os.getenv(
        "SERVER_PORT",
        os.getenv("PORT", "8000")
    )
)

ALLOWED_ORIGIN = os.getenv(
    "ALLOWED_ORIGIN",
    "*"
)


# =========================
# FastAPI
# =========================

app = FastAPI(
    title="Social Media Video Downloader API",
    version="1.0.0"
)


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOWED_ORIGIN == "*" else [ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# Home
# =========================

@app.get("/")
async def root():

    return {
        "success": True,
        "message": "Social Media Video Downloader API is online.",
        "version": "1.0.0",
        "endpoints": {
            "download": "/download",
            "health": "/health",
            "docs": "/docs"
        }
    }


# =========================
# Health Check
# =========================

@app.get("/health")
async def health():

    return {
        "status": "online",
        "service": "downloader-api"
    }


# =========================
# Download
# =========================

@app.get("/download")
async def download_video(
    url: str = Query(...),
    format: str = Query("best[height<=720]")
):

    if not url.startswith(("http://", "https://")):

        raise HTTPException(
            status_code=400,
            detail="Invalid video URL."
        )

    uid = uuid.uuid4().hex[:12]

    output_template = f"/tmp/{uid}.%(ext)s"

    try:

        # =========================
        # Extract Metadata
        # =========================

        info_options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(info_options) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        title = info.get(
            "title",
            "video"
        )

        # Safe filename
        title = (
            title
            .replace("/", "-")
            .replace("\\", "-")
            .replace('"', "'")
        )

        filename = f"{title}.mp4"


        # =========================
        # Download Settings
        # =========================

        ydl_opts = {

            "format": format,

            "outtmpl": output_template,

            "quiet": True,

            "no_warnings": True,

            "noplaylist": True,

            "merge_output_format": "mp4",

            "retries": 2,

            "fragment_retries": 2,

            "concurrent_fragment_downloads": 2,

            "socket_timeout": 20
        }


        # =========================
        # Download
        # =========================

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            ydl.download([url])


        # =========================
        # Find Downloaded File
        # =========================

        actual_file_path = None

        for file in os.listdir("/tmp"):

            if file.startswith(uid):

                actual_file_path = os.path.join(
                    "/tmp",
                    file
                )

                break


        if (
            not actual_file_path
            or not os.path.exists(actual_file_path)
        ):

            raise HTTPException(
                status_code=500,
                detail="Download failed or file not found."
            )


        # =========================
        # Stream File
        # =========================

        def iterfile():

            try:

                with open(
                    actual_file_path,
                    "rb"
                ) as file:

                    while True:

                        chunk = file.read(
                            1024 * 1024
                        )

                        if not chunk:
                            break

                        yield chunk

            finally:

                try:

                    if os.path.exists(
                        actual_file_path
                    ):
                        os.remove(
                            actual_file_path
                        )

                except Exception:
                    pass


        return StreamingResponse(

            iterfile(),

            media_type="application/octet-stream",

            headers={
                "Content-Disposition":
                    f'attachment; filename="{filename}"'
            }
        )


    except HTTPException:

        raise


    except Exception as e:

        # Cleanup temporary file

        try:

            for file in os.listdir("/tmp"):

                if file.startswith(uid):

                    path = os.path.join(
                        "/tmp",
                        file
                    )

                    if os.path.isfile(path):
                        os.remove(path)

        except Exception:
            pass


        raise HTTPException(
            status_code=500,
            detail=f"Error during download: {str(e)}"
        )


# =========================
# Run Server
# =========================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT
    )
