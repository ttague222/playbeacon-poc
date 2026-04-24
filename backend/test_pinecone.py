"""
Test script to verify Pinecone integration
"""
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.pinecone_service import PineconeService
from app.services.embedding_service_pinecone import EmbeddingService
from app.db.firebase import get_db, GAMES_COLLECTION

print("=" * 60)
print("Testing Pinecone Integration")
print("=" * 60)

# Test 1: Pinecone Connection
print("\n[1] Testing Pinecone Connection...")
try:
    pinecone_service = PineconeService()
    stats = pinecone_service.get_index_stats()
    print(f"  ✓ Connected to Pinecone index")
    print(f"  Index stats: {stats}")
except Exception as e:
    print(f"  ✗ Error connecting to Pinecone: {e}")
    print("\n  Make sure you have:")
    print("  1. Created a Pinecone account at https://www.pinecone.io/")
    print("  2. Created an index with 1536 dimensions and cosine metric")
    print("  3. Added PINECONE_API_KEY to your .env file")
    sys.exit(1)

# Test 2: Check Firestore games
print("\n[2] Checking games in Firestore...")
try:
    db = get_db()
    games_ref = db.collection(GAMES_COLLECTION)
    games = list(games_ref.limit(5).stream())
    print(f"  ✓ Found {len(games)} games in Firestore")

    if games:
        for game in games:
            data = game.to_dict()
            print(f"    - {data.get('title', 'No title')} (ID: {game.id})")
    else:
        print("  ! No games found. You may need to run the crawler first.")
except Exception as e:
    print(f"  ✗ Error accessing Firestore: {e}")
    sys.exit(1)

# Test 3: Generate embedding for one game (if games exist)
if games:
    print("\n[3] Testing embedding generation...")
    try:
        embedding_service = EmbeddingService()
        test_game = games[0]
        test_game_id = test_game.id
        test_game_data = test_game.to_dict()

        print(f"  Generating embedding for: {test_game_data.get('title')}")
        success = embedding_service.generate_game_embedding(test_game_id)

        if success:
            print(f"  ✓ Successfully generated and stored embedding in Pinecone")
        else:
            print(f"  ✗ Failed to generate embedding")

    except Exception as e:
        print(f"  ✗ Error generating embedding: {e}")
        if "quota" in str(e).lower() or "429" in str(e):
            print("\n  Note: This appears to be an OpenAI API quota issue.")
            print("  Your Pinecone integration is working, but you need OpenAI credits.")

    # Test 4: Check Pinecone stats after upload
    print("\n[4] Checking Pinecone index stats...")
    try:
        stats = pinecone_service.get_index_stats()
        total_vectors = stats.get('total_vector_count', 0)
        print(f"  ✓ Total vectors in Pinecone: {total_vectors}")
    except Exception as e:
        print(f"  ✗ Error getting stats: {e}")

print("\n" + "=" * 60)
print("Pinecone Integration Test Complete!")
print("=" * 60)

print("\nNext Steps:")
print("1. Add your Pinecone API key to .env file")
print("2. Make sure you have OpenAI credits available")
print("3. Run: python -m uvicorn main_pinecone:app --host 127.0.0.1 --port 8000")
print("4. Test the API at: http://127.0.0.1:8000/docs")
print("\nAPI Documentation: http://127.0.0.1:8000/docs")
