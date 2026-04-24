"""
Database initialization script
Run this to set up the database and verify pgvector is installed
"""

import sys
from sqlalchemy import text
from app.db.database import engine, init_db
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_pgvector():
    """Check if pgvector extension is available"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM pg_available_extensions WHERE name = 'vector'")
            )
            extensions = result.fetchall()

            if not extensions:
                logger.error("pgvector extension not found in PostgreSQL")
                logger.error("Please install pgvector:")
                logger.error("  macOS: brew install pgvector")
                logger.error("  Ubuntu: sudo apt install postgresql-14-pgvector")
                logger.error("  Windows: See https://github.com/pgvector/pgvector")
                return False

            logger.info("✓ pgvector extension is available")
            return True

    except Exception as e:
        logger.error(f"Error checking pgvector: {e}")
        return False


def enable_pgvector():
    """Enable pgvector extension"""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            logger.info("✓ pgvector extension enabled")
            return True

    except Exception as e:
        logger.error(f"Error enabling pgvector: {e}")
        return False


def create_tables():
    """Create all database tables"""
    try:
        init_db()
        logger.info("✓ Database tables created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


def verify_connection():
    """Verify database connection"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("✓ Database connection successful")
            logger.info(f"  Connected to: {settings.database_url.split('@')[1]}")
            return True

    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        logger.error(f"  Connection string: {settings.database_url.split('@')[0]}@...")
        logger.error("\nPlease check:")
        logger.error("  1. PostgreSQL is running")
        logger.error("  2. Database 'roblox_discovery' exists")
        logger.error("  3. Credentials in .env are correct")
        return False


def main():
    """Main initialization function"""
    logger.info("=" * 60)
    logger.info("Roblox Discovery - Database Initialization")
    logger.info("=" * 60)
    logger.info("")

    # Step 1: Verify connection
    logger.info("Step 1: Verifying database connection...")
    if not verify_connection():
        sys.exit(1)
    logger.info("")

    # Step 2: Check pgvector
    logger.info("Step 2: Checking pgvector extension...")
    if not check_pgvector():
        sys.exit(1)
    logger.info("")

    # Step 3: Enable pgvector
    logger.info("Step 3: Enabling pgvector extension...")
    if not enable_pgvector():
        sys.exit(1)
    logger.info("")

    # Step 4: Create tables
    logger.info("Step 4: Creating database tables...")
    if not create_tables():
        sys.exit(1)
    logger.info("")

    logger.info("=" * 60)
    logger.info("✓ Database initialization complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Start the backend: python main.py")
    logger.info("  2. Start the frontend: cd ../frontend && npm run dev")
    logger.info("  3. Open http://localhost:3000 in your browser")
    logger.info("  4. Go to Admin page to crawl games and generate embeddings")
    logger.info("")


if __name__ == "__main__":
    main()
