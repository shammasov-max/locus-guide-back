import httpx
from typing import Optional, Tuple
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GeoIPService:
    """
    Service for getting user coordinates from IP address.
    Uses ip-api.com free tier (no API key required, 45 req/min limit).
    """

    def __init__(self):
        self.enabled = settings.geoip_enabled
        self.url_template = settings.geoip_url

    def get_coordinates(self, ip: str) -> Optional[Tuple[float, float]]:
        """
        Get latitude and longitude from IP address.

        Args:
            ip: Client IP address

        Returns:
            Tuple of (lat, lon) or None if lookup fails
        """
        if not self.enabled:
            return None

        # Skip private/local IPs
        if self._is_private_ip(ip):
            logger.debug(f"Skipping GeoIP lookup for private IP: {ip}")
            return None

        try:
            url = self.url_template.format(ip=ip)
            with httpx.Client(timeout=2.0) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "success":
                    lat = data.get("lat")
                    lon = data.get("lon")
                    if lat is not None and lon is not None:
                        logger.debug(f"GeoIP resolved {ip} to ({lat}, {lon})")
                        return (float(lat), float(lon))

                logger.debug(f"GeoIP lookup failed for {ip}: {data}")
                return None

        except httpx.TimeoutException:
            logger.warning(f"GeoIP lookup timeout for {ip}")
            return None
        except Exception as e:
            logger.warning(f"GeoIP lookup error for {ip}: {e}")
            return None

    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """Check if IP is private/local (RFC 1918, localhost, etc.)"""
        if not ip:
            return True

        # Common private ranges
        private_prefixes = (
            "10.",
            "172.16.", "172.17.", "172.18.", "172.19.",
            "172.20.", "172.21.", "172.22.", "172.23.",
            "172.24.", "172.25.", "172.26.", "172.27.",
            "172.28.", "172.29.", "172.30.", "172.31.",
            "192.168.",
            "127.",
            "0.",
            "::1",
            "localhost",
        )
        return ip.startswith(private_prefixes)


# Singleton instance
geoip_service = GeoIPService()
