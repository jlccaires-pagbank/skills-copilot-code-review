"""
Authentication endpoints for the High School Management System API
"""

from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from ..database import teachers_collection, verify_password

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

SESSION_TTL = timedelta(hours=8)
active_sessions: Dict[str, Dict[str, Any]] = {}


def get_teacher_from_session_token(session_token: str) -> Dict[str, Any]:
    """Validate a server-issued session token and return the teacher."""
    session = active_sessions.get(session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    if session["expires_at"] <= datetime.utcnow():
        active_sessions.pop(session_token, None)
        raise HTTPException(status_code=401, detail="Session expired")

    teacher = teachers_collection.find_one({"_id": session["username"]})
    if not teacher:
        active_sessions.pop(session_token, None)
        raise HTTPException(status_code=401, detail="Invalid session")

    return teacher


@router.post("/login")
def login(username: str, password: str) -> Dict[str, Any]:
    """Login a teacher account"""
    # Find the teacher in the database
    teacher = teachers_collection.find_one({"_id": username})

    # Verify password using Argon2 verifier from database.py
    if not teacher or not verify_password(teacher.get("password", ""), password):
        raise HTTPException(
            status_code=401, detail="Invalid username or password")

    session_token = token_urlsafe(32)
    active_sessions[session_token] = {
        "username": teacher["username"],
        "expires_at": datetime.utcnow() + SESSION_TTL
    }

    # Return teacher information (excluding password)
    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "session_token": session_token
    }


@router.get("/check-session")
def check_session(session_token: str) -> Dict[str, Any]:
    """Check if a server-issued session token is valid."""
    teacher = get_teacher_from_session_token(session_token)

    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "session_token": session_token
    }
