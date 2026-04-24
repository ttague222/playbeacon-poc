from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional

from app.db.firebase import get_db, GAMES_COLLECTION
from app.api.schemas import (
    GameResponse,
    QueueRequest,
    QueueResponse,
    FeedbackRequest,
    FeedbackResponse,
    CrawlRequest,
    CrawlResponse,
    GenerateEmbeddingsResponse,
    RobloxUserResponse,
    RobloxImportDataResponse,
    RobloxImportRequest,
    RobloxImportResponse,
    CrawlerEnqueueRequest,
    CrawlerEnqueueResponse,
    CrawlerStatusResponse,
    CrawlerKeywordRequest,
    CrawlerSortsRequest,
    CrawlerGraphRequest,
    ThumbnailFixRequest,
    EmbedRegenRequest,
    AdminStatusResponse,
    ScheduleToggleRequest,
)
from app.models.firestore_models import Game
from app.services.roblox_crawler_firestore import RobloxCrawler
from app.services.game_scorer import GameScorer
from app.services.embedding_service_pinecone import EmbeddingService
from app.services.recommendation_service_pinecone import RecommendationService
from app.services.pinecone_service import PineconeService
from app.services.roblox_api_service import RobloxAPIService
from app.services.llm_service import LLMService
from app.api.scheduler import scheduler
from app.api.auth import get_current_user_id, get_current_admin_user_id
from app.services.thumbnail_utils import is_bad_thumbnail
from firebase_admin import firestore
from datetime import datetime
import logging
import asyncio
import re

logger = logging.getLogger(__name__)

router = APIRouter()
CRAWLER_QUEUE_COLLECTION = "crawler_queue"
DEFAULT_SORTS = ["popular", "top_rated", "recommended", "up_and_coming", "hidden_gems"]
DEFAULT_KEYWORDS = ["horror", "simulator", "tycoon", "anime", "roleplay", "pet", "zombie", "adventure"]
DEFAULT_GRAPH_SEEDS = [1818, 920587237]
TEMPLATE_TITLES = {"my place", "test", "baseplate"}
PROFANE_WORDS = {"sex", "fuck", "shit", "nude"}  # simple blocklist
TEMPLATE_PATTERNS = [re.compile(r"^my\s+place", re.I), re.compile(r"^test", re.I), re.compile(r"^baseplate", re.I)]
THUMB_PLACEHOLDERS = ["placeholder", "noplaceholder", "assetdelivery"]
GENRE_MAP = {
    "horror": "horror",
    "simulator": "simulator",
    "tycoon": "tycoon",
    "adventure": "adventure",
    "roleplay": "roleplay",
    "rpg": "rpg",
    "action": "action",
    "fps": "shooter",
    "shooter": "shooter",
    "anime": "anime",
    "zombie": "zombie",
}
# Simple schedule metadata
SCHEDULE_METADATA = {
    "queue_worker": "hourly",
    "keywords": "daily",
    "sorts": "daily",
    "graph": "daily",
}


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


