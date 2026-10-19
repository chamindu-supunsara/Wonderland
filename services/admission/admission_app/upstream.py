import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from admission_app.config import get_settings
from admission_app.schemas import TicketSnapshot


def read_json(url, authorization=None):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        with urlopen(Request(url, headers=headers), timeout=6) as response:
            data = response.read(1048577)
        if len(data) > 1048576:
            raise ValueError("Oversize upstream response")
        return json.loads(data)
    except HTTPError as exc:
        if exc.code in {401, 403, 404, 409}:
            raise HTTPException(
                exc.code, "Ticket or active attraction unavailable; refresh and check your access."
            ) from exc
        raise HTTPException(503, "Upstream service unavailable; retry the same request.") from exc
    except (URLError, OSError, ValueError) as exc:
        raise HTTPException(503, "Upstream service unavailable; retry the same request.") from exc


def get_ticket(reference, authorization):
    raw = read_json(
        get_settings().booking_url.rstrip("/") + "/api/v1/admin/mock-tickets/" + reference,
        authorization,
    )
    try:
        ticket = TicketSnapshot.model_validate(raw)
        if ticket.reference != reference:
            raise ValueError("Wrong ticket returned")
        return ticket
    except (ValidationError, ValueError) as exc:
        raise HTTPException(503, "Booking returned an invalid mock ticket.") from exc


class ActiveAttraction(BaseModel):
    id: UUID
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)


def get_attraction(attraction_id):
    raw = read_json(
        get_settings().catalog_url.rstrip("/") + "/api/v1/attractions/" + str(attraction_id)
    )
    try:
        row = ActiveAttraction.model_validate(raw)
        if row.id != attraction_id:
            raise ValueError("Wrong attraction returned")
        return row
    except (ValidationError, ValueError) as exc:
        raise HTTPException(503, "Catalog returned an invalid attraction.") from exc
