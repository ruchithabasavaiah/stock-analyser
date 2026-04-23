from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.db import create_db
from api.routes.analyze import router as analyze_router
from api.routes.results import router as results_router

INDEX_HTML = Path(__file__).parent.parent / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/api")
app.include_router(results_router, prefix="/api")


@app.get("/")
async def root():
    return FileResponse(str(INDEX_HTML))


@app.get("/health")
async def health():
    return {"status": "ok"}
