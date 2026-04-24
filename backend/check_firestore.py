"""
Check what's in Firestore database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.firebase import get_db, GAMES_COLLECTION, USER_PROFILES_COLLECTION, USER_FEEDBACK_COLLECTION

print("Checking Firestore Database...")
print("=" * 60)

db = get_db()

# Check games collection
print("\n[GAMES COLLECTION]")
games_ref = db.collection(GAMES_COLLECTION)
games = list(games_ref.limit(10).stream())
print(f"  Total games (showing first 10): {len(games)}")
for game in games:
    data = game.to_dict()
    print(f"  - {data.get('title', 'No title')} (ID: {game.id})")

# Check user profiles
print("\n[USER PROFILES COLLECTION]")
profiles_ref = db.collection(USER_PROFILES_COLLECTION)
profiles = list(profiles_ref.limit(5).stream())
print(f"  Total user profiles: {len(profiles)}")
for profile in profiles:
    print(f"  - User ID: {profile.id}")

# Check user feedback
print("\n[USER FEEDBACK COLLECTION]")
feedback_ref = db.collection(USER_FEEDBACK_COLLECTION)
feedback = list(feedback_ref.limit(5).stream())
print(f"  Total feedback entries: {len(feedback)}")

print("\n" + "=" * 60)
print("Firestore Database Check Complete!")
print("\nTo view in Firebase Console:")
print("https://console.firebase.google.com/project/roblox-discovery/firestore")
