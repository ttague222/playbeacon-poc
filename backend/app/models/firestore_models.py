from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class Game(BaseModel):
    """Game model for Firestore"""
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
    last_update: datetime = Field(default_factory=datetime.now)
    embedding: Optional[List[float]] = None
    has_embedding: bool = False
    tags: Optional[List[str]] = None
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore document dict"""
        data = self.model_dump()
        # Convert datetime to timestamp for Firestore
        if isinstance(data.get('last_update'), datetime):
            data['last_update'] = data['last_update']
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Game':
        """Create from Firestore document"""
        # Handle timestamp conversion if needed
        if 'last_update' in data and not isinstance(data['last_update'], datetime):
            data['last_update'] = datetime.now()
        return cls(**data)


class UserProfile(BaseModel):
    """User profile model for Firestore"""
    user_id: str
    profile_embedding: Optional[List[float]] = None
    liked_count: int = 0
    disliked_count: int = 0
    is_admin: bool = False
    roblox_username: Optional[str] = None
    roblox_userId: Optional[int] = None
    roblox_imported: bool = False
    skipped_roblox_import: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore document dict"""
        data = self.model_dump()
        # Convert datetime to timestamp for Firestore
        if isinstance(data.get('created_at'), datetime):
            data['created_at'] = data['created_at']
        if isinstance(data.get('updated_at'), datetime):
            data['updated_at'] = data['updated_at']
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """Create from Firestore document"""
        # Handle timestamp conversion if needed
        if 'created_at' in data and not isinstance(data['created_at'], datetime):
            data['created_at'] = datetime.now()
        if 'updated_at' in data and not isinstance(data['updated_at'], datetime):
            data['updated_at'] = datetime.now()
        return cls(**data)


class UserFeedback(BaseModel):
    """User feedback model for Firestore"""
    id: Optional[str] = None
    user_id: str
    universe_id: str
    feedback: int  # 1 = like, 0 = skip, -1 = dislike
    created_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore document dict"""
        data = self.model_dump(exclude={'id'})
        # Convert datetime to timestamp for Firestore
        if isinstance(data.get('created_at'), datetime):
            data['created_at'] = data['created_at']
        return data

    @classmethod
    def from_dict(cls, doc_id: str, data: Dict[str, Any]) -> 'UserFeedback':
        """Create from Firestore document"""
        # Handle timestamp conversion if needed
        if 'created_at' in data and not isinstance(data['created_at'], datetime):
            data['created_at'] = datetime.now()
        data['id'] = doc_id
        return cls(**data)
