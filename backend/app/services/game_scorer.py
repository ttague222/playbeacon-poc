"""
Game Scoring Service

Calculates confidence scores for games to determine if they should be:
- Imported immediately (high confidence)
- Added to backlog (medium confidence)
- Rejected (low confidence)
"""
import logging
from typing import Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GameScorer:
    """Service for scoring game quality and confidence"""

    # Score thresholds
    HIGH_CONFIDENCE_THRESHOLD = 70  # Import immediately with full processing
    MEDIUM_CONFIDENCE_THRESHOLD = 40  # Add to backlog for later review

    def __init__(self):
        pass

    def calculate_score(self, game_data: Dict) -> Tuple[float, str, Dict]:
        """
        Calculate a confidence score (0-100) for a game.

        Returns:
            Tuple of (score, tier, breakdown)
            - score: 0-100 confidence score
            - tier: 'high', 'medium', 'low'
            - breakdown: dict of individual score components
        """
        breakdown = {}
        total_score = 0.0

        # Extract game metadata
        visits = game_data.get("visits", 0)
        playing = game_data.get("playing", 0)
        up_votes = game_data.get("upVotes", 0)
        down_votes = game_data.get("downVotes", 0)
        total_votes = up_votes + down_votes
        like_ratio = (up_votes / total_votes) if total_votes > 0 else None

        title = (game_data.get("name") or "").strip()
        description = (game_data.get("description") or "").strip()
        creator = game_data.get("creator", {}) or {}
        creator_id = creator.get("id", 0)

        updated_str = game_data.get("updated")
        last_update_dt = None
        if updated_str:
            try:
                last_update_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except Exception:
                pass

        # 1. Popularity Score (0-30 points)
        popularity_score = self._score_popularity(visits, playing)
        breakdown["popularity"] = popularity_score
        total_score += popularity_score

        # 2. Engagement Score (0-25 points)
        engagement_score = self._score_engagement(total_votes, like_ratio)
        breakdown["engagement"] = engagement_score
        total_score += engagement_score

        # 3. Content Quality Score (0-20 points)
        content_score = self._score_content_quality(title, description)
        breakdown["content_quality"] = content_score
        total_score += content_score

        # 4. Freshness Score (0-15 points)
        freshness_score = self._score_freshness(last_update_dt, visits)
        breakdown["freshness"] = freshness_score
        total_score += freshness_score

        # 5. Creator Trust Score (0-10 points)
        creator_score = self._score_creator(creator_id, creator)
        breakdown["creator_trust"] = creator_score
        total_score += creator_score

        # Determine tier
        if total_score >= self.HIGH_CONFIDENCE_THRESHOLD:
            tier = "high"
        elif total_score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            tier = "medium"
        else:
            tier = "low"

        return total_score, tier, breakdown

    def _score_popularity(self, visits: int, playing: int) -> float:
        """Score based on visits and active players (0-30 points)"""
        score = 0.0

        # Visits component (0-20 points)
        if visits >= 10_000_000:
            score += 20
        elif visits >= 1_000_000:
            score += 15
        elif visits >= 100_000:
            score += 12
        elif visits >= 10_000:
            score += 8
        elif visits >= 1_000:
            score += 5
        elif visits >= 100:
            score += 2

        # Active players component (0-10 points)
        if playing >= 10_000:
            score += 10
        elif playing >= 1_000:
            score += 8
        elif playing >= 100:
            score += 6
        elif playing >= 10:
            score += 4
        elif playing >= 1:
            score += 2

        return min(score, 30)

    def _score_engagement(self, total_votes: int, like_ratio: float) -> float:
        """Score based on voting data (0-25 points)"""
        score = 0.0

        # Vote volume component (0-10 points)
        if total_votes >= 100_000:
            score += 10
        elif total_votes >= 10_000:
            score += 8
        elif total_votes >= 1_000:
            score += 6
        elif total_votes >= 100:
            score += 4
        elif total_votes >= 10:
            score += 2

        # Like ratio component (0-15 points)
        if like_ratio is not None:
            if like_ratio >= 0.9:
                score += 15
            elif like_ratio >= 0.8:
                score += 12
            elif like_ratio >= 0.7:
                score += 10
            elif like_ratio >= 0.6:
                score += 8
            elif like_ratio >= 0.5:
                score += 5
            elif like_ratio >= 0.4:
                score += 3
            elif like_ratio >= 0.3:
                score += 1
            # Below 0.3 gets 0 points
        else:
            # No votes - neutral score
            score += 5

        return min(score, 25)

    def _score_content_quality(self, title: str, description: str) -> float:
        """Score based on title and description quality (0-20 points)"""
        score = 0.0

        # Title quality (0-8 points)
        if title:
            title_len = len(title)
            if 10 <= title_len <= 60:
                score += 8
            elif 5 <= title_len < 10 or 60 < title_len <= 100:
                score += 5
            elif title_len > 0:
                score += 2

        # Description quality (0-12 points)
        if description:
            desc_len = len(description)
            if desc_len >= 200:
                score += 12
            elif desc_len >= 100:
                score += 10
            elif desc_len >= 50:
                score += 7
            elif desc_len >= 20:
                score += 4
            elif desc_len > 0:
                score += 2

        return min(score, 20)

    def _score_freshness(self, last_update_dt: datetime, visits: int) -> float:
        """Score based on how recently updated (0-15 points)"""
        if not last_update_dt:
            # No update date - assume it's recent if it has visits
            return 8 if visits > 100 else 4

        now = datetime.now(last_update_dt.tzinfo)
        age = now - last_update_dt

        if age <= timedelta(days=7):
            return 15
        elif age <= timedelta(days=30):
            return 12
        elif age <= timedelta(days=90):
            return 10
        elif age <= timedelta(days=180):
            return 7
        elif age <= timedelta(days=365):
            return 5
        else:
            # Old but might still be good if popular
            return 3 if visits > 10000 else 1

    def _score_creator(self, creator_id: int, creator: Dict) -> float:
        """Score based on creator information (0-10 points)"""
        if creator_id == 0:
            return 0

        score = 5  # Base score for having a valid creator

        # Check if creator has a name
        creator_name = creator.get("name", "")
        if creator_name and len(creator_name) > 0:
            score += 3

        # Check creator type (groups tend to be more established)
        creator_type = creator.get("type", "")
        if creator_type == "Group":
            score += 2

        return min(score, 10)

    def should_import(self, score: float, tier: str) -> Tuple[bool, bool]:
        """
        Determine if a game should be imported and if it should get full processing.

        Returns:
            Tuple of (should_import, full_processing)
            - should_import: True if game should be stored
            - full_processing: True if game should get embeddings + LLM enrichment
        """
        if tier == "high":
            return True, True  # Import with full processing
        elif tier == "medium":
            return True, False  # Import to backlog without full processing
        else:
            return False, False  # Reject

    def log_score(self, universe_id: int, score: float, tier: str, breakdown: Dict):
        """Log scoring details for analysis"""
        logger.info(
            f"[GameScorer] Universe {universe_id}: Score={score:.1f} Tier={tier} "
            f"Breakdown={breakdown}"
        )
