from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.api.schemas import (
    GameResponse,
    QueueRequest,
    QueueResponse,
    FeedbackRequest,
    FeedbackResponse,
    CrawlRequest,
    CrawlResponse,
    GenerateEmbeddingsResponse
)
from app.models.models import Game
from app.services.roblox_crawler import RobloxCrawler
from app.services.embedding_service import EmbeddingService
from app.services.recommendation_service import RecommendationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/games", response_model=List[GameResponse])
async def get_games(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get list of games (for debugging/testing)"""
    games = db.query(Game).offset(offset).limit(limit).all()
    return games


@router.get("/games/{universe_id}", response_model=GameResponse)
async def get_game(universe_id: str, db: Session = Depends(get_db)):
    """Get a specific game by universe ID"""
    game = db.query(Game).filter(Game.universe_id == universe_id).first()

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return game


@router.post("/queue", response_model=QueueResponse)
async def get_queue(request: QueueRequest, db: Session = Depends(get_db)):
    """Get personalized game recommendations for a user"""
    try:
        rec_service = RecommendationService(db)
        recommendations = rec_service.get_recommendations(
            user_id=request.user_id,
            limit=request.limit
        )

        return QueueResponse(
            user_id=request.user_id,
            games=recommendations,
            count=len(recommendations)
        )

    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    """Submit user feedback on a game"""
    try:
        # Validate game exists
        game = db.query(Game).filter(Game.universe_id == request.universe_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        # Save feedback
        rec_service = RecommendationService(db)
        success = rec_service.save_feedback(
            user_id=request.user_id,
            universe_id=request.universe_id,
            feedback=request.feedback
        )

        if success:
            feedback_text = {1: "liked", 0: "skipped", -1: "disliked"}.get(request.feedback, "unknown")
            return FeedbackResponse(
                success=True,
                message=f"Feedback recorded: {feedback_text}"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save feedback")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl", response_model=CrawlResponse)
async def crawl_games(request: CrawlRequest, db: Session = Depends(get_db)):
    """Crawl Roblox games by keywords (manual trigger)"""
    try:
        crawler = RobloxCrawler(db)
        games_stored = await crawler.crawl_and_store_games(
            keywords=request.keywords,
            limit_per_keyword=request.limit_per_keyword
        )

        return CrawlResponse(
            success=True,
            games_stored=games_stored,
            message=f"Successfully crawled and stored {games_stored} games"
        )

    except Exception as e:
        logger.error(f"Error during crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(db: Session = Depends(get_db)):
    """Generate embeddings for games that don't have them"""
    try:
        embedding_service = EmbeddingService(db)
        count = embedding_service.update_all_missing_embeddings()

        return GenerateEmbeddingsResponse(
            success=True,
            embeddings_generated=count,
            message=f"Generated {count} embeddings"
        )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
