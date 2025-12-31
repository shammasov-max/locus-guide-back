"""Notification interface for wish/want triggers.

This module provides an abstract interface for sending notifications
when wished tours become available or wanted cities get tours.

Implementation Notes:
---------------------
Integrate with your push notification service (Firebase Cloud Messaging,
OneSignal, etc.) by implementing the WishNotificationService interface.

Trigger Points:
- Tour Published: Call in RouteService.publish_version when status
  changes from coming_soon to published
- City Has Tour: Call in RouteService.publish_version when publishing
  the first tour in a city
"""

from abc import ABC, abstractmethod
from uuid import UUID


class WishNotificationService(ABC):
    """Abstract interface for sending wish/want notifications."""

    @abstractmethod
    async def notify_route_published(
        self, route_id: UUID, route_title: str, user_ids: list[int]
    ) -> None:
        """
        Send notification when a wished tour becomes published.

        Message template:
        "You wished tour '{route_title}' - it's waiting for you in the app!"

        Args:
            route_id: The tour that was published
            route_title: Title of the tour (localized)
            user_ids: List of user IDs who wished this tour
        """
        pass

    @abstractmethod
    async def notify_city_has_route(
        self, geonameid: int, city_name: str, route_id: UUID, user_ids: list[int]
    ) -> None:
        """
        Send notification when first tour is added to a wanted city.

        Message template:
        "You wanted tours in {city_name} - it's now available!"

        Args:
            geonameid: The city that got a new tour
            city_name: Name of the city
            route_id: The first published tour in the city
            user_ids: List of user IDs who wanted this city
        """
        pass


class DummyNotificationService(WishNotificationService):
    """Placeholder implementation for development/testing.

    Logs notifications to stdout instead of sending real push notifications.
    Replace with actual implementation (FCM, OneSignal, etc.) in production.
    """

    async def notify_route_published(
        self, route_id: UUID, route_title: str, user_ids: list[int]
    ) -> None:
        print(
            f"[NOTIFY] Tour '{route_title}' ({route_id}) published, "
            f"would notify {len(user_ids)} users: {user_ids[:5]}..."
        )

    async def notify_city_has_route(
        self, geonameid: int, city_name: str, route_id: UUID, user_ids: list[int]
    ) -> None:
        print(
            f"[NOTIFY] City '{city_name}' ({geonameid}) has tour {route_id}, "
            f"would notify {len(user_ids)} users: {user_ids[:5]}..."
        )
