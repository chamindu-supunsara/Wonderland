from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.admin_schemas import (
    AdminAttractionResponse,
    AdminTierResponse,
    AttractionEdit,
    AttractionWrite,
    AuditResponse,
    PriceResponse,
    PriceWrite,
    RevisionRequest,
)
from app.api.routes import DatabaseSession
from app.auth import Administrator, administrator
from app.events import price_event
from app.models import Attraction, CatalogAudit, TicketPrice, TicketTier

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["administrator catalog"],
    dependencies=[Depends(administrator)],
)


def attraction_snapshot(attraction: Attraction) -> dict:
    return AdminAttractionResponse.model_validate(attraction).model_dump(mode="json")


def audit(session, user, action, resource_id, before, after):
    session.add(
        CatalogAudit(
            actor_id=user.user_id,
            action=action,
            resource_id=resource_id,
            changes={"before": before, "after": after},
        )
    )


def locked_attraction(session, attraction_id, expected_revision):
    attraction = session.scalar(
        select(Attraction)
        .where(Attraction.id == attraction_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if attraction is None:
        raise HTTPException(404, "Attraction not found")
    if attraction.revision != expected_revision:
        raise HTTPException(409, "This attraction changed. Reload it before saving again.")
    return attraction


@router.get("/attractions", response_model=list[AdminAttractionResponse])
def list_attractions(
    session: DatabaseSession,
    status: Literal["ALL", "ACTIVE", "RETIRED"] = "ALL",
):
    statement = select(Attraction).order_by(Attraction.name, Attraction.id)
    if status != "ALL":
        statement = statement.where(Attraction.status == status)
    return session.scalars(statement).all()


@router.post("/attractions", response_model=AdminAttractionResponse, status_code=201)
def create_attraction(body: AttractionWrite, session: DatabaseSession, user: Administrator):
    with session.begin():
        attraction = Attraction(**body.model_dump())
        session.add(attraction)
        session.flush()
        result = attraction_snapshot(attraction)
        audit(session, user, "ATTRACTION_CREATED", attraction.id, None, result)
    return result


@router.put("/attractions/{attraction_id}", response_model=AdminAttractionResponse)
def edit_attraction(
    attraction_id: UUID,
    body: AttractionEdit,
    session: DatabaseSession,
    user: Administrator,
):
    with session.begin():
        attraction = locked_attraction(session, attraction_id, body.expected_revision)
        if attraction.status == "RETIRED":
            raise HTTPException(409, "Retired attractions are read only.")
        before = attraction_snapshot(attraction)
        for field, value in body.model_dump(exclude={"expected_revision"}).items():
            setattr(attraction, field, value)
        attraction.revision += 1
        session.flush()
        result = attraction_snapshot(attraction)
        audit(session, user, "ATTRACTION_UPDATED", attraction.id, before, result)
    return result


@router.post("/attractions/{attraction_id}/retire", response_model=AdminAttractionResponse)
def retire_attraction(
    attraction_id: UUID,
    body: RevisionRequest,
    session: DatabaseSession,
    user: Administrator,
):
    with session.begin():
        attraction = locked_attraction(session, attraction_id, body.expected_revision)
        if attraction.status == "ACTIVE":
            before = attraction_snapshot(attraction)
            attraction.status = "RETIRED"
            attraction.revision += 1
            session.flush()
            audit(
                session,
                user,
                "ATTRACTION_RETIRED",
                attraction.id,
                before,
                attraction_snapshot(attraction),
            )
        result = attraction_snapshot(attraction)
    return result


@router.get("/ticket-tiers", response_model=list[AdminTierResponse])
def list_tiers(session: DatabaseSession):
    rows = session.execute(
        select(TicketTier, TicketPrice)
        .join(TicketPrice)
        .where(TicketPrice.active.is_(True))
        .order_by(TicketTier.max_guests, TicketTier.code)
    ).all()
    return [
        AdminTierResponse(
            id=tier.id,
            code=tier.code,
            name=tier.name,
            min_guests=tier.min_guests,
            max_guests=tier.max_guests,
            active=tier.active,
            amount_minor=price.amount_minor,
            currency=price.currency,
            price_version=price.version,
        )
        for tier, price in rows
    ]


@router.get("/ticket-tiers/{tier_id}/prices", response_model=list[PriceResponse])
def price_history(tier_id: UUID, session: DatabaseSession):
    if session.get(TicketTier, tier_id) is None:
        raise HTTPException(404, "Ticket tier not found")
    return session.scalars(
        select(TicketPrice)
        .where(TicketPrice.tier_id == tier_id)
        .order_by(TicketPrice.version.desc())
    ).all()


@router.post("/ticket-tiers/{tier_id}/prices", response_model=PriceResponse, status_code=201)
def publish_price(tier_id: UUID, body: PriceWrite, session: DatabaseSession, user: Administrator):
    # A lock on the stable tier row serializes writers, including replacement of the active price.
    with session.begin():
        tier = session.scalar(select(TicketTier).where(TicketTier.id == tier_id).with_for_update())
        if tier is None:
            raise HTTPException(404, "Ticket tier not found")
        if not tier.active:
            raise HTTPException(409, "This ticket tier is inactive.")
        current = session.scalar(
            select(TicketPrice)
            .where(TicketPrice.tier_id == tier_id, TicketPrice.active.is_(True))
            .execution_options(populate_existing=True)
        )
        if current is None or current.version != body.expected_version:
            raise HTTPException(409, "The price changed. Reload pricing before publishing again.")
        if current.amount_minor == body.amount_minor:
            raise HTTPException(409, "Enter a different price to publish a new version.")
        before = PriceResponse.model_validate(current).model_dump(mode="json")
        current.active = False
        session.flush()  # Release the partial unique-index slot before inserting its successor.
        price = TicketPrice(
            tier_id=tier_id,
            amount_minor=body.amount_minor,
            currency=current.currency,
            version=current.version + 1,
            created_by=user.user_id,
        )
        session.add(price)
        session.flush()
        result = PriceResponse.model_validate(price).model_dump(mode="json")
        audit(session, user, "PRICE_PUBLISHED", tier_id, before, result)
        price_event(session, tier, price)
    return result


@router.get("/audit", response_model=list[AuditResponse])
def list_audit(
    session: DatabaseSession,
    resource_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
):
    statement = select(CatalogAudit).order_by(
        CatalogAudit.created_at.desc(), CatalogAudit.id.desc()
    )
    if resource_id:
        statement = statement.where(CatalogAudit.resource_id == resource_id)
    return session.scalars(statement.limit(limit)).all()
