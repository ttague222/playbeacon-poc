from openai import OpenAI
from typing import List, Optional
from app.db.firebase import get_db, GAMES_COLLECTION
from app.models.firestore_models import Game
from app.config import settings
import logging
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing embeddings using OpenAI"""

    def __init__(self):
        self.db = get_db()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    def create_game_text_representation(self, game: Game) -> str:
        """Create text representation of game for embedding"""
        parts = []

        if game.title:
            parts.append(f"Title: {game.title}")

        if game.description:
            # Limit description length to avoid token limits
            description = game.description[:500]
            parts.append(f"Description: {description}")

        if game.genre:
            parts.append(f"Genre: {game.genre}")

        if game.creator_name:
            parts.append(f"Creator: {game.creator_name}")

        parts.append(f"Active Players: {game.active_players}")
        parts.append(f"Visits: {game.visits}")
        parts.append(f"Upvotes: {game.votes_up}")

        return "\n".join(parts)

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using OpenAI API"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def generate_game_embedding(self, game: Game) -> Optional[List[float]]:
        """Generate embedding for a game"""
        text = self.create_game_text_representation(game)
        return self.generate_embedding(text)

    def update_game_embedding(self, universe_id: str) -> bool:
        """Generate and update embedding for a specific game"""
        try:
            games_ref = self.db.collection(GAMES_COLLECTION)
            doc_ref = games_ref.document(universe_id)
            doc = doc_ref.get()

            if not doc.exists:
                logger.error(f"Game {universe_id} not found")
                return False

            game = Game.from_dict(doc.to_dict())
            embedding = self.generate_game_embedding(game)

            if embedding:
                doc_ref.update({'embedding': embedding})
                logger.info(f"Updated embedding for game {universe_id}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error updating game embedding: {e}")
            return False

    def update_all_missing_embeddings(self) -> int:
        """Generate embeddings for all games that don't have one"""
        games_ref = self.db.collection(GAMES_COLLECTION)

        # Query games without embeddings
        # Note: Firestore doesn't support NOT NULL queries, so we get all and filter
        docs = games_ref.stream()

        count = 0
        for doc in docs:
            try:
                game_data = doc.to_dict()

                # Skip if already has embedding
                if game_data.get('embedding'):
                    continue

                game = Game.from_dict(game_data)
                embedding = self.generate_game_embedding(game)

                if embedding:
                    games_ref.document(doc.id).update({'embedding': embedding})
                    count += 1
                    logger.info(f"Generated embedding for {game.title}")

            except Exception as e:
                logger.error(f"Error generating embedding for {doc.id}: {e}")

        logger.info(f"Generated {count} embeddings")
        return count

    def compute_average_embedding(self, embeddings: List[List[float]]) -> Optional[List[float]]:
        """Compute average of multiple embeddings"""
        if not embeddings:
            return None

        try:
            # Convert to numpy array
            embeddings_array = np.array(embeddings)

            # Compute mean
            avg_embedding = np.mean(embeddings_array, axis=0)

            # Normalize
            norm = np.linalg.norm(avg_embedding)
            if norm > 0:
                avg_embedding = avg_embedding / norm

            return avg_embedding.tolist()

        except Exception as e:
            logger.error(f"Error computing average embedding: {e}")
            return None
