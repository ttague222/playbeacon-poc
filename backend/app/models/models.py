from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
# TODO: Enable when pgvector extension is installed
# from pgvector.sqlalchemy import Vector
from app.db.database import Base


class Game(Base):
    """Game model storing Roblox game metadata and embeddings"""
    __tablename__ = "games"

    universe_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    thumbnail_url = Column(String)
    creator_name = Column(String)
    visits = Column(Integer, default=0)
    active_players = Column(Integer, default=0)
    votes_up = Column(Integer, default=0)
    votes_down = Column(Integer, default=0)
    genre = Column(String)
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    embedding = Column(Text, nullable=True)  # OpenAI embedding vector (stored as JSON text until pgvector is available)

    def __repr__(self):
        return f"<Game(universe_id={self.universe_id}, title={self.title})>"


class UserProfile(Base):
    """User profile storing taste preferences as embedding vector"""
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True, index=True)
    embedding = Column(Text, nullable=True)  # Computed taste vector (stored as JSON text until pgvector is available)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id})>"


class UserFeedback(Base):
    """User feedback on recommended games"""
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    universe_id = Column(String, ForeignKey("games.universe_id"), nullable=False, index=True)
    feedback = Column(Integer, nullable=False)  # 1 = like, 0 = skip, -1 = dislike
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<UserFeedback(user_id={self.user_id}, universe_id={self.universe_id}, feedback={self.feedback})>"
