from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Global Pinecone client
_pc = None
_index = None


def get_pinecone_client():
    """Get or create Pinecone client"""
    global _pc

    if _pc is None:
        if not settings.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY not set in environment variables")

        _pc = Pinecone(api_key=settings.pinecone_api_key)
        logger.info("Pinecone client initialized")

    return _pc


def get_pinecone_index():
    """Get or create Pinecone index"""
    global _index

    if _index is None:
        pc = get_pinecone_client()
        index_name = settings.pinecone_index_name

        # Check if index exists, create if it doesn't
        existing_indexes = [index.name for index in pc.list_indexes()]

        if index_name not in existing_indexes:
            logger.info(f"Creating Pinecone index: {index_name}")
            pc.create_index(
                name=index_name,
                dimension=settings.embedding_dimensions,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            logger.info(f"Index {index_name} created successfully")

        _index = pc.Index(index_name)
        logger.info(f"Connected to Pinecone index: {index_name}")

    return _index


class PineconeService:
    """Service for managing vector embeddings in Pinecone"""

    def __init__(self):
        self.index = get_pinecone_index()

    def upsert_embedding(self, universe_id: str, embedding: List[float], metadata: Optional[Dict] = None):
        """
        Store or update a game embedding in Pinecone

        Args:
            universe_id: Unique game identifier
            embedding: Vector embedding (1536 dimensions)
            metadata: Optional metadata to store with the vector
        """
        try:
            vector_data = {
                "id": str(universe_id),
                "values": embedding,
            }

            if metadata:
                vector_data["metadata"] = metadata

            self.index.upsert(vectors=[vector_data])
            logger.debug(f"Upserted embedding for game {universe_id}")
            return True

        except Exception as e:
            logger.error(f"Error upserting embedding for {universe_id}: {e}")
            return False

    def upsert_batch(self, vectors: List[Dict]):
        """
        Batch upsert multiple embeddings

        Args:
            vectors: List of dicts with 'id', 'values', and optional 'metadata'
        """
        try:
            self.index.upsert(vectors=vectors)
            logger.info(f"Batch upserted {len(vectors)} vectors")
            return True

        except Exception as e:
            logger.error(f"Error in batch upsert: {e}")
            return False

    def query_similar(self, embedding: List[float], top_k: int = 10, filter_dict: Optional[Dict] = None) -> List[Dict]:
        """
        Find similar games based on embedding vector

        Args:
            embedding: Query vector
            top_k: Number of results to return
            filter_dict: Optional metadata filter

        Returns:
            List of matches with id, score, and metadata
        """
        try:
            results = self.index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )

            matches = []
            for match in results.get('matches', []):
                matches.append({
                    'id': match['id'],
                    'score': match['score'],
                    'metadata': match.get('metadata', {})
                })

            return matches

        except Exception as e:
            logger.error(f"Error querying similar vectors: {e}")
            return []

    def delete_embedding(self, universe_id: str):
        """Delete a game embedding from Pinecone"""
        try:
            self.index.delete(ids=[str(universe_id)])
            logger.debug(f"Deleted embedding for game {universe_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting embedding for {universe_id}: {e}")
            return False

    def get_index_stats(self) -> Dict:
        """Get statistics about the Pinecone index"""
        try:
            stats = self.index.describe_index_stats()
            return stats

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}
