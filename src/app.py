from fastapi import FastAPI, HTTPException
import logging
import os
import platform
import uvicorn

# Import from scrapper
from scrapper import lens_service, LensRequest, LensResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Google Lens API", version="1.0.0")


@app.post("/search", response_model=LensResponse)
async def search_lens(request: LensRequest):
    """Search Google Lens with image URL"""
    try:
        logger.info(f"Received search request for: {request.image_url}")
        result = lens_service.search_image(
            str(request.image_url), request.search_type)
        return result
    except Exception as e:
        logger.error(f"API error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint"""
    try:
        return {
            "message": "Welcome to Google Lens API",
            "status": "healthy",
            "service": "Google Lens API",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        chrome_status = "installed" if lens_service.chrome_installed else "not installed"
        system_info = lens_service.system_info

        return {
            "status": "healthy",
            "service": "Google Lens API",
            "chrome_status": chrome_status,
            "system": system_info['system'],
            "architecture": system_info['machine'],
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/docs")
async def docs():
    """API Documentation"""
    try:
        return {
            "message": "Welcome to Google Lens API",
            "status": "healthy",
            "service": "Google Lens API",
            "apis": [
                {
                    "name": "Search Google Lens",
                    "url": "/search",
                    "method": "POST",
                    "parameters": {
                        "image_url": "Image URL",
                        "search_type": "exact_matches, visual_matches (default all)"
                    },
                    "description": "Search Google Lens with image URL"
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/system-info")
async def get_system_info():
    """Get system information"""
    return {
        "system_info": lens_service.system_info,
        "chrome_installed": lens_service.chrome_installed,
    }

if __name__ == "__main__":
    # Get port from environment variable or default to 8000
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"Starting FastAPI server on {host}:{port}")
    print(f"System: {platform.system()} {platform.machine()}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"Health Check: http://{host}:{port}/health")

    uvicorn.run("app:app", host=host, port=port, reload=True)
