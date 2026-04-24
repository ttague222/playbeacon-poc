"""
Embedding Service using Pinecone for vector storage
"""
from typing import List, Dict, Optional
from openai import OpenAI
from app.config import settings
from app.db.firebase import get_db, GAMES_COLLECTION
from app.services.pinecone_service import PineconeService
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.openai_api_key)


class EmbeddingService:
    """Service for generating and managing game embeddings with Pinecone"""

    def __init__(self):
        self.db = get_db()
        self.pinecone_service = PineconeService()
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for given text using OpenAI

        Args:
            text: Text to generate embedding for

        Returns:
            List of floats representing the embedding vector, or None on error
        """
        try:
            response = openai_client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding of dimension {len(embedding)}")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def create_game_text(self, game_data: Dict) -> str:
        """
        Create a text representation of a game for embedding generation

        Args:
            game_data: Dictionary containing game information

        Returns:
            Combined text string for embedding
        """
        parts = []

        if game_data.get('title'):
            parts.append(f"Title: {game_data['title']}")

        if game_data.get('description'):
            parts.append(f"Description: {game_data['description']}")

        if game_data.get('genre'):
            parts.append(f"Genre: {game_data['genre']}")

        if game_data.get('creator_name'):
            parts.append(f"Creator: {game_data['creator_name']}")

        return " | ".join(parts)

    def generate_game_embedding(self, universe_id: str) -> bool:
        """
        Generate and store embedding for a specific game in Pinecone

        Args:
            universe_id: The game's universe ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get game data from Firestore
            game_ref = self.db.collection(GAMES_COLLECTION).document(str(universe_id))
            game_doc = game_ref.get()

            if not game_doc.exists:
                logger.error(f"Game {universe_id} not found in Firestore")
                return False

            game_data = game_doc.to_dict()

            # Create text representation
            game_text = self.create_game_text(game_data)
            logger.info(f"Generating embedding for game {universe_id}: {game_data.get('title')}")

            # Generate embedding
            embedding = self.generate_embedding(game_text)

            if not embedding:
                logger.error(f"Failed to generate embedding for game {universe_id}")
                return False

            # Prepare metadata for Pinecone
            metadata = {
                'title': game_data.get('title', ''),
                'genre': game_data.get('genre', ''),
                'creator_name': game_data.get('creator_name', ''),
                'visits': game_data.get('visits', 0),
                'active_players': game_data.get('active_players', 0),
            }

            # Store in Pinecone
            success = self.pinecone_service.upsert_embedding(
                universe_id=universe_id,
                embedding=embedding,
                metadata=metadata
            )

            if success:
                logger.info(f"Successfully stored embedding for game {universe_id} in Pinecone")
                try:
                    game_ref.update({
                        'has_embedding': True,
                        'embedding_updated_at': firestore.SERVER_TIMESTAMP
                    })
                except Exception as update_err:
                    logger.error(f"Failed to mark has_embedding for {universe_id}: {update_err}")
            else:
                logger.error(f"Failed to store embedding for game {universe_id} in Pinecone")

            return success

        except Exception as e:
            logger.error(f"Error generating game embedding for {universe_id}: {e}")
            return False

    def generate_embeddings_batch(self, universe_ids: List[str]) -> Dict[str, bool]:
        """
        Generate embeddings for multiple games

        Args:
            universe_ids: List of game universe IDs

        Returns:
            Dictionary mapping universe_id to success status
        """
        results = {}
        vectors_to_upsert = []

        for universe_id in universe_ids:
            try:
                # Get game data from Firestore
                game_ref = self.db.collection(GAMES_COLLECTION).document(str(universe_id))
                game_doc = game_ref.get()

                if not game_doc.exists:
                    logger.warning(f"Game {universe_id} not found in Firestore")
                    results[universe_id] = False
                    continue

                game_data = game_doc.to_dict()

                # Create text representation
                game_text = self.create_game_text(game_data)

                # Generate embedding
                embedding = self.generate_embedding(game_text)

                if not embedding:
                    results[universe_id] = False
                    continue

                # Prepare metadata
                metadata = {
                    'title': game_data.get('title', ''),
                    'genre': game_data.get('genre', ''),
                    'creator_name': game_data.get('creator_name', ''),
                    'visits': game_data.get('visits', 0),
                    'active_players': game_data.get('active_players', 0),
                }

                # Add to batch
                vectors_to_upsert.append({
                    'id': str(universe_id),
                    'values': embedding,
                    'metadata': metadata
                })

                results[universe_id] = True

            except Exception as e:
                logger.error(f"Error processing game {universe_id}: {e}")
                results[universe_id] = False

        # Batch upsert to Pinecone
        if vectors_to_upsert:
            batch_success = self.pinecone_service.upsert_batch(vectors_to_upsert)
            if not batch_success:
                logger.error("Batch upsert to Pinecone failed")
                # Mark all as failed
                for vector in vectors_to_upsert:
                    results[vector['id']] = False
            else:
                # Mark Firestore docs as having embeddings
                try:
                    batch = self.db.batch()
                    for vector in vectors_to_upsert:
                        doc_ref = self.db.collection(GAMES_COLLECTION).document(vector['id'])
                        batch.update(doc_ref, {
                            'has_embedding': True,
                            'embedding_updated_at': firestore.SERVER_TIMESTAMP
                        })
                    batch.commit()
                except Exception as update_err:
                    logger.error(f"Failed to update has_embedding flags after batch upsert: {update_err}")

        logger.info(f"Batch embedding generation complete: {sum(results.values())}/{len(universe_ids)} successful")
        return results

    def generate_all_game_embeddings(self) -> int:
        """
        Generate embeddings for all games in Firestore that don't have embeddings in Pinecone

        Returns:
            Number of embeddings successfully generated
        """
        try:
            # Get all games from Firestore
            games_ref = self.db.collection(GAMES_COLLECTION)
            games = list(games_ref.stream())

            universe_ids = [game.id for game in games]
            logger.info(f"Found {len(universe_ids)} games in Firestore")

            if not universe_ids:
                logger.info("No games found to generate embeddings for")
                return 0

            # Generate embeddings in batch
            results = self.generate_embeddings_batch(universe_ids)
            successful = sum(results.values())

            logger.info(f"Generated embeddings for {successful}/{len(universe_ids)} games")

            # Update last embedding timestamp
            try:
                from datetime import datetime
                admin_status_ref = self.db.collection('admin').document('status')
                admin_status_ref.set({
                    'last_embedding': datetime.now()
                }, merge=True)
            except Exception as e:
                logger.error(f"Error updating embedding timestamp: {e}")

            return successful

        except Exception as e:
            logger.error(f"Error generating all embeddings: {e}")
            return 0
