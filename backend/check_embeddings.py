"""
Check if games have embeddings
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.firebase import get_db, GAMES_COLLECTION

print("Checking Game Embeddings...")
print("=" * 60)

db = get_db()
games_ref = db.collection(GAMES_COLLECTION)
games = list(games_ref.stream())

total_games = len(games)
games_with_embeddings = 0
games_without_embeddings = 0

print(f"\nTotal games in database: {total_games}")
print("\nGames status:")

for game in games:
    data = game.to_dict()
    title = data.get('title', 'Unknown')
    has_embedding = data.get('embedding') is not None

    if has_embedding:
        games_with_embeddings += 1
        embedding_size = len(data.get('embedding', []))
        print(f"  [OK] {title} - Embedding: {embedding_size} dimensions")
    else:
        games_without_embeddings += 1
        print(f"  [MISSING] {title} - No embedding")

print("\n" + "=" * 60)
print(f"Summary:")
print(f"  Games with embeddings: {games_with_embeddings}")
print(f"  Games without embeddings: {games_without_embeddings}")

if games_without_embeddings > 0:
    print(f"\nTo generate embeddings, run:")
    print(f"  python sample_crawl_firestore.py")
    print(f"\nOr use the API endpoint:")
    print(f"  POST http://127.0.0.1:8000/api/generate-embeddings")
