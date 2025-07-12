import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Literal, Optional
try:
    from .agent_browser import lens_search
except ImportError:
    from agent_browser import lens_search

app = FastAPI(title="Google Lens API", version="1.0.0")


class SearchRequest(BaseModel):
    image_url: HttpUrl
    search_type: Optional[Literal["visual_matches",
                                  "exact_matches", "all", "both"]] = "all"


@app.post("/search")
async def search_lens(request: SearchRequest):
    try:
        results = await lens_search(str(request.image_url), request.search_type or "all")
        return {"success": True, **results, "search_type": request.search_type or "all"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Google Lens API"}


@app.get("/")
async def root():
    return {"status": "healthy", "service": "Google Lens API"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8081))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