@router.get("/games/{universe_id}/similar")
async def get_similar_games(universe_id: str, limit: int = 10):
    """Get games similar to a specific game using Pinecone"""
    try:
        rec_service = RecommendationService()
        similar_games = rec_service.get_similar_games(
            universe_id=universe_id,
            top_k=limit
        )

        return {
            "universe_id": universe_id,
            "similar_games": similar_games,
            "count": len(similar_games)
        }

    except Exception as e:
        logger.error(f"Error getting similar games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_games_by_text(query: str, limit: int = 10):
    """Search for games based on text description using Pinecone"""
    try:
        rec_service = RecommendationService()
        games = rec_service.get_recommendations_by_text(
            query_text=query,
            top_k=limit
        )

        return {
            "query": query,
            "games": games,
            "count": len(games)
        }

    except Exception as e:
        logger.error(f"Error searching games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue", response_model=QueueResponse)
async def get_queue(request: QueueRequest, user_id: str = Depends(get_current_user_id)):
    """Get personalized game recommendations for a user using Pinecone"""
    try:
        rec_service = RecommendationService()
        recommendations = rec_service.get_personalized_recommendations(
            user_id=user_id,
            top_k=request.limit
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

        # Map feedback integer to type
        feedback_map = {1: "like", 0: "skip", -1: "dislike"}
        feedback_type = feedback_map.get(request.feedback, "unknown")

        # Save feedback
        rec_service = RecommendationService()
        success = rec_service.record_user_feedback(
            user_id=user_id,
            universe_id=request.universe_id,
            feedback_type=feedback_type
        )

        if success:
            return FeedbackResponse(
                success=True,
                message=f"Feedback recorded: {feedback_type}"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save feedback")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/reset-profile")
async def reset_profile(user_id: str = Depends(get_current_user_id)):
    """Clear user feedback and reset profile embedding/counts."""
    try:
        db = get_db()
        user_ref = db.collection('users').document(user_id)

        # Delete feedback subcollection
        feedback_ref = user_ref.collection('feedback')
        feedback_docs = list(feedback_ref.stream())
        batch = db.batch()
        for doc in feedback_docs:
            batch.delete(doc.reference)
        batch.commit()

        # Reset profile fields
        user_ref.set({
            'profile_embedding': None,
            'liked_count': 0,
            'disliked_count': 0,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, merge=True)

        return {"success": True, "message": "Profile reset"}
    except Exception as e:
        logger.error(f"Error resetting profile for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/skip-roblox-import")
async def skip_roblox_import(user_id: str = Depends(get_current_user_id)):
    """Mark Roblox import as skipped for this user to stop onboarding prompts."""
    try:
        db = get_db()
        user_ref = db.collection("users").document(user_id)
        user_ref.set(
            {
                "skipped_roblox_import": True,
                "updated_at": datetime.now()
            },
            merge=True,
        )
        return {"success": True, "message": "Roblox import skipped"}
    except Exception as e:
        logger.error(f"Error skipping Roblox import for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _enqueue_universe_ids(db, universe_ids: List[int], source: str, priority: int) -> (int, int):
    """Enqueue universe IDs into crawler_queue, idempotently bumping priority/timestamp."""
    queue_ref = db.collection(CRAWLER_QUEUE_COLLECTION)
    enqueued = 0
    updated = 0
    now = datetime.now()

    for uid in universe_ids:
        doc_ref = queue_ref.document(str(uid))
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.set(
                {
                    "priority": max(priority, doc.to_dict().get("priority", 1)),
                    "status": "pending",
                    "added_at": now,
                    "source": source,
                },
                merge=True,
            )
            updated += 1
        else:
            doc_ref.set(
                {
                    "universeId": int(uid),
                    "added_at": now,
                    "priority": priority,
                    "source": source,
                    "attempts": 0,
                    "status": "pending",
                }
            )
            enqueued += 1
    return enqueued, updated


async def _process_queue_batch(limit: int = 10):
    """Process a batch of crawler queue items."""
    db = get_db()
    queue_ref = db.collection(CRAWLER_QUEUE_COLLECTION)
    banned_titles = TEMPLATE_TITLES
    llm_service = LLMService()
    game_scorer = GameScorer()

    # Fetch pending items and sort in Python to avoid composite index requirement
    try:
        docs = queue_ref.where("status", "==", "pending").limit(limit * 3).stream()
        items = sorted(
            list(docs),
            key=lambda d: (
                -1 * int(d.to_dict().get("priority", 0)),
                d.to_dict().get("added_at") or datetime.min,
            ),
        )[:limit]
    except Exception as e:
        logger.error(f"Error loading crawler queue batch: {e}")
        return {"processed": 0, "imported": 0, "skipped": 0, "errors": 1, "embedded": 0}

    if not items:
        return {"processed": 0, "imported": 0, "skipped": 0, "errors": 0}

    universe_ids = [int(doc.to_dict().get("universeId")) for doc in items if doc.to_dict().get("status") != "processing"]

    roblox_service = RobloxAPIService()
    details_map = await roblox_service.get_game_details(universe_ids)
    thumbs_map = await roblox_service.get_game_thumbnails(universe_ids)
    await roblox_service.close()

    imported = 0
    skipped = 0
    errors = 0
    embedded = 0

    for doc in items:
        doc_data = doc.to_dict()
        uid = int(doc_data.get("universeId"))
        doc_ref = doc.reference

        try:
            # Mark processing
            doc_ref.set({"status": "processing"}, merge=True)

            game_data = details_map.get(uid)
            if not game_data:
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "No game data"}, merge=True)
                continue

            # Basic validation
            title = (game_data.get("name") or "").strip()
            description = (game_data.get("description") or "").strip()
            visits = game_data.get("visits", 0)
            last_updated = game_data.get("updated", None)
            creator = game_data.get("creator", {}) or {}
            creator_id = creator.get("id", 0)
            is_playable = game_data.get("isPlayable")
            is_public = game_data.get("isPublic", True)
            updated_str = game_data.get("updated")
            last_update_dt = None
            if updated_str:
                try:
                    last_update_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                except Exception:
                    last_update_dt = None
            up_votes = game_data.get("upVotes", 0)
            down_votes = game_data.get("downVotes", 0)
            total_votes = up_votes + down_votes
            like_ratio = (up_votes / total_votes) if total_votes > 0 else None

            # Calculate confidence score
            score, tier, breakdown = game_scorer.calculate_score(game_data)
            game_scorer.log_score(uid, score, tier, breakdown)

            # Check if we should import this game
            should_import, full_processing = game_scorer.should_import(score, tier)

            if not should_import:
                skipped += 1
                doc_ref.set({
                    "status": "error",
                    "last_error": f"Low confidence score: {score:.1f} (tier: {tier})",
                    "confidence_score": score,
                    "confidence_tier": tier,
                    "score_breakdown": breakdown
                }, merge=True)
                continue

            if not title:
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Empty title"}, merge=True)
                continue

            if title.lower() in banned_titles:
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Template title"}, merge=True)
                continue

            lowered_title = title.lower()
            if any(word in lowered_title for word in PROFANE_WORDS):
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Profane title"}, merge=True)
                continue
            if any(pat.search(title) for pat in TEMPLATE_PATTERNS):
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Template pattern"}, merge=True)
                continue

            if any(word in (description or "").lower() for word in PROFANE_WORDS):
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Profane description"}, merge=True)
                continue

            if not description and visits < 10:
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "No description and low visits"}, merge=True)
                continue

            # Age filter: if visits == 0 and last update older than 1 year
            if visits == 0 and last_update_dt:
                from datetime import timedelta
                if datetime.now(last_update_dt.tzinfo) - last_update_dt > timedelta(days=365):
                    skipped += 1
                    doc_ref.set({"status": "error", "last_error": "Stale game with zero visits"}, merge=True)
                    continue

            # Reject unplayable/private if field exists
            if is_playable is False or is_public is False:
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Unplayable/private game"}, merge=True)
                continue

            if creator_id == 0:
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Invalid creator"}, merge=True)
                continue

            # Relax voting requirements - only reject if like ratio is very low AND has enough votes to be meaningful
            if total_votes >= 10 and like_ratio is not None and like_ratio < 0.2:
                skipped += 1
                doc_ref.set({"status": "error", "last_error": "Low like ratio with sufficient votes"}, merge=True)
                continue

            # Thumbnail is optional - we'll use a default if missing
            thumb_url = thumbs_map.get(uid)
            if thumb_url and is_bad_thumbnail(thumb_url):
                thumb_url = None  # Use default instead of rejecting

            # Prepare Firestore doc
            games_ref = db.collection(GAMES_COLLECTION)
            game_ref = games_ref.document(str(uid))
            now = datetime.now()
            existing_doc = game_ref.get()
            prev_visits = 0
            if existing_doc.exists:
                prev_visits = existing_doc.to_dict().get("visits", 0)

            # Flags
            is_new = False
            if last_update_dt:
                try:
                    from datetime import timedelta
                    is_new = (datetime.now(last_update_dt.tzinfo) - last_update_dt) <= timedelta(days=30)
                except Exception:
                    is_new = False

            is_popular = visits > 1_000_000 or game_data.get("playing", 0) > 500
            is_trending = False
            try:
                if visits > 0 and prev_visits > 0:
                    delta = visits - prev_visits
                    if delta / max(prev_visits, 1) >= 0.1:
                        is_trending = True
            except Exception:
                is_trending = False

            payload = {
                "universe_id": str(uid),
                "title": title,
                "description": description,
                "thumbnail_url": thumb_url or "",  # Use empty string if no thumbnail
                "creator_name": creator.get("name", ""),
                "creator_id": creator_id,
                "visits": visits,
                "active_players": game_data.get("playing", 0),
                "likes": up_votes,
                "dislikes": down_votes,
                "like_ratio": like_ratio if like_ratio is not None else 0.5,  # Default to neutral if no votes
                "genre": GENRE_MAP.get(game_data.get("genre", "").lower(), game_data.get("genre", "").lower()),
                "last_update": last_updated,
                "search_terms": [title.lower(), GENRE_MAP.get(game_data.get("genre", "").lower(), game_data.get("genre", "").lower())],
                "confidence_score": score,
                "confidence_tier": tier,
                "score_breakdown": breakdown,
            }

            # Only do LLM enrichment for high-confidence games (full_processing=True)
            if full_processing:
                # LLM enrichment for tags and summary
                safe_text = llm_service.moderate_text(f"{title}\n{description}")
                if safe_text:
                    llm_output = llm_service.generate_tags_and_summary(title, description, payload["genre"])
                    if llm_output.get("tags"):
                        payload["tags"] = llm_output["tags"]
                        payload["search_terms"].extend([t.lower() for t in llm_output["tags"]])
                    if llm_output.get("summary"):
                        payload["summary"] = llm_output["summary"]
                    else:
                        payload["summary"] = description[:500] if description else ""
                else:
                    payload["tags"] = []
                    payload["summary"] = description[:500] if description else ""
            else:
                # Medium confidence - skip LLM enrichment to save costs
                payload["tags"] = []
                payload["summary"] = description[:500] if description else ""

            if len(payload["search_terms"]) > 20:
                payload["search_terms"] = payload["search_terms"][:20]

            # Deduplicate search_terms
            payload["search_terms"] = list(dict.fromkeys(payload["search_terms"]))

            # Get source from queue doc
            doc_dict = doc.to_dict()
            source = doc_dict.get("source", "unknown") if doc_dict else "unknown"

            payload.update({
                "has_embedding": False,
                "last_crawled": now,
                "sources": firestore.ArrayUnion([source]),
                "is_new": is_new,
                "is_popular": is_popular,
                "is_trending": is_trending,
            })

            game_ref.set(payload, merge=True)

            # Mark queue done
            doc_ref.set({"status": "done", "attempts": firestore.Increment(1)}, merge=True)
            imported += 1

            # Generate embedding only for high-confidence games (full_processing=True)
            if full_processing:
                try:
                    embedding_service = EmbeddingService()
                    text_parts = [title, description, game_data.get("genre", "")]
                    embed_text = " | ".join([p for p in text_parts if p])
                    embedding = embedding_service.generate_embedding(embed_text)

                    if embedding:
                        metadata = {
                            "title": title,
                            "genre": game_data.get("genre", ""),
                            "creator_name": creator.get("name", ""),
                            "visits": visits,
                            "active_players": game_data.get("playing", 0),
                        }
                        pinecone_ok = embedding_service.pinecone_service.upsert_embedding(
                            universe_id=uid,
                            embedding=embedding,
                            metadata=metadata
                        )
                        if pinecone_ok:
                            game_ref.set({
                                "has_embedding": True,
                                "embedding_updated_at": datetime.now()
                            }, merge=True)
                            embedded += 1
                except Exception as embed_err:
                    logger.error(f"Embedding error for {uid}: {embed_err}")
            else:
                # Medium confidence - skip embedding generation
                logger.info(f"Skipping embedding for medium-confidence game {uid} (score: {score:.1f})")

        except Exception as e:
            logger.error(f"Error processing universeId {uid}: {e}")
            errors += 1
            doc_ref.set(
                {
                    "status": "error",
                    "last_error": str(e),
                    "attempts": firestore.Increment(1),
                },
                merge=True,
            )

    return {
        "processed": len(items),
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "embedded": embedded,
    }


