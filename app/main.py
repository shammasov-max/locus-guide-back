from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.cities.router import router as cities_router
from app.routes.router import router as routes_router
from app.routes.admin_router import router as routes_admin_router
from app.wishes.router import router as wishes_router
from app.wishes.admin_router import router as wishes_admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Locus Guide API",
    description="Backend API for Locus Guide audio tour application",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with /api/v1 prefix
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(cities_router, prefix="/api/v1/cities", tags=["cities"])
app.include_router(routes_router, prefix="/api/v1/routes", tags=["routes"])
app.include_router(routes_admin_router, prefix="/api/v1/routes/admin", tags=["routes-admin"])
app.include_router(wishes_router, prefix="/api/v1/wishes", tags=["wishes"])
app.include_router(wishes_admin_router, prefix="/api/v1/wishes/admin", tags=["wishes-admin"])


@app.get("/health")
def health_check():
    return {"status": "healthy"}
