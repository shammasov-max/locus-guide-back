"""User-facing endpoints for wishes (routes) and wants (cities)."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.wishes.dependencies import WishServiceDep
from app.auth.dependencies import CurrentUser
from app.wishes.schemas import (
    WishedRouteResponse,
    WantedCityResponse,
    UserWishesResponse,
    WishActionResponse,
)

router = APIRouter()


# ========== Wished Routes ==========

@router.post(
    "/routes/{route_id}/wish",
    response_model=WishedRouteResponse,
    status_code=status.HTTP_201_CREATED,
)
def wish_route(
    route_id: UUID,
    wish_service: WishServiceDep,
    current_user: CurrentUser,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Wish a coming_soon route to receive notification when published.

    - Route must have status 'coming_soon'
    - Cannot wish a route you have already completed
    - Idempotent: re-wishing reactivates an inactive wish
    """
    result = wish_service.wish_route(current_user.id, route_id, lang)
    if result.get("error"):
        if result["code"] == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    return result


@router.delete("/routes/{route_id}/wish", response_model=WishedRouteResponse)
def unwish_route(
    route_id: UUID,
    wish_service: WishServiceDep,
    current_user: CurrentUser,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Unwish a route (unsubscribe from notifications).

    Soft deletes the wish - can be reactivated by wishing again.
    """
    result = wish_service.unwish_route(current_user.id, route_id, lang)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wish not found"
        )
    return result


@router.get("/routes/{route_id}/wish", response_model=WishedRouteResponse)
def get_route_wish_status(
    route_id: UUID,
    wish_service: WishServiceDep,
    current_user: CurrentUser,
    lang: str = Query("en", description="Language for i18n content"),
):
    """Get user's wish status for a specific route."""
    result = wish_service.get_wished_route(current_user.id, route_id, lang)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No wish found for this route"
        )
    return result


# ========== Wanted Cities ==========

@router.post(
    "/cities/{geonameid}/want",
    response_model=WantedCityResponse,
    status_code=status.HTTP_201_CREATED,
)
def want_city(
    geonameid: int,
    wish_service: WishServiceDep,
    current_user: CurrentUser,
):
    """
    Want a city to receive notification when first route is added.

    - Can want any city in GeoNames database
    - Idempotent: re-wanting reactivates an inactive want
    """
    result = wish_service.want_city(current_user.id, geonameid)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="City not found"
        )
    return result


@router.delete("/cities/{geonameid}/want", response_model=WantedCityResponse)
def unwant_city(
    geonameid: int,
    wish_service: WishServiceDep,
    current_user: CurrentUser,
):
    """
    Unwant a city (unsubscribe from notifications).

    Soft deletes the want - can be reactivated by wanting again.
    """
    result = wish_service.unwant_city(current_user.id, geonameid)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Want not found"
        )
    return result


@router.get("/cities/{geonameid}/want", response_model=WantedCityResponse)
def get_city_want_status(
    geonameid: int,
    wish_service: WishServiceDep,
    current_user: CurrentUser,
):
    """Get user's want status for a specific city."""
    result = wish_service.get_wanted_city(current_user.id, geonameid)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No want found for this city"
        )
    return result


# ========== User's Wishes ==========

@router.get("/me", response_model=UserWishesResponse)
def get_my_wishes(
    wish_service: WishServiceDep,
    current_user: CurrentUser,
    lang: str = Query("en", description="Language for i18n content"),
):
    """Get all user's active wishes and wants."""
    wished = wish_service.get_user_wished_routes(
        current_user.id, active_only=True, lang=lang
    )
    wanted = wish_service.get_user_wanted_cities(
        current_user.id, active_only=True
    )
    return {"wished_routes": wished, "wanted_cities": wanted}
