from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_firestore import router
from app.db.firebase import initialize_firebase
from app.config import settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PlayBeacon API (Firestore)",
    description="AI-powered game discovery for Roblox using Firebase Firestore",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize Firebase on startup"""
    logger.info("Initializing Firebase...")
    try:
        initialize_firebase()
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Firebase: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PlayBeacon API (Firestore)",
        "version": "2.0.0",
        "database": "Firebase Firestore",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_firestore:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )
