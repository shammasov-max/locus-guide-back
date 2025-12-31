"""Business logic for achievements module (US-025-028)."""

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.achievements.models import Achievement, UserAchievement
from app.achievements.schemas import AchievementResponse
from app.routes.models import UserActiveTour, Tour


# Achievement thresholds (from User Stories)
TOUR_THRESHOLDS = [
    ("first_steps", 1),      # US-025
    ("curious", 5),           # US-026
    ("explorer", 15),         # US-026
    ("traveler", 30),         # US-026
    ("nomad", 50),            # US-026
    ("road_legend", 100),     # US-026
]

CITY_THRESHOLDS = [
    ("tourist", 3),           # US-027
    ("cosmopolitan", 10),     # US-027
    ("world_citizen", 25),    # US-027
    ("city_collector", 50),   # US-027
]


async def get_all_achievements(db: AsyncSession) -> list[Achievement]:
    """Get all available achievements."""
    result = await db.execute(
        select(Achievement).order_by(Achievement.category, Achievement.threshold)
    )
    return list(result.scalars().all())


async def get_user_achievements(db: AsyncSession, user_id: int) -> list[UserAchievement]:
    """Get all achievements earned by a user."""
    result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.earned_at.desc())
    )
    return list(result.scalars().all())


async def get_user_achievement_codes(db: AsyncSession, user_id: int) -> set[str]:
    """Get codes of achievements user already has."""
    result = await db.execute(
        select(Achievement.code)
        .join(UserAchievement, Achievement.id == UserAchievement.achievement_id)
        .where(UserAchievement.user_id == user_id)
    )
    return set(result.scalars().all())


async def count_completed_tours(db: AsyncSession, user_id: int, min_progress: int = 90) -> int:
    """Count tours completed by user with at least min_progress%.

    A tour is considered completed if user has finished it
    (completed_at is not null in user_active_routes).
    """
    result = await db.execute(
        select(func.count(UserActiveTour.id))
        .where(
            UserActiveTour.user_id == user_id,
            UserActiveTour.completed_at.is_not(None),
        )
    )
    return result.scalar() or 0


async def count_unique_cities(db: AsyncSession, user_id: int) -> int:
    """Count unique cities where user has completed at least one tour."""
    result = await db.execute(
        select(func.count(distinct(Tour.city_id)))
        .join(UserActiveTour, Tour.id == UserActiveTour.tour_id)
        .where(
            UserActiveTour.user_id == user_id,
            UserActiveTour.completed_at.is_not(None),
        )
    )
    return result.scalar() or 0


async def award_achievement(
    db: AsyncSession, user_id: int, achievement_code: str
) -> UserAchievement | None:
    """Award an achievement to a user if not already earned."""
    # Get achievement by code
    result = await db.execute(
        select(Achievement).where(Achievement.code == achievement_code)
    )
    achievement = result.scalar_one_or_none()

    if not achievement:
        return None

    # Check if already awarded
    result = await db.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return None  # Already has this achievement

    # Award the achievement
    user_achievement = UserAchievement(
        user_id=user_id,
        achievement_id=achievement.id,
    )
    db.add(user_achievement)
    await db.commit()
    await db.refresh(user_achievement)

    return user_achievement


async def check_and_award_achievements(
    db: AsyncSession, user_id: int
) -> list[Achievement]:
    """Check progress and award any new achievements.

    Returns list of newly awarded achievements.
    """
    # Get current stats
    tours_count = await count_completed_tours(db, user_id)
    cities_count = await count_unique_cities(db, user_id)

    # Get already earned achievements
    earned_codes = await get_user_achievement_codes(db, user_id)

    new_achievements = []

    # Check tour achievements
    for code, threshold in TOUR_THRESHOLDS:
        if code not in earned_codes and tours_count >= threshold:
            ua = await award_achievement(db, user_id, code)
            if ua:
                await db.refresh(ua, ["achievement"])
                new_achievements.append(ua.achievement)

    # Check city achievements
    for code, threshold in CITY_THRESHOLDS:
        if code not in earned_codes and cities_count >= threshold:
            ua = await award_achievement(db, user_id, code)
            if ua:
                await db.refresh(ua, ["achievement"])
                new_achievements.append(ua.achievement)

    return new_achievements


async def get_achievement_progress(
    db: AsyncSession, user_id: int, lang: str = "en"
) -> dict:
    """Get user's progress toward achievements."""
    tours_count = await count_completed_tours(db, user_id)
    cities_count = await count_unique_cities(db, user_id)
    earned_codes = await get_user_achievement_codes(db, user_id)

    # Find next tour achievement
    next_tour = None
    tours_to_next = None
    for code, threshold in TOUR_THRESHOLDS:
        if code not in earned_codes:
            result = await db.execute(
                select(Achievement).where(Achievement.code == code)
            )
            next_tour = result.scalar_one_or_none()
            tours_to_next = threshold - tours_count
            break

    # Find next city achievement
    next_city = None
    cities_to_next = None
    for code, threshold in CITY_THRESHOLDS:
        if code not in earned_codes:
            result = await db.execute(
                select(Achievement).where(Achievement.code == code)
            )
            next_city = result.scalar_one_or_none()
            cities_to_next = threshold - cities_count
            break

    return {
        "tours_completed": tours_count,
        "cities_visited": cities_count,
        "next_tour_achievement": next_tour,
        "next_city_achievement": next_city,
        "tours_to_next": tours_to_next,
        "cities_to_next": cities_to_next,
    }
