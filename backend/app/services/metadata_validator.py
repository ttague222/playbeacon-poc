"""
Metadata Validator

Validates and filters game metadata according to quality rules.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MetadataValidator:
    """Validates game metadata and filters out low-quality games"""

    # Template game titles to reject
    TEMPLATE_TITLES = {
        'my place', 'test', 'baseplate', 'classic baseplate', 'new place',
        'untitled', 'game', 'test game', 'my game', 'testing', 'test place',
        'place', 'new game', 'default', 'template'
    }

    # Placeholder/invalid thumbnail patterns
    INVALID_THUMBNAIL_PATTERNS = [
        'placeholder',
        'default',
        'missing',
        'unavailable',
    ]

    def __init__(self):
        pass

    def validate(self, metadata: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate game metadata.

        Args:
            metadata: Game metadata dictionary

        Returns:
            Tuple of (is_valid: bool, error_reason: Optional[str])
        """
        # Check required fields
        if not metadata.get('title'):
            return False, "Title is empty"

        if not metadata.get('id'):
            return False, "Universe ID is missing"

        # Check for template games
        title_lower = metadata['title'].lower().strip()
        if title_lower in self.TEMPLATE_TITLES:
            return False, f"Template game title: {metadata['title']}"

        # Check description + visits combination
        description = metadata.get('description', '').strip()
        visits = metadata.get('visits', 0)

        if not description and visits < 10:
            return False, "Empty description with low visits"

        # Check for abandoned games
        if visits == 0:
            updated_at = metadata.get('updated_at') or metadata.get('updated')
            if updated_at:
                if isinstance(updated_at, str):
                    try:
                        updated_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    except:
                        updated_dt = None
                elif isinstance(updated_at, datetime):
                    updated_dt = updated_at
                else:
                    updated_dt = None

                if updated_dt:
                    one_year_ago = datetime.now() - timedelta(days=365)
                    if updated_dt < one_year_ago:
                        return False, "Zero visits and not updated in over 1 year"

        # Check thumbnail
        thumbnail = metadata.get('thumbnailUrl') or metadata.get('thumbnail_url')
        if thumbnail:
            thumbnail_lower = thumbnail.lower()
            for pattern in self.INVALID_THUMBNAIL_PATTERNS:
                if pattern in thumbnail_lower:
                    return False, f"Invalid thumbnail: contains '{pattern}'"
        else:
            return False, "Missing thumbnail"

        # Check creator
        creator_id = metadata.get('creatorId') or metadata.get('creator_id')
        if creator_id == 0 or creator_id == '0':
            return False, "System game (creatorId = 0)"

        # Check voting data exists
        votes_up = metadata.get('votesUp') or metadata.get('votes_up') or metadata.get('upVotes', 0)
        votes_down = metadata.get('votesDown') or metadata.get('votes_down') or metadata.get('downVotes', 0)

        if votes_up is None and votes_down is None:
            return False, "Missing like/dislike data"

        # All checks passed
        return True, None

    def normalize_genre(self, genre: Optional[str]) -> Optional[str]:
        """
        Normalize genre name to a standard set.

        Args:
            genre: Raw genre string

        Returns:
            Normalized genre or None
        """
        if not genre:
            return None

        genre_lower = genre.lower().strip()

        # Map variants to standard genres
        genre_map = {
            'rpg': 'RPG',
            'role playing': 'RPG',
            'roleplay': 'RPG',
            'fps': 'FPS',
            'first person shooter': 'FPS',
            'shooter': 'FPS',
            'tycoon': 'Tycoon',
            'simulator': 'Simulator',
            'sim': 'Simulator',
            'adventure': 'Adventure',
            'obby': 'Obby',
            'obstacle': 'Obby',
            'parkour': 'Obby',
            'horror': 'Horror',
            'scary': 'Horror',
            'fighting': 'Fighting',
            'pvp': 'PvP',
            'sports': 'Sports',
            'racing': 'Racing',
            'building': 'Building',
            'town and city': 'Town and City',
            'city': 'Town and City',
            'survival': 'Survival',
            'comedy': 'Comedy',
            'medieval': 'Medieval',
            'military': 'Military',
            'naval': 'Naval',
            'western': 'Western',
            'sci-fi': 'Sci-Fi',
            'fantasy': 'Fantasy',
        }

        return genre_map.get(genre_lower, genre.title())

    def sanitize_text(self, text: str) -> str:
        """
        Sanitize text content (remove unsafe characters, normalize whitespace).

        Args:
            text: Input text

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

        # Normalize whitespace
        text = ' '.join(text.split())

        # Remove excessive special characters
        text = re.sub(r'[^\w\s\-.,!?()\'"]+', '', text)

        return text.strip()

    def calculate_like_ratio(self, votes_up: int, votes_down: int) -> float:
        """
        Calculate like ratio (0.0 to 1.0).

        Args:
            votes_up: Number of upvotes
            votes_down: Number of downvotes

        Returns:
            Like ratio as a float
        """
        total = votes_up + votes_down
        if total == 0:
            return 0.5  # Neutral if no votes

        return votes_up / total

    def enrich_metadata(self, metadata: Dict) -> Dict:
        """
        Enrich metadata with calculated fields and normalized values.

        Args:
            metadata: Raw metadata dictionary

        Returns:
            Enriched metadata dictionary
        """
        enriched = metadata.copy()

        # Normalize genre
        if 'genre' in enriched:
            enriched['genre'] = self.normalize_genre(enriched['genre'])

        # Sanitize text fields
        if 'title' in enriched:
            enriched['title'] = self.sanitize_text(enriched['title'])

        if 'description' in enriched:
            enriched['description'] = self.sanitize_text(enriched['description'])

        # Calculate like_ratio
        votes_up = enriched.get('votesUp') or enriched.get('votes_up') or enriched.get('upVotes', 0)
        votes_down = enriched.get('votesDown') or enriched.get('votes_down') or enriched.get('downVotes', 0)
        enriched['like_ratio'] = self.calculate_like_ratio(votes_up, votes_down)

        # Add calculated flags
        visits = enriched.get('visits', 0)
        active_players = enriched.get('playing') or enriched.get('active_players', 0)

        enriched['is_popular'] = visits > 1_000_000 or active_players > 500
        enriched['is_trending'] = False  # Will be calculated by comparing to previous visits
        enriched['is_new'] = False  # Will be calculated based on created_at

        # Add crawler metadata
        enriched['last_crawled'] = datetime.now()
        enriched['has_embedding'] = False  # Will be set after embedding generation

        return enriched
