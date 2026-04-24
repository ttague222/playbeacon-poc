"""
Crawler API Routes

Endpoints for managing the game crawler system.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.api.schemas import (
    CrawlerEnqueueRequest,
    CrawlerEnqueueResponse,
    CrawlerStatusResponse,
    CrawlerKeywordRequest,
    CrawlerSortsRequest,
    CrawlerGraphRequest,
)
from app.services.crawler_queue import CrawlerQueue
from app.services.game_importer import GameImporter
from app.services.roblox_api_service import RobloxAPIService
from app.api.auth import get_current_user_id, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crawler", tags=["crawler"])


@router.get("/status", response_model=CrawlerStatusResponse)
async def get_crawler_status(
    _: str = Depends(require_admin)
):
    """
    Get crawler queue status and statistics.
    Requires admin access.
    """
    queue = CrawlerQueue()
    stats = queue.get_stats()

    # TODO: Add more stats (missing embeddings, new today, etc.)
    return CrawlerStatusResponse(
        success=True,
        queue_length=stats['queue_length'],
        missing_embeddings=0,  # TODO: Calculate
        crawl_errors=stats['errors'],
        new_today=0,  # TODO: Calculate
        last_crawl=None,  # TODO: Track
        last_embed=None,  # TODO: Track
        worker_status="idle",  # TODO: Track worker status
        next_runs=None,  # TODO: Add scheduler info
    )


@router.post("/enqueue", response_model=CrawlerEnqueueResponse)
async def enqueue_games(
    request: CrawlerEnqueueRequest,
    _: str = Depends(require_admin)
):
    """
    Manually add universe IDs to the crawler queue.
    Requires admin access.
    """
    try:
        queue = CrawlerQueue()
        result = queue.enqueue(
            universe_ids=request.universe_ids,
            source=request.source,
            priority=request.priority
        )

        return CrawlerEnqueueResponse(
            success=True,
            enqueued=result['enqueued'],
            updated=result['updated'],
            message=f"Added {result['enqueued']} new entries, updated {result['updated']} existing entries"
        )
    except Exception as e:
        logger.error(f"Error enqueueing games: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue games: {str(e)}"
        )


@router.post("/process-batch")
async def process_batch(
    limit: int = 10,
    _: str = Depends(require_admin)
):
    """
    Process a batch of games from the crawler queue.
    Requires admin access.
    """
    try:
        queue = CrawlerQueue()
        importer = GameImporter()

        # Reset any stuck processing entries
        queue.reset_stuck_processing(timeout_minutes=30)

        # Get next batch
        entries = queue.get_next_batch(limit=limit)

        if not entries:
            return {
                "success": True,
                "message": "Queue is empty",
                "processed": 0
            }

        # Extract universe IDs
        universe_ids = [entry['universeId'] for entry in entries]

        # Import batch
        stats = await importer.import_batch(universe_ids, source="queue_worker")

        await importer.close()

        return {
            "success": True,
            "message": f"Processed {len(universe_ids)} games",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error processing batch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process batch: {str(e)}"
        )


@router.post("/enqueue-keywords")
async def enqueue_keywords(
    request: CrawlerKeywordRequest,
    _: str = Depends(require_admin)
):
    """
    Search for games by keywords and add to queue.
    Requires admin access.
    """
    try:
        roblox_api = RobloxAPIService()
        queue = CrawlerQueue()

        all_universe_ids = []

        for keyword in request.keywords:
            logger.info(f"Searching keyword: {keyword}")
            universe_ids = await roblox_api.get_universe_ids_by_keyword(
                keyword=keyword,
                limit=request.limit_per_keyword
            )
            all_universe_ids.extend(universe_ids)
            logger.info(f"Found {len(universe_ids)} games for keyword '{keyword}'")

        await roblox_api.close()

        # Remove duplicates
        unique_ids = list(set(all_universe_ids))

        # Enqueue
        result = queue.enqueue(
            universe_ids=unique_ids,
            source="keyword_search",
            priority=request.priority
        )

        return CrawlerEnqueueResponse(
            success=True,
            enqueued=result['enqueued'],
            updated=result['updated'],
            message=f"Found {len(unique_ids)} unique games from {len(request.keywords)} keywords"
        )
    except Exception as e:
        logger.error(f"Error enqueueing keywords: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue keywords: {str(e)}"
        )


@router.post("/enqueue-sorts")
async def enqueue_sorts(
    request: CrawlerSortsRequest,
    _: str = Depends(require_admin)
):
    """
    Fetch games from official Roblox sorts and add to queue.
    Requires admin access.
    """
    try:
        roblox_api = RobloxAPIService()
        queue = CrawlerQueue()

        # Default sorts if none provided
        sorts = request.sorts or [
            "popular", "top_rated", "recommended", "up_and_coming",
            "premium", "most_engaging", "top_earning", "hidden_gems", "featured"
        ]

        all_universe_ids = []

        for sort_name in sorts:
            logger.info(f"Fetching sort: {sort_name}")
            universe_ids = await roblox_api.get_universe_ids_by_sort(
                sort_name=sort_name,
                limit=request.limit
            )
            all_universe_ids.extend(universe_ids)
            logger.info(f"Found {len(universe_ids)} games for sort '{sort_name}'")

        await roblox_api.close()

        # Remove duplicates
        unique_ids = list(set(all_universe_ids))

        # Enqueue
        result = queue.enqueue(
            universe_ids=unique_ids,
            source="official_sorts",
            priority=request.priority
        )

        return CrawlerEnqueueResponse(
            success=True,
            enqueued=result['enqueued'],
            updated=result['updated'],
            message=f"Found {len(unique_ids)} unique games from {len(sorts)} sorts"
        )
    except Exception as e:
        logger.error(f"Error enqueueing sorts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue sorts: {str(e)}"
        )


@router.post("/enqueue-graph")
async def enqueue_graph(
    request: CrawlerGraphRequest,
    _: str = Depends(require_admin)
):
    """
    Perform graph expansion crawl (related games, developer games, etc.)
    Requires admin access.
    """
    try:
        roblox_api = RobloxAPIService()
        queue = CrawlerQueue()

        all_universe_ids = []

        for universe_id in request.universe_ids:
            # Get related games
            related = await roblox_api.get_related_universe_ids(universe_id)
            all_universe_ids.extend(related)
            logger.info(f"Found {len(related)} related games for {universe_id}")

        await roblox_api.close()

        # Remove duplicates
        unique_ids = list(set(all_universe_ids))

        # Enqueue
        result = queue.enqueue(
            universe_ids=unique_ids,
            source="graph_expansion",
            priority=request.priority
        )

        return CrawlerEnqueueResponse(
            success=True,
            enqueued=result['enqueued'],
            updated=result['updated'],
            message=f"Found {len(unique_ids)} unique games via graph expansion"
        )
    except Exception as e:
        logger.error(f"Error enqueueing graph: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue graph: {str(e)}"
        )


@router.post("/run-full")
async def run_full_crawl(_: str = Depends(require_admin)):
    """
    Run a full crawl cycle: enqueue all official sorts, then process a batch.
    Requires admin access.
    """
    try:
        # Enqueue official sorts (await the coroutine, ignore the result)
        sorts_request = CrawlerSortsRequest(sorts=[], limit=50, priority=7)
        await enqueue_sorts(sorts_request, _)

        # Process a batch (await the coroutine)
        result = await process_batch(limit=50, _=_)

        return {
            "success": True,
            "message": "Full crawl cycle initiated",
            "batch_result": result
        }
    except Exception as e:
        logger.error(f"Error running full crawl: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run full crawl: {str(e)}"
        )


@router.post("/enrich-llm")
async def enrich_with_llm(
    limit: int = 50,
    _: str = Depends(require_admin)
):
    """
    Generate LLM tags and summaries for games missing them.
    Requires admin access.

    Args:
        limit: Maximum number of games to enrich
    """
    try:
        from app.db.firebase import get_db, GAMES_COLLECTION
        from app.services.llm_service import LLMService

        db = get_db()
        llm_service = LLMService()

        # Find games without LLM enrichment
        games_ref = db.collection(GAMES_COLLECTION)
        # Query for games that don't have llm_enriched_at field
        games_cursor = games_ref.limit(limit).stream()

        enriched_count = 0
        skipped_count = 0

        for doc in games_cursor:
            game_data = doc.to_dict()

            # Skip if already enriched
            if game_data.get('llm_enriched_at'):
                continue

            title = game_data.get('title', '')
            description = game_data.get('description', '')
            genre = game_data.get('genre', '')

            if not title or not description:
                skipped_count += 1
                continue

            try:
                # Check content moderation
                combined_text = f"{title} {description}"
                is_safe = llm_service.moderate_text(combined_text)

                if not is_safe:
                    logger.warning(f"Content moderation failed for {doc.id}, skipping")
                    skipped_count += 1
                    continue

                # Generate tags and summary
                enrichment = llm_service.generate_tags_and_summary(
                    title=title,
                    description=description,
                    genre=genre
                )

                if enrichment.get('tags') or enrichment.get('summary'):
                    from datetime import datetime
                    doc.reference.update({
                        'tags': enrichment.get('tags', []),
                        'ai_summary': enrichment.get('summary', ''),
                        'llm_enriched_at': datetime.now()
                    })
                    enriched_count += 1
                    logger.info(f"LLM enriched game {doc.id}: {title}")
                else:
                    skipped_count += 1

            except Exception as e:
                logger.error(f"Error enriching game {doc.id}: {e}")
                skipped_count += 1

        return {
            "success": True,
            "enriched": enriched_count,
            "skipped": skipped_count,
            "message": f"Enriched {enriched_count} games with LLM tags/summaries"
        }

    except Exception as e:
        logger.error(f"Error in LLM enrichment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enrich with LLM: {str(e)}"
        )


@router.post("/embed-missing")
async def embed_missing(
    limit: int = 50,
    _: str = Depends(require_admin)
):
    """
    Generate embeddings for games that don't have them yet.
    Requires admin access.
    """
    try:
        from app.db.firebase import get_db, GAMES_COLLECTION
        from app.services.embedding_service_pinecone import EmbeddingService

        db = get_db()
        embedding_service = EmbeddingService()

        # Find games without embeddings
        games_ref = db.collection(GAMES_COLLECTION)
        games_cursor = games_ref.where("has_embedding", "==", False).limit(limit).stream()

        embedded_count = 0

        for doc in games_cursor:
            game_data = doc.to_dict()

            try:
                # Generate embedding
                game_text = embedding_service.create_game_text(game_data)
                embedding = embedding_service.generate_embedding(game_text)

                if embedding:
                    # Upsert to Pinecone
                    metadata = {
                        'title': game_data.get('title', ''),
                        'genre': game_data.get('genre', ''),
                        'creator_name': game_data.get('creator_name', ''),
                        'visits': game_data.get('visits', 0),
                        'active_players': game_data.get('active_players', 0),
                    }

                    success = embedding_service.pinecone_service.upsert_embedding(
                        universe_id=doc.id,
                        embedding=embedding,
                        metadata=metadata
                    )

                    if success:
                        from datetime import datetime
                        doc.reference.update({
                            'has_embedding': True,
                            'embedding_updated_at': datetime.now()
                        })
                        embedded_count += 1
                        logger.info(f"Generated embedding for {doc.id}")

            except Exception as e:
                logger.error(f"Error embedding game {doc.id}: {e}")

        return {
            "success": True,
            "embedded": embedded_count,
            "message": f"Generated embeddings for {embedded_count} games"
        }

    except Exception as e:
        logger.error(f"Error in embed missing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed missing games: {str(e)}"
        )


@router.post("/fix-thumbnails")
async def fix_thumbnails(
    limit: int = 100,
    _: str = Depends(require_admin)
):
    """
    Fix missing thumbnails for games.
    Requires admin access.
    """
    try:
        from app.db.firebase import get_db, GAMES_COLLECTION

        db = get_db()
        roblox_api = RobloxAPIService()

        # Find games with missing thumbnails
        games_ref = db.collection(GAMES_COLLECTION)
        # Query for empty or null thumbnail_url
        games_cursor = games_ref.where("thumbnail_url", "in", ["", None]).limit(limit).stream()

        docs = list(games_cursor)
        if not docs:
            return {
                "success": True,
                "fixed": 0,
                "message": "No games with missing thumbnails"
            }

        universe_ids = [int(doc.id) for doc in docs]
        thumbnails = await roblox_api.get_game_thumbnails(universe_ids)
        await roblox_api.close()

        fixed_count = 0
        for doc in docs:
            thumb = thumbnails.get(int(doc.id))
            if thumb:
                doc.reference.update({'thumbnail_url': thumb})
                fixed_count += 1

        return {
            "success": True,
            "fixed": fixed_count,
            "message": f"Fixed {fixed_count} thumbnails"
        }

    except Exception as e:
        logger.error(f"Error fixing thumbnails: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fix thumbnails: {str(e)}"
        )


@router.post("/regenerate-embeddings")
async def regenerate_embeddings(
    limit: int = 200,
    _: str = Depends(require_admin)
):
    """
    Regenerate embeddings for recent games.
    Requires admin access.
    """
    try:
        from app.db.firebase import get_db, GAMES_COLLECTION
        from app.services.embedding_service_pinecone import EmbeddingService
        from datetime import datetime

        db = get_db()
        embedding_service = EmbeddingService()
        games_ref = db.collection(GAMES_COLLECTION)
        games_cursor = games_ref.order_by("last_crawled", direction="DESCENDING").limit(limit).stream()

        regenerated_count = 0

        for doc in games_cursor:
            game_data = doc.to_dict()

            try:
                # Generate embedding
                game_text = embedding_service.create_game_text(game_data)
                embedding = embedding_service.generate_embedding(game_text)

                if embedding:
                    # Upsert to Pinecone
                    metadata = {
                        'title': game_data.get('title', ''),
                        'genre': game_data.get('genre', ''),
                        'creator_name': game_data.get('creator_name', ''),
                        'visits': game_data.get('visits', 0),
                        'active_players': game_data.get('active_players', 0),
                    }

                    success = embedding_service.pinecone_service.upsert_embedding(
                        universe_id=doc.id,
                        embedding=embedding,
                        metadata=metadata
                    )

                    if success:
                        doc.reference.update({
                            'has_embedding': True,
                            'embedding_updated_at': datetime.now()
                        })
                        regenerated_count += 1

            except Exception as e:
                logger.error(f"Error regenerating embedding for {doc.id}: {e}")

        return {
            "success": True,
            "regenerated": regenerated_count,
            "message": f"Regenerated {regenerated_count} embeddings"
        }

    except Exception as e:
        logger.error(f"Error regenerating embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate embeddings: {str(e)}"
        )


@router.post("/schedule-toggle")
async def schedule_toggle(
    _: str = Depends(require_admin)
):
    """
    Toggle scheduler settings.
    Requires admin access.

    Note: This is a placeholder. Actual scheduler management should be implemented
    in the scheduler service.
    """
    try:
        return {
            "success": True,
            "enabled": {
                "queue_worker": True,
                "keywords": True,
                "sorts": True,
                "graph": True,
                "embed_sweep": True,
                "thumb_fix": True,
                "weekly": True,
            },
            "message": "Scheduler settings updated (placeholder)"
        }

    except Exception as e:
        logger.error(f"Error toggling schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle schedule: {str(e)}"
        )
