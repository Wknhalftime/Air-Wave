"""FastAPI application entry point for Airwave API.

This module initializes the FastAPI application with all routers, middleware,
and lifecycle management. It provides a RESTful API for the Airwave radio
broadcast archiving and analytics system.

The API includes endpoints for:
- System health and configuration
- Music library management (artists, recordings, albums)
- Broadcast log history and analytics
- Administrative operations (import, scan, sync)
- Universal search across tracks and logs
- Identity management (bridges, aliases, splits)

The application uses async/await throughout for optimal performance and
includes CORS middleware for frontend integration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from airwave.api.routers import (
    admin,
    analytics,
    export,
    history,
    identity,
    library,
    search,
    system,
    stations,
    discovery,
)
from airwave.core.config import settings
from airwave.core.db import AsyncSessionLocal, init_db
from airwave.core.logger import setup_logging
from airwave.core.models import SystemSetting

# Initialize Logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    await init_db()  # Ensure DB is ready before loading settings
    setup_logging()

    # Load Dynamic Settings
    async with AsyncSessionLocal() as session:
        try:
            stmt = select(SystemSetting)
            res = await session.execute(stmt)
            rows = res.scalars().all()
            for row in rows:
                if hasattr(settings, row.key):
                    # Convert to float if original is float (Basic type inference)
                    orig = getattr(settings, row.key)
                    if isinstance(orig, float):
                        setattr(settings, row.key, float(row.value))
                    elif isinstance(orig, int):
                        setattr(settings, row.key, int(row.value))
                    else:
                        setattr(settings, row.key, row.value)
        except Exception:
            # logger might not be fully configured if setup_logging failed, but safe to try
            pass

    yield
    # Shutdown


app = FastAPI(
    title="Airwave API",
    version="0.1.0",
    description="Radio Broadcast Archiving & Analytics System API",
    lifespan=lifespan,
)

# CORS - Allow Vite Frontend
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(system.router, prefix="/api/v1/system", tags=["System"])
app.include_router(library.router, prefix="/api/v1/library", tags=["Library"])
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])
app.include_router(
    analytics.router, prefix="/api/v1/analytics", tags=["Analytics"]
)
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(
    identity.router, prefix="/api/v1/identity", tags=["Identity"]
)
app.include_router(
    stations.router, prefix="/api/v1/stations", tags=["Stations"]
)
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(
    discovery.router, prefix="/api/v1/discovery", tags=["Discovery"]
)


@app.get("/")
async def root():
    return {"message": "Airwave API is running"}
