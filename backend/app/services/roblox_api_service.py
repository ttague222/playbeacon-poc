"""
Roblox API Service for fetching user data and game information
"""
import httpx
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache for Roblox API responses (1 hour TTL)
_roblox_cache = {}
_cache_ttl = timedelta(hours=1)


class RobloxAPIService:
    """Service for interacting with Roblox APIs"""

    BASE_URL = "https://api.roblox.com"
    USERS_URL = "https://users.roblox.com"
    GAMES_URL = "https://games.roblox.com"
    BADGES_URL = "https://badges.roblox.com"
    INVENTORY_URL = "https://inventory.roblox.com"
    GROUPS_URL = "https://groups.roblox.com"
    SORTS_URL = "https://games.roblox.com/v1/games/list"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def get_game_details(self, universe_ids: List[int]) -> Dict[int, Dict]:
        """Fetch game details for a list of universe IDs"""
        if not universe_ids:
            return {}

        try:
            response = await self.client.get(
                f"{self.GAMES_URL}/v1/games",
                params={"universeIds": ",".join(map(str, universe_ids))}
            )
            response.raise_for_status()
            data = response.json()
            games = {}
            for item in data.get("data", []):
                games[int(item.get("id"))] = item
            return games
        except Exception as e:
            logger.error(f"Error fetching game details for {universe_ids}: {e}")
            return {}

    async def get_game_thumbnails(self, universe_ids: List[int]) -> Dict[int, str]:
        """Fetch game thumbnails for a list of universe IDs"""
        if not universe_ids:
            return {}

        try:
            response = await self.client.get(
                "https://thumbnails.roblox.com/v1/games/icons",
                params={
                    "universeIds": ",".join(map(str, universe_ids)),
                    "size": "512x512",
                    "format": "Png"
                }
            )
            response.raise_for_status()
            data = response.json()
            thumbs = {}
            for item in data.get("data", []):
                uid = int(item.get("targetId"))
                thumbs[uid] = item.get("imageUrl")
            return thumbs
        except Exception as e:
            logger.error(f"Error fetching thumbnails for {universe_ids}: {e}")
            return {}

    def _get_cache(self, key: str) -> Optional[Dict]:
        """Get cached response if not expired"""
        if key in _roblox_cache:
            data, timestamp = _roblox_cache[key]
            if datetime.now() - timestamp < _cache_ttl:
                return data
            else:
                del _roblox_cache[key]
        return None

    def _set_cache(self, key: str, data: Dict):
        """Cache a response with timestamp"""
        _roblox_cache[key] = (data, datetime.now())

    async def resolve_username(self, username: str) -> Optional[Dict]:
        """
        Resolve a Roblox username to user data

        Args:
            username: Roblox username to resolve

        Returns:
            User data dict or None if not found
        """
        cache_key = f"user:{username.lower()}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            # Get user by username
            response = await self.client.post(
                f"{self.USERS_URL}/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": True}
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("data") or len(data["data"]) == 0:
                logger.warning(f"Username not found: {username}")
                return None

            user_data = data["data"][0]
            user_id = user_data["id"]

            # Get detailed user info
            detail_response = await self.client.get(
                f"{self.USERS_URL}/v1/users/{user_id}"
            )
            detail_response.raise_for_status()
            detail_data = detail_response.json()

            # Get avatar headshot
            avatar_response = await self.client.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png"
            )
            avatar_url = None
            if avatar_response.status_code == 200:
                avatar_data = avatar_response.json()
                if avatar_data.get("data") and len(avatar_data["data"]) > 0:
                    avatar_url = avatar_data["data"][0].get("imageUrl")

            result = {
                "userId": user_id,
                "username": user_data["name"],
                "displayName": user_data["displayName"],
                "description": detail_data.get("description", ""),
                "created": detail_data.get("created"),
                "avatarUrl": avatar_url
            }

            self._set_cache(cache_key, result)
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Roblox API error resolving username {username}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error resolving username {username}: {e}")
            return None

    async def get_user_favorites(self, user_id: int) -> List[Dict]:
        """
        Get user's favorite games

        Args:
            user_id: Roblox user ID

        Returns:
            List of favorite games with universeIds
        """
        cache_key = f"favorites:{user_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            response = await self.client.get(
                f"{self.GAMES_URL}/v2/users/{user_id}/favorite/games",
                params={"limit": 50}
            )
            response.raise_for_status()
            data = response.json()

            favorites = []
            for game in data.get("data", []):
                favorites.append({
                    "universeId": str(game["id"]),
                    "name": game.get("name"),
                    "placeId": game.get("rootPlaceId"),
                    "source": "favorite",
                    "score": 2  # Favorite weight
                })

            self._set_cache(cache_key, favorites)
            return favorites

        except Exception as e:
            logger.error(f"Error fetching favorites for user {user_id}: {e}")
            return []

    async def get_user_badges(self, user_id: int, limit: int = 100) -> List[Dict]:
        """
        Get badges earned by user and extract universe IDs

        Args:
            user_id: Roblox user ID
            limit: Maximum badges to fetch

        Returns:
            List of games where user earned badges
        """
        cache_key = f"badges:{user_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            response = await self.client.get(
                f"{self.BADGES_URL}/v1/users/{user_id}/badges",
                params={"limit": limit, "sortOrder": "Desc"}
            )
            response.raise_for_status()
            data = response.json()

            # Extract unique universe IDs from badges
            games_map = {}
            for badge in data.get("data", []):
                universe_id = str(badge.get("awardingUniverse", {}).get("id"))
                if universe_id and universe_id != "None":
                    if universe_id not in games_map:
                        games_map[universe_id] = {
                            "universeId": universe_id,
                            "name": badge.get("awardingUniverse", {}).get("name"),
                            "source": "badge",
                            "score": 1,  # Badge weight
                            "badgeCount": 1
                        }
                    else:
                        games_map[universe_id]["badgeCount"] += 1

            result = list(games_map.values())
            self._set_cache(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"Error fetching badges for user {user_id}: {e}")
            return []

    async def get_user_groups(self, user_id: int) -> List[Dict]:
        """
        Get user's groups (can be used to infer game interests)

        Args:
            user_id: Roblox user ID

        Returns:
            List of groups
        """
        cache_key = f"groups:{user_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            response = await self.client.get(
                f"{self.GROUPS_URL}/v2/users/{user_id}/groups/roles"
            )
            response.raise_for_status()
            data = response.json()

            groups = []
            for item in data.get("data", []):
                group = item.get("group", {})
                groups.append({
                    "groupId": group.get("id"),
                    "name": group.get("name"),
                    "memberCount": group.get("memberCount", 0)
                })

            self._set_cache(cache_key, groups)
            return groups

        except Exception as e:
            logger.error(f"Error fetching groups for user {user_id}: {e}")
            return []

    async def get_import_data(self, user_id: int) -> Dict:
        """
        Get all import data for a user (favorites, badges, groups)

        Args:
            user_id: Roblox user ID

        Returns:
            Aggregated import data
        """
        try:
            # Fetch all data in parallel
            favorites = await self.get_user_favorites(user_id)
            badges = await self.get_user_badges(user_id)
            groups = await self.get_user_groups(user_id)

            # Aggregate games by universeId with cumulative scores
            games_map = {}

            # Add favorites
            for game in favorites:
                uid = game["universeId"]
                games_map[uid] = game

            # Add badge games
            for game in badges:
                uid = game["universeId"]
                if uid in games_map:
                    games_map[uid]["score"] += game["score"]
                    games_map[uid]["source"] = "favorite+badge"
                else:
                    games_map[uid] = game

            # Sort by score (highest first)
            sorted_games = sorted(
                games_map.values(),
                key=lambda x: x["score"],
                reverse=True
            )

            # Categorize by confidence
            strong_matches = [g for g in sorted_games if g["score"] >= 3]
            medium_matches = [g for g in sorted_games if 1 <= g["score"] < 3]

            return {
                "favorites": favorites,
                "badges": badges,
                "groups": groups,
                "aggregated_games": sorted_games[:200],  # Limit to 200
                "strong_matches": strong_matches,
                "medium_matches": medium_matches,
                "total_games": len(sorted_games),
                "favorite_count": len(favorites),
                "badge_count": len(badges),
                "group_count": len(groups)
            }

        except Exception as e:
            logger.error(f"Error getting import data for user {user_id}: {e}")
            return {
                "favorites": [],
                "badges": [],
                "groups": [],
                "aggregated_games": [],
                "strong_matches": [],
                "medium_matches": [],
                "total_games": 0,
                "favorite_count": 0,
                "badge_count": 0,
                "group_count": 0
            }

    async def get_universe_ids_by_keyword(self, keyword: str, limit: int = 20) -> List[int]:
        """
        Search games by keyword using Roblox catalog search and return universe IDs.
        """
        if not keyword:
            return []

        cache_key = f"kw:{keyword.lower()}:{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            allowed_limits = [10, 28, 30, 50, 60, 100, 120]
            limit_param = next((l for l in allowed_limits if l >= limit), allowed_limits[-1])
            url = "https://catalog.roblox.com/v1/search/items"
            params = {
                "category": "Games",
                "keyword": keyword,
                "limit": limit_param,
                "sortType": "Relevance",
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            universe_ids = []
            for item in data.get("data", []):
                uid = item.get("id")
                if uid:
                    universe_ids.append(int(uid))
            self._set_cache(cache_key, universe_ids)
            return universe_ids
        except Exception as e:
            logger.error(f"Error searching keyword '{keyword}': {e}")
            return []

    async def get_universe_ids_by_sort(self, sort_name: str, limit: int = 50) -> List[int]:
        """
        Fetch official Roblox sorts and return universe IDs.
        """
        if not sort_name:
            return []

        try:
            params = {
                "model.sortType": self._sort_to_int(sort_name),
                "maxRows": min(limit, 100),  # Roblox API cap
            }
            response = await self.client.get(self.SORTS_URL, params=params)
            response.raise_for_status()
            data = response.json()
            ids = []
            for game in data.get("games", []):
                uid = game.get("universeId")
                if uid:
                    ids.append(int(uid))
            return ids
        except Exception as e:
            logger.error(f"Error fetching sort '{sort_name}': {e}")
            return []

    def _sort_to_int(self, sort_name: str) -> int:
        """Map sort names to Roblox sortType int. Approximate mapping."""
        sort_map = {
            "popular": 1,
            "top_rated": 2,
            "recommended": 3,
            "up_and_coming": 4,
            "premium": 5,
            "most_engaging": 6,
            "top_earning": 7,
            "hidden_gems": 8,
            "featured": 9,
        }
        return sort_map.get(sort_name, 1)

    async def get_related_universe_ids(self, universe_id: int) -> List[int]:
        """
        Fetch related/recommended games for a universe via Roblox games/recommendations endpoint (approx).
        """
        try:
            url = f"{self.GAMES_URL}/v1/games/recommendations"
            params = {"universeId": universe_id}
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            ids = []
            for item in data.get("data", []):
                uid = item.get("id")
                if uid:
                    ids.append(int(uid))
            return ids
        except Exception as e:
            logger.error(f"Error fetching related games for {universe_id}: {e}")
            return []

    async def get_creator_universe_ids(self, creator_id: int, limit: int = 50) -> List[int]:
        """
        Fetch games created by a developer/creator.
        """
        if not creator_id:
            return []
        try:
            url = f"{self.BASE_URL}/users/{creator_id}/games"
            params = {"page": 1, "limit": min(limit, 100)}
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            ids = []
            for item in data.get("games", []):
                uid = item.get("universeId")
                if uid:
                    ids.append(int(uid))
            return ids
        except Exception as e:
            logger.error(f"Error fetching creator games for {creator_id}: {e}")
            return []
