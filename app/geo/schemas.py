from pydantic import BaseModel, Field


class CityResult(BaseModel):
    geoname_id: int
    name: str
    local_name: str | None = None
    country_code: str
    country_name: str | None = None
    admin1: str | None = None
    population: int
    lat: float
    lon: float
    distance_km: float | None = None
    timezone: str | None = None


class UserLocation(BaseModel):
    lat: float
    lon: float
    source: str  # gps, geoip, header


class AutocompleteResponse(BaseModel):
    query: str
    lang: str
    user_location: UserLocation | None = None
    count: int
    cities: list[CityResult]


class LanguageInfo(BaseModel):
    code: str
    name: str
    native_name: str | None = None


class LanguagesResponse(BaseModel):
    languages: list[LanguageInfo]
    default: str


class CityWithToursCount(BaseModel):
    geoname_id: int
    name: str
    local_name: str | None = None
    country_code: str
    country_name: str | None = None
    lat: float
    lon: float
    tour_count: int


class CitiesWithToursResponse(BaseModel):
    count: int
    cities: list[CityWithToursCount]


class AutocompleteParams(BaseModel):
    q: str = Field(..., min_length=1, max_length=200)
    lang: str = Field("en", max_length=7)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    limit: int = Field(10, ge=1, le=50)
