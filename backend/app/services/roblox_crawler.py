import httpx
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models.models import Game
import logging

logger = logging.getLogger(__name__)


class RobloxCrawler:
    """Service for crawling Roblox games data"""

    BASE_URL = "https://games.roblox.com"
    CATALOG_URL = "https://catalog.roblox.com"
    THUMBNAILS_URL = "https://thumbnails.roblox.com"

    def __init__(self, db: Session):
        self.db = db

    async def search_games_by_keyword(self, keyword: str, limit: int = 50) -> List[Dict]:
        """
        Search games by keyword using Roblox catalog search (public endpoint).

        Note: /v1/games/list now returns 404. The catalog search works unauthenticated
        and returns item ids we can use as universe ids for the detail lookup.
        """
        games = []
        # Roblox only accepts specific limits; pick the smallest allowed >= requested.
        allowed_limits = [10, 28, 30, 50, 60, 100, 120]
        requested_limit = max(1, limit)
        limit_param = next((l for l in allowed_limits if l >= requested_limit), allowed_limits[-1])

        url = f"{self.CATALOG_URL}/v1/search/items"
        params = {
            "category": "Games",
            "keyword": keyword,
            "limit": limit_param,
            "sortType": "Relevance",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                games = data.get("data", [])
                logger.info(f"Found {len(games)} catalog results for keyword '{keyword}'")
        except Exception as e:
            logger.error(f"Error searching games for keyword '{keyword}': {e}")

        return games

    async def get_game_details(self, universe_ids: List[str]) -> List[Dict]:
        """Get detailed game information by universe IDs"""
        if not universe_ids:
            return []

        url = f"{self.BASE_URL}/v1/games"
        params = {"universeIds": ",".join(map(str, universe_ids))}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])

        except Exception as e:
            logger.error(f"Error fetching game details: {e}")
            return []

    async def get_game_thumbnails(self, universe_ids: List[str]) -> Dict[str, str]:
        """Get game thumbnail URLs"""
        if not universe_ids:
            return {}

        url = f"{self.THUMBNAILS_URL}/v1/games/icons"
        params = {
            "universeIds": ",".join(map(str, universe_ids)),
            "size": "512x512",
            "format": "Png"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                thumbnails = {}
                for item in data.get("data", []):
                    universe_id = str(item.get("targetId"))
                    image_url = item.get("imageUrl")
                    if image_url:
                        thumbnails[universe_id] = image_url

                return thumbnails

        except Exception as e:
            logger.error(f"Error fetching thumbnails: {e}")
            return {}

    async def crawl_and_store_games(self, keywords: List[str], limit_per_keyword: int = 50) -> int:
        """Crawl games by keywords and store in database"""
        total_stored = 0

        for keyword in keywords:
            logger.info(f"Crawling games for keyword: {keyword}")

            # Search games
            games_data = await self.search_games_by_keyword(keyword, limit_per_keyword)

            if not games_data:
                continue

            # Extract universe IDs
            universe_ids = [str(game.get("id")) for game in games_data if game.get("id")]

            # Get detailed info
            detailed_games = await self.get_game_details(universe_ids)

            # Get thumbnails
            thumbnails = await self.get_game_thumbnails(universe_ids)

            # Store games
            for game_data in detailed_games:
                try:
                    universe_id = str(game_data.get("id"))

                    # Check if game already exists
                    existing_game = self.db.query(Game).filter(Game.universe_id == universe_id).first()

                    game_info = {
                        "universe_id": universe_id,
                        "title": game_data.get("name", ""),
                        "description": game_data.get("description", ""),
                        "thumbnail_url": thumbnails.get(universe_id, ""),
                        "creator_name": game_data.get("creator", {}).get("name", ""),
                        "visits": game_data.get("visits", 0),
                        "active_players": game_data.get("playing", 0),
                        "votes_up": game_data.get("favoritedCount", 0),
                        "votes_down": 0,  # Not available in API
                        "genre": game_data.get("genre", "")
                    }

                    if existing_game:
                        # Update existing game
                        for key, value in game_info.items():
                            if key != "universe_id":
                                setattr(existing_game, key, value)
                    else:
                        # Create new game
                        new_game = Game(**game_info)
                        self.db.add(new_game)
                        total_stored += 1

                    self.db.commit()

                except Exception as e:
                    logger.error(f"Error storing game {universe_id}: {e}")
                    self.db.rollback()

        logger.info(f"Crawled and stored {total_stored} new games")
        return total_stored
