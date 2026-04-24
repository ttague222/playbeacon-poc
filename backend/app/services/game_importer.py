"""
Game Importer Service

Handles the complete pipeline of importing games: fetch metadata, validate, enrich, and store.
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from app.db.firebase import get_db
from app.services.roblox_api_service import RobloxAPIService
from app.services.metadata_validator import MetadataValidator
from app.services.crawler_queue import CrawlerQueue
from app.services.embedding_service_pinecone import EmbeddingService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class GameImporter:
    """Service for importing and enriching game data"""

    GAMES_COLLECTION = "games"

    def __init__(self, generate_embeddings: bool = True, generate_llm_enrichment: bool = False):
        """
        Initialize GameImporter

        Args:
            generate_embeddings: Whether to generate embeddings after import (default: True)
            generate_llm_enrichment: Whether to generate LLM tags/summaries (default: False, costs API calls)
        """
        self.db = get_db()
        self.roblox_api = RobloxAPIService()
        self.validator = MetadataValidator()
        self.queue = CrawlerQueue()
        self.embedding_service = EmbeddingService() if generate_embeddings else None
        self.llm_service = LLMService() if generate_llm_enrichment else None
        self.generate_embeddings = generate_embeddings
        self.generate_llm_enrichment = generate_llm_enrichment

    async def close(self):
        """Close HTTP clients"""
        await self.roblox_api.close()

    async def import_batch(self, universe_ids: List[int], source: str = "manual") -> Dict:
        """
        Import a batch of games.

        Args:
            universe_ids: List of universe IDs to import
            source: Source of the import

        Returns:
            Dict with import statistics
        """
        stats = {
            'total': len(universe_ids),
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }

        # Fetch game details in batch
        logger.info(f"Fetching details for {len(universe_ids)} games")
        game_details = await self.roblox_api.get_game_details(universe_ids)

        # Fetch thumbnails in batch
        logger.info(f"Fetching thumbnails for {len(universe_ids)} games")
        thumbnails = await self.roblox_api.get_game_thumbnails(universe_ids)

        for universe_id in universe_ids:
            try:
                # Mark as processing in queue
                self.queue.mark_processing(universe_id)

                # Get game data
                game_data = game_details.get(universe_id)
                if not game_data:
                    logger.warning(f"No data found for universe_id: {universe_id}")
                    self.queue.mark_error(universe_id, "No data returned from Roblox API")
                    stats['failed'] += 1
                    stats['errors'].append({
                        'universe_id': universe_id,
                        'error': 'No data returned'
                    })
                    continue

                # Build metadata object
                metadata = self._build_metadata(universe_id, game_data, thumbnails.get(universe_id))

                # Validate metadata
                is_valid, error_reason = self.validator.validate(metadata)
                if not is_valid:
                    logger.info(f"Skipping universe_id {universe_id}: {error_reason}")
                    self.queue.mark_done(universe_id)  # Remove from queue (invalid game)
                    stats['skipped'] += 1
                    continue

                # Enrich metadata
                enriched = self.validator.enrich_metadata(metadata)

                # Check if game already exists
                doc_ref = self.db.collection(self.GAMES_COLLECTION).document(str(universe_id))
                existing_doc = doc_ref.get()

                if existing_doc.exists:
                    # Update existing game
                    self._update_game(doc_ref, existing_doc, enriched, source)
                    stats['updated'] += 1
                    logger.info(f"Updated game: {universe_id} - {enriched['title']}")
                else:
                    # Create new game
                    self._create_game(doc_ref, enriched, source)
                    stats['imported'] += 1
                    logger.info(f"Imported new game: {universe_id} - {enriched['title']}")

                # Mark as done in queue
                self.queue.mark_done(universe_id)

            except Exception as e:
                logger.error(f"Error importing universe_id {universe_id}: {e}", exc_info=True)
                self.queue.mark_error(universe_id, str(e))
                stats['failed'] += 1
                stats['errors'].append({
                    'universe_id': universe_id,
                    'error': str(e)
                })

        logger.info(f"Import batch complete: {stats}")

        # Phase 2: Post-import enrichment (embeddings + LLM)
        successfully_imported = []
        for universe_id in universe_ids:
            doc_ref = self.db.collection(self.GAMES_COLLECTION).document(str(universe_id))
            if doc_ref.get().exists:
                successfully_imported.append(universe_id)

        if successfully_imported:
            enrichment_stats = await self._enrich_batch(successfully_imported)
            stats['embeddings_generated'] = enrichment_stats.get('embeddings_generated', 0)
            stats['llm_enriched'] = enrichment_stats.get('llm_enriched', 0)

        return stats

    def _build_metadata(self, universe_id: int, game_data: Dict, thumbnail_url: Optional[str]) -> Dict:
        """Build metadata object from Roblox API response"""
        return {
            'id': universe_id,
            'title': game_data.get('name', ''),
            'description': game_data.get('description', ''),
            'genre': game_data.get('genre'),
            'creatorId': game_data.get('creator', {}).get('id', 0),
            'creatorName': game_data.get('creator', {}).get('name', ''),
            'creatorType': game_data.get('creator', {}).get('type', 'User'),
            'visits': game_data.get('visits', 0),
            'playing': game_data.get('playing', 0),
            'votesUp': game_data.get('upVotes', 0) or game_data.get('likes', 0),
            'votesDown': game_data.get('downVotes', 0) or game_data.get('dislikes', 0),
            'thumbnailUrl': thumbnail_url,
            'created': game_data.get('created'),
            'updated': game_data.get('updated'),
            'rootPlaceId': game_data.get('rootPlaceId'),
            'maxPlayers': game_data.get('maxPlayers', 0),
            'price': game_data.get('price', 0),
            'copyingAllowed': game_data.get('copyingAllowed', False),
        }

    def _create_game(self, doc_ref, enriched: Dict, source: str):
        """Create a new game document"""
        doc_ref.set({
            'universe_id': enriched['id'],
            'title': enriched['title'],
            'description': enriched['description'],
            'genre': enriched.get('genre'),
            'creator_name': enriched.get('creatorName'),
            'creator_id': enriched.get('creatorId'),
            'creator_type': enriched.get('creatorType', 'User'),
            'visits': enriched['visits'],
            'active_players': enriched.get('playing', 0),
            'votes_up': enriched['votesUp'],
            'votes_down': enriched['votesDown'],
            'like_ratio': enriched['like_ratio'],
            'thumbnail_url': enriched.get('thumbnailUrl'),
            'root_place_id': enriched.get('rootPlaceId'),
            'max_players': enriched.get('maxPlayers', 0),
            'price': enriched.get('price', 0),
            'created_at': enriched.get('created'),
            'updated_at': enriched.get('updated'),
            'last_crawled': enriched['last_crawled'],
            'has_embedding': enriched['has_embedding'],
            'is_popular': enriched['is_popular'],
            'is_trending': enriched['is_trending'],
            'is_new': enriched['is_new'],
            'sources': [source],
            'import_date': datetime.now(),
        })

    def _update_game(self, doc_ref, existing_doc, enriched: Dict, source: str):
        """Update an existing game document"""
        existing_data = existing_doc.to_dict()

        # Calculate is_trending based on visit delta
        old_visits = existing_data.get('visits', 0)
        new_visits = enriched['visits']
        visit_delta = new_visits - old_visits
        is_trending = visit_delta > (old_visits * 0.1)  # 10% increase

        # Add source if not already present
        sources = existing_data.get('sources', [])
        if source not in sources:
            sources.append(source)

        # Calculate is_new
        created_at = enriched.get('created')
        is_new = False
        if created_at:
            try:
                if isinstance(created_at, str):
                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created_dt = created_at
                thirty_days_ago = datetime.now().replace(tzinfo=created_dt.tzinfo) - timedelta(days=30)
                is_new = created_dt > thirty_days_ago
            except:
                pass

        doc_ref.update({
            'title': enriched['title'],
            'description': enriched['description'],
            'genre': enriched.get('genre'),
            'creator_name': enriched.get('creatorName'),
            'visits': enriched['visits'],
            'active_players': enriched.get('playing', 0),
            'votes_up': enriched['votesUp'],
            'votes_down': enriched['votesDown'],
            'like_ratio': enriched['like_ratio'],
            'thumbnail_url': enriched.get('thumbnailUrl'),
            'updated_at': enriched.get('updated'),
            'last_crawled': enriched['last_crawled'],
            'is_popular': enriched['is_popular'],
            'is_trending': is_trending,
            'is_new': is_new,
            'sources': sources,
        })

    async def _enrich_batch(self, universe_ids: List[int]) -> Dict:
        """
        Generate embeddings and LLM enrichment for a batch of games.

        Args:
            universe_ids: List of universe IDs to enrich

        Returns:
            Dict with enrichment statistics
        """
        stats = {
            'embeddings_generated': 0,
            'llm_enriched': 0,
            'errors': []
        }

        if not self.generate_embeddings and not self.generate_llm_enrichment:
            return stats

        for universe_id in universe_ids:
            try:
                doc_ref = self.db.collection(self.GAMES_COLLECTION).document(str(universe_id))
                game_doc = doc_ref.get()

                if not game_doc.exists:
                    continue

                game_data = game_doc.to_dict()

                # Generate embedding
                if self.generate_embeddings and self.embedding_service:
                    try:
                        game_text = self.embedding_service.create_game_text(game_data)
                        embedding = self.embedding_service.generate_embedding(game_text)

                        if embedding:
                            # Upsert to Pinecone
                            metadata = {
                                'title': game_data.get('title', ''),
                                'genre': game_data.get('genre', ''),
                                'creator_name': game_data.get('creator_name', ''),
                                'visits': game_data.get('visits', 0),
                                'active_players': game_data.get('active_players', 0),
                            }

                            success = self.embedding_service.pinecone_service.upsert_embedding(
                                universe_id=str(universe_id),
                                embedding=embedding,
                                metadata=metadata
                            )

                            if success:
                                doc_ref.update({
                                    'has_embedding': True,
                                    'embedding_updated_at': datetime.now()
                                })
                                stats['embeddings_generated'] += 1
                                logger.info(f"Generated embedding for {universe_id}")

                    except Exception as embed_error:
                        logger.error(f"Embedding error for {universe_id}: {embed_error}")

                # Generate LLM tags and summary
                if self.generate_llm_enrichment and self.llm_service:
                    try:
                        title = game_data.get('title', '')
                        description = game_data.get('description', '')
                        genre = game_data.get('genre', '')

                        if title and description:
                            # Check content moderation
                            combined_text = f"{title} {description}"
                            is_safe = self.llm_service.moderate_text(combined_text)

                            if is_safe:
                                enrichment = self.llm_service.generate_tags_and_summary(
                                    title=title,
                                    description=description,
                                    genre=genre
                                )

                                if enrichment.get('tags') or enrichment.get('summary'):
                                    doc_ref.update({
                                        'tags': enrichment.get('tags', []),
                                        'ai_summary': enrichment.get('summary', ''),
                                        'llm_enriched_at': datetime.now()
                                    })
                                    stats['llm_enriched'] += 1
                                    logger.info(f"LLM enriched {universe_id}")
                            else:
                                logger.warning(f"Content moderation failed for {universe_id}, skipping LLM enrichment")

                    except Exception as llm_error:
                        logger.error(f"LLM enrichment error for {universe_id}: {llm_error}")

            except Exception as e:
                logger.error(f"Error enriching {universe_id}: {e}")
                stats['errors'].append({'universe_id': universe_id, 'error': str(e)})

        logger.info(f"Enrichment batch complete: {stats['embeddings_generated']} embeddings, {stats['llm_enriched']} LLM enrichments")
        return stats
