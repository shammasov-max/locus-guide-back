from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from app.cities.schemas import CityResponse


class CitySearchService:
    """Service for city autocomplete search with PostGIS distance calculation"""

    SEARCH_QUERY_WITH_COORDS = """
        WITH matched_cities AS (
            SELECT DISTINCT si.geonameid
            FROM city_search_index si
            WHERE si.search_term_lower LIKE :query_pattern
            LIMIT 1000
        )
        SELECT
            c.geonameid,
            c.name,
            COALESCE(an.name, c.name) AS local_name,
            c.country_code,
            co.name AS country_name,
            c.admin1_code,
            c.population,
            ST_Y(c.geom) AS lat,
            ST_X(c.geom) AS lon,
            ROUND((ST_DistanceSphere(
                c.geom,
                ST_SetSRID(ST_MakePoint(:user_lon, :user_lat), 4326)
            ) / 1000)::numeric, 1) AS distance_km,
            c.timezone
        FROM cities c
        INNER JOIN matched_cities mc ON mc.geonameid = c.geonameid
        LEFT JOIN countries co ON co.iso = c.country_code
        LEFT JOIN LATERAL (
            SELECT name
            FROM alternate_names
            WHERE geonameid = c.geonameid
              AND language = :lang
            ORDER BY is_preferred DESC, is_short ASC
            LIMIT 1
        ) an ON true
        ORDER BY distance_km ASC, c.population DESC
        LIMIT :limit
    """

    SEARCH_QUERY_NO_COORDS = """
        WITH matched_cities AS (
            SELECT DISTINCT si.geonameid
            FROM city_search_index si
            WHERE si.search_term_lower LIKE :query_pattern
            LIMIT 1000
        )
        SELECT
            c.geonameid,
            c.name,
            COALESCE(an.name, c.name) AS local_name,
            c.country_code,
            co.name AS country_name,
            c.admin1_code,
            c.population,
            ST_Y(c.geom) AS lat,
            ST_X(c.geom) AS lon,
            NULL::numeric AS distance_km,
            c.timezone
        FROM cities c
        INNER JOIN matched_cities mc ON mc.geonameid = c.geonameid
        LEFT JOIN countries co ON co.iso = c.country_code
        LEFT JOIN LATERAL (
            SELECT name
            FROM alternate_names
            WHERE geonameid = c.geonameid
              AND language = :lang
            ORDER BY is_preferred DESC, is_short ASC
            LIMIT 1
        ) an ON true
        ORDER BY c.population DESC
        LIMIT :limit
    """

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query: str,
        lang: str = "en",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        limit: int = 10,
    ) -> list[CityResponse]:
        """
        Search cities by prefix with optional distance sorting.

        Args:
            query: Search query (prefix match)
            lang: Language for local names (en, ru, de)
            lat: User latitude for distance calculation
            lon: User longitude for distance calculation
            limit: Maximum number of results

        Returns:
            List of matching cities sorted by distance (if coords provided) then population
        """
        query_pattern = query.lower() + "%"

        if lat is not None and lon is not None:
            result = self.db.execute(
                text(self.SEARCH_QUERY_WITH_COORDS),
                {
                    "query_pattern": query_pattern,
                    "lang": lang,
                    "user_lat": lat,
                    "user_lon": lon,
                    "limit": limit,
                }
            )
        else:
            result = self.db.execute(
                text(self.SEARCH_QUERY_NO_COORDS),
                {
                    "query_pattern": query_pattern,
                    "lang": lang,
                    "limit": limit,
                }
            )

        rows = result.fetchall()

        return [
            CityResponse(
                geoname_id=row.geonameid,
                name=row.name,
                local_name=row.local_name or row.name,
                country_code=row.country_code,
                country_name=row.country_name,
                admin1=row.admin1_code,
                population=row.population,
                lat=row.lat,
                lon=row.lon,
                distance_km=float(row.distance_km) if row.distance_km is not None else None,
                timezone=row.timezone,
            )
            for row in rows
        ]
