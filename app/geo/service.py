from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.geo.models import City, CitySearchIndex
from app.geo.schemas import (
    AutocompleteResponse,
    CityResult,
    CityWithToursCount,
    LanguageInfo,
    LanguagesResponse,
    UserLocation,
)
from app.tours.models import Tour

SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English"},
    {"code": "ru", "name": "Russian", "native_name": "Русский"},
    {"code": "de", "name": "German", "native_name": "Deutsch"},
    {"code": "fr", "name": "French", "native_name": "Français"},
    {"code": "es", "name": "Spanish", "native_name": "Español"},
    {"code": "it", "name": "Italian", "native_name": "Italiano"},
    {"code": "pt", "name": "Portuguese", "native_name": "Português"},
    {"code": "zh", "name": "Chinese", "native_name": "中文"},
    {"code": "ja", "name": "Japanese", "native_name": "日本語"},
    {"code": "ko", "name": "Korean", "native_name": "한국어"},
]


async def autocomplete_cities(
    db: AsyncSession,
    query: str,
    lang: str = "en",
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 10,
) -> AutocompleteResponse:
    query_lower = query.lower()

    # Build base query using search index
    stmt = (
        select(City, CitySearchIndex)
        .join(CitySearchIndex, City.geonameid == CitySearchIndex.geonameid)
        .options(selectinload(City.country), selectinload(City.alternate_names))
        .where(CitySearchIndex.search_term_lower.like(f"{query_lower}%"))
    )

    # Filter by language if not 'en'
    if lang != "en":
        stmt = stmt.where(
            (CitySearchIndex.language == lang) | (CitySearchIndex.language.is_(None))
        )

    # Add distance calculation if coordinates provided
    if lat is not None and lon is not None:
        point = func.ST_MakePoint(lon, lat)
        distance_expr = func.ST_Distance(
            func.cast(City.geom, text("geography")),
            func.cast(point, text("geography")),
        ) / 1000  # Convert to km

        stmt = stmt.add_columns(distance_expr.label("distance_km"))
        stmt = stmt.order_by(distance_expr, City.population.desc())
    else:
        stmt = stmt.order_by(City.population.desc())

    stmt = stmt.limit(limit).distinct(City.geonameid)

    result = await db.execute(stmt)
    rows = result.all()

    cities = []
    for row in rows:
        city = row[0]
        # row[1] is CitySearchIndex, not needed for response
        distance_km = row[2] if len(row) > 2 else None

        # Get local name
        local_name = None
        if lang != "en":
            alt_name = next(
                (
                    an
                    for an in city.alternate_names
                    if an.language == lang and an.is_preferred
                ),
                None,
            )
            if not alt_name:
                alt_name = next(
                    (an for an in city.alternate_names if an.language == lang), None
                )
            if alt_name:
                local_name = alt_name.name

        cities.append(
            CityResult(
                geoname_id=city.geonameid,
                name=city.name,
                local_name=local_name,
                country_code=city.country_code,
                country_name=city.country.name if city.country else None,
                admin1=city.admin1_code,
                population=city.population,
                lat=db.scalar(func.ST_Y(city.geom)),
                lon=db.scalar(func.ST_X(city.geom)),
                distance_km=round(distance_km, 2) if distance_km else None,
                timezone=city.timezone,
            )
        )

    user_location = None
    if lat is not None and lon is not None:
        user_location = UserLocation(lat=lat, lon=lon, source="params")

    return AutocompleteResponse(
        query=query,
        lang=lang,
        user_location=user_location,
        count=len(cities),
        cities=cities,
    )


async def get_languages() -> LanguagesResponse:
    return LanguagesResponse(
        languages=[LanguageInfo(**lang) for lang in SUPPORTED_LANGUAGES],
        default="en",
    )


async def get_cities_with_tours(db: AsyncSession, lang: str = "en") -> list[CityWithToursCount]:
    stmt = (
        select(
            City,
            func.count(Tour.id).label("tour_count"),
        )
        .join(Tour, City.geonameid == Tour.city_id)
        .options(selectinload(City.country), selectinload(City.alternate_names))
        .where(Tour.is_archived == False)  # noqa: E712
        .where(Tour.active_route_id.isnot(None))
        .group_by(City.geonameid)
        .having(func.count(Tour.id) > 0)
        .order_by(func.count(Tour.id).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    cities = []
    for city, tour_count in rows:
        local_name = None
        if lang != "en":
            alt_name = next(
                (
                    an
                    for an in city.alternate_names
                    if an.language == lang and an.is_preferred
                ),
                None,
            )
            if not alt_name:
                alt_name = next(
                    (an for an in city.alternate_names if an.language == lang), None
                )
            if alt_name:
                local_name = alt_name.name

        # Extract lat/lon from geometry
        lat = await db.scalar(func.ST_Y(city.geom))
        lon = await db.scalar(func.ST_X(city.geom))

        cities.append(
            CityWithToursCount(
                geoname_id=city.geonameid,
                name=city.name,
                local_name=local_name,
                country_code=city.country_code,
                country_name=city.country.name if city.country else None,
                lat=lat,
                lon=lon,
                tour_count=tour_count,
            )
        )

    return cities


async def get_city_by_id(db: AsyncSession, geonameid: int) -> City | None:
    result = await db.execute(
        select(City)
        .options(selectinload(City.country), selectinload(City.alternate_names))
        .where(City.geonameid == geonameid)
    )
    return result.scalar_one_or_none()
