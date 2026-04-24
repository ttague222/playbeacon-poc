from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_pinecone import router
from app.api.routes_crawler import router as crawler_router
from app.api.scheduler import scheduler
from app.db.firebase import initialize_firebase
from app.config import settings
import logging
import asyncio
from datetime import timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PlayBeacon API (Pinecone)",
    description="AI-powered game discovery for Roblox using Firebase Firestore + Pinecone",
    version="3.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")
app.include_router(crawler_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize Firebase on startup"""
    logger.info("Initializing Firebase...")
    try:
        initialize_firebase()
        logger.info("Firebase initialized successfully")
        # Start background queue worker (hourly)
        asyncio.create_task(scheduler.run_hourly_queue_worker())
        # Schedule daily keyword/sort/graph crawls (using defaults)
        asyncio.create_task(scheduler.run_daily_keyword_crawl(
            keywords=["horror", "simulator", "tycoon", "anime", "roleplay", "pet", "zombie", "adventure"],
            limit_per_keyword=20,
            priority=6
        ))
        asyncio.create_task(scheduler.run_daily_sorts_crawl(
            sorts=["popular", "top_rated", "recommended", "up_and_coming", "hidden_gems"],
            limit=50,
            priority=6
        ))
        # Schedule daily graph crawl using a small seed set (can be expanded)
        asyncio.create_task(scheduler.run_daily_graph_crawl(
            seed_ids=[1818, 920587237],  # example universeIds
            priority=6
        ))
        # Daily embedding sweep and thumbnail fix
        asyncio.create_task(scheduler.run_daily_embed_sweep(limit=200))
        asyncio.create_task(scheduler.run_daily_thumbnail_fix(limit=100))
        asyncio.create_task(scheduler.run_weekly_deep_crawl(
            keywords=[
                "pet simulator", "defense", "tower", "military", "racing", "parkour",
                "fighting", "ninja", "pirate", "music", "sandbox", "builder"
            ],
            limit_per_keyword=50,
            priority=5
        ))
    except Exception as e:
        logger.error(f"Error initializing Firebase: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PlayBeacon API (Pinecone)",
        "version": "3.0.0",
        "database": "Firebase Firestore",
        "vector_db": "Pinecone",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_pinecone:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )
