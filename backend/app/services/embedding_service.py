from openai import OpenAI
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.models import Game
from app.config import settings
import logging
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing embeddings using OpenAI"""

    def __init__(self, db: Session):
        self.db = db
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
            game = self.db.query(Game).filter(Game.universe_id == universe_id).first()

            if not game:
                logger.error(f"Game {universe_id} not found")
                return False

            embedding = self.generate_game_embedding(game)

            if embedding:
                game.embedding = embedding
                self.db.commit()
                logger.info(f"Updated embedding for game {universe_id}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error updating game embedding: {e}")
            self.db.rollback()
            return False

    def update_all_missing_embeddings(self) -> int:
        """Generate embeddings for all games that don't have one"""
        games_without_embeddings = self.db.query(Game).filter(Game.embedding == None).all()

        count = 0
        for game in games_without_embeddings:
            try:
                embedding = self.generate_game_embedding(game)

                if embedding:
                    game.embedding = embedding
                    self.db.commit()
                    count += 1
                    logger.info(f"Generated embedding for {game.title}")

            except Exception as e:
                logger.error(f"Error generating embedding for {game.universe_id}: {e}")
                self.db.rollback()

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
