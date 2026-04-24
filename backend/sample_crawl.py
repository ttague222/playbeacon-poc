"""
Sample crawler script
Run this to quickly populate your database with games
"""

import asyncio
from app.db.database import SessionLocal
from app.services.roblox_crawler import RobloxCrawler
from app.services.embedding_service import EmbeddingService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Crawl games and generate embeddings"""

    # Sample keywords covering various game types
    keywords = [
        "adventure",
        "tycoon",
        "horror",
        "simulator",
        "roleplay",
        "obby",
        "fighting",
        "racing",
        "survival",
        "building"
    ]

    logger.info("=" * 60)
    logger.info("Roblox Game Crawler - Sample Crawl")
    logger.info("=" * 60)
    logger.info(f"Keywords: {', '.join(keywords)}")
    logger.info("Games per keyword: 20")
    logger.info("=" * 60)
    logger.info("")

    # Create database session
    db = SessionLocal()

    try:
        # Step 1: Crawl games
        logger.info("Step 1: Crawling games from Roblox...")
        crawler = RobloxCrawler(db)
        games_stored = await crawler.crawl_and_store_games(
            keywords=keywords,
            limit_per_keyword=20
        )

        logger.info(f"✓ Crawled and stored {games_stored} new games")
        logger.info("")

        # Step 2: Generate embeddings
        logger.info("Step 2: Generating AI embeddings...")
        logger.info("This may take a few minutes...")

        embedding_service = EmbeddingService(db)
        embeddings_generated = embedding_service.update_all_missing_embeddings()

        logger.info(f"✓ Generated {embeddings_generated} embeddings")
        logger.info("")

        # Summary
        logger.info("=" * 60)
        logger.info("✓ Sample crawl complete!")
        logger.info("=" * 60)
        logger.info(f"Total games crawled: {games_stored}")
        logger.info(f"Total embeddings generated: {embeddings_generated}")
        logger.info("")
        logger.info("You can now:")
        logger.info("  1. Start the frontend: cd ../frontend && npm run dev")
        logger.info("  2. Visit http://localhost:3000")
        logger.info("  3. Go to Discovery Queue and start swiping!")
        logger.info("")

    except Exception as e:
        logger.error(f"Error during crawl: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
