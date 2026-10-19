from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.admin import router as admin_router
from app.api.identity import router as identity_router
from app.api.routes import DatabaseSession, router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Public catalog, Cognito identity, and protected administrator updates.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "ok", "service": "catalog"}

    @app.get("/health/ready", tags=["health"])
    def ready(session: DatabaseSession):
        try:
            # Readiness checks migration state as well as database connectivity.
            session.execute(text("SELECT id, revision, seed_key FROM catalog.attractions LIMIT 1"))
            session.execute(text("SELECT id, created_by FROM catalog.ticket_prices LIMIT 1"))
            session.execute(text("SELECT id FROM catalog.audit_events LIMIT 1"))
            session.execute(text("SELECT published_at FROM catalog.outbox_events LIMIT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="Catalog storage is not ready") from exc
        return {"status": "ready", "service": "catalog"}

    app.include_router(router)
    app.include_router(identity_router)
    app.include_router(admin_router)
    return app


app = create_app()
