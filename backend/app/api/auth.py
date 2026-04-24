import logging
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth, firestore
from app.db.firebase import get_db, USER_PROFILES_COLLECTION

logger = logging.getLogger(__name__)


def _verify_authorization_header(authorization: Optional[str]) -> str:
    """
    Extract and verify Firebase ID token from Authorization header.

    Args:
        authorization: Raw Authorization header value.

    Returns:
        Firebase UID.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header format")

    token = parts[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded.get("uid")
        if not uid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return uid
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def ensure_user_profile(uid: str) -> None:
    """Ensure a Firestore user profile exists and update the timestamp."""
    db = get_db()
    user_ref = db.collection(USER_PROFILES_COLLECTION).document(uid)
    doc = user_ref.get()

    base_profile = {
        "profile_embedding": None,
        "liked_count": 0,
        "disliked_count": 0,
        "is_admin": False,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    if not doc.exists:
        user_ref.set(base_profile)
    else:
        user_ref.set({"updated_at": firestore.SERVER_TIMESTAMP}, merge=True)


def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Dependency to obtain the authenticated Firebase UID.
    Verifies the ID token and ensures the Firestore profile exists.
    """
    uid = _verify_authorization_header(authorization)
    ensure_user_profile(uid)
    return uid


def get_current_admin_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Dependency to obtain the authenticated Firebase UID with admin claim.
    """
    uid = _verify_authorization_header(authorization)
    try:
        decoded = firebase_auth.verify_id_token(authorization.split()[1])
        if not decoded.get("admin", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    except Exception:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")

    ensure_user_profile(uid)
    return uid


# Alias for consistency
require_admin = get_current_admin_user_id
