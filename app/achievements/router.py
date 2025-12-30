"""API endpoints for achievements module (US-025-028)."""

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from typing import Annotated

from app.auth.dependencies import CurrentUser
from app.database import get_db
from app.achievements import service
from app.achievements.schemas import (
    AchievementResponse,
    AchievementListResponse,
    UserAchievementsResponse,
    UserAchievementResponse,
    CheckAchievementsResponse,
    AchievementProgressResponse,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _achievement_to_response(achievement, lang: str = "en") -> AchievementResponse:
    """Convert Achievement model to response with localized text."""
    title = achievement.title_i18n.get(lang) or achievement.title_i18n.get("en", "")
    description = None
    if achievement.description_i18n:
        description = achievement.description_i18n.get(lang) or achievement.description_i18n.get("en")

    return AchievementResponse(
        id=achievement.id,
        code=achievement.code,
        title=title,
        description=description,
        icon_url=achievement.icon_url,
        category=achievement.category,
        threshold=achievement.threshold,
    )


@router.get(
    "",
    response_model=AchievementListResponse,
)
async def get_all_achievements(
    db: DbSession,
    lang: str = Query("en", description="Language for i18n content"),
):
    """Get all available achievements."""
    achievements = await service.get_all_achievements(db)
    return AchievementListResponse(
        achievements=[_achievement_to_response(a, lang) for a in achievements],
        count=len(achievements),
    )


@router.get(
    "/me",
    response_model=UserAchievementsResponse,
)
async def get_my_achievements(
    current_user: CurrentUser,
    db: DbSession,
    lang: str = Query("en", description="Language for i18n content"),
):
    """Get current user's earned achievements."""
    user_achievements = await service.get_user_achievements(db, current_user.id)

    responses = []
    for ua in user_achievements:
        responses.append(
            UserAchievementResponse(
                achievement=_achievement_to_response(ua.achievement, lang),
                earned_at=ua.earned_at,
            )
        )

    return UserAchievementsResponse(
        achievements=responses,
        count=len(responses),
    )


@router.post(
    "/check",
    response_model=CheckAchievementsResponse,
)
async def check_achievements(
    current_user: CurrentUser,
    db: DbSession,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Check and award any new achievements for current user.

    This endpoint should be called after:
    - Completing a trip
    - Starting a trip in a new city
    - Any other action that might trigger an achievement

    Returns list of newly earned achievements.
    """
    new_achievements = await service.check_and_award_achievements(db, current_user.id)
    all_achievements = await service.get_user_achievements(db, current_user.id)

    return CheckAchievementsResponse(
        new_achievements=[_achievement_to_response(a, lang) for a in new_achievements],
        total_earned=len(all_achievements),
    )


@router.get(
    "/progress",
    response_model=AchievementProgressResponse,
)
async def get_achievement_progress(
    current_user: CurrentUser,
    db: DbSession,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Get user's progress toward achievements.

    Returns:
    - Current trip and city counts
    - Next achievement to earn in each category
    - How many more trips/cities needed
    """
    progress = await service.get_achievement_progress(db, current_user.id, lang)

    return AchievementProgressResponse(
        trips_completed=progress["trips_completed"],
        cities_visited=progress["cities_visited"],
        next_trip_achievement=(
            _achievement_to_response(progress["next_trip_achievement"], lang)
            if progress["next_trip_achievement"]
            else None
        ),
        next_city_achievement=(
            _achievement_to_response(progress["next_city_achievement"], lang)
            if progress["next_city_achievement"]
            else None
        ),
        trips_to_next=progress["trips_to_next"],
        cities_to_next=progress["cities_to_next"],
    )
