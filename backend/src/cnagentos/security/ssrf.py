"""
SSRF protection utilities for collection targets.

Implements security checks for URLs and hosts according to the security baseline.
"""

import ipaddress
import re
from typing import Set
from urllib.parse import urlparse

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
]

CLOUD_METADATA_HOSTS = [
    "metadata.google.internal",
    "169.254.169.254",
    "metadata.azure.com",
    "instance-data.service.compute.internal",
    "openstack.metadata",
]

ALLOWED_PROTOCOLS = ["https", "http"]


class SSRFValidationError(Exception):
    """Raised when SSRF validation fails."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


def is_ip_address(host: str) -> bool:
    """Check if host is an IP address."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def resolve_and_check_ip(host: str, allowed_hosts: list[str]) -> str | None:
    """
    Resolve hostname and verify result is in allowed_hosts.

    Returns the resolved IP if valid, None if host is in allowed_hosts directly.
    Raises SSRFValidationError if resolved IP is not in allowed_hosts.
    """
    import socket

    if host in allowed_hosts and not is_ip_address(host):
        return None

    try:
        addr_info = socket.getaddrinfo(host, None)
        for family, _, _, _, sockaddr in addr_info:
            resolved_ip = sockaddr[0]
            if not _is_ip_allowed(resolved_ip, allowed_hosts):
                raise SSRFValidationError(
                    f"Resolved IP {resolved_ip} for host {host} is not in allowed hosts",
                    "RESOLVED_IP_BLOCKED"
                )
    except socket.gaierror:
        if host not in allowed_hosts:
            raise SSRFValidationError(
                f"Cannot resolve host {host} and it's not in allowed hosts",
                "HOST_UNRESOLVABLE"
            )
    return None


def _is_ip_allowed(ip_str: str, allowed_hosts: list[str]) -> bool:
    """Check if an IP address is in the allowed hosts list or allowed networks."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for allowed in allowed_hosts:
        if is_ip_address(allowed):
            if ip == ipaddress.ip_address(allowed):
                return True
        else:
            try:
                network = ipaddress.ip_network(allowed, strict=False)
                if ip in network:
                    return True
            except ValueError:
                continue

    for private_network in PRIVATE_NETWORKS:
        if ip in private_network:
            return False

    return False


def validate_url(url: str, allowed_hosts: list[str]) -> None:
    """
    Validate a URL against security requirements.

    Raises SSRFValidationError if:
    - Protocol is not allowed (only https/http)
    - Host is not in allowed_hosts
    - Host resolves to a blocked address
    - Host is a cloud metadata endpoint
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFValidationError(f"Invalid URL: {url}", "INVALID_URL") from e

    protocol = parsed.scheme.lower()
    if protocol not in ALLOWED_PROTOCOLS:
        raise SSRFValidationError(
            f"Protocol {protocol} is not allowed, use https or http",
            "PROTOCOL_BLOCKED"
        )

    host = parsed.hostname
    if not host:
        raise SSRFValidationError(f"No host found in URL: {url}", "NO_HOST")

    if host.lower() in CLOUD_METADATA_HOSTS:
        raise SSRFValidationError(
            f"Cloud metadata host {host} is blocked",
            "METADATA_HOST_BLOCKED"
        )

    if host.lower() in [h.lower() for h in allowed_hosts]:
        return

    resolve_and_check_ip(host, allowed_hosts)


def validate_redirect_chain(urls: list[str], allowed_hosts: list[str], max_redirects: int = 10) -> None:
    """
    Validate a chain of redirect URLs.

    Raises SSRFValidationError if any URL in the chain fails validation
    or if the chain exceeds max_redirects.
    """
    if len(urls) > max_redirects:
        raise SSRFValidationError(
            f"Redirect chain exceeds maximum of {max_redirects} hops",
            "TOO_MANY_REDIRECTS"
        )

    for url in urls:
        validate_url(url, allowed_hosts)


def sanitize_header_key(key: str) -> bool:
    """
    Check if a header key is safe to use.

    Returns True if the header key does not contain dangerous patterns.
    """
    dangerous_patterns = [
        r"\r\n",
        r"\n",
        r"<script",
        r"javascript:",
        r"data:",
    ]
    key_lower = key.lower()
    for pattern in dangerous_patterns:
        if pattern.lower() in key_lower:
            return False
    return True


def sanitize_header_value(value: str) -> bool:
    """
    Check if a header value is safe to use.

    Returns True if the header value does not contain dangerous patterns.
    """
    dangerous_patterns = [
        r"\r\n",
        r"\n",
    ]
    for pattern in dangerous_patterns:
        if pattern in value:
            return False
    return True


def validate_request_headers(headers: dict | None) -> None:
    """
    Validate request headers for SSRF-related dangers.

    Raises SSRFValidationError if any header is dangerous.
    """
    if not headers:
        return

    for key, value in headers.items():
        if not sanitize_header_key(key):
            raise SSRFValidationError(
                f"Header key contains dangerous pattern: {key}",
                "DANGEROUS_HEADER_KEY"
            )
        if not sanitize_header_value(str(value)):
            raise SSRFValidationError(
                f"Header value contains dangerous pattern: {value}",
                "DANGEROUS_HEADER_VALUE"
            )
