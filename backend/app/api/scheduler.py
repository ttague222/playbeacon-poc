"""
Simple background scheduler for crawler tasks.
Note: For production, use a proper scheduler (e.g., Cloud Scheduler, Celery, APScheduler).
"""
import asyncio
import logging
from datetime import datetime, timedelta
# Import within functions to avoid circular imports
def _lazy_import_routes():
    from . import routes_pinecone  # type: ignore
    return routes_pinecone._process_queue_batch, routes_pinecone._enqueue_universe_ids
from app.services.roblox_api_service import RobloxAPIService
from app.db.firebase import get_db

logger = logging.getLogger(__name__)


class CrawlerScheduler:
    def __init__(self):
        self.running = False
        self.db = get_db()
        self.next_runs = {
            "queue_worker": None,
            "keywords": None,
            "sorts": None,
            "graph": None,
            "embed_sweep": None,
            "thumb_fix": None,
            "weekly": None,
        }
        self.enabled = {
            "queue_worker": True,
            "keywords": True,
            "sorts": True,
            "graph": True,
            "embed_sweep": True,
            "thumb_fix": True,
            "weekly": True,
        }

    async def run_hourly_queue_worker(self, batch_size: int = 20, interval_minutes: int = 60):
        """Process queue every interval."""
        if self.running:
            return
        self.running = True
        _process_queue_batch, _ = _lazy_import_routes()
        while self.running:
            try:
                self.next_runs["queue_worker"] = datetime.utcnow() + timedelta(minutes=interval_minutes)
                result = await _process_queue_batch(limit=batch_size)
                logger.info(f"[Scheduler] Queue batch processed: {result}")
            except Exception as e:
                logger.error(f"[Scheduler] Error processing queue batch: {e}")
            await asyncio.sleep(interval_minutes * 60)
        self.running = False

    async def run_daily_keyword_crawl(self, keywords: list, limit_per_keyword: int = 20, priority: int = 6):
        """Enqueue keywords daily."""
        _, _enqueue_universe_ids = _lazy_import_routes()
        while True:
            try:
                if not self.enabled.get("keywords", True):
                    self.next_runs["keywords"] = datetime.utcnow() + timedelta(days=1)
                    await asyncio.sleep(24 * 60 * 60)  # Sleep 1 day
                    continue

                roblox_service = RobloxAPIService()
                all_ids = []
                for kw in keywords:
                    try:
                        ids = await roblox_service.get_universe_ids_by_keyword(kw, limit_per_keyword)
                        all_ids.extend(ids)
                    except Exception as e:
                        logger.error(f"[Scheduler] Keyword crawl error for {kw}: {e}")
                await roblox_service.close()
                all_ids = list({int(uid) for uid in all_ids})
                _enqueue_universe_ids(self.db, all_ids, source="keyword_scheduled", priority=priority)
                logger.info(f"[Scheduler] Daily keyword crawl enqueued {len(all_ids)} ids")
                self.next_runs["keywords"] = datetime.utcnow() + timedelta(days=1)
            except Exception as e:
                logger.error(f"[Scheduler] Daily keyword crawl error: {e}")

            await asyncio.sleep(24 * 60 * 60)  # Sleep 1 day

    async def run_daily_sorts_crawl(self, sorts: list, limit: int = 50, priority: int = 6):
        """Enqueue official sorts daily."""
        _, _enqueue_universe_ids = _lazy_import_routes()
        while True:
            try:
                if not self.enabled.get("sorts", True):
                    self.next_runs["sorts"] = datetime.utcnow() + timedelta(days=1)
                    await asyncio.sleep(24 * 60 * 60)
                    continue

                roblox_service = RobloxAPIService()
                all_ids = []
                for sort_name in sorts:
                    try:
                        ids = await roblox_service.get_universe_ids_by_sort(sort_name, limit)
                        all_ids.extend(ids)
                    except Exception as e:
                        logger.error(f"[Scheduler] Sort crawl error for {sort_name}: {e}")
                await roblox_service.close()
                all_ids = list({int(uid) for uid in all_ids})
                _enqueue_universe_ids(self.db, all_ids, source="sort_scheduled", priority=priority)
                logger.info(f"[Scheduler] Daily sorts crawl enqueued {len(all_ids)} ids")
                self.next_runs["sorts"] = datetime.utcnow() + timedelta(days=1)
            except Exception as e:
                logger.error(f"[Scheduler] Daily sorts crawl error: {e}")

            await asyncio.sleep(24 * 60 * 60)

    async def run_daily_graph_crawl(self, seed_ids: list, priority: int = 6):
        """Graph expansion crawl for a list of seed universe IDs."""
        if not self.enabled.get("graph", True):
            self.next_runs["graph"] = datetime.utcnow() + timedelta(days=1)
            return
        _, _enqueue_universe_ids = _lazy_import_routes()
        roblox_service = RobloxAPIService()
        all_ids = []
        for uid in seed_ids:
            try:
                uid_int = int(uid)
            except Exception:
                continue
            related = await roblox_service.get_related_universe_ids(uid_int)
            details_map = await roblox_service.get_game_details([uid_int])
            detail = details_map.get(uid_int)
            creator = detail.get("creator", {}) if detail else {}
            creator_id = creator.get("id")
            if creator_id:
                creator_games = await roblox_service.get_creator_universe_ids(creator_id)
                all_ids.extend(creator_games)
            all_ids.extend(related)
        await roblox_service.close()
        all_ids = list({int(x) for x in all_ids})
        _enqueue_universe_ids(self.db, all_ids, source="graph_scheduled", priority=priority)
        logger.info(f"[Scheduler] Daily graph crawl enqueued {len(all_ids)} ids")
        self.next_runs["graph"] = datetime.utcnow() + timedelta(days=1)

    async def run_daily_embed_sweep(self, limit: int = 200):
        """Regenerate embeddings for recent games (daily sweep)."""
        if not self.enabled.get("embed_sweep", True):
            self.next_runs["embed_sweep"] = datetime.utcnow() + timedelta(days=1)
            return
        from app.services.embedding_service_pinecone import EmbeddingService
        from app.db.firebase import GAMES_COLLECTION

        try:
            games_ref = self.db.collection(GAMES_COLLECTION)
            games_cursor = games_ref.order_by("last_crawled", direction="DESCENDING").limit(limit).stream()
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
                    ok = embedding_service.pinecone_service.upsert_embedding(doc.id, embedding, metadata)
                    if ok:
                        doc.reference.set(
                            {"has_embedding": True, "embedding_updated_at": datetime.utcnow()},
                            merge=True,
                        )
                        regenerated += 1
            logger.info(f"[Scheduler] Daily embed sweep regenerated {regenerated} embeddings")
        except Exception as e:
            logger.error(f"[Scheduler] Embed sweep error: {e}")
        self.next_runs["embed_sweep"] = datetime.utcnow() + timedelta(days=1)

    async def run_daily_thumbnail_fix(self, limit: int = 100):
        """Fix missing thumbnails daily."""
        if not self.enabled.get("thumb_fix", True):
            self.next_runs["thumb_fix"] = datetime.utcnow() + timedelta(days=1)
            return
        from app.services.roblox_api_service import RobloxAPIService
        from app.db.firebase import GAMES_COLLECTION

        try:
            games_ref = self.db.collection(GAMES_COLLECTION)
            games_cursor = games_ref.where("thumbnail_url", "==", "").limit(limit).stream()
            docs = list(games_cursor)
            if not docs:
                self.next_runs["thumb_fix"] = datetime.utcnow() + timedelta(days=1)
                return
            ids = [int(doc.id) for doc in docs]
            roblox = RobloxAPIService()
            thumbs = await roblox.get_game_thumbnails(ids)
            await roblox.close()
            fixed = 0
            for d in docs:
                thumb = thumbs.get(int(d.id))
                if thumb:
                    d.reference.set({"thumbnail_url": thumb}, merge=True)
                    fixed += 1
            logger.info(f"[Scheduler] Daily thumbnail fix updated {fixed} games")
        except Exception as e:
            logger.error(f"[Scheduler] Thumbnail fix error: {e}")
        self.next_runs["thumb_fix"] = datetime.utcnow() + timedelta(days=1)

    async def run_weekly_deep_crawl(self, keywords: list, limit_per_keyword: int = 50, priority: int = 5):
        """Weekly deep keyword crawl."""
        if not self.enabled.get("weekly", True):
            self.next_runs["weekly"] = datetime.utcnow() + timedelta(days=7)
            return
        _, _enqueue_universe_ids = _lazy_import_routes()
        roblox_service = RobloxAPIService()
        all_ids = []
        for kw in keywords:
            try:
                ids = await roblox_service.get_universe_ids_by_keyword(kw, limit_per_keyword)
                all_ids.extend(ids)
            except Exception as e:
                logger.error(f"[Scheduler] Weekly keyword crawl error for {kw}: {e}")
        await roblox_service.close()
        all_ids = list({int(uid) for uid in all_ids})
        _enqueue_universe_ids(self.db, all_ids, source="weekly_keyword", priority=priority)
        logger.info(f"[Scheduler] Weekly keyword crawl enqueued {len(all_ids)} ids")
        self.next_runs["weekly"] = datetime.utcnow() + timedelta(days=7)


scheduler = CrawlerScheduler()
