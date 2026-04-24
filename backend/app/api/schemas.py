from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class GameResponse(BaseModel):
    """Schema for game response"""
    universe_id: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    creator_name: Optional[str] = None
    visits: int = 0
    active_players: int = 0
    votes_up: int = 0
    votes_down: int = 0
    genre: Optional[str] = None

    class Config:
        from_attributes = True


class QueueRequest(BaseModel):
    """Schema for queue request"""
    limit: int = Field(10, ge=1, le=50, description="Number of games to return")


class QueueResponse(BaseModel):
    """Schema for queue response"""
    user_id: str
    games: List[GameResponse]
    count: int


class FeedbackRequest(BaseModel):
    """Schema for feedback request"""
    universe_id: str = Field(..., description="Game universe ID")
    feedback: int = Field(..., ge=-1, le=1, description="Feedback: 1=like, 0=skip, -1=dislike")


class FeedbackResponse(BaseModel):
    """Schema for feedback response"""
    success: bool
    message: str


class CrawlRequest(BaseModel):
    """Schema for crawl request"""
    keywords: List[str] = Field(..., description="Keywords to search for")
    limit_per_keyword: int = Field(50, ge=1, le=100, description="Max games per keyword")


class CrawlResponse(BaseModel):
    """Schema for crawl response"""
    success: bool
    games_stored: int
    message: str


class GenerateEmbeddingsResponse(BaseModel):
    """Schema for generate embeddings response"""
    success: bool
    embeddings_generated: int
    message: str


class CrawlerEnqueueRequest(BaseModel):
    """Schema for crawler enqueue request"""
    universe_ids: List[int]
    source: str = Field(..., description="Source identifier, e.g. 'manual', 'keyword', 'user_import'")
    priority: int = Field(5, ge=1, le=10, description="Priority 1-10 (higher is processed first)")


class CrawlerEnqueueResponse(BaseModel):
    """Schema for crawler enqueue response"""
    success: bool
    enqueued: int
    updated: int
    message: str


class CrawlerStatusResponse(BaseModel):
    """Schema for crawler status response"""
    success: bool
    queue_length: int
    missing_embeddings: int
    crawl_errors: int
    new_today: int
    last_crawl: Optional[str] = None
    last_embed: Optional[str] = None
    worker_status: Optional[str] = None
    next_runs: Optional[dict] = None


class AdminStatusResponse(BaseModel):
    """Schema for admin system status (for AdminStatusPanel)"""
    firestore: dict
    pinecone: dict
    jobs: dict
    errors: List[dict]


class CrawlerKeywordRequest(BaseModel):
    """Schema for keyword enqueue request"""
    keywords: List[str]
    limit_per_keyword: int = Field(20, ge=1, le=100)
    priority: int = Field(5, ge=1, le=10)


class CrawlerSortsRequest(BaseModel):
    """Schema for official sorts enqueue request"""
    sorts: List[str] = Field(default_factory=list, description="e.g. popular, top_rated, recommended")
    limit: int = Field(50, ge=1, le=200)
    priority: int = Field(6, ge=1, le=10)


class CrawlerGraphRequest(BaseModel):
    """Schema for graph expansion enqueue request"""
    universe_ids: List[int]
    priority: int = Field(6, ge=1, le=10)


class ThumbnailFixRequest(BaseModel):
    """Schema for thumbnail fix request"""
    limit: int = Field(50, ge=1, le=200)


class EmbedRegenRequest(BaseModel):
    """Schema for full embedding regeneration request"""
    limit: int = Field(200, ge=1, le=1000)


class ScheduleToggleRequest(BaseModel):
    """Schema for enabling/disabling scheduler tasks"""
    queue_worker: Optional[bool] = None
    keywords: Optional[bool] = None
    sorts: Optional[bool] = None
    graph: Optional[bool] = None
    embed_sweep: Optional[bool] = None
    thumb_fix: Optional[bool] = None
    weekly: Optional[bool] = None


# Roblox Import Schemas

class RobloxUserResponse(BaseModel):
    """Schema for resolved Roblox user"""
    userId: int
    username: str
    displayName: str
    description: Optional[str] = None
    created: Optional[str] = None
    avatarUrl: Optional[str] = None


class RobloxGameMatch(BaseModel):
    """Schema for a matched game from Roblox"""
    universeId: str
    name: Optional[str] = None
    placeId: Optional[int] = None
    source: str
    score: int
    badgeCount: Optional[int] = None


class RobloxImportDataResponse(BaseModel):
    """Schema for Roblox import data"""
    favorites: List[RobloxGameMatch]
    badges: List[RobloxGameMatch]
    groups: List[dict]
    aggregated_games: List[RobloxGameMatch]
    strong_matches: List[RobloxGameMatch]
    medium_matches: List[RobloxGameMatch]
    total_games: int
    favorite_count: int
    badge_count: int
    group_count: int


class SelectedGame(BaseModel):
    """Schema for a selected game to import"""
    universeId: str
    score: int


class RobloxImportRequest(BaseModel):
    """Schema for importing selected Roblox games"""
    robloxUserId: int
    robloxUsername: str
    selectedGames: List[SelectedGame]


class RobloxImportResponse(BaseModel):
    """Schema for import response"""
    success: bool
    games_imported: int
    message: str
