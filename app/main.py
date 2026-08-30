from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings  # noqa: F401 -- imported to fail fast on missing env vars at startup
from app.routes.chat import router as chat_router

app = FastAPI(title="Skylark BI Agent")
app.include_router(chat_router)

_static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
