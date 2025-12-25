from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session, selectinload, joinedload
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_SetSRID, ST_MakePoint
from geoalchemy2.shape import to_shape, from_shape
from shapely.geometry import LineString, Point, shape

from app.routes.models import (
    Route, RouteVersion, Checkpoint, VisitedPoint, UserActiveRoute,
    RouteStatus, RouteVersionStatus, AudioListenStatus, CompletionType
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

    def _calculate_user_progress(self, user_id: int, route_version_id: UUID) -> dict:
        """Calculate user's progress on a route version"""
        # Count total visible checkpoints
        total = self.db.query(func.count(Checkpoint.id)).filter(
            Checkpoint.route_version_id == route_version_id,
            Checkpoint.is_visible == True
        ).scalar() or 0

        # Count visited checkpoints
        visited_count = self.db.query(func.count(VisitedPoint.checkpoint_id)).join(
            Checkpoint, VisitedPoint.checkpoint_id == Checkpoint.id
        ).filter(
            VisitedPoint.user_id == user_id,
            Checkpoint.route_version_id == route_version_id,
            VisitedPoint.visited == True
        ).scalar() or 0

        # Count audio completed
        audio_completed = self.db.query(func.count(VisitedPoint.checkpoint_id)).join(
            Checkpoint, VisitedPoint.checkpoint_id == Checkpoint.id
        ).filter(
            VisitedPoint.user_id == user_id,
            Checkpoint.route_version_id == route_version_id,
            VisitedPoint.audio_status == AudioListenStatus.COMPLETED
        ).scalar() or 0

        progress_pct = (audio_completed / total * 100) if total > 0 else 0

        return {
            "checkpoints_visited": visited_count,
            "checkpoints_total": total,
            "audio_completed": audio_completed,
            "progress_percent": round(progress_pct, 1)
        }

    def _check_automatic_completion(self, user_id: int, route_id: UUID) -> bool:
        """Check if all checkpoints done and auto-complete if so"""
        # Get user's active session
        session = self.db.query(UserActiveRoute).filter(
            UserActiveRoute.user_id == user_id,
            UserActiveRoute.route_id == route_id,
            UserActiveRoute.completed_at == None
        ).first()

        if not session:
            return False

        # Get progress
        progress = self._calculate_user_progress(user_id, session.locked_version_id)

        # If all audio completed, mark as auto-completed
        if progress["audio_completed"] >= progress["checkpoints_total"] and progress["checkpoints_total"] > 0:
            session.completed_at = datetime.now(timezone.utc)
            session.completion_type = CompletionType.AUTOMATIC
            self.db.commit()
            return True

        return False

    # ========== Read Operations ==========

    def list_routes(
        self,
        user_id: int | None = None,
        city_id: int | None = None,
        lat: float | None = None,
        lon: float | None = None,
        nearby_km: float = 50.0,
        status_filter: list[str] | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        lang: str = "en"
    ) -> dict:
        """List routes with filters"""
        # Base query: published routes with their published versions
        query = self.db.query(Route).join(
            RouteVersion, Route.published_version_id == RouteVersion.id
        ).filter(Route.status == RouteStatus.PUBLISHED)

        # Filter by city
        if city_id:
            query = query.filter(Route.city_id == city_id)

        # Filter by status
        if status_filter:
            statuses = [RouteStatus(s) for s in status_filter if s in RouteStatus.__members__.values()]
            if statuses:
                query = query.filter(Route.status.in_(statuses))

        # Filter by search query in title/summary for specified language
        if search:
            search_pattern = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    func.lower(RouteVersion.title_i18n[lang]).ilike(search_pattern),
                    func.lower(RouteVersion.summary_i18n[lang]).ilike(search_pattern)
                )
            )

        # Nearby filter using first checkpoint location (seq_no=0)
        if lat is not None and lon is not None:
            # Subquery to get first checkpoint (seq_no=0) of each published version
            first_checkpoint_sq = self.db.query(
                Checkpoint.route_version_id,
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
                RouteVersion.id == first_checkpoint_sq.c.route_version_id
            ).filter(
                ST_DWithin(
                    first_checkpoint_sq.c.location,
                    user_point,
                    distance_meters
                )
            )

        count = query.count()
        routes = query.offset(offset).limit(limit).all()

        result = []
        for route in routes:
            version = route.published_version
            checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
                Checkpoint.route_version_id == version.id,
                Checkpoint.is_visible == True
            ).scalar() or 0

            city = self.db.query(City).filter(City.geonameid == route.city_id).first()

            item = {
                "id": route.id,
                "slug": route.slug,
                "status": route.status.value,
                "title": self._resolve_i18n(version.title_i18n, lang),
                "summary": self._resolve_i18n(version.summary_i18n, lang) if version.summary_i18n else None,
                "duration_min": version.duration_min,
                "distance_m": version.distance_m,
                "ascent_m": version.ascent_m,
                "descent_m": version.descent_m,
                "languages": version.languages or [],
                "free_checkpoint_limit": version.free_checkpoint_limit,
                "price_amount": version.price_amount,
                "price_currency": version.price_currency,
                "city_id": route.city_id,
                "city_name": city.name if city else "",
                "checkpoint_count": checkpoint_count,
                "user_progress": None
            }

            # Add user progress if authenticated
            if user_id:
                active = self.db.query(UserActiveRoute).filter(
                    UserActiveRoute.user_id == user_id,
                    UserActiveRoute.route_id == route.id
                ).first()
                if active:
                    progress = self._calculate_user_progress(user_id, active.locked_version_id)
                    item["user_progress"] = {
                        "started_at": active.started_at,
                        "completed_at": active.completed_at,
                        "completion_type": active.completion_type.value if active.completion_type else None,
                        **progress
                    }

            result.append(item)

        return {"count": count, "routes": result}

    def get_route_detail(self, route_id: UUID, user_id: int | None = None, lang: str = "en") -> dict | None:
        """Get full route details"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route or not route.published_version_id:
            return None

        version = route.published_version
        city = self.db.query(City).filter(City.geonameid == route.city_id).first()

        checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
            Checkpoint.route_version_id == version.id,
            Checkpoint.is_visible == True
        ).scalar() or 0

        result = {
            "id": route.id,
            "slug": route.slug,
            "status": route.status.value,
            "city_id": route.city_id,
            "city_name": city.name if city else "",
            "version_id": version.id,
            "version_no": version.version_no,
            "title": self._resolve_i18n(version.title_i18n, lang),
            "summary": self._resolve_i18n(version.summary_i18n, lang) if version.summary_i18n else None,
            "languages": version.languages or [],
            "duration_min": version.duration_min,
            "distance_m": version.distance_m,
            "ascent_m": version.ascent_m,
            "descent_m": version.descent_m,
            "geojson": version.geojson,
            "free_checkpoint_limit": version.free_checkpoint_limit,
            "price_amount": version.price_amount,
            "price_currency": version.price_currency,
            "checkpoint_count": checkpoint_count,
            "created_at": route.created_at,
            "published_at": version.published_at,
            "user_progress": None
        }

        if user_id:
            active = self.db.query(UserActiveRoute).filter(
                UserActiveRoute.user_id == user_id,
                UserActiveRoute.route_id == route.id
            ).first()
            if active:
                progress = self._calculate_user_progress(user_id, active.locked_version_id)
                result["user_progress"] = {
                    "started_at": active.started_at,
                    "completed_at": active.completed_at,
                    "completion_type": active.completion_type.value if active.completion_type else None,
                    **progress
                }

        return result

    def get_route_checkpoints(
        self,
        route_id: UUID,
        user_id: int | None = None,
        lang: str = "en"
    ) -> list[dict]:
        """Get checkpoints for a route"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route or not route.published_version_id:
            return []

        # Use locked version if user has active session
        version_id = route.published_version_id
        if user_id:
            active = self.db.query(UserActiveRoute).filter(
                UserActiveRoute.user_id == user_id,
                UserActiveRoute.route_id == route_id,
                UserActiveRoute.completed_at == None
            ).first()
            if active:
                version_id = active.locked_version_id

        checkpoints = self.db.query(Checkpoint).filter(
            Checkpoint.route_version_id == version_id
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
        route = self.db.query(Route).join(
            RouteVersion, Route.id == RouteVersion.route_id
        ).filter(RouteVersion.id == checkpoint.route_version_id).first()
        if route:
            self._check_automatic_completion(user_id, route.id)

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
        route = self.db.query(Route).join(
            RouteVersion, Route.id == RouteVersion.route_id
        ).filter(RouteVersion.id == checkpoint.route_version_id).first()
        if route:
            self._check_automatic_completion(user_id, route.id)

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

    # ========== Active Routes Operations ==========

    def get_user_active_routes(self, user_id: int, lang: str = "en") -> list[dict]:
        """Get user's active routes"""
        sessions = self.db.query(UserActiveRoute).filter(
            UserActiveRoute.user_id == user_id
        ).order_by(UserActiveRoute.started_at.desc()).all()

        result = []
        for session in sessions:
            route = session.route
            version = session.locked_version
            city = self.db.query(City).filter(City.geonameid == route.city_id).first()

            checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
                Checkpoint.route_version_id == version.id,
                Checkpoint.is_visible == True
            ).scalar() or 0

            progress = self._calculate_user_progress(user_id, version.id)

            result.append({
                "id": session.id,
                "route": {
                    "id": route.id,
                    "slug": route.slug,
                    "status": route.status.value,
                    "title": self._resolve_i18n(version.title_i18n, lang),
                    "summary": self._resolve_i18n(version.summary_i18n, lang) if version.summary_i18n else None,
                    "duration_min": version.duration_min,
                    "distance_m": version.distance_m,
                    "ascent_m": version.ascent_m,
                    "descent_m": version.descent_m,
                    "languages": version.languages or [],
                    "free_checkpoint_limit": version.free_checkpoint_limit,
                    "price_amount": version.price_amount,
                    "price_currency": version.price_currency,
                    "city_id": route.city_id,
                    "city_name": city.name if city else "",
                    "checkpoint_count": checkpoint_count,
                    "user_progress": None
                },
                "locked_version_id": session.locked_version_id,
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

    def start_route(self, user_id: int, route_id: UUID) -> dict | None:
        """Start a route session"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route or not route.published_version_id:
            return None

        # Check if already started
        existing = self.db.query(UserActiveRoute).filter(
            UserActiveRoute.user_id == user_id,
            UserActiveRoute.route_id == route_id
        ).first()

        if existing:
            # Return existing session
            return self._get_active_route_response(existing, "en")

        # Create new session
        session = UserActiveRoute(
            user_id=user_id,
            route_id=route_id,
            locked_version_id=route.published_version_id
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return self._get_active_route_response(session, "en")

    def finish_route(self, user_id: int, route_id: UUID) -> dict | None:
        """Manually finish a route"""
        session = self.db.query(UserActiveRoute).filter(
            UserActiveRoute.user_id == user_id,
            UserActiveRoute.route_id == route_id,
            UserActiveRoute.completed_at == None
        ).first()

        if not session:
            return None

        session.completed_at = datetime.now(timezone.utc)
        session.completion_type = CompletionType.MANUAL
        self.db.commit()

        return self._get_active_route_response(session, "en")

    def _get_active_route_response(self, session: UserActiveRoute, lang: str) -> dict:
        """Build active route response"""
        route = session.route
        version = session.locked_version
        city = self.db.query(City).filter(City.geonameid == route.city_id).first()

        checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
            Checkpoint.route_version_id == version.id,
            Checkpoint.is_visible == True
        ).scalar() or 0

        progress = self._calculate_user_progress(session.user_id, version.id)

        return {
            "id": session.id,
            "route": {
                "id": route.id,
                "slug": route.slug,
                "status": route.status.value,
                "title": self._resolve_i18n(version.title_i18n, lang),
                "summary": self._resolve_i18n(version.summary_i18n, lang) if version.summary_i18n else None,
                "duration_min": version.duration_min,
                "distance_m": version.distance_m,
                "ascent_m": version.ascent_m,
                "descent_m": version.descent_m,
                "languages": version.languages or [],
                "free_checkpoint_limit": version.free_checkpoint_limit,
                "price_amount": version.price_amount,
                "price_currency": version.price_currency,
                "city_id": route.city_id,
                "city_name": city.name if city else "",
                "checkpoint_count": checkpoint_count,
                "user_progress": None
            },
            "locked_version_id": session.locked_version_id,
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

    def create_route(self, user_id: int, city_id: int, slug: str, status: str = "draft") -> Route:
        """Create new route"""
        route = Route(
            created_by_user_id=user_id,
            city_id=city_id,
            slug=slug,
            status=RouteStatus(status)
        )
        self.db.add(route)
        self.db.commit()
        self.db.refresh(route)
        return route

    def update_route(self, route_id: UUID, slug: str | None = None, status: str | None = None) -> Route | None:
        """Update route metadata"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            return None

        if slug is not None:
            route.slug = slug
        if status is not None:
            route.status = RouteStatus(status)

        self.db.commit()
        self.db.refresh(route)
        return route

    def delete_route(self, route_id: UUID) -> bool:
        """Delete route (cascades to versions, checkpoints)"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            return False

        self.db.delete(route)
        self.db.commit()
        return True

    def get_route_admin(self, route_id: UUID) -> dict | None:
        """Get route with version count for admin view"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            return None

        version_count = self.db.query(func.count(RouteVersion.id)).filter(
            RouteVersion.route_id == route_id
        ).scalar() or 0

        city = self.db.query(City).filter(City.geonameid == route.city_id).first()

        return {
            "id": route.id,
            "slug": route.slug,
            "status": route.status.value,
            "city_id": route.city_id,
            "city_name": city.name if city else "",
            "created_by_user_id": route.created_by_user_id,
            "published_version_id": route.published_version_id,
            "version_count": version_count,
            "created_at": route.created_at,
            "updated_at": route.updated_at
        }

    def list_routes_admin(
        self,
        city_id: int | None = None,
        status: list[str] | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        """List routes for admin with all statuses"""
        query = self.db.query(Route)

        if city_id:
            query = query.filter(Route.city_id == city_id)

        if status:
            statuses = [RouteStatus(s) for s in status if s in RouteStatus.__members__.values()]
            if statuses:
                query = query.filter(Route.status.in_(statuses))

        count = query.count()
        routes = query.order_by(Route.created_at.desc()).offset(offset).limit(limit).all()

        result = []
        for route in routes:
            version_count = self.db.query(func.count(RouteVersion.id)).filter(
                RouteVersion.route_id == route.id
            ).scalar() or 0

            city = self.db.query(City).filter(City.geonameid == route.city_id).first()

            result.append({
                "id": route.id,
                "slug": route.slug,
                "status": route.status.value,
                "city_id": route.city_id,
                "city_name": city.name if city else "",
                "created_by_user_id": route.created_by_user_id,
                "published_version_id": route.published_version_id,
                "version_count": version_count,
                "created_at": route.created_at,
                "updated_at": route.updated_at
            })

        return {"count": count, "routes": result}

    def create_route_version(self, route_id: UUID, user_id: int, data: dict) -> RouteVersion | None:
        """Create version from data dict with automatic checkpoint creation"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            return None

        # Auto-set version_no to max(existing) + 1
        max_version = self.db.query(func.max(RouteVersion.version_no)).filter(
            RouteVersion.route_id == route_id
        ).scalar() or 0
        version_no = max_version + 1

        # Create version
        version = RouteVersion(
            route_id=route_id,
            version_no=version_no,
            created_by_user_id=user_id,
            status=RouteVersionStatus.DRAFT,
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
        self.db.add(version)
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
                        route_version_id=version.id,
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
                    version.path = from_shape(geom, srid=4326)

        self.db.commit()
        self.db.refresh(version)
        return version

    def get_route_versions(self, route_id: UUID) -> list[dict]:
        """List all versions for a route"""
        versions = self.db.query(RouteVersion).filter(
            RouteVersion.route_id == route_id
        ).order_by(RouteVersion.version_no.desc()).all()

        result = []
        for version in versions:
            checkpoint_count = self.db.query(func.count(Checkpoint.id)).filter(
                Checkpoint.route_version_id == version.id
            ).scalar() or 0

            result.append({
                "id": version.id,
                "route_id": version.route_id,
                "version_no": version.version_no,
                "status": version.status.value,
                "created_by_user_id": version.created_by_user_id,
                "title_i18n": version.title_i18n,
                "summary_i18n": version.summary_i18n,
                "languages": version.languages,
                "duration_min": version.duration_min,
                "distance_m": version.distance_m,
                "ascent_m": version.ascent_m,
                "descent_m": version.descent_m,
                "free_checkpoint_limit": version.free_checkpoint_limit,
                "price_amount": version.price_amount,
                "price_currency": version.price_currency,
                "checkpoint_count": checkpoint_count,
                "created_at": version.created_at,
                "updated_at": version.updated_at,
                "published_at": version.published_at
            })

        return result

    def update_route_version(self, version_id: UUID, data: dict) -> RouteVersion | None:
        """Update version metadata (not checkpoints)"""
        version = self.db.query(RouteVersion).filter(RouteVersion.id == version_id).first()
        if not version:
            return None

        # Update fields if provided
        if "title_i18n" in data:
            version.title_i18n = data["title_i18n"]
        if "summary_i18n" in data:
            version.summary_i18n = data["summary_i18n"]
        if "languages" in data:
            version.languages = data["languages"]
        if "duration_min" in data:
            version.duration_min = data["duration_min"]
        if "distance_m" in data:
            version.distance_m = data["distance_m"]
        if "ascent_m" in data:
            version.ascent_m = data["ascent_m"]
        if "descent_m" in data:
            version.descent_m = data["descent_m"]
        if "free_checkpoint_limit" in data:
            version.free_checkpoint_limit = data["free_checkpoint_limit"]
        if "price_amount" in data:
            version.price_amount = data["price_amount"]
        if "price_currency" in data:
            version.price_currency = data["price_currency"]
        if "geojson" in data:
            version.geojson = data["geojson"]

        version.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(version)
        return version

    def publish_version(self, route_id: UUID, version_id: UUID) -> Route | None:
        """Set version status to published and update route"""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            return None

        version = self.db.query(RouteVersion).filter(RouteVersion.id == version_id).first()
        if not version or version.route_id != route_id:
            return None

        # Set any previously published version to superseded
        if route.published_version_id:
            old_version = self.db.query(RouteVersion).filter(
                RouteVersion.id == route.published_version_id
            ).first()
            if old_version:
                old_version.status = RouteVersionStatus.SUPERSEDED
                old_version.updated_at = datetime.now(timezone.utc)

        # Publish new version
        version.status = RouteVersionStatus.PUBLISHED
        version.published_at = datetime.now(timezone.utc)
        version.updated_at = datetime.now(timezone.utc)

        # Update route
        route.published_version_id = version_id
        if route.status != RouteStatus.PUBLISHED:
            route.status = RouteStatus.PUBLISHED
        route.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(route)
        return route

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

    def get_version_checkpoints_admin(self, version_id: UUID) -> list[dict]:
        """Get all checkpoints for a version (admin view, all fields)"""
        checkpoints = self.db.query(Checkpoint).filter(
            Checkpoint.route_version_id == version_id
        ).order_by(Checkpoint.seq_no).all()

        result = []
        for cp in checkpoints:
            point = to_shape(cp.location)
            result.append({
                "id": cp.id,
                "route_version_id": cp.route_version_id,
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
