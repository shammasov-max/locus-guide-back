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

    model_config = {"from_attributes": True}


class AutocompleteResponse(BaseModel):
    """Response from autocomplete endpoint"""
    query: str = Field(..., description="Original search query")
    lang: str = Field(..., description="Language used for results")
    user_location: Optional[UserLocation] = Field(None, description="User coordinates used for distance calculation")
    count: int = Field(..., description="Number of results returned")
    cities: list[CityResponse] = Field(default_factory=list, description="Matching cities")
