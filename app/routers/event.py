"""
app/routers/event.py
─────────────────────
Event hiring system endpoints.

Prefix: /api/v1/events

Permission matrix:
    GET  /                  — public (open events)
    GET  /{id}              — public
    GET  /my/events         — event host sees own events
    POST /                  — any authenticated user
    PATCH/{id}              — event host only
    DELETE /{id}            — event host only (soft-cancel)
    GET  /{id}/applications — event host only
    POST /{id}/applications/{app_id}/decide — event host only
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.application import ApplicationStatus
from app.models.user import User
from app.schemas.application import ApplicationDecision, ApplicationResponse, ApplicationSummary
from app.schemas.event import EventCreate, EventResponse, EventSummary, EventUpdate
from app.services.application_service import (
    decide_application, get_application_by_id, list_applications_for_event,
)
from app.services.event_service import (
    cancel_event, create_event, get_event_by_id, list_events, update_event,
)

router = APIRouter(prefix="/events", tags=["Events (Hiring)"])


@router.get("/", response_model=List[EventSummary], summary="Browse open events (public)")
async def browse_events(
    event_category: Optional[str] = Query(None),
    city:           Optional[str] = Query(None),
    collab_type:    Optional[str] = Query(None, description="paid | unpaid"),
    my_followers:   Optional[int] = Query(None, ge=0,
        description="Your follower count — filters events you qualify for"),
    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await list_events(
        db, event_category=event_category, city=city,
        collab_type=collab_type, max_min_followers=my_followers,
        limit=limit, offset=offset,
    )


@router.get("/my/events", response_model=List[EventSummary],
            summary="Events posted by the current user")
async def my_events(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_events(db, posted_by_user_id=current_user.id, limit=100)


@router.get("/{event_id}", response_model=EventResponse, summary="Event detail (public)")
async def get_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


@router.post("/", response_model=EventResponse, status_code=201,
             summary="Post a new event (any authenticated user)")
async def create_new_event(
    payload: EventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_event(db, current_user, payload)


@router.patch("/{event_id}", response_model=EventResponse,
              summary="Update an event (host only)")
async def update_existing_event(
    event_id: uuid.UUID,
    payload: EventUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    try:
        return await update_event(db, event, current_user, payload)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{event_id}", status_code=204,
               summary="Cancel an event (host only)")
async def cancel_existing_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    try:
        await cancel_event(db, event, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/{event_id}/applications", response_model=List[ApplicationSummary],
            summary="View applications for an event (host only)")
async def get_event_applications(
    event_id: uuid.UUID,
    app_status: Optional[ApplicationStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    if event.posted_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return await list_applications_for_event(db, event_id, status=app_status)


@router.post("/{event_id}/applications/{app_id}/decide",
             response_model=ApplicationResponse,
             summary="Accept or reject an application (host only)")
async def decide_event_application(
    event_id: uuid.UUID,
    app_id:   uuid.UUID,
    payload:  ApplicationDecision,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    application = await get_application_by_id(db, app_id)
    if not application or application.event_id != event_id:
        raise HTTPException(status_code=404, detail="Application not found.")
    try:
        return await decide_application(db, application, current_user, payload)
    except (ValueError, PermissionError) as e:
        code = 403 if isinstance(e, PermissionError) else 400
        raise HTTPException(status_code=code, detail=str(e))
