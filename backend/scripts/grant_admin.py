"""
Script to grant admin access to a Firebase user.

Usage:
    python scripts/grant_admin.py <user_email_or_uid>
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.firebase import get_db, initialize_firebase
from firebase_admin import auth as admin_auth

# Initialize Firebase
initialize_firebase()
firestore = get_db()


def grant_admin(identifier: str):
    """
    Grant admin custom claim to a user identified by email or UID.

    Args:
        identifier: User email or UID
    """
    try:
        # Try to get user by UID first
        try:
            user = admin_auth.get_user(identifier)
            print(f"✓ Found user by UID: {user.uid}")
        except:
            # If that fails, try by email
            user = admin_auth.get_user_by_email(identifier)
            print(f"✓ Found user by email: {user.email}")

        # Set admin custom claim
        admin_auth.set_custom_user_claims(user.uid, {'admin': True})
        print(f"✓ Admin claim granted to user: {user.uid}")
        print(f"  Email: {user.email or 'N/A'}")
        print(f"  Display Name: {user.display_name or 'N/A'}")

        # Update Firestore user document
        user_ref = firestore.collection('users').document(user.uid)
        user_ref.set({'is_admin': True}, merge=True)
        print(f"✓ Updated Firestore user document")

        print("\n⚠ IMPORTANT: The user must sign out and sign back in for the changes to take effect!")
        print("  The ID token needs to be refreshed to include the new admin claim.\n")

    except Exception as e:
        print(f"✗ Error granting admin access: {e}")
        sys.exit(1)


def list_users():
    """List all users in Firebase Auth"""
    print("\nListing all users:\n")
    page = admin_auth.list_users()
    count = 0

    while page:
        for user in page.users:
            count += 1
            claims = user.custom_claims or {}
            is_admin = claims.get('admin', False)
            admin_badge = " [ADMIN]" if is_admin else ""

            print(f"{count}. UID: {user.uid}{admin_badge}")
            print(f"   Email: {user.email or 'N/A'}")
            print(f"   Display Name: {user.display_name or 'N/A'}")
            print(f"   Created: {user.user_metadata.creation_timestamp}")
            print()

        page = page.get_next_page()

    print(f"Total users: {count}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/grant_admin.py <email_or_uid>  - Grant admin to specific user")
        print("  python scripts/grant_admin.py --list          - List all users")
        print("\nExamples:")
        print("  python scripts/grant_admin.py user@example.com")
        print("  python scripts/grant_admin.py abc123xyz456")
        print("  python scripts/grant_admin.py --list")
        sys.exit(1)

    if sys.argv[1] == "--list":
        list_users()
    else:
        identifier = sys.argv[1]
        grant_admin(identifier)
