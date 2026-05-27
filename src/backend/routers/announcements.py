"""Announcement endpoints for the High School Management System API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..database import announcements_collection
from .auth import get_teacher_from_session_token

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    """Payload used to create or update announcements."""

    title: str = Field(..., min_length=3, max_length=80)
    message: str = Field(..., min_length=8, max_length=280)
    start_date: Optional[datetime] = None
    expires_at: datetime


def require_teacher(session_token: Optional[str]) -> Dict[str, Any]:
    """Validate that a server-issued session token is present and valid."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    return get_teacher_from_session_token(session_token)


def serialize_announcement(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a MongoDB document to an API-safe announcement object."""
    return {
        "id": document["_id"],
        "title": document["title"],
        "message": document["message"],
        "start_date": document.get("start_date").isoformat() if document.get("start_date") else None,
        "expires_at": document["expires_at"].isoformat(),
        "created_by": document.get("created_by"),
        "created_at": document.get("created_at").isoformat() if document.get("created_at") else None,
        "updated_at": document.get("updated_at").isoformat() if document.get("updated_at") else None,
    }


def validate_announcement_dates(payload: AnnouncementPayload) -> None:
    """Ensure announcement dates are coherent."""
    if payload.start_date and payload.start_date >= payload.expires_at:
        raise HTTPException(status_code=400, detail="Start date must be before expiration date")


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return currently active announcements for the public banner."""
    now = datetime.utcnow()
    query = {
        "$and": [
            {"expires_at": {"$gt": now}},
            {
                "$or": [
                    {"start_date": None},
                    {"start_date": {"$lte": now}},
                ]
            },
        ]
    }
    documents = announcements_collection.find(query).sort([("expires_at", 1), ("created_at", -1)])
    return [serialize_announcement(document) for document in documents]


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_manageable_announcements(
    session_token: Optional[str] = Header(None, alias="X-Session-Token")
) -> List[Dict[str, Any]]:
    """Return all announcements for authenticated management screens."""
    require_teacher(session_token)
    documents = announcements_collection.find({}).sort([("expires_at", 1), ("created_at", -1)])
    return [serialize_announcement(document) for document in documents]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    payload: AnnouncementPayload,
    session_token: Optional[str] = Header(None, alias="X-Session-Token")
) -> Dict[str, Any]:
    """Create a new announcement."""
    teacher = require_teacher(session_token)
    validate_announcement_dates(payload)

    now = datetime.utcnow()
    document = {
        "_id": uuid4().hex,
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": payload.start_date,
        "expires_at": payload.expires_at,
        "created_by": teacher["username"],
        "created_at": now,
        "updated_at": now,
    }
    announcements_collection.insert_one(document)
    return serialize_announcement(document)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    session_token: Optional[str] = Header(None, alias="X-Session-Token")
) -> Dict[str, Any]:
    """Update an existing announcement."""
    teacher = require_teacher(session_token)
    validate_announcement_dates(payload)

    existing = announcements_collection.find_one({"_id": announcement_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updates = {
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": payload.start_date,
        "expires_at": payload.expires_at,
        "created_by": teacher["username"],
        "updated_at": datetime.utcnow(),
    }
    announcements_collection.update_one({"_id": announcement_id}, {"$set": updates})

    updated = {**existing, **updates}
    return serialize_announcement(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    session_token: Optional[str] = Header(None, alias="X-Session-Token")
) -> Dict[str, str]:
    """Delete an announcement."""
    require_teacher(session_token)
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
