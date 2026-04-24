from fastapi import APIRouter, HTTPException, Depends
from typing import List
from firebase_admin import firestore
from app.db.firebase import get_db, GAMES_COLLECTION, USER_PROFILES_COLLECTION
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
from app.api.auth import get_current_user_id
from app.models.firestore_models import Game
from app.services.roblox_crawler_firestore import RobloxCrawler
from app.services.embedding_service_firestore import EmbeddingService
from app.services.recommendation_service_firestore import RecommendationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/games", response_model=List[GameResponse])
async def get_games(limit: int = 50, offset: int = 0):
    """Get list of games (for debugging/testing)"""
    try:
        db = get_db()
        games_ref = db.collection(GAMES_COLLECTION)

        # Firestore doesn't have offset, so we'll get all and slice
        docs = games_ref.limit(limit + offset).stream()

        games = []
        for i, doc in enumerate(docs):
            if i < offset:
                continue
            game_data = doc.to_dict()
            games.append(game_data)

        return games
    except Exception as e:
        logger.error(f"Error getting games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{universe_id}", response_model=GameResponse)
async def get_game(universe_id: str):
    """Get a specific game by universe ID"""
    try:
        db = get_db()
        games_ref = db.collection(GAMES_COLLECTION)
        doc = games_ref.document(universe_id).get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Game not found")

        return doc.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting game: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue", response_model=QueueResponse)
async def get_queue(request: QueueRequest, user_id: str = Depends(get_current_user_id)):
    """Get personalized game recommendations for a user"""
    try:
        rec_service = RecommendationService()
        recommendations = rec_service.get_recommendations(
            user_id=user_id,
            limit=request.limit
        )

        return QueueResponse(
            user_id=user_id,
            games=recommendations,
            count=len(recommendations)
        )

    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest, user_id: str = Depends(get_current_user_id)):
    """Submit user feedback on a game"""
    try:
        # Validate game exists
        db = get_db()
        games_ref = db.collection(GAMES_COLLECTION)
        game_doc = games_ref.document(request.universe_id).get()

        if not game_doc.exists:
            raise HTTPException(status_code=404, detail="Game not found")

        # Save feedback
        rec_service = RecommendationService()
        success = rec_service.save_feedback(
            user_id=user_id,
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
async def crawl_games(request: CrawlRequest):
    """Crawl Roblox games by keywords (manual trigger)"""
    try:
        crawler = RobloxCrawler()
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
async def generate_embeddings():
    """Generate embeddings for games that don't have them"""
    try:
        embedding_service = EmbeddingService()
        count = embedding_service.update_all_missing_embeddings()

        return GenerateEmbeddingsResponse(
            success=True,
            embeddings_generated=count,
            message=f"Generated {count} embeddings"
        )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/reset-profile")
async def reset_profile(user_id: str = Depends(get_current_user_id)):
    """Clear user feedback and reset profile embedding/counts"""
    try:
        db = get_db()
        user_ref = db.collection(USER_PROFILES_COLLECTION).document(user_id)

        # Get user document
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User profile not found")

        # Clear feedback subcollection
        feedback_ref = user_ref.collection('feedback')
        feedback_docs = feedback_ref.stream()

        batch = db.batch()
        for doc in feedback_docs:
            batch.delete(doc.reference)
        batch.commit()

        # Reset profile data
        user_ref.update({
            'profile_embedding': None,
            'liked_count': 0,
            'disliked_count': 0,
            'updated_at': firestore.SERVER_TIMESTAMP
        })

        return {
            "success": True,
            "message": "Profile reset successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting profile for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/status")
async def get_admin_status():
    """Get admin status - game counts and system health"""
    try:
        db = get_db()
        games_ref = db.collection(GAMES_COLLECTION)

        # Count total games
        games_docs = games_ref.stream()
        total_games = sum(1 for _ in games_docs)

        # Count games with embeddings
        games_with_embeddings_docs = games_ref.where("embedding", "!=", None).stream()
        games_with_embeddings = sum(1 for _ in games_with_embeddings_docs)

        return {
            "status": "healthy",
            "total_games": total_games,
            "games_with_embeddings": games_with_embeddings,
            "database": "Firestore"
        }
    except Exception as e:
        logger.error(f"Error getting admin status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
