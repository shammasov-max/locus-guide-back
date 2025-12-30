from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, and_, or_, exists
from sqlalchemy.orm import Session, selectinload, joinedload
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_SetSRID, ST_MakePoint
from geoalchemy2.shape import to_shape, from_shape
from shapely.geometry import LineString, Point, shape

from app.routes.models import (
    Trip, Route, Checkpoint, VisitedPoint, UserActiveTrip,
    TripStatus, RouteStatus, AudioListenStatus, CompletionType
)
from app.cities.models import City


class RouteService:
    def __init__(self, db: Session):
        self.db = db

    # ========== Helper Methods ==========

    def _resolve_i18n(self, hstore: dict | None, lang: str, fallback: str = "en") -> str:
        """Resolve HSTORE to string for given language with fallback"""
        if not hstore:
            return ""
        return hstore.get(lang) or hstore.get(fallback) or next(iter(hstore.values()), "")

    def _calculate_user_progress(self, user_id: int, route_id: UUID) -> dict:
        """Calculate user's progress on a route"""
        # Count total visible checkpoints
        total = self.db.query(func.count(Checkpoint.id)).filter(
            Checkpoint.route_id == route_id,
            Checkpoint.is_visible == True
        ).scalar() or 0

        # Count visited checkpoints
        visited_count = self.db.query(func.count(VisitedPoint.checkpoint_id)).join(
            Checkpoint, VisitedPoint.checkpoint_id == Checkpoint.id
        ).filter(
            VisitedPoint.user_id == user_id,
            Checkpoint.route_id == route_id,
            VisitedPoint.visited == True
        ).scalar() or 0

        # Count audio completed
        audio_completed = self.db.query(func.count(VisitedPoint.checkpoint_id)).join(
            Checkpoint, VisitedPoint.checkpoint_id == Checkpoint.id
        ).filter(
            VisitedPoint.user_id == user_id,
            Checkpoint.route_id == route_id,
            VisitedPoint.audio_status == AudioListenStatus.COMPLETED
        ).scalar() or 0

        progress_pct = (audio_completed / total * 100) if total > 0 else 0

        return {
            "checkpoints_visited": visited_count,
            "checkpoints_total": total,
            "audio_completed": audio_completed,
            "progress_percent": round(progress_pct, 1)
        }

    def _check_automatic_completion(self, user_id: int, trip_id: UUID) -> bool:
        """Check if all checkpoints done and auto-complete if so"""
        # Get user's active session
        session = self.db.query(UserActiveTrip).filter(
            UserActiveTrip.user_id == user_id,
            UserActiveTrip.trip_id == trip_id,
            UserActiveTrip.completed_at == None
        ).first()

        if not session:
            return False

        # Get progress
        progress = self._calculate_user_progress(user_id, session.locked_route_id)

        # If all audio completed, mark as auto-completed
        if progress["audio_completed"] >= progress["checkpoints_total"] and progress["checkpoints_total"] > 0:
            session.completed_at = datetime.now(timezone.utc)
            session.completion_type = CompletionType.AUTOMATIC
            self.db.commit()
            return True

        return False

    # ========== Read Operations ==========

    def list_trips(
        self,
        user_id: int | None = None,
        city_id: int | None = None,
        lat: float | None = None,
        lon: float | None = None,
        nearby_km: float = 50.0,
        status_filter: list[str] | None = None,
        search: str | None = None,
        wished: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        lang: str = "en"
    ) -> dict:
        """List trips with filters"""
        # Base query: published trips with their published routes
        query = self.db.query(Trip).join(
            Route, Trip.published_route_id == Route.id
        ).filter(Trip.status == TripStatus.PUBLISHED)

        # Filter by city
        if city_id:
            query = query.filter(Trip.city_id == city_id)

        # Filter by status
        if status_filter:
            statuses = [TripStatus(s) for s in status_filter if s in TripStatus.__members__.values()]
            if statuses:
                query = query.filter(Trip.status.in_(statuses))

        # Filter by search query in title/summary for specified language
        if search:
            search_pattern = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    func.lower(Route.title_i18n[lang]).ilike(search_pattern),
                    func.lower(Route.summary_i18n[lang]).ilike(search_pattern)
                )
            )

        # Nearby filter using first checkpoint location (seq_no=0)
        if lat is not None and lon is not None:
            # Subquery to get first checkpoint (seq_no=0) of each published route
            first_checkpoint_sq = self.db.query(
                Checkpoint.route_id,
                Checkpoint.location
            ).filter(
                Checkpoint.seq_no == 0
            ).subquery('first_checkpoints')

            # Create a point from user coordinates (lon, lat order for PostGIS)
            user_point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

            # Convert km to meters for ST_DWithin
            distance_meters = nearby_km * 1000

            # Join with first checkpoints and filter by distance
            query = query.join(
                first_checkpoint_sq,
                Route.id == first_checkpoint_sq.c.route_id
            ).filter(
                ST_DWithin(
                    first_checkpoint_sq.c.location,
                    user_point,
                    distance_meters
                )
            )

        # Filter by wished status (requires user_id)
        if wished is not None and user_id:
            from app.wishes.models import WishedRoute
            if wished:
                # Only trips user has wished
                query = query.join(
                    WishedRoute,
                    and_(
                        WishedRoute.route_id == Trip.id,
                        WishedRoute.user_id == user_id,
                        WishedRoute.is_active == True  # noqa: E712
                    )
                )
            else:
                # Exclude trips user has wished
                wished_subq = self.db.query(WishedRoute.route_id).filter(
                    WishedRoute.user_id == user_id,
                    WishedRoute.is_active == True  # noqa: E712
                ).subquery()
                query = query.filter(~Trip.id.in_(select(wished_subq)))

        count = query.count()
        trips = query.offset(offset).limit(limit).all()

        if not trips:
            return {"count": count, "trips": []}

        # Batch fetch related data to avoid N+1 queries
        trip_ids = [t.id for t in trips]
        route_ids = [t.published_route_id for t in trips]

        # Batch fetch cities
        city_ids = [t.city_id for t in trips]
        cities = {
            c.geonameid: c
            for c in self.db.query(City).filter(City.geonameid.in_(city_ids)).all()
        }

        # Batch fetch checkpoint counts
        checkpoint_counts = dict(
            self.db.query(Checkpoint.route_id, func.count(Checkpoint.id))
            .filter(
                Checkpoint.route_id.in_(route_ids),
                Checkpoint.is_visible == True  # noqa: E712
            )
            .group_by(Checkpoint.route_id)
            .all()
        )

        # Batch fetch wish statuses for user
        wished_trip_ids = set()
        if user_id:
            from app.wishes.models import WishedRoute
            wished_trip_ids = {
                r.route_id for r in self.db.query(WishedRoute.route_id).filter(
                    WishedRoute.user_id == user_id,
                    WishedRoute.route_id.in_(trip_ids),
                    WishedRoute.is_active == True  # noqa: E712
                ).all()
            }

        # Batch fetch active trips for user
        active_trips = {}
        if user_id:
            active_trips = {
                at.trip_id: at for at in self.db.query(UserActiveTrip).filter(
                    UserActiveTrip.user_id == user_id,
                    UserActiveTrip.trip_id.in_(trip_ids)
                ).all()
            }

        result = []
        for trip in trips:
            route = trip.published_route
            city = cities.get(trip.city_id)
            checkpoint_count = checkpoint_counts.get(route.id, 0)
            is_wished = trip.id in wished_trip_ids

            item = {
                "id": trip.id,
                "slug": trip.slug,
                "status": trip.status.value,
                "title": self._resolve_i18n(route.title_i18n, lang),
                "summary": self._resolve_i18n(route.summary_i18n, lang) if route.summary_i18n else None,
                "duration_min": route.duration_min,
                "distance_m": route.distance_m,
                "ascent_m": route.ascent_m,
                "descent_m": route.descent_m,
                "languages": route.languages or [],
                "free_checkpoint_limit": route.free_checkpoint_limit,
                "price_amount": route.price_amount,
                "price_currency": route.price_currency,
                "city_id": trip.city_id,
                "city_name": city.name if city else "",
                "checkpoint_count": checkpoint_count,
                "user_progress": None,
                "is_wished": is_wished,
            }

            # Add user progress if authenticated
            if user_id:
                active = active_trips.get(trip.id)
                if active:
                    progress = self._calculate_user_progress(user_id, active.locked_route_id)
                    item["user_progress"] = {
                        "started_at": active.started_at,
                        "completed_at": active.completed_at,
                        "completion_type": active.completion_type.value if active.completion_type else None,
                        **progress
                    }

            result.append(item)

        return {"count": count, "trips": result}

    def get_trip_detail(self, trip_id: UUID, user_id: int | None = None, lang: str = "en") -> dict | None:
        """Get full trip details"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip or not trip.published_route_id:
            return None

        route = trip.published_route
        city = self.db.query(City).filter(City.geonameid == trip.city_id).first()

        checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
            Checkpoint.route_id == route.id,
            Checkpoint.is_visible == True
        ).scalar() or 0

        result = {
            "id": trip.id,
            "slug": trip.slug,
            "status": trip.status.value,
            "city_id": trip.city_id,
            "city_name": city.name if city else "",
            "route_id": route.id,
            "version_no": route.version_no,
            "title": self._resolve_i18n(route.title_i18n, lang),
            "summary": self._resolve_i18n(route.summary_i18n, lang) if route.summary_i18n else None,
            "languages": route.languages or [],
            "duration_min": route.duration_min,
            "distance_m": route.distance_m,
            "ascent_m": route.ascent_m,
            "descent_m": route.descent_m,
            "geojson": route.geojson,
            "free_checkpoint_limit": route.free_checkpoint_limit,
            "price_amount": route.price_amount,
            "price_currency": route.price_currency,
            "checkpoint_count": checkpoint_count,
            "created_at": trip.created_at,
            "published_at": route.published_at,
            "user_progress": None
        }

        if user_id:
            active = self.db.query(UserActiveTrip).filter(
                UserActiveTrip.user_id == user_id,
                UserActiveTrip.trip_id == trip.id
            ).first()
            if active:
                progress = self._calculate_user_progress(user_id, active.locked_route_id)
                result["user_progress"] = {
                    "started_at": active.started_at,
                    "completed_at": active.completed_at,
                    "completion_type": active.completion_type.value if active.completion_type else None,
                    **progress
                }

        return result

    def get_trip_checkpoints(
        self,
        trip_id: UUID,
        user_id: int | None = None,
        lang: str = "en"
    ) -> list[dict]:
        """Get checkpoints for a trip"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip or not trip.published_route_id:
            return []

        # Use locked route if user has active session
        route_id = trip.published_route_id
        if user_id:
            active = self.db.query(UserActiveTrip).filter(
                UserActiveTrip.user_id == user_id,
                UserActiveTrip.trip_id == trip_id,
                UserActiveTrip.completed_at == None
            ).first()
            if active:
                route_id = active.locked_route_id

        checkpoints = self.db.query(Checkpoint).filter(
            Checkpoint.route_id == route_id
        ).order_by(Checkpoint.seq_no).all()

        result = []
        for cp in checkpoints:
            # Extract lat/lon from PostGIS point
            point = to_shape(cp.location)

            item = {
                "id": cp.id,
                "seq_no": cp.seq_no,
                "display_number": cp.display_number,
                "is_visible": cp.is_visible,
                "title": self._resolve_i18n(cp.title_i18n, lang),
                "description": self._resolve_i18n(cp.description_i18n, lang) if cp.description_i18n else None,
                "lat": point.y,
                "lon": point.x,
                "trigger_radius_m": cp.trigger_radius_m,
                "is_free_preview": cp.is_free_preview,
                "visited": False,
                "visited_at": None,
                "audio_status": "none",
                "audio_started_at": None,
                "audio_completed_at": None
            }

            # Add user progress if authenticated
            if user_id:
                vp = self.db.query(VisitedPoint).filter(
                    VisitedPoint.user_id == user_id,
                    VisitedPoint.checkpoint_id == cp.id
                ).first()
                if vp:
                    item["visited"] = vp.visited
                    item["visited_at"] = vp.visited_at
                    item["audio_status"] = vp.audio_status.value
                    item["audio_started_at"] = vp.audio_started_at
                    item["audio_completed_at"] = vp.audio_completed_at

            result.append(item)

        return result

    # ========== User Progress Operations ==========

    def mark_checkpoint_visited(self, user_id: int, checkpoint_id: UUID) -> dict | None:
        """Mark checkpoint as GPS visited (upsert)"""
        checkpoint = self.db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
        if not checkpoint:
            return None

        # Upsert visited_point
        vp = self.db.query(VisitedPoint).filter(
            VisitedPoint.user_id == user_id,
            VisitedPoint.checkpoint_id == checkpoint_id
        ).first()

        now = datetime.now(timezone.utc)

        if vp:
            if not vp.visited:
                vp.visited = True
                vp.visited_at = now
                vp.updated_at = now
        else:
            vp = VisitedPoint(
                user_id=user_id,
                checkpoint_id=checkpoint_id,
                visited=True,
                visited_at=now,
                audio_status=AudioListenStatus.NONE
            )
            self.db.add(vp)

        self.db.commit()

        # Check for auto-completion
        trip = self.db.query(Trip).join(
            Route, Trip.id == Route.trip_id
        ).filter(Route.id == checkpoint.route_id).first()
        if trip:
            self._check_automatic_completion(user_id, trip.id)

        return self._get_checkpoint_progress(checkpoint, vp, "en")

    def update_audio_status(self, user_id: int, checkpoint_id: UUID, status: str) -> dict | None:
        """Update audio listening status"""
        checkpoint = self.db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
        if not checkpoint:
            return None

        new_status = AudioListenStatus(status)

        vp = self.db.query(VisitedPoint).filter(
            VisitedPoint.user_id == user_id,
            VisitedPoint.checkpoint_id == checkpoint_id
        ).first()

        now = datetime.now(timezone.utc)

        if vp:
            vp.audio_status = new_status
            if new_status == AudioListenStatus.STARTED and not vp.audio_started_at:
                vp.audio_started_at = now
            elif new_status == AudioListenStatus.COMPLETED and not vp.audio_completed_at:
                vp.audio_completed_at = now
            vp.updated_at = now
        else:
            vp = VisitedPoint(
                user_id=user_id,
                checkpoint_id=checkpoint_id,
                visited=False,
                audio_status=new_status,
                audio_started_at=now if new_status == AudioListenStatus.STARTED else None,
                audio_completed_at=now if new_status == AudioListenStatus.COMPLETED else None
            )
            self.db.add(vp)

        self.db.commit()

        # Check for auto-completion
        trip = self.db.query(Trip).join(
            Route, Trip.id == Route.trip_id
        ).filter(Route.id == checkpoint.route_id).first()
        if trip:
            self._check_automatic_completion(user_id, trip.id)

        return self._get_checkpoint_progress(checkpoint, vp, "en")

    def _get_checkpoint_progress(self, checkpoint: Checkpoint, vp: VisitedPoint | None, lang: str) -> dict:
        """Build checkpoint progress response"""
        point = to_shape(checkpoint.location)

        return {
            "id": checkpoint.id,
            "seq_no": checkpoint.seq_no,
            "display_number": checkpoint.display_number,
            "is_visible": checkpoint.is_visible,
            "title": self._resolve_i18n(checkpoint.title_i18n, lang),
            "description": self._resolve_i18n(checkpoint.description_i18n, lang) if checkpoint.description_i18n else None,
            "lat": point.y,
            "lon": point.x,
            "trigger_radius_m": checkpoint.trigger_radius_m,
            "is_free_preview": checkpoint.is_free_preview,
            "visited": vp.visited if vp else False,
            "visited_at": vp.visited_at if vp else None,
            "audio_status": vp.audio_status.value if vp else "none",
            "audio_started_at": vp.audio_started_at if vp else None,
            "audio_completed_at": vp.audio_completed_at if vp else None
        }

    # ========== Active Trips Operations ==========

    def get_user_active_trips(self, user_id: int, lang: str = "en") -> list[dict]:
        """Get user's active trips"""
        sessions = self.db.query(UserActiveTrip).filter(
            UserActiveTrip.user_id == user_id
        ).order_by(UserActiveTrip.started_at.desc()).all()

        result = []
        for session in sessions:
            trip = session.trip
            route = session.locked_route
            city = self.db.query(City).filter(City.geonameid == trip.city_id).first()

            checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
                Checkpoint.route_id == route.id,
                Checkpoint.is_visible == True
            ).scalar() or 0

            progress = self._calculate_user_progress(user_id, route.id)

            result.append({
                "id": session.id,
                "trip": {
                    "id": trip.id,
                    "slug": trip.slug,
                    "status": trip.status.value,
                    "title": self._resolve_i18n(route.title_i18n, lang),
                    "summary": self._resolve_i18n(route.summary_i18n, lang) if route.summary_i18n else None,
                    "duration_min": route.duration_min,
                    "distance_m": route.distance_m,
                    "ascent_m": route.ascent_m,
                    "descent_m": route.descent_m,
                    "languages": route.languages or [],
                    "free_checkpoint_limit": route.free_checkpoint_limit,
                    "price_amount": route.price_amount,
                    "price_currency": route.price_currency,
                    "city_id": trip.city_id,
                    "city_name": city.name if city else "",
                    "checkpoint_count": checkpoint_count,
                    "user_progress": None
                },
                "locked_route_id": session.locked_route_id,
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "completion_type": session.completion_type.value if session.completion_type else None,
                "progress": {
                    "started_at": session.started_at,
                    "completed_at": session.completed_at,
                    "completion_type": session.completion_type.value if session.completion_type else None,
                    **progress
                }
            })

        return result

    def start_trip(self, user_id: int, trip_id: UUID) -> dict | None:
        """Start a trip session"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip or not trip.published_route_id:
            return None

        # Check if already started
        existing = self.db.query(UserActiveTrip).filter(
            UserActiveTrip.user_id == user_id,
            UserActiveTrip.trip_id == trip_id
        ).first()

        if existing:
            # Return existing session
            return self._get_active_trip_response(existing, "en")

        # Create new session
        session = UserActiveTrip(
            user_id=user_id,
            trip_id=trip_id,
            locked_route_id=trip.published_route_id
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return self._get_active_trip_response(session, "en")

    def finish_trip(self, user_id: int, trip_id: UUID) -> dict | None:
        """Manually finish a trip"""
        session = self.db.query(UserActiveTrip).filter(
            UserActiveTrip.user_id == user_id,
            UserActiveTrip.trip_id == trip_id,
            UserActiveTrip.completed_at == None
        ).first()

        if not session:
            return None

        session.completed_at = datetime.now(timezone.utc)
        session.completion_type = CompletionType.MANUAL
        self.db.commit()

        return self._get_active_trip_response(session, "en")

    def _get_active_trip_response(self, session: UserActiveTrip, lang: str) -> dict:
        """Build active trip response"""
        trip = session.trip
        route = session.locked_route
        city = self.db.query(City).filter(City.geonameid == trip.city_id).first()

        checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
            Checkpoint.route_id == route.id,
            Checkpoint.is_visible == True
        ).scalar() or 0

        progress = self._calculate_user_progress(session.user_id, route.id)

        return {
            "id": session.id,
            "trip": {
                "id": trip.id,
                "slug": trip.slug,
                "status": trip.status.value,
                "title": self._resolve_i18n(route.title_i18n, lang),
                "summary": self._resolve_i18n(route.summary_i18n, lang) if route.summary_i18n else None,
                "duration_min": route.duration_min,
                "distance_m": route.distance_m,
                "ascent_m": route.ascent_m,
                "descent_m": route.descent_m,
                "languages": route.languages or [],
                "free_checkpoint_limit": route.free_checkpoint_limit,
                "price_amount": route.price_amount,
                "price_currency": route.price_currency,
                "city_id": trip.city_id,
                "city_name": city.name if city else "",
                "checkpoint_count": checkpoint_count,
                "user_progress": None
            },
            "locked_route_id": session.locked_route_id,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "completion_type": session.completion_type.value if session.completion_type else None,
            "progress": {
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "completion_type": session.completion_type.value if session.completion_type else None,
                **progress
            }
        }

    # ========== Admin Operations ==========

    def create_trip(self, user_id: int, city_id: int, slug: str, status: str = "draft") -> Trip:
        """Create new trip"""
        trip = Trip(
            created_by_user_id=user_id,
            city_id=city_id,
            slug=slug,
            status=TripStatus(status)
        )
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def update_trip(self, trip_id: UUID, slug: str | None = None, status: str | None = None) -> Trip | None:
        """Update trip metadata"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return None

        if slug is not None:
            trip.slug = slug
        if status is not None:
            trip.status = TripStatus(status)

        self.db.commit()
        self.db.refresh(trip)
        return trip

    def delete_trip(self, trip_id: UUID) -> bool:
        """Delete trip (cascades to routes, checkpoints)"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return False

        self.db.delete(trip)
        self.db.commit()
        return True

    def get_trip_admin(self, trip_id: UUID) -> dict | None:
        """Get trip with route count for admin view"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return None

        route_count = self.db.query(func.count(Route.id)).filter(
            Route.trip_id == trip_id
        ).scalar() or 0

        city = self.db.query(City).filter(City.geonameid == trip.city_id).first()

        return {
            "id": trip.id,
            "slug": trip.slug,
            "status": trip.status.value,
            "city_id": trip.city_id,
            "city_name": city.name if city else "",
            "created_by_user_id": trip.created_by_user_id,
            "published_route_id": trip.published_route_id,
            "route_count": route_count,
            "created_at": trip.created_at,
            "updated_at": trip.updated_at
        }

    def list_trips_admin(
        self,
        city_id: int | None = None,
        status: list[str] | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        """List trips for admin with all statuses"""
        query = self.db.query(Trip)

        if city_id:
            query = query.filter(Trip.city_id == city_id)

        if status:
            statuses = [TripStatus(s) for s in status if s in TripStatus.__members__.values()]
            if statuses:
                query = query.filter(Trip.status.in_(statuses))

        count = query.count()
        trips = query.order_by(Trip.created_at.desc()).offset(offset).limit(limit).all()

        result = []
        for trip in trips:
            route_count = self.db.query(func.count(Route.id)).filter(
                Route.trip_id == trip.id
            ).scalar() or 0

            city = self.db.query(City).filter(City.geonameid == trip.city_id).first()

            result.append({
                "id": trip.id,
                "slug": trip.slug,
                "status": trip.status.value,
                "city_id": trip.city_id,
                "city_name": city.name if city else "",
                "created_by_user_id": trip.created_by_user_id,
                "published_route_id": trip.published_route_id,
                "route_count": route_count,
                "created_at": trip.created_at,
                "updated_at": trip.updated_at
            })

        return {"count": count, "trips": result}

    def create_route(self, trip_id: UUID, user_id: int, data: dict) -> Route | None:
        """Create route from data dict with automatic checkpoint creation"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return None

        # Auto-set version_no to max(existing) + 1
        max_version = self.db.query(func.max(Route.version_no)).filter(
            Route.trip_id == trip_id
        ).scalar() or 0
        version_no = max_version + 1

        # Create route
        route = Route(
            trip_id=trip_id,
            version_no=version_no,
            created_by_user_id=user_id,
            status=RouteStatus.DRAFT,
            title_i18n=data.get("title_i18n", {}),
            summary_i18n=data.get("summary_i18n"),
            languages=data.get("languages", []),
            duration_min=data.get("duration_min"),
            distance_m=data.get("distance_m"),
            ascent_m=data.get("ascent_m"),
            descent_m=data.get("descent_m"),
            geojson=data.get("geojson"),
            free_checkpoint_limit=data.get("free_checkpoint_limit", 0),
            price_amount=data.get("price_amount"),
            price_currency=data.get("price_currency", "USD")
        )
        self.db.add(route)
        self.db.flush()

        # Extract features from geojson and create checkpoints
        if "geojson" in data and data["geojson"]:
            features = data["geojson"].get("features", [])
            seq_no = 0

            for feature in features:
                geom = shape(feature["geometry"])
                if isinstance(geom, Point):
                    props = feature.get("properties", {})
                    checkpoint = Checkpoint(
                        route_id=route.id,
                        seq_no=seq_no,
                        source_point_id=props.get("id"),
                        title_i18n=props.get("title_i18n", {"en": f"Point {seq_no}"}),
                        description_i18n=props.get("description_i18n"),
                        location=from_shape(geom, srid=4326),
                        display_number=props.get("display_number"),
                        is_visible=props.get("is_visible", True),
                        trigger_radius_m=props.get("trigger_radius_m", 25),
                        is_free_preview=seq_no < data.get("free_checkpoint_limit", 0),
                        osm_way_id=props.get("osm_way_id"),
                    )
                    self.db.add(checkpoint)
                    seq_no += 1
                elif isinstance(geom, LineString):
                    route.path = from_shape(geom, srid=4326)

        self.db.commit()
        self.db.refresh(route)
        return route

    def get_trip_routes(self, trip_id: UUID) -> list[dict]:
        """List all routes for a trip"""
        routes = self.db.query(Route).filter(
            Route.trip_id == trip_id
        ).order_by(Route.version_no.desc()).all()

        result = []
        for route in routes:
            checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
                Checkpoint.route_id == route.id
            ).scalar() or 0

            result.append({
                "id": route.id,
                "trip_id": route.trip_id,
                "version_no": route.version_no,
                "status": route.status.value,
                "created_by_user_id": route.created_by_user_id,
                "title_i18n": route.title_i18n,
                "summary_i18n": route.summary_i18n,
                "languages": route.languages,
                "duration_min": route.duration_min,
                "distance_m": route.distance_m,
                "ascent_m": route.ascent_m,
                "descent_m": route.descent_m,
                "free_checkpoint_limit": route.free_checkpoint_limit,
                "price_amount": route.price_amount,
                "price_currency": route.price_currency,
                "checkpoint_count": checkpoint_count,
                "created_at": route.created_at,
                "updated_at": route.updated_at,
                "published_at": route.published_at
            })

        return result

    def update_route(self, route_id: UUID, data: dict) -> Route | None:
        """Update route metadata (not checkpoints)"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            return None

        # Update fields if provided
        if "title_i18n" in data:
            route.title_i18n = data["title_i18n"]
        if "summary_i18n" in data:
            route.summary_i18n = data["summary_i18n"]
        if "languages" in data:
            route.languages = data["languages"]
        if "duration_min" in data:
            route.duration_min = data["duration_min"]
        if "distance_m" in data:
            route.distance_m = data["distance_m"]
        if "ascent_m" in data:
            route.ascent_m = data["ascent_m"]
        if "descent_m" in data:
            route.descent_m = data["descent_m"]
        if "free_checkpoint_limit" in data:
            route.free_checkpoint_limit = data["free_checkpoint_limit"]
        if "price_amount" in data:
            route.price_amount = data["price_amount"]
        if "price_currency" in data:
            route.price_currency = data["price_currency"]
        if "geojson" in data:
            route.geojson = data["geojson"]

        route.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(route)
        return route

    def publish_route(self, trip_id: UUID, route_id: UUID) -> Trip | None:
        """Set route status to published and update trip"""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return None

        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route or route.trip_id != trip_id:
            return None

        # Set any previously published route to superseded
        if trip.published_route_id:
            old_route = self.db.query(Route).filter(
                Route.id == trip.published_route_id
            ).first()
            if old_route:
                old_route.status = RouteStatus.SUPERSEDED
                old_route.updated_at = datetime.now(timezone.utc)

        # Publish new route
        route.status = RouteStatus.PUBLISHED
        route.published_at = datetime.now(timezone.utc)
        route.updated_at = datetime.now(timezone.utc)

        # Update trip
        trip.published_route_id = route_id
        if trip.status != TripStatus.PUBLISHED:
            trip.status = TripStatus.PUBLISHED
        trip.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(trip)
        return trip

    def update_checkpoint(self, checkpoint_id: UUID, data: dict) -> Checkpoint | None:
        """Update checkpoint metadata"""
        checkpoint = self.db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
        if not checkpoint:
            return None

        # Update fields if provided
        if "seq_no" in data:
            checkpoint.seq_no = data["seq_no"]
        if "source_point_id" in data:
            checkpoint.source_point_id = data["source_point_id"]
        if "title_i18n" in data:
            checkpoint.title_i18n = data["title_i18n"]
        if "description_i18n" in data:
            checkpoint.description_i18n = data["description_i18n"]
        if "display_number" in data:
            checkpoint.display_number = data["display_number"]
        if "is_visible" in data:
            checkpoint.is_visible = data["is_visible"]
        if "trigger_radius_m" in data:
            checkpoint.trigger_radius_m = data["trigger_radius_m"]
        if "is_free_preview" in data:
            checkpoint.is_free_preview = data["is_free_preview"]
        if "osm_way_id" in data:
            checkpoint.osm_way_id = data["osm_way_id"]
        if "location" in data and "lat" in data["location"] and "lon" in data["location"]:
            point = Point(data["location"]["lon"], data["location"]["lat"])
            checkpoint.location = from_shape(point, srid=4326)

        checkpoint.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def get_route_checkpoints_admin(self, route_id: UUID) -> list[dict]:
        """Get all checkpoints for a route (admin view, all fields)"""
        checkpoints = self.db.query(Checkpoint).filter(
            Checkpoint.route_id == route_id
        ).order_by(Checkpoint.seq_no).all()

        result = []
        for cp in checkpoints:
            point = to_shape(cp.location)
            result.append({
                "id": cp.id,
                "route_id": cp.route_id,
                "seq_no": cp.seq_no,
                "source_point_id": cp.source_point_id,
                "title_i18n": cp.title_i18n,
                "description_i18n": cp.description_i18n,
                "location": {
                    "lat": point.y,
                    "lon": point.x
                },
                "display_number": cp.display_number,
                "is_visible": cp.is_visible,
                "trigger_radius_m": cp.trigger_radius_m,
                "is_free_preview": cp.is_free_preview,
                "osm_way_id": cp.osm_way_id,
                "created_at": cp.created_at,
                "updated_at": cp.updated_at
            })

        return result
