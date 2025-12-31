"""Admin endpoints for wish analytics."""

from fastapi import APIRouter, Query

from app.wishes.dependencies import WishServiceDep
from app.auth.dependencies import RequireEditor
from app.wishes.schemas import WishStatsListResponse, WantStatsListResponse

router = APIRouter()


@router.get("/routes/stats", response_model=WishStatsListResponse)
def get_route_wish_stats(
    wish_service: WishServiceDep,
    current_user: RequireEditor,
    status: list[str] | None = Query(
        None,
        description="Filter by tour status (coming_soon, published, etc)"
    ),
    city_id: int | None = Query(None, description="Filter by city geonameid"),
    min_wishes: int = Query(0, ge=0, description="Minimum active wish count"),
    lang: str = Query("en", description="Language for i18n content"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Get aggregated wish counts per tour for prioritization.

    Sorted by active wish count (descending).
    Use to identify which coming_soon tours have most demand.
    Requires editor role.
    """
    return wish_service.get_route_wish_stats(
        status_filter=status,
        city_id=city_id,
        min_wishes=min_wishes,
        limit=limit,
        offset=offset,
        lang=lang,
    )


@router.get("/cities/stats", response_model=WantStatsListResponse)
def get_city_want_stats(
    wish_service: WishServiceDep,
    current_user: RequireEditor,
    country_code: str | None = Query(
        None,
        min_length=2,
        max_length=2,
        description="Filter by country ISO code (e.g., US, DE)"
    ),
    has_routes: bool | None = Query(
        None,
        description="Filter by whether city has published tours"
    ),
    min_wants: int = Query(0, ge=0, description="Minimum active want count"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Get aggregated want counts per city for expansion planning.

    Sorted by active want count (descending).
    Use to identify which cities users want tours in most.
    Requires editor role.
    """
    return wish_service.get_city_want_stats(
        country_code=country_code,
        has_routes=has_routes,
        min_wants=min_wants,
        limit=limit,
        offset=offset,
    )
