"""Add missing demo records without resetting administrator changes or existing prices."""

from sqlalchemy import select

from app.db import session_factory
from app.models import Attraction, TicketPrice, TicketTier

ATTRACTIONS = [
    {
        "name": "Skyline Rush",
        "description": "Climb above the park before a fast coaster run through sweeping turns.",
        "category": "ROLLER_COASTER",
        "thrill_level": "HIGH",
        "min_age": 12,
        "min_height_cm": 140,
        "guidance_text": "High-speed ride. Follow staff instructions and posted health guidance.",
    },
    {
        "name": "Little Explorers",
        "description": "A gentle adventure through a colourful world made for younger visitors.",
        "category": "KIDS",
        "thrill_level": "LOW",
        "min_age": 3,
        "min_height_cm": None,
        "guidance_text": "Children must be accompanied by a responsible adult.",
    },
    {
        "name": "River Rapids",
        "description": "Share a raft and follow the river through splashes, bends, and waterfalls.",
        "category": "WATER",
        "thrill_level": "MEDIUM",
        "min_age": 6,
        "min_height_cm": 110,
        "guidance_text": "Expect to get wet. Secure loose items before boarding.",
    },
    {
        "name": "Wonder Quest",
        "description": (
            "Work together to solve playful challenges in an interactive discovery zone."
        ),
        "category": "INTERACTIVE",
        "thrill_level": "LOW",
        "min_age": None,
        "min_height_cm": None,
        "guidance_text": "All ages welcome. Younger children should have adult supervision.",
    },
]
TIERS = [
    ("INDIVIDUAL", "Individual", 1, 1, 4000),
    ("COUPLE", "Couple", 2, 2, 7500),
    ("FAMILY", "Family", 1, 4, 14000),
    ("GROUP", "Group", 1, 5, 16500),
]


def seed() -> None:
    with session_factory().begin() as session:
        for data in ATTRACTIONS:
            seed_key = data["name"].lower().replace(" ", "-")
            existing = session.scalar(select(Attraction).where(Attraction.seed_key == seed_key))
            if existing is None:
                session.add(Attraction(**data, seed_key=seed_key))
        for code, name, minimum, maximum, amount in TIERS:
            tier = session.scalar(select(TicketTier).where(TicketTier.code == code))
            if tier is None:
                tier = TicketTier(code=code, name=name, min_guests=minimum, max_guests=maximum)
                session.add(tier)
                session.flush()
                session.add(TicketPrice(tier_id=tier.id, amount_minor=amount, currency="USD"))
    print("Demo attractions and ticket tiers are ready (existing records preserved).")


if __name__ == "__main__":
    seed()
