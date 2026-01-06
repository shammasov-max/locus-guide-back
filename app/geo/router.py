from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.exceptions import BadRequestException
from app.geo import service
from app.geo.schemas import AutocompleteResponse, CitiesWithToursResponse, LanguagesResponse

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Query(max_length=7)] = "en",
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> AutocompleteResponse:
    # Validate that if one coord is provided, both must be
    if (lat is None) != (lon is None):
        raise BadRequestException("Both lat and lon must be provided together")

    return await service.autocomplete_cities(db, q, lang, lat, lon, limit)


@router.get("/languages", response_model=LanguagesResponse)
async def get_languages() -> LanguagesResponse:
    return await service.get_languages()


# Cities with tour counts - listed under /api/v1/cities
cities_router = APIRouter(prefix="/api/v1/cities", tags=["cities"])


@cities_router.get("", response_model=CitiesWithToursResponse)
async def get_cities_with_tours(
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Query(max_length=7)] = "en",
) -> CitiesWithToursResponse:
    cities = await service.get_cities_with_tours(db, lang)
    return CitiesWithToursResponse(count=len(cities), cities=cities)
