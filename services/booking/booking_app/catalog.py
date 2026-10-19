import json
from urllib.error import URLError
from urllib.request import urlopen
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from booking_app.config import get_settings
from booking_app.schemas import TierQuote


def get_quote(tier_id: UUID) -> TierQuote:
    # Interim service API dependency; replace with the pricing projection in Step 05.
    try:
        url = get_settings().catalog_url.rstrip("/") + "/api/v1/ticket-tiers"
        with urlopen(url, timeout=5) as response:  # Fixed configured host, no browser credentials.
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Oversize catalog response")
        quotes = [TierQuote.model_validate(item) for item in json.loads(raw)]
    except (URLError, TimeoutError, OSError, ValueError, TypeError, ValidationError) as exc:
        raise HTTPException(503, "Pricing is unavailable. Retry the same booking attempt.") from exc
    for quote in quotes:
        if quote.id == tier_id:
            return quote
    raise HTTPException(409, "This ticket tier is no longer available. Reload the catalog.")
