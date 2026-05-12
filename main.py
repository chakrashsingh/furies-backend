from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.models import user, link, influencer, brand, campaign
from app.routers.auth import router as auth_router
from app.routers.links import router as links_router, redirect_router
from app.routers.influencer import router as influencer_router
from app.routers.brand import router as brand_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅  Furies is live!")
    yield
    await engine.dispose()

app = FastAPI(title="Furies", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(redirect_router)
app.include_router(auth_router,       prefix="/api/v1")
app.include_router(links_router,      prefix="/api/v1")
app.include_router(influencer_router, prefix="/api/v1")
app.include_router(brand_router,      prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok", "app": "Furies"}
