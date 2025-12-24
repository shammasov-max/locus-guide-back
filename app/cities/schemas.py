from pydantic import BaseModel, Field
from typing import Optional


class UserLocation(BaseModel):
    """User's geographic location"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class CityResponse(BaseModel):
    """Single city in autocomplete results"""
    geoname_id: int = Field(..., description="GeoNames ID")
    name: str = Field(..., description="Default city name (ASCII)")
    local_name: str = Field(..., description="City name in requested language")
    country_code: str = Field(..., description="ISO 2-letter country code")
    country_name: Optional[str] = Field(None, description="Country name")
    admin1: Optional[str] = Field(None, description="Admin level 1 (state/region)")
    population: int = Field(..., description="City population")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    distance_km: Optional[float] = Field(None, description="Distance from user in km")
    timezone: Optional[str] = Field(None, description="Timezone identifier")

    class Config:
        from_attributes = True


class AutocompleteRequest(BaseModel):
    """Request parameters for autocomplete endpoint"""
    q: str = Field(..., min_length=1, max_length=200, description="Search query")
    lang: str = Field("en", description="Language for results (en, ru, de)")
    lat: Optional[float] = Field(None, ge=-90, le=90, description="User latitude")
    lon: Optional[float] = Field(None, ge=-180, le=180, description="User longitude")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class AutocompleteResponse(BaseModel):
    """Response from autocomplete endpoint"""
    query: str = Field(..., description="Original search query")
    lang: str = Field(..., description="Language used for results")
    user_location: Optional[UserLocation] = Field(None, description="User coordinates used for distance calculation")
    count: int = Field(..., description="Number of results returned")
    cities: list[CityResponse] = Field(default_factory=list, description="Matching cities")
