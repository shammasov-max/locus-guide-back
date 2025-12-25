from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.cities.router import router as cities_router
from app.routes.router import router as routes_router


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


@app.get("/health")
def health_check():
    return {"status": "healthy"}