@router.post("/crawler/enqueue", response_model=CrawlerEnqueueResponse)
async def enqueue_crawler(request: CrawlerEnqueueRequest, user_id: str = Depends(get_current_admin_user_id)):
    """Enqueue universe IDs for crawling."""
    try:
        db = get_db()
        universe_ids = list({int(uid) for uid in request.universe_ids if uid})
        if not universe_ids:
            raise HTTPException(status_code=400, detail="No universe IDs provided")

        enqueued, updated = _enqueue_universe_ids(
            db=db,
            universe_ids=universe_ids,
            source=request.source,
            priority=request.priority,
        )

        return CrawlerEnqueueResponse(
            success=True,
            enqueued=enqueued,
            updated=updated,
            message=f"Queued {enqueued} new, updated {updated} existing IDs",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing crawler IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/process-batch")
async def process_crawler_batch(limit: int = 10, user_id: str = Depends(get_current_admin_user_id)):
    """Process a batch of crawler queue items (manual trigger)."""
    try:
        result = await _process_queue_batch(limit=limit)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error processing crawler batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/run")
async def run_crawler(limit: int = 50, user_id: str = Depends(get_current_admin_user_id)):
    """
    Convenience endpoint to process queue batches until empty or limit reached.
    """
    try:
        total_processed = 0
        total_imported = 0
        total_embedded = 0
        total_skipped = 0
        total_errors = 0

        while total_processed < limit:
            batch_limit = min(10, limit - total_processed)
            result = await _process_queue_batch(limit=batch_limit)
            processed = result.get("processed", 0)
            if processed == 0:
                break
            total_processed += processed
            total_imported += result.get("imported", 0)
            total_embedded += result.get("embedded", 0)
            total_skipped += result.get("skipped", 0)
            total_errors += result.get("errors", 0)

        return {
          "success": True,
          "processed": total_processed,
          "imported": total_imported,
          "embedded": total_embedded,
          "skipped": total_skipped,
          "errors": total_errors,
          "message": f"Processed {total_processed} items"
        }
    except Exception as e:
        logger.error(f"Error running crawler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/run-full")
async def run_full_crawler(user_id: str = Depends(get_current_admin_user_id)):
    """
    Enqueue default sorts and keywords, then process a batch.
    """
    try:
        db = get_db()
        roblox_service = RobloxAPIService()
        all_ids = []
        # Fetch sorts
        for sort_name in DEFAULT_SORTS:
            ids = await roblox_service.get_universe_ids_by_sort(sort_name, 50)
            all_ids.extend(ids)
        # Fetch keywords
        for kw in DEFAULT_KEYWORDS:
            ids = await roblox_service.get_universe_ids_by_keyword(kw, 20)
            all_ids.extend(ids)
        await roblox_service.close()
        all_ids = list({int(uid) for uid in all_ids})
        enqueued, updated = _enqueue_universe_ids(db, all_ids, source="full_crawl", priority=7)

        # Process an initial batch
        result = await _process_queue_batch(limit=50)

        return {
            "success": True,
            "enqueued": enqueued,
            "updated": updated,
            "processed": result.get("processed", 0),
            "imported": result.get("imported", 0),
            "embedded": result.get("embedded", 0),
            "skipped": result.get("skipped", 0),
            "errors": result.get("errors", 0),
            "message": "Full crawl kickstarted",
        }
    except Exception as e:
        logger.error(f"Error running full crawler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/enqueue-keywords")
async def enqueue_keywords(request: CrawlerKeywordRequest, user_id: str = Depends(get_current_admin_user_id)):
    """Search keywords on Roblox and enqueue resulting universe IDs."""
    try:
        if not request.keywords:
            raise HTTPException(status_code=400, detail="No keywords provided")

        roblox_service = RobloxAPIService()
        all_ids = []
        for kw in request.keywords:
            ids = await roblox_service.get_universe_ids_by_keyword(kw.strip(), request.limit_per_keyword)
            all_ids.extend(ids)
        await roblox_service.close()

        # Deduplicate
        all_ids = list({int(uid) for uid in all_ids})

        db = get_db()
        enqueued, updated = _enqueue_universe_ids(
            db=db,
            universe_ids=all_ids,
            source="keyword_search",
            priority=request.priority,
        )

        return {
            "success": True,
            "keywords": len(request.keywords),
            "found_universe_ids": len(all_ids),
            "enqueued": enqueued,
            "updated": updated,
            "message": f"Enqueued {enqueued} new IDs from keywords",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/enqueue-sorts")
async def enqueue_sorts(request: CrawlerSortsRequest, user_id: str = Depends(get_current_admin_user_id)):
    """Fetch official Roblox sorts and enqueue resulting universe IDs."""
    try:
        if not request.sorts:
            raise HTTPException(status_code=400, detail="No sorts provided")

        roblox_service = RobloxAPIService()
        all_ids = []
        for sort_name in request.sorts:
            ids = await roblox_service.get_universe_ids_by_sort(sort_name.strip(), request.limit)
            all_ids.extend(ids)
        await roblox_service.close()

        all_ids = list({int(uid) for uid in all_ids})

        db = get_db()
        enqueued, updated = _enqueue_universe_ids(
            db=db,
            universe_ids=all_ids,
            source="official_sort",
            priority=request.priority,
        )

        return {
            "success": True,
            "sorts": len(request.sorts),
            "found_universe_ids": len(all_ids),
            "enqueued": enqueued,
            "updated": updated,
            "message": f"Enqueued {enqueued} new IDs from sorts",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing sorts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/enqueue-graph")
async def enqueue_graph(request: CrawlerGraphRequest, user_id: str = Depends(get_current_admin_user_id)):
    """
    Enqueue related and creator games for given universe IDs (graph expansion).
    """
    try:
        if not request.universe_ids:
            raise HTTPException(status_code=400, detail="No universe IDs provided")

        roblox_service = RobloxAPIService()
        all_ids = []
        for uid in request.universe_ids:
            try:
                uid_int = int(uid)
            except Exception:
                continue
            related = await roblox_service.get_related_universe_ids(uid_int)
            creator_ids = []
            # Fetch creator games using details
            details_map = await roblox_service.get_game_details([uid_int])
            detail = details_map.get(uid_int)
            creator = detail.get("creator", {}) if detail else {}
            creator_id = creator.get("id")
            if creator_id:
                creator_games = await roblox_service.get_creator_universe_ids(creator_id)
                creator_ids.extend(creator_games)
            all_ids.extend(related)
            all_ids.extend(creator_ids)
        await roblox_service.close()

        all_ids = list({int(x) for x in all_ids})
        db = get_db()
        enqueued, updated = _enqueue_universe_ids(
            db=db,
            universe_ids=all_ids,
            source="graph_expansion",
            priority=request.priority,
        )

        return {
            "success": True,
            "source_universe_ids": len(request.universe_ids),
            "found_universe_ids": len(all_ids),
            "enqueued": enqueued,
            "updated": updated,
            "message": f"Enqueued {enqueued} new IDs from graph expansion",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing graph expansion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/embed-missing")
async def embed_missing_games(limit: int = 50, user_id: str = Depends(get_current_admin_user_id)):
    """Generate embeddings for games missing embeddings."""
    try:
        db = get_db()
        games_ref = db.collection(GAMES_COLLECTION)
        games_cursor = games_ref.where("has_embedding", "==", False).limit(limit).stream()
        embedding_service = EmbeddingService()

        embedded = 0
        for doc in games_cursor:
            data = doc.to_dict()
            text_parts = [data.get("title", ""), data.get("description", ""), data.get("genre", "")]
            embed_text = " | ".join([p for p in text_parts if p])
            embedding = embedding_service.generate_embedding(embed_text)
            if embedding:
                metadata = {
                    "title": data.get("title", ""),
                    "genre": data.get("genre", ""),
                    "creator_name": data.get("creator_name", ""),
                    "visits": data.get("visits", 0),
                    "active_players": data.get("active_players", 0),
                }
                pinecone_ok = embedding_service.pinecone_service.upsert_embedding(
                    universe_id=doc.id,
                    embedding=embedding,
                    metadata=metadata,
                )
                if pinecone_ok:
                    doc.reference.set(
                        {
                            "has_embedding": True,
                            "embedding_updated_at": datetime.now(),
                        },
                        merge=True,
                    )
                    embedded += 1

        return {"success": True, "embedded": embedded}
    except Exception as e:
        logger.error(f"Error embedding missing games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crawler/status", response_model=CrawlerStatusResponse)
async def get_crawler_status(user_id: str = Depends(get_current_admin_user_id)):
    """Get crawler queue and catalog status for dashboard."""
    try:
        db = get_db()
        queue_ref = db.collection(CRAWLER_QUEUE_COLLECTION)
        games_ref = db.collection(GAMES_COLLECTION)

        queue_length = len(list(queue_ref.where("status", "in", ["pending", "processing"]).stream()))
        missing_embeddings = len(list(games_ref.where("has_embedding", "==", False).stream()))
        crawl_errors = len(list(queue_ref.where("status", "==", "error").stream()))

        # New today: games with last_crawled >= today
        from datetime import datetime, timedelta
        start_of_day = datetime.combine(datetime.now().date(), datetime.min.time())
        new_today = len(list(games_ref.where("last_crawled", ">=", start_of_day).stream()))

        # Last crawl and embed timestamps from admin/status doc if present
        admin_status_ref = db.collection("admin").document("status")
        admin_status_doc = admin_status_ref.get()
        last_crawl = None
        last_embed = None
        if admin_status_doc.exists:
            admin_data = admin_status_doc.to_dict()
            last_crawl = admin_data.get("last_crawl")
            last_embed = admin_data.get("last_embedding")

        return CrawlerStatusResponse(
            success=True,
            queue_length=queue_length,
            missing_embeddings=missing_embeddings,
            crawl_errors=crawl_errors,
            new_today=new_today,
            last_crawl=last_crawl.isoformat() if last_crawl else None,
            last_embed=last_embed.isoformat() if last_embed else None,
            worker_status="online",
            next_runs={
                "queue_worker": scheduler.next_runs.get("queue_worker").isoformat() if scheduler.next_runs.get("queue_worker") else None,
                "keywords": scheduler.next_runs.get("keywords").isoformat() if scheduler.next_runs.get("keywords") else None,
                "sorts": scheduler.next_runs.get("sorts").isoformat() if scheduler.next_runs.get("sorts") else None,
                "graph": scheduler.next_runs.get("graph").isoformat() if scheduler.next_runs.get("graph") else None,
                "embed_sweep": scheduler.next_runs.get("embed_sweep").isoformat() if scheduler.next_runs.get("embed_sweep") else None,
                "thumb_fix": scheduler.next_runs.get("thumb_fix").isoformat() if scheduler.next_runs.get("thumb_fix") else None,
                "weekly": scheduler.next_runs.get("weekly").isoformat() if scheduler.next_runs.get("weekly") else None,
            },
            schedule_enabled=scheduler.enabled,
        )
    except Exception as e:
        logger.error(f"Error getting crawler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/fix-thumbnails")
async def fix_thumbnails(request: ThumbnailFixRequest, user_id: str = Depends(get_current_admin_user_id)):
    """Re-fetch thumbnails for games missing them."""
    try:
        db = get_db()
        games_ref = db.collection(GAMES_COLLECTION)
        games_cursor = games_ref.where("thumbnail_url", "==", "").limit(request.limit).stream()

        to_fix = [doc for doc in games_cursor]
        if not to_fix:
            return {"success": True, "fixed": 0, "message": "No games missing thumbnails"}

        roblox_service = RobloxAPIService()
        ids = [int(doc.id) for doc in to_fix]
        thumbs_map = await roblox_service.get_game_thumbnails(ids)
        await roblox_service.close()

        fixed = 0
        for doc in to_fix:
            thumb = thumbs_map.get(int(doc.id))
            if thumb:
                doc.reference.set({"thumbnail_url": thumb}, merge=True)
                fixed += 1

        return {"success": True, "fixed": fixed, "message": f"Updated thumbnails for {fixed} games"}
    except Exception as e:
        logger.error(f"Error fixing thumbnails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/regenerate-embeddings")
async def regenerate_embeddings(request: EmbedRegenRequest, user_id: str = Depends(get_current_admin_user_id)):
    """Regenerate embeddings for the most recently crawled games."""
    try:
        db = get_db()
        games_ref = db.collection(GAMES_COLLECTION)
        # Grab recent games (last_crawled desc)
        games_cursor = games_ref.order_by("last_crawled", direction="DESCENDING").limit(request.limit).stream()

        embedding_service = EmbeddingService()
        regenerated = 0
        for doc in games_cursor:
            data = doc.to_dict()
            text_parts = [data.get("title", ""), data.get("description", ""), data.get("genre", "")]
            embed_text = " | ".join([p for p in text_parts if p])
            embedding = embedding_service.generate_embedding(embed_text)
            if embedding:
                metadata = {
                    "title": data.get("title", ""),
                    "genre": data.get("genre", ""),
                    "creator_name": data.get("creator_name", ""),
                    "visits": data.get("visits", 0),
                    "active_players": data.get("active_players", 0),
                }
                pinecone_ok = embedding_service.pinecone_service.upsert_embedding(
                    universe_id=doc.id,
                    embedding=embedding,
                    metadata=metadata,
                )
                if pinecone_ok:
                    doc.reference.set(
                        {
                            "has_embedding": True,
                            "embedding_updated_at": datetime.now(),
                        },
                        merge=True,
                    )
                    regenerated += 1

        return {"success": True, "regenerated": regenerated, "message": f"Regenerated {regenerated} embeddings"}
    except Exception as e:
        logger.error(f"Error regenerating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/schedule-toggle")
async def toggle_schedule(request: ScheduleToggleRequest, user_id: str = Depends(get_current_admin_user_id)):
    """Enable/disable scheduler tasks."""
    try:
        for key in scheduler.enabled.keys():
            val = getattr(request, key, None)
            if val is not None:
                scheduler.enabled[key] = bool(val)
        return {"success": True, "enabled": scheduler.enabled}
    except Exception as e:
        logger.error(f"Error toggling scheduler: {e}")
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
async def generate_embeddings(universe_ids: Optional[List[str]] = None):
    """Generate embeddings for games and store in Pinecone"""
    try:
        embedding_service = EmbeddingService()

        if universe_ids:
            # Generate for specific games
            results = embedding_service.generate_embeddings_batch(universe_ids)
            count = sum(results.values())
        else:
            # Generate for all games
            count = embedding_service.generate_all_game_embeddings()

        return GenerateEmbeddingsResponse(
            success=True,
            embeddings_generated=count,
            message=f"Generated and stored {count} embeddings in Pinecone"
        )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pinecone/stats")
async def get_pinecone_stats():
    """Get Pinecone index statistics"""
    try:
        pinecone_service = None
        pinecone_stats = {"total_vector_count": 0}
        try:
            pinecone_service = PineconeService()
            pinecone_stats = pinecone_service.get_index_stats() or {}
        except Exception as pinecone_err:
            logger.warning(f"Pinecone stats unavailable: {pinecone_err}")
        stats = pinecone_service.get_index_stats()

        # Extract only JSON-serializable primitive fields
        return {
            "success": True,
            "total_vector_count": int(stats.get("total_vector_count", 0)),
            "dimension": int(stats.get("dimension", 0)),
            "index_fullness": float(stats.get("index_fullness", 0.0))
        }

    except Exception as e:
        logger.error(f"Error getting Pinecone stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/status", response_model=AdminStatusResponse)
async def get_admin_status(user_id: str = Depends(get_current_admin_user_id)):
    """Get admin dashboard status metrics"""
    try:
        db = get_db()
        pinecone_service = PineconeService()

        # Get Firestore stats
        games_ref = db.collection(GAMES_COLLECTION)
        all_games = list(games_ref.stream())
        total_games = len(all_games)

        # Count games with/without embeddings
        games_with_embeddings = sum(1 for game in all_games if game.to_dict().get('has_embedding', False))
        games_missing_embeddings = total_games - games_with_embeddings

        # Get Pinecone stats
        pinecone_stats = pinecone_service.get_index_stats()
        total_vectors = int(pinecone_stats.get("total_vector_count", 0))

        # Get job tracking info
        admin_status_ref = db.collection('admin').document('status')
        admin_status_doc = admin_status_ref.get()

        last_crawl = None
        last_embedding = None

        if admin_status_doc.exists:
            admin_data = admin_status_doc.to_dict()
            last_crawl = admin_data.get('last_crawl')
            last_embedding = admin_data.get('last_embedding')

        # Get recent errors
        errors_ref = db.collection('admin').document('errors').collection('entries')
        error_docs = list(errors_ref.order_by('timestamp', direction='DESCENDING').limit(5).stream())

        errors = []
        for error_doc in error_docs:
            error_data = error_doc.to_dict()
            errors.append({
                'timestamp': error_data.get('timestamp'),
                'message': error_data.get('message', '')
            })

        return {
            "firestore": {
                "total_games": total_games,
                "games_with_embeddings": games_with_embeddings,
                "games_missing_embeddings": games_missing_embeddings
            },
            "pinecone": {
                "total_vectors": total_vectors
            },
            "jobs": {
                "last_crawl": last_crawl.isoformat() if last_crawl else None,
                "last_embedding": last_embedding.isoformat() if last_embedding else None
            },
            "errors": errors
        }

    except Exception as e:
        logger.error(f"Error getting admin status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Firebase connection
        db = get_db()

        # Check Pinecone connection
        pinecone_service = PineconeService()
        stats = pinecone_service.get_index_stats()

        return {
            "status": "healthy",
            "firebase": "connected",
            "pinecone": "connected",
            "vector_count": stats.get("total_vector_count", 0) if stats else 0
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Roblox Import Endpoints

@router.get("/roblox/resolve", response_model=RobloxUserResponse)
async def resolve_roblox_username(username: str):
    """
    Resolve a Roblox username to user data

    Args:
        username: Roblox username to look up

    Returns:
        Roblox user data including userId, displayName, avatar, etc.
    """
    try:
        roblox_service = RobloxAPIService()
        user_data = await roblox_service.resolve_username(username)
        await roblox_service.close()

        if not user_data:
            raise HTTPException(status_code=404, detail="Roblox user not found")

        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving Roblox username {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roblox/import-data", response_model=RobloxImportDataResponse)
async def get_roblox_import_data(userId: int):
    """
    Get all importable data for a Roblox user

    Args:
        userId: Roblox user ID

    Returns:
        Aggregated game data from favorites, badges, and groups
    """
    try:
        roblox_service = RobloxAPIService()
        import_data = await roblox_service.get_import_data(userId)
        await roblox_service.close()

        return import_data

    except Exception as e:
        logger.error(f"Error getting Roblox import data for user {userId}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/roblox/import-selected", response_model=RobloxImportResponse)
async def import_selected_games(
    request: RobloxImportRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Import selected Roblox games as user feedback

    Args:
        request: Import request with selectedGames and Roblox user data
        user_id: Firebase user ID from auth token

    Returns:
        Success response with number of games imported
    """
    try:
        db = get_db()
        user_ref = db.collection("users").document(user_id)

        # Write feedback for each selected game
        batch = db.batch()
        games_imported = 0

        for selected_game in request.selectedGames:
            feedback_ref = user_ref.collection("feedback").document(selected_game.universeId)

            feedback_data = {
                "user_id": user_id,
                "universe_id": selected_game.universeId,
                "feedback": 1,  # Like
                "score": selected_game.score,
                "source": "roblox-import",
                "timestamp": datetime.now()
            }

            batch.set(feedback_ref, feedback_data)
            games_imported += 1

        # Commit all feedback writes
        batch.commit()

        # Update user profile with Roblox info
        user_ref.update({
            "roblox_username": request.robloxUsername,
            "roblox_userId": request.robloxUserId,
            "roblox_imported": True,
            "liked_count": firestore.Increment(games_imported),
            "updated_at": datetime.now()
        })

        # Write Roblox import metadata
        import_metadata_ref = user_ref.collection("roblox_import").document("metadata")
        import_metadata_ref.set({
            "imported_at": datetime.now(),
            "total_games_identified": games_imported,
            "robloxUserId": request.robloxUserId,
            "robloxUsername": request.robloxUsername
        })

        # Enqueue imported universe IDs for full crawl
        try:
            _enqueue_universe_ids(
                db=get_db(),
                universe_ids=[int(g.universeId) for g in request.selectedGames if g.universeId],
                source="user_import",
                priority=7,
            )
        except Exception as enqueue_err:
            logger.warning(f"Could not enqueue imported games for crawl: {enqueue_err}")

        # Trigger profile embedding regeneration
        try:
            rec_service = RecommendationService()
            # This will regenerate the embedding based on all feedback including new imports
            rec_service.get_personalized_recommendations(user_id, top_k=1)
        except Exception as e:
            logger.warning(f"Could not regenerate embedding for {user_id}: {e}")

        logger.info(f"Successfully imported {games_imported} games for user {user_id} from Roblox user {request.robloxUsername}")

        return RobloxImportResponse(
            success=True,
            games_imported=games_imported,
            message=f"Successfully imported {games_imported} games from your Roblox account"
        )

    except Exception as e:
        logger.error(f"Error importing Roblox games for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
