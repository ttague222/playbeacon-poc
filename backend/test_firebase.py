"""
Quick test script to verify Firebase connection
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.db.firebase import initialize_firebase, GAMES_COLLECTION

    print("Testing Firebase connection...")
    print("=" * 60)

    # Initialize Firebase
    db = initialize_firebase()
    print("[OK] Firebase initialized successfully!")

    # Test Firestore connection
    print("[OK] Firestore client created")

    # Try to read from games collection (should be empty initially)
    games_ref = db.collection(GAMES_COLLECTION)
    docs = list(games_ref.limit(1).stream())

    print("[OK] Successfully connected to Firestore!")
    print(f"  - Games in database: {len(docs)}")

    print("=" * 60)
    print("SUCCESS: Firebase connection test PASSED!")
    print("")
    print("Your Firebase setup is complete!")
    print("Next step: Run 'python sample_crawl_firestore.py' to populate the database")

except FileNotFoundError as e:
    print("[ERROR] Firebase credentials file not found!")
    print(f"Error: {e}")
    print("")
    print("Please make sure 'serviceAccountKey.json' is in the backend directory")
    sys.exit(1)

except Exception as e:
    print("[ERROR] Firebase connection test FAILED!")
    print(f"Error: {e}")
    print("")
    print("Please check:")
    print("1. Firebase credentials file exists (serviceAccountKey.json)")
    print("2. FIREBASE_PROJECT_ID is correct in .env")
    print("3. Firestore is enabled in your Firebase project")
    sys.exit(1)
