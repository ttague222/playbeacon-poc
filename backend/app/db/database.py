from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and pgvector extension"""
    from app.models import models  # Import to register models
    from sqlalchemy import text

    # Enable pgvector extension
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        except Exception as e:
            print(f"Warning: Could not create pgvector extension: {e}")
            print("The app will run but vector similarity features will be limited.")
            conn.rollback()

    # Create all tables
    Base.metadata.create_all(bind=engine)
