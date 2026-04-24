from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.models.models import Game, UserProfile, UserFeedback
from app.services.embedding_service import EmbeddingService
import logging

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating game recommendations using vector similarity"""

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService(db)

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get or create user profile"""
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

        if not profile:
            profile = UserProfile(user_id=user_id, embedding=None)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)

        return profile

    def get_popular_games(self, limit: int = 10, exclude_universe_ids: List[str] = None) -> List[Game]:
        """Get popular games when no user embedding exists"""
        query = self.db.query(Game).filter(Game.embedding != None)

        if exclude_universe_ids:
            query = query.filter(~Game.universe_id.in_(exclude_universe_ids))

        # Order by a combination of visits and active players
        games = query.order_by(
            (Game.visits + Game.active_players * 1000).desc()
        ).limit(limit).all()

        return games

    def get_similar_games(
        self,
        user_embedding: List[float],
        limit: int = 10,
        exclude_universe_ids: List[str] = None
    ) -> List[Game]:
        """Get games similar to user's taste using cosine similarity"""

        # Build the query with vector similarity
        query = self.db.query(
            Game,
            Game.embedding.cosine_distance(user_embedding).label("distance")
        ).filter(Game.embedding != None)

        # Exclude already seen games
        if exclude_universe_ids:
            query = query.filter(~Game.universe_id.in_(exclude_universe_ids))

        # Order by similarity (lower distance = more similar)
        results = query.order_by("distance").limit(limit).all()

        # Extract just the Game objects
        games = [result[0] for result in results]

        return games

    def get_user_feedback_universe_ids(self, user_id: str) -> List[str]:
        """Get all universe IDs the user has given feedback on"""
        feedbacks = self.db.query(UserFeedback.universe_id).filter(
            UserFeedback.user_id == user_id
        ).distinct().all()

        return [f[0] for f in feedbacks]

    def get_recommendations(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get personalized game recommendations for a user"""

        # Get user profile
        profile = self.get_user_profile(user_id)

        # Get games user has already seen
        seen_universe_ids = self.get_user_feedback_universe_ids(user_id)

        # Get recommendations
        if profile.embedding is None:
            # No user embedding yet - return popular games
            logger.info(f"User {user_id} has no embedding, returning popular games")
            games = self.get_popular_games(limit, seen_universe_ids)
        else:
            # Use user embedding for similarity search
            logger.info(f"Getting similar games for user {user_id}")
            games = self.get_similar_games(profile.embedding, limit, seen_universe_ids)

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
            liked_feedbacks = self.db.query(UserFeedback).filter(
                UserFeedback.user_id == user_id,
                UserFeedback.feedback == 1
            ).all()

            if not liked_feedbacks:
                logger.info(f"User {user_id} has no liked games yet")
                return False

            # Get embeddings of liked games
            liked_universe_ids = [f.universe_id for f in liked_feedbacks]
            liked_games = self.db.query(Game).filter(
                Game.universe_id.in_(liked_universe_ids),
                Game.embedding != None
            ).all()

            if not liked_games:
                logger.error(f"No valid game embeddings found for user {user_id}")
                return False

            # Extract embeddings
            embeddings = [game.embedding for game in liked_games]

            # Compute average embedding
            avg_embedding = self.embedding_service.compute_average_embedding(embeddings)

            if avg_embedding is None:
                return False

            # Update user profile
            profile = self.get_user_profile(user_id)
            profile.embedding = avg_embedding
            self.db.commit()

            logger.info(f"Updated embedding for user {user_id} based on {len(liked_games)} liked games")
            return True

        except Exception as e:
            logger.error(f"Error updating user embedding: {e}")
            self.db.rollback()
            return False

    def save_feedback(self, user_id: str, universe_id: str, feedback: int) -> bool:
        """Save user feedback and update user embedding"""
        try:
            # Ensure user profile exists
            self.get_user_profile(user_id)

            # Check if feedback already exists
            existing_feedback = self.db.query(UserFeedback).filter(
                UserFeedback.user_id == user_id,
                UserFeedback.universe_id == universe_id
            ).first()

            if existing_feedback:
                # Update existing feedback
                existing_feedback.feedback = feedback
            else:
                # Create new feedback
                new_feedback = UserFeedback(
                    user_id=user_id,
                    universe_id=universe_id,
                    feedback=feedback
                )
                self.db.add(new_feedback)

            self.db.commit()

            # Update user embedding if feedback is like or dislike (not skip)
            if feedback != 0:
                self.update_user_embedding(user_id)

            return True

        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            self.db.rollback()
            return False
