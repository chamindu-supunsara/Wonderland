from fastapi import APIRouter

from app.auth import Administrator, CurrentUser, Principal

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get("/users/me", response_model=Principal)
def profile(user: CurrentUser):
    """Identity comes exclusively from the verified access token, never a request-supplied ID."""
    return user


@router.get("/admin/access-check")
def admin_access(user: Administrator):
    return {"status": "authorized", "role": user.role}
