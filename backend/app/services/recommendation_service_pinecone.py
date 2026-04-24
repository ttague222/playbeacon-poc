"""
Recommendation Service using Pinecone for similarity search
"""
from typing import List, Dict, Optional
from openai import OpenAI
from app.config import settings
from app.db.firebase import get_db, GAMES_COLLECTION, USER_PROFILES_COLLECTION, USER_FEEDBACK_COLLECTION
from app.services.pinecone_service import PineconeService
from firebase_admin import firestore
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.openai_api_key)


class RecommendationService:
    """Service for generating game recommendations using Pinecone"""

    def __init__(self):
        self.db = get_db()
        self.pinecone_service = PineconeService()
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    def get_game_by_id(self, universe_id: str) -> Optional[Dict]:
        """
        Retrieve game data from Firestore

        Args:
            universe_id: The game's universe ID

        Returns:
            Game data dictionary or None
        """
        try:
            game_ref = self.db.collection(GAMES_COLLECTION).document(str(universe_id))
            game_doc = game_ref.get()

            if game_doc.exists:
                game_data = game_doc.to_dict()
                game_data['universe_id'] = game_doc.id
                return game_data
            return None

        except Exception as e:
            logger.error(f"Error retrieving game {universe_id}: {e}")
            return None

    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for given text

        Args:
            text: Text to generate embedding for

        Returns:
            Embedding vector or None on error
        """
        try:
            response = openai_client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Error generating text embedding: {e}")
            return None

    def get_similar_games(
        self,
        universe_id: str,
        top_k: int = 10,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Find games similar to a given game using Pinecone

        Args:
            universe_id: The reference game's universe ID
            top_k: Number of similar games to return
            filter_dict: Optional metadata filter

        Returns:
            List of similar games with metadata
        """
        try:
            # First, we need to get the embedding from Pinecone by querying with the game's ID
            # We'll fetch the game first and regenerate its embedding, or query by fetching
            game_data = self.get_game_by_id(universe_id)
            if not game_data:
                logger.error(f"Game {universe_id} not found")
                return []

            # Create game text and generate embedding
            game_text = self._create_game_text(game_data)
            embedding = self.generate_text_embedding(game_text)

            if not embedding:
                logger.error(f"Could not generate embedding for game {universe_id}")
                return []

            # Query Pinecone for similar vectors
            matches = self.pinecone_service.query_similar(
                embedding=embedding,
                top_k=top_k + 1,  # +1 to account for the query game itself
                filter_dict=filter_dict
            )

            # Remove the query game from results and enrich with Firestore data
            similar_games = []
            for match in matches:
                # Skip the query game itself
                if match['id'] == str(universe_id):
                    continue

                # Get full game data from Firestore
                game = self.get_game_by_id(match['id'])
                if game:
                    game['similarity_score'] = match['score']
                    similar_games.append(game)

                # Stop when we have enough results
                if len(similar_games) >= top_k:
                    break

            logger.info(f"Found {len(similar_games)} similar games for {universe_id}")
            return similar_games

        except Exception as e:
            logger.error(f"Error finding similar games for {universe_id}: {e}")
            return []

    def get_recommendations_by_text(
        self,
        query_text: str,
        top_k: int = 10,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Find games based on text description using Pinecone

        Args:
            query_text: Text description to search for
            top_k: Number of games to return
            filter_dict: Optional metadata filter

        Returns:
            List of recommended games
        """
        try:
            # Generate embedding for the query text
            embedding = self.generate_text_embedding(query_text)

            if not embedding:
                logger.error("Could not generate embedding for query text")
                return []

            # Query Pinecone
            matches = self.pinecone_service.query_similar(
                embedding=embedding,
                top_k=top_k,
                filter_dict=filter_dict
            )

            # Enrich with Firestore data
            recommended_games = []
            for match in matches:
                game = self.get_game_by_id(match['id'])
                if game:
                    game['similarity_score'] = match['score']
                    recommended_games.append(game)

            logger.info(f"Found {len(recommended_games)} games matching text query")
            return recommended_games

        except Exception as e:
            logger.error(f"Error getting recommendations by text: {e}")
            return []

    def get_personalized_recommendations(
        self,
        user_id: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Get personalized recommendations based on user's interaction history

        Args:
            user_id: User's unique identifier
            top_k: Number of recommendations to return

        Returns:
            List of recommended games
        """
        try:
            user_ref = self.db.collection(USER_PROFILES_COLLECTION).document(user_id)
            feedback_ref = user_ref.collection('feedback')
            # Get all feedback and filter in memory to avoid requiring composite index
            feedback_docs = list(feedback_ref.stream())

            # Filter for likes only and get universe_ids
            liked_game_ids = []
            for doc in feedback_docs:
                data = doc.to_dict()
                # Check if feedback is 1 (like)
                if data.get('feedback') == 1 and data.get('universe_id'):
                    liked_game_ids.append(data.get('universe_id'))

            if not liked_game_ids:
                logger.info(f"No user feedback found for {user_id}, returning popular games")
                return self.get_popular_games(top_k)

            # Generate combined embedding from liked games
            liked_embeddings = []
            for game_id in liked_game_ids[:5]:  # Use top 5 most recent likes
                game_data = self.get_game_by_id(game_id)
                if game_data:
                    game_text = self._create_game_text(game_data)
                    embedding = self.generate_text_embedding(game_text)
                    if embedding:
                        liked_embeddings.append(embedding)

            if not liked_embeddings:
                logger.warning(f"Could not generate embeddings for user {user_id}'s liked games")
                return self.get_popular_games(top_k)

            # Average the embeddings to create a user preference vector
            avg_embedding = [
                sum(emb[i] for emb in liked_embeddings) / len(liked_embeddings)
                for i in range(self.dimensions)
            ]

            # Query Pinecone with the averaged embedding
            matches = self.pinecone_service.query_similar(
                embedding=avg_embedding,
                top_k=top_k * 2  # Get more to filter out already liked games
            )

            # Filter out games the user already liked and enrich with data
            recommended_games = []
            for match in matches:
                # Skip if user already interacted with this game
                if match['id'] in liked_game_ids:
                    continue

                game = self.get_game_by_id(match['id'])
                if game:
                    game['similarity_score'] = match['score']
                    recommended_games.append(game)

                # Stop when we have enough recommendations
                if len(recommended_games) >= top_k:
                    break

            logger.info(f"Generated {len(recommended_games)} personalized recommendations for user {user_id}")
            return recommended_games

        except Exception as e:
            logger.error(f"Error getting personalized recommendations for {user_id}: {e}")
            return []

    def get_popular_games(self, limit: int = 10) -> List[Dict]:
        """
        Get popular games as fallback recommendations

        Args:
            limit: Number of games to return

        Returns:
            List of popular games
        """
        try:
            games_ref = self.db.collection(GAMES_COLLECTION)
            # Order by visits (popularity metric)
            popular_query = games_ref.order_by('visits', direction='DESCENDING').limit(limit)
            popular_docs = list(popular_query.stream())

            popular_games = []
            for doc in popular_docs:
                game_data = doc.to_dict()
                game_data['universe_id'] = doc.id
                popular_games.append(game_data)

            return popular_games

        except Exception as e:
            logger.error(f"Error getting popular games: {e}")
            return []

    def record_user_feedback(
        self,
        user_id: str,
        universe_id: str,
        feedback_type: str
    ) -> bool:
        """
        Record user feedback (like/dislike) for a game

        Args:
            user_id: User's unique identifier
            universe_id: Game's universe ID
            feedback_type: Type of feedback ('like', 'dislike', 'view', etc.)

        Returns:
            True if successful, False otherwise
        """
        try:
            user_ref = self.db.collection(USER_PROFILES_COLLECTION).document(user_id)
            feedback_ref = user_ref.collection('feedback').document(str(universe_id))

            feedback_data = {
                'user_id': user_id,
                'universe_id': str(universe_id),
                'feedback_type': feedback_type,
                'timestamp': datetime.now()
            }

            feedback_ref.set(feedback_data, merge=True)

            # Update counters on profile
            count_updates = {
                'updated_at': datetime.now()
            }
            if feedback_type == 'like':
                count_updates['liked_count'] = firestore.Increment(1)
            elif feedback_type == 'dislike':
                count_updates['disliked_count'] = firestore.Increment(1)

            user_ref.set(count_updates, merge=True)

            logger.info(f"Recorded {feedback_type} feedback from user {user_id} for game {universe_id}")
            return True

        except Exception as e:
            logger.error(f"Error recording user feedback: {e}")
            return False

    def _create_game_text(self, game_data: Dict) -> str:
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
