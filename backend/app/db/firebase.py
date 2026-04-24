import firebase_admin
from firebase_admin import credentials, firestore
from app.config import settings
import os
import logging

logger = logging.getLogger(__name__)

# Global Firestore client
_db = None


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global _db

    if _db is not None:
        return _db

    try:
        # Check if already initialized
        firebase_admin.get_app()
        logger.info("Firebase already initialized")
    except ValueError:
        # Initialize Firebase
        cred_path = settings.firebase_credentials_path

        if not os.path.exists(cred_path):
            logger.error(f"Firebase credentials file not found: {cred_path}")
            raise FileNotFoundError(
                f"Firebase credentials file not found: {cred_path}. "
                "Please download your service account key from Firebase Console "
                "and save it as 'serviceAccountKey.json' in the backend directory."
            )

        cred = credentials.Certificate(cred_path)

        if settings.firebase_project_id:
            firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id
            })
        else:
            firebase_admin.initialize_app(cred)

        logger.info("Firebase Admin SDK initialized successfully")

    # Get Firestore client
    _db = firestore.client()
    return _db


def get_db():
    """Get Firestore database client"""
    global _db

    if _db is None:
        _db = initialize_firebase()

    return _db


# Collection names
GAMES_COLLECTION = "games"
USER_PROFILES_COLLECTION = "users"
USER_FEEDBACK_COLLECTION = "user_feedback"  # legacy; new feedback stored under users/{uid}/feedback
