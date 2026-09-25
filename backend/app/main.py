from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import area, contour
from app.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contour.router)
app.include_router(area.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name}
