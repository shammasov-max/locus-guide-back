"""Pydantic schemas for achievements module (US-025-028)."""

from datetime import datetime

from pydantic import BaseModel, Field


class AchievementResponse(BaseModel):
    """Achievement details."""

    id: int
    code: str
    title: str
    description: str | None = None
    icon_url: str | None = None
    category: str
    threshold: int

    model_config = {"from_attributes": True}


class UserAchievementResponse(BaseModel):
    """User's earned achievement with earn date."""

    achievement: AchievementResponse
    earned_at: datetime

    model_config = {"from_attributes": True}


class AchievementListResponse(BaseModel):
    """List of all available achievements."""

    achievements: list[AchievementResponse]
    count: int


class UserAchievementsResponse(BaseModel):
    """List of user's earned achievements."""

    achievements: list[UserAchievementResponse]
    count: int


class CheckAchievementsResponse(BaseModel):
    """Response after checking for new achievements."""

    new_achievements: list[AchievementResponse]
    total_earned: int


class AchievementProgressResponse(BaseModel):
    """Progress toward achievements."""

    trips_completed: int = Field(..., description="Trips completed with >90% progress")
    cities_visited: int = Field(..., description="Unique cities with completed trips")
    next_trip_achievement: AchievementResponse | None = None
    next_city_achievement: AchievementResponse | None = None
    trips_to_next: int | None = Field(None, description="Trips needed for next achievement")
    cities_to_next: int | None = Field(None, description="Cities needed for next achievement")
