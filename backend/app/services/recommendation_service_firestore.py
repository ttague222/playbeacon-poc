from typing import List, Optional, Dict
from app.db.firebase import get_db, GAMES_COLLECTION, USER_PROFILES_COLLECTION, USER_FEEDBACK_COLLECTION
from app.models.firestore_models import Game, UserProfile, UserFeedback
from app.services.embedding_service_firestore import EmbeddingService
import logging
import numpy as np

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating game recommendations using vector similarity"""

    def __init__(self):
        self.db = get_db()
        self.embedding_service = EmbeddingService()

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get or create user profile"""
        profiles_ref = self.db.collection(USER_PROFILES_COLLECTION)
        doc_ref = profiles_ref.document(user_id)
        doc = doc_ref.get()

        if not doc.exists:
            # Create new profile
            profile = UserProfile(user_id=user_id, profile_embedding=None)
            doc_ref.set(profile.to_dict())
            return profile
        else:
            # Add user_id from document ID since Firestore doesn't store it in the document
            data = doc.to_dict()
            data['user_id'] = user_id
            return UserProfile.from_dict(data)

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            a_array = np.array(a)
            b_array = np.array(b)

            dot_product = np.dot(a_array, b_array)
            norm_a = np.linalg.norm(a_array)
            norm_b = np.linalg.norm(b_array)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return dot_product / (norm_a * norm_b)
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    def get_popular_games(self, limit: int = 10, exclude_universe_ids: List[str] = None) -> List[Game]:
        """Get popular games when no user embedding exists"""
        games_ref = self.db.collection(GAMES_COLLECTION)
        docs = games_ref.stream()

        games = []
        for doc in docs:
            game_data = doc.to_dict()

            # Skip if no embedding
            if not game_data.get('embedding'):
                continue

            # Skip excluded games
            if exclude_universe_ids and game_data.get('universe_id') in exclude_universe_ids:
                continue

            games.append(Game.from_dict(game_data))

        # Sort by popularity (visits + active_players * 1000)
        games.sort(key=lambda g: g.visits + g.active_players * 1000, reverse=True)

        return games[:limit]

    def get_similar_games(
        self,
        user_embedding: List[float],
        limit: int = 10,
        exclude_universe_ids: List[str] = None
    ) -> List[Game]:
        """Get games similar to user's taste using cosine similarity"""
        games_ref = self.db.collection(GAMES_COLLECTION)
        docs = games_ref.stream()

        games_with_similarity = []
        for doc in docs:
            game_data = doc.to_dict()

            # Skip if no embedding
            if not game_data.get('embedding'):
                continue

            # Skip excluded games
            if exclude_universe_ids and game_data.get('universe_id') in exclude_universe_ids:
                continue

            # Calculate similarity
            similarity = self.cosine_similarity(user_embedding, game_data['embedding'])
            games_with_similarity.append((Game.from_dict(game_data), similarity))

        # Sort by similarity (higher is better)
        games_with_similarity.sort(key=lambda x: x[1], reverse=True)

        # Return just the games (without similarity scores)
        return [game for game, _ in games_with_similarity[:limit]]

    def get_user_feedback_universe_ids(self, user_id: str) -> List[str]:
        """Get all universe IDs the user has given feedback on"""
        feedback_ref = self.db.collection(USER_FEEDBACK_COLLECTION)
        query = feedback_ref.where('user_id', '==', user_id)
        docs = query.stream()

        universe_ids = []
        for doc in docs:
            feedback_data = doc.to_dict()
            universe_ids.append(feedback_data.get('universe_id'))

        return list(set(universe_ids))  # Remove duplicates

    def get_recommendations(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get personalized game recommendations for a user"""

        # Get user profile
        profile = self.get_user_profile(user_id)

        # Get games user has already seen
        seen_universe_ids = self.get_user_feedback_universe_ids(user_id)

        # Get recommendations
        if profile.profile_embedding is None:
            # No user embedding yet - return popular games
            logger.info(f"User {user_id} has no embedding, returning popular games")
            games = self.get_popular_games(limit, seen_universe_ids)
        else:
            # Use user embedding for similarity search
            logger.info(f"Getting similar games for user {user_id}")
            games = self.get_similar_games(profile.profile_embedding, limit, seen_universe_ids)

        # Convert to dict format
        recommendations = []
        for game in games:
            recommendations.append({
                "universe_id": game.universe_id,
                "title": game.title,
                "description": game.description,
                "thumbnail_url": game.thumbnail_url,
                "creator_name": game.creator_name,
                "visits": game.visits,
                "active_players": game.active_players,
                "votes_up": game.votes_up,
                "votes_down": game.votes_down,
                "genre": game.genre
            })

        return recommendations

    def update_user_embedding(self, user_id: str) -> bool:
        """Update user embedding based on liked games"""
        try:
            # Get all liked games (feedback = 1)
            feedback_ref = self.db.collection(USER_FEEDBACK_COLLECTION)
            query = feedback_ref.where('user_id', '==', user_id).where('feedback', '==', 1)
            liked_docs = query.stream()

            liked_universe_ids = []
            for doc in liked_docs:
                feedback_data = doc.to_dict()
                liked_universe_ids.append(feedback_data.get('universe_id'))

            if not liked_universe_ids:
                logger.info(f"User {user_id} has no liked games yet")
                return False

            # Get embeddings of liked games
            games_ref = self.db.collection(GAMES_COLLECTION)
            embeddings = []

            for universe_id in liked_universe_ids:
                doc = games_ref.document(universe_id).get()
                if doc.exists:
                    game_data = doc.to_dict()
                    if game_data.get('embedding'):
                        embeddings.append(game_data['embedding'])

            if not embeddings:
                logger.error(f"No valid game embeddings found for user {user_id}")
                return False

            # Compute average embedding
            avg_embedding = self.embedding_service.compute_average_embedding(embeddings)

            if avg_embedding is None:
                return False

            # Update user profile
            profiles_ref = self.db.collection(USER_PROFILES_COLLECTION)
            profiles_ref.document(user_id).update({
                'embedding': avg_embedding,
                'updated_at': UserProfile(user_id=user_id).updated_at
            })

            logger.info(f"Updated embedding for user {user_id} based on {len(embeddings)} liked games")
            return True

        except Exception as e:
            logger.error(f"Error updating user embedding: {e}")
            return False

    def save_feedback(self, user_id: str, universe_id: str, feedback: int) -> bool:
        """Save user feedback and update user embedding"""
        try:
            # Ensure user profile exists
            self.get_user_profile(user_id)

            # Check if feedback already exists
            feedback_ref = self.db.collection(USER_FEEDBACK_COLLECTION)
            query = feedback_ref.where('user_id', '==', user_id).where('universe_id', '==', universe_id)
            existing_docs = list(query.stream())

            if existing_docs:
                # Update existing feedback
                existing_docs[0].reference.update({'feedback': feedback})
            else:
                # Create new feedback
                new_feedback = UserFeedback(
                    user_id=user_id,
                    universe_id=universe_id,
                    feedback=feedback
                )
                feedback_ref.add(new_feedback.to_dict())

            # Update user embedding if feedback is like or dislike (not skip)
            if feedback != 0:
                self.update_user_embedding(user_id)

            return True

        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            return False
