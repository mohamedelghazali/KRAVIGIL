import ipaddress
import logging
import socket
from typing import List, Optional, Set
from urllib.parse import urlparse
from backend.core.exceptions import ScopeViolationException

logger = logging.getLogger(__name__)
BLOCKED_NETWORKS = tuple(ipaddress.ip_network(cidr) for cidr in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24",
    "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24",
    "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32",
    "::/128", "::1/128", "::ffff:0:0/96", "64:ff9b:1::/48",
    "100::/64", "2001:db8::/32", "fc00::/7", "fe80::/10", "ff00::/8",
))

class ScopeGuard:
    def __init__(self, allowed_cidrs: Optional[List[str]] = None):
        self.allowed_networks: Set[ipaddress._BaseNetwork] = set()
        for cidr in allowed_cidrs or []:
            try:
                self.allowed_networks.add(ipaddress.ip_network(cidr, strict=False))
            except ValueError as exc:
                logger.error("Invalid allowed CIDR %r: %s", cidr, exc)
                raise ScopeViolationException(f"Invalid allowed CIDR: {cidr}") from exc

    def validate_target(self, target: str) -> List[str]:
        hostname = self._extract_hostname(target)
        try:
            addresses = self._resolve(hostname)
        except socket.gaierror as exc:
            raise ScopeViolationException(f"DNS resolution failed for {hostname}: {exc}") from exc
        if not addresses:
            raise ScopeViolationException(f"No IP addresses resolved for {hostname}")
        for address in addresses:
            self.validate_ip_direct(address)
        return addresses

    def validate_ip_direct(self, ip_str: str) -> bool:
        try:
            address = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise ScopeViolationException(f"Invalid IP address: {ip_str}") from exc
        for blocked in BLOCKED_NETWORKS:
            if address.version == blocked.version and address in blocked:
                if not self._is_explicitly_allowed(address):
                    raise ScopeViolationException(f"IP {ip_str} is in blocked network {blocked}")
        return True

    def validate_redirect(self, original_host: str, redirect_url: str) -> bool:
        try:
            parsed = urlparse(redirect_url)
            if parsed.scheme.lower() not in {"http", "https"}:
                raise ValueError("Only HTTP and HTTPS redirects are allowed")
            new_host = parsed.hostname
        except (TypeError, ValueError) as exc:
            raise ScopeViolationException(f"Invalid redirect URL: {exc}") from exc
        if not new_host:
            raise ScopeViolationException("Redirect URL has no hostname")
        self.validate_target(new_host)
        return True

    def _extract_hostname(self, target: str) -> str:
        if not isinstance(target, str) or not target.strip():
            raise ScopeViolationException("Target must be a non-empty string")
        value = target.strip()
        try:
            if "://" in value:
                parsed = urlparse(value)
                if parsed.scheme.lower() not in {"http", "https"}:
                    raise ValueError("Only HTTP and HTTPS targets are allowed")
                hostname = parsed.hostname
            else:
                hostname = value.strip("[]")
                if any(char in hostname for char in "/?#@"):
                    raise ValueError("Invalid hostname")
        except ValueError as exc:
            raise ScopeViolationException(f"Invalid target: {exc}") from exc
        if not hostname:
            raise ScopeViolationException(f"Could not extract hostname from target: {target}")
        return hostname

    def _resolve(self, hostname: str) -> List[str]:
        results = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        return sorted({item[4][0] for item in results})

    def _is_explicitly_allowed(self, address: ipaddress._BaseAddress) -> bool:
        return any(address.version == net.version and address in net for net in self.allowed_networks)
