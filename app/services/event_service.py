"""
app/services/event_service.py
──────────────────────────────
Business logic for Event CRUD and lifecycle.

Authorization:
    CREATE / UPDATE / DELETE  — any authenticated user (role=user or brand)
    LIST / GET                — public (open events)
"""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventStatus, EventCategory
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate


async def get_event_by_id(
    db: AsyncSession, event_id: uuid.UUID
) -> Optional[Event]:
    result = await db.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def list_events(
    db: AsyncSession,
    posted_by_user_id: Optional[uuid.UUID]     = None,
    event_category:    Optional[EventCategory] = None,
    city:              Optional[str]            = None,
    collab_type:       Optional[str]            = None,
    max_min_followers: Optional[int]            = None,
    limit:  int = 20,
    offset: int = 0,
) -> List[Event]:
    """
    Public event marketplace.
    - Default: open events only.
    - posted_by_user_id: host sees their own events of all statuses.
    - city, category, collab_type: filter for influencer discovery.
    - max_min_followers: influencer sees only events they qualify for.
    """
    query = select(Event)

    if posted_by_user_id:
        query = query.where(Event.posted_by_user_id == posted_by_user_id)
    else:
        query = query.where(Event.status == EventStatus.OPEN)

    if event_category:
        query = query.where(Event.event_category == event_category)
    if city:
        query = query.where(Event.location_city.ilike(f"%{city}%"))
    if collab_type:
        query = query.where(Event.collab_type == collab_type)
    if max_min_followers is not None:
        query = query.where(Event.min_followers <= max_min_followers)

    query = query.order_by(Event.event_date.asc().nullslast(), Event.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def create_event(
    db: AsyncSession,
    user: User,
    payload: EventCreate,
) -> Event:
    event = Event(
        posted_by_user_id=user.id,
        **payload.model_dump(exclude_none=False),
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def update_event(
    db: AsyncSession,
    event: Event,
    user: User,
    payload: EventUpdate,
) -> Event:
    if event.posted_by_user_id != user.id:
        raise PermissionError("You did not post this event.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def cancel_event(
    db: AsyncSession,
    event: Event,
    user: User,
) -> Event:
    if event.posted_by_user_id != user.id:
        raise PermissionError("You did not post this event.")
    event.status = EventStatus.CANCELLED
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event
