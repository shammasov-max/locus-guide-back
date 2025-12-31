"""Business logic for user wishes (tours) and wants (cities)."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.wishes.models import WishedRoute, WantedCity
from app.routes.models import Tour, Route, TourStatus, UserActiveTour
from app.cities.models import City, Country


class WishService:
    def __init__(self, db: Session):
        self.db = db

    def _resolve_i18n(self, hstore: dict | None, lang: str, fallback: str = "en") -> str:
        """Resolve HSTORE to string for given language with fallback."""
        if not hstore:
            return ""
        return hstore.get(lang) or hstore.get(fallback) or next(iter(hstore.values()), "")

    # ========== Wished Tours ==========

    def wish_route(self, user_id: int, route_id: UUID, lang: str = "en") -> dict:
        """Add or reactivate a wish for a coming_soon tour.

        Returns dict with result or error info.
        """
        # Validate tour exists
        tour = self.db.query(Tour).filter(Tour.id == route_id).first()
        if not tour:
            return {"error": "Tour not found", "code": "not_found"}

        # Only coming_soon tours can be wished
        if tour.status != TourStatus.COMING_SOON:
            return {
                "error": "Can only wish coming_soon tours",
                "code": "invalid_status"
            }

        # Check if user already completed this tour
        completed = self.db.query(UserActiveTour).filter(
            UserActiveTour.user_id == user_id,
            UserActiveTour.tour_id == route_id,
            UserActiveTour.completed_at != None  # noqa: E711
        ).first()
        if completed:
            return {
                "error": "Cannot wish a tour you have already completed",
                "code": "already_completed"
            }

        # Upsert wish
        existing = self.db.query(WishedRoute).filter(
            WishedRoute.user_id == user_id,
            WishedRoute.tour_id == route_id
        ).first()

        if existing:
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
        else:
            wish = WishedRoute(user_id=user_id, tour_id=route_id)
            self.db.add(wish)

        self.db.commit()
        return self.get_wished_route(user_id, route_id, lang)

    def unwish_route(self, user_id: int, route_id: UUID, lang: str = "en") -> dict | None:
        """Deactivate a wish (soft delete)."""
        wish = self.db.query(WishedRoute).filter(
            WishedRoute.user_id == user_id,
            WishedRoute.tour_id == route_id
        ).first()

        if not wish:
            return None

        wish.is_active = False
        wish.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return self.get_wished_route(user_id, route_id, lang)

    def get_wished_route(self, user_id: int, route_id: UUID, lang: str = "en") -> dict | None:
        """Get single wished tour with tour details."""
        wish = self.db.query(WishedRoute).filter(
            WishedRoute.user_id == user_id,
            WishedRoute.tour_id == route_id
        ).first()

        if not wish:
            return None

        tour = wish.tour
        city = self.db.query(City).filter(City.geonameid == tour.city_id).first()

        # Get title from published route or latest route
        title = ""
        if tour.published_route:
            title = self._resolve_i18n(tour.published_route.title_i18n, lang)
        else:
            latest = self.db.query(Route).filter(
                Route.tour_id == route_id
            ).order_by(Route.version_no.desc()).first()
            if latest:
                title = self._resolve_i18n(latest.title_i18n, lang)

        return {
            "tour_id": tour.id,
            "tour_slug": tour.slug,
            "tour_title": title,
            "city_id": tour.city_id,
            "city_name": city.name if city else "",
            "is_active": wish.is_active,
            "created_at": wish.created_at,
        }

    def get_user_wished_routes(
        self, user_id: int, active_only: bool = True, lang: str = "en"
    ) -> list[dict]:
        """Get all user's wished tours."""
        query = self.db.query(WishedRoute).filter(WishedRoute.user_id == user_id)
        if active_only:
            query = query.filter(WishedRoute.is_active == True)  # noqa: E712

        wishes = query.order_by(WishedRoute.created_at.desc()).all()
        result = []
        for w in wishes:
            item = self.get_wished_route(user_id, w.tour_id, lang)
            if item:
                result.append(item)
        return result

    def is_route_wished(self, user_id: int, route_id: UUID) -> bool:
        """Check if user has active wish for tour."""
        return self.db.query(WishedRoute).filter(
            WishedRoute.user_id == user_id,
            WishedRoute.tour_id == route_id,
            WishedRoute.is_active == True  # noqa: E712
        ).first() is not None

    # ========== Wanted Cities ==========

    def want_city(self, user_id: int, geonameid: int) -> dict | None:
        """Add or reactivate a want for a city."""
        # Validate city exists
        city = self.db.query(City).filter(City.geonameid == geonameid).first()
        if not city:
            return None

        # Upsert want
        existing = self.db.query(WantedCity).filter(
            WantedCity.user_id == user_id,
            WantedCity.geonameid == geonameid
        ).first()

        if existing:
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
        else:
            want = WantedCity(user_id=user_id, geonameid=geonameid)
            self.db.add(want)

        self.db.commit()
        return self.get_wanted_city(user_id, geonameid)

    def unwant_city(self, user_id: int, geonameid: int) -> dict | None:
        """Deactivate a want (soft delete)."""
        want = self.db.query(WantedCity).filter(
            WantedCity.user_id == user_id,
            WantedCity.geonameid == geonameid
        ).first()

        if not want:
            return None

        want.is_active = False
        want.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return self.get_wanted_city(user_id, geonameid)

    def get_wanted_city(self, user_id: int, geonameid: int) -> dict | None:
        """Get single wanted city with details."""
        want = self.db.query(WantedCity).filter(
            WantedCity.user_id == user_id,
            WantedCity.geonameid == geonameid
        ).first()

        if not want:
            return None

        city = want.city

        # Check if city now has published tours
        has_routes = self.db.query(Tour).filter(
            Tour.city_id == geonameid,
            Tour.status == TourStatus.PUBLISHED
        ).first() is not None

        return {
            "geonameid": city.geonameid,
            "city_name": city.name,
            "country_code": city.country_code,
            "is_active": want.is_active,
            "has_routes": has_routes,
            "created_at": want.created_at,
        }

    def get_user_wanted_cities(
        self, user_id: int, active_only: bool = True
    ) -> list[dict]:
        """Get all user's wanted cities."""
        query = self.db.query(WantedCity).filter(WantedCity.user_id == user_id)
        if active_only:
            query = query.filter(WantedCity.is_active == True)  # noqa: E712

        wants = query.order_by(WantedCity.created_at.desc()).all()
        result = []
        for w in wants:
            item = self.get_wanted_city(user_id, w.geonameid)
            if item:
                result.append(item)
        return result

    def is_city_wanted(self, user_id: int, geonameid: int) -> bool:
        """Check if user has active want for city."""
        return self.db.query(WantedCity).filter(
            WantedCity.user_id == user_id,
            WantedCity.geonameid == geonameid,
            WantedCity.is_active == True  # noqa: E712
        ).first() is not None

    # ========== Admin Analytics ==========

    def get_route_wish_stats(
        self,
        status_filter: list[str] | None = None,
        city_id: int | None = None,
        min_wishes: int = 0,
        limit: int = 50,
        offset: int = 0,
        lang: str = "en"
    ) -> dict:
        """Get aggregated wish counts per tour for admin."""
        # Subquery for active wish count
        active_count_sq = self.db.query(
            WishedRoute.tour_id,
            func.count(WishedRoute.user_id).label("active_count")
        ).filter(
            WishedRoute.is_active == True  # noqa: E712
        ).group_by(WishedRoute.tour_id).subquery()

        # Subquery for total wish count (including inactive)
        total_count_sq = self.db.query(
            WishedRoute.tour_id,
            func.count(WishedRoute.user_id).label("total_count")
        ).group_by(WishedRoute.tour_id).subquery()

        # Main query joining tours with wish counts
        query = self.db.query(
            Tour,
            func.coalesce(active_count_sq.c.active_count, 0).label("active_wish_count"),
            func.coalesce(total_count_sq.c.total_count, 0).label("total_wish_count")
        ).outerjoin(
            active_count_sq, Tour.id == active_count_sq.c.tour_id
        ).outerjoin(
            total_count_sq, Tour.id == total_count_sq.c.tour_id
        )

        # Apply filters
        if status_filter:
            statuses = [TourStatus(s) for s in status_filter]
            query = query.filter(Tour.status.in_(statuses))

        if city_id:
            query = query.filter(Tour.city_id == city_id)

        if min_wishes > 0:
            query = query.filter(
                func.coalesce(active_count_sq.c.active_count, 0) >= min_wishes
            )

        # Order by active wish count descending
        query = query.order_by(
            func.coalesce(active_count_sq.c.active_count, 0).desc()
        )

        count = query.count()
        results = query.offset(offset).limit(limit).all()

        tours_data = []
        for tour, active_count, total_count in results:
            city = self.db.query(City).filter(City.geonameid == tour.city_id).first()

            title = ""
            if tour.published_route:
                title = self._resolve_i18n(tour.published_route.title_i18n, lang)
            else:
                latest = self.db.query(Route).filter(
                    Route.tour_id == tour.id
                ).order_by(Route.version_no.desc()).first()
                if latest:
                    title = self._resolve_i18n(latest.title_i18n, lang)

            tours_data.append({
                "tour_id": tour.id,
                "tour_slug": tour.slug,
                "tour_title": title,
                "city_id": tour.city_id,
                "city_name": city.name if city else "",
                "tour_status": tour.status.value,
                "active_wish_count": active_count,
                "total_wish_count": total_count,
            })

        return {"count": count, "tours": tours_data}

    def get_city_want_stats(
        self,
        country_code: str | None = None,
        has_routes: bool | None = None,
        min_wants: int = 0,
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        """Get aggregated want counts per city for admin."""
        # Subquery for active want count
        active_count_sq = self.db.query(
            WantedCity.geonameid,
            func.count(WantedCity.user_id).label("active_count")
        ).filter(
            WantedCity.is_active == True  # noqa: E712
        ).group_by(WantedCity.geonameid).subquery()

        # Subquery for total want count
        total_count_sq = self.db.query(
            WantedCity.geonameid,
            func.count(WantedCity.user_id).label("total_count")
        ).group_by(WantedCity.geonameid).subquery()

        # Subquery for published tour count per city
        route_count_sq = self.db.query(
            Tour.city_id,
            func.count(Tour.id).label("route_count")
        ).filter(
            Tour.status == TourStatus.PUBLISHED
        ).group_by(Tour.city_id).subquery()

        # Main query - only cities with at least one want
        query = self.db.query(
            City,
            func.coalesce(active_count_sq.c.active_count, 0).label("active_want_count"),
            func.coalesce(total_count_sq.c.total_count, 0).label("total_want_count"),
            func.coalesce(route_count_sq.c.route_count, 0).label("route_count")
        ).join(
            active_count_sq, City.geonameid == active_count_sq.c.geonameid
        ).outerjoin(
            total_count_sq, City.geonameid == total_count_sq.c.geonameid
        ).outerjoin(
            route_count_sq, City.geonameid == route_count_sq.c.city_id
        )

        # Apply filters
        if country_code:
            query = query.filter(City.country_code == country_code)

        if has_routes is not None:
            if has_routes:
                query = query.filter(
                    func.coalesce(route_count_sq.c.route_count, 0) > 0
                )
            else:
                query = query.filter(
                    func.coalesce(route_count_sq.c.route_count, 0) == 0
                )

        if min_wants > 0:
            query = query.filter(
                func.coalesce(active_count_sq.c.active_count, 0) >= min_wants
            )

        # Order by active want count descending
        query = query.order_by(
            func.coalesce(active_count_sq.c.active_count, 0).desc()
        )

        count = query.count()
        results = query.offset(offset).limit(limit).all()

        cities_data = []
        for city, active_count, total_count, route_count in results:
            country = self.db.query(Country).filter(
                Country.iso == city.country_code
            ).first()

            cities_data.append({
                "geonameid": city.geonameid,
                "city_name": city.name,
                "country_code": city.country_code,
                "country_name": country.name if country else "",
                "population": city.population,
                "has_routes": route_count > 0,
                "tour_count": route_count,
                "active_want_count": active_count,
                "total_want_count": total_count,
            })

        return {"count": count, "cities": cities_data}

    # ========== Notification Helpers ==========

    def get_users_who_wished_route(self, route_id: UUID) -> list[int]:
        """Get user IDs who actively wished a tour (for notifications)."""
        wishes = self.db.query(WishedRoute.user_id).filter(
            WishedRoute.tour_id == route_id,
            WishedRoute.is_active == True  # noqa: E712
        ).all()
        return [w.user_id for w in wishes]

    def get_users_who_wanted_city(self, geonameid: int) -> list[int]:
        """Get user IDs who actively wanted a city (for notifications)."""
        wants = self.db.query(WantedCity.user_id).filter(
            WantedCity.geonameid == geonameid,
            WantedCity.is_active == True  # noqa: E712
        ).all()
        return [w.user_id for w in wants]

    # ========== GDPR Compliance ==========

    def delete_user_wishes(self, user_id: int) -> dict:
        """Hard delete all wishes/wants for a user (GDPR compliance)."""
        wished_count = self.db.query(WishedRoute).filter(
            WishedRoute.user_id == user_id
        ).delete()

        wanted_count = self.db.query(WantedCity).filter(
            WantedCity.user_id == user_id
        ).delete()

        self.db.commit()
        return {
            "wished_routes_deleted": wished_count,
            "wanted_cities_deleted": wanted_count
        }
