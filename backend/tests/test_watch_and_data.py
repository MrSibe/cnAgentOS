"""Integration tests for Phase 2B Watch and Data features."""

import pytest
from sqlalchemy import select

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    AuditLog,
    CollectionTask,
    CollectionTaskSource,
    KnowledgeItem,
    WatchRule,
    WatchSource,
)
from cnagentos.services.collection_security import (
    validate_fetch_target,
    validate_rule_security,
    validate_source_policy,
)


def resolver_for(records: dict[str, list[str]]):
    def resolve(host: str) -> list[str]:
        if host not in records:
            raise OSError("host not found")
        return records[host]

    return resolve


# --- Source Policy Tests ---

def test_source_policy_https_only():
    """Phase 2 security: Only HTTPS allowed."""
    with pytest.raises(ApiError) as exc:
        validate_source_policy(
            "http://example.com/path",
            ["example.com"],
            resolver=resolver_for({"example.com": ["93.184.216.34"]}),
        )
    assert exc.value.code == "SOURCE_UNSAFE"
    assert "HTTPS" in str(exc.value.details) or "https" in str(exc.value).lower()


def test_source_policy_allows_https_public_host():
    """Valid source with HTTPS and allowed public host."""
    validate_source_policy(
        "https://news.example.com/search?q=test",
        ["news.example.com"],
        resolver=resolver_for({"news.example.com": ["93.184.216.34"]}),
    )


def test_source_policy_with_mock_resolver():
    """Source creation with mock resolver to avoid DNS dependency."""
    # Use public IP (8.8.8.8 is Google's public DNS server)
    validate_source_policy(
        "https://test.example.com/page",
        ["test.example.com"],
        resolver=resolver_for({"test.example.com": ["8.8.8.8"]}),
    )


def test_source_policy_rejects_private_ip_in_allowed_hosts():
    """Phase 2 security: Private IPs not allowed even in allowed_hosts."""
    with pytest.raises(ApiError):
        validate_source_policy(
            "https://192.168.1.100/path",
            ["192.168.1.100"],
            resolver=resolver_for({"192.168.1.100": ["192.168.1.100"]}),
        )


def test_source_policy_rejects_localhost():
    """Phase 2 security: localhost not allowed."""
    with pytest.raises(ApiError):
        validate_source_policy(
            "https://localhost/status",
            ["localhost"],
            resolver=resolver_for({"localhost": ["127.0.0.1"]}),
        )


def test_source_policy_rejects_metadata_host():
    """Phase 2 security: Cloud metadata hosts blocked."""
    with pytest.raises(ApiError):
        validate_source_policy(
            "https://169.254.169.254/latest/meta-data",
            ["169.254.169.254"],
            resolver=resolver_for({"169.254.169.254": ["169.254.169.254"]}),
        )


def test_source_policy_rejects_dns_rebinding():
    """DNS resolves to private IP even though hostname is in allowed_hosts."""
    with pytest.raises(ApiError):
        validate_source_policy(
            "https://trusted.example/path",
            ["trusted.example"],
            resolver=resolver_for({"trusted.example": ["10.0.0.5", "93.184.216.34"]}),
        )


def test_source_policy_rejects_host_not_in_allowed_list():
    """URL host must be in allowed_hosts."""
    with pytest.raises(ApiError):
        validate_source_policy(
            "https://evil.com/path",
            ["allowed.com"],
            resolver=resolver_for({"evil.com": ["93.184.216.34"]}),
        )


# --- Fetch Target Tests ---

def test_fetch_target_validates_url_against_allowed_hosts():
    """Fetch target validates URL against allowed_hosts."""
    with pytest.raises(ApiError):
        validate_fetch_target(
            "https://other-site.com/path",
            ["mysite.com"],
            resolver=resolver_for({"other-site.com": ["93.184.216.34"]}),
        )


# --- Rule Security Tests ---

def test_rule_security_rejects_dangerous_headers():
    """Dangerous headers like Authorization, Cookie blocked."""
    with pytest.raises(ApiError):
        validate_rule_security(
            {"Authorization": "Bearer secret"},
            {"query": "{{query}}"},
            {"item_selector": ".news"},
        )


def test_rule_security_accepts_safe_configuration():
    """Valid rule configuration passes."""
    validate_rule_security(
        {"Accept": "text/html", "User-Agent": "cnAgentOS/1.0"},
        {"keyword": "{{query}}"},
        {
            "item_selector": ".news-item",
            "title_selector": ".title",
            "url_selector": "a@href",
            "content_selector": ".summary",
        },
    )


def test_rule_security_rejects_script_patterns():
    """Script patterns in extractor config blocked."""
    with pytest.raises(ApiError):
        validate_rule_security(
            {"Accept": "text/html"},
            {},
            {"script": "alert(1)"},
        )


# --- Service Tests ---

async def test_watch_sources_permission_included(client, admin_session):
    """watch.sources.manage permission exists."""
    response = await client.get("/api/v1/admin/permissions")
    codes = {item["code"] for item in response.json()["data"]}
    assert "watch.sources.manage" in codes


async def test_watch_tasks_permission_included(client, admin_session):
    """watch.tasks.run and watch.tasks.view permissions exist."""
    response = await client.get("/api/v1/admin/permissions")
    codes = {item["code"] for item in response.json()["data"]}
    assert "watch.tasks.run" in codes
    assert "watch.tasks.view" in codes


async def test_data_items_permission_included(client, admin_session):
    """data.items permissions exist."""
    response = await client.get("/api/v1/admin/permissions")
    codes = {item["code"] for item in response.json()["data"]}
    assert "data.items.view" in codes
    assert "data.items.manage" in codes


async def test_watch_sources_list_endpoint_exists(client, admin_session):
    """GET /api/v1/admin/watch-sources endpoint works."""
    response = await client.get(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


async def test_watch_rules_list_endpoint(client, admin_session):
    """GET /api/v1/admin/watch-sources/{id}/rules returns 404 for non-existent source."""
    response = await client.get(
        "/api/v1/admin/watch-sources/non-existent-source-id/rules",
        headers={"X-CSRF-Token": admin_session},
    )
    assert response.status_code == 404


async def test_collection_tasks_list_endpoint_exists(client, admin_session):
    """GET /api/v1/admin/collection-tasks endpoint works."""
    response = await client.get(
        "/api/v1/admin/collection-tasks",
        headers={"X-CSRF-Token": admin_session},
    )
    assert response.status_code == 200


async def test_knowledge_items_list_endpoint_exists(client, admin_session):
    """GET /api/v1/admin/knowledge-items endpoint works."""
    response = await client.get(
        "/api/v1/admin/knowledge-items",
        headers={"X-CSRF-Token": admin_session},
    )
    assert response.status_code == 200


async def test_create_source_requires_csrf(client, admin_session):
    """POST /api/v1/admin/watch-sources requires CSRF token."""
    response = await client.post(
        "/api/v1/admin/watch-sources",
        json={
            "name": "Test",
            "source_type": "web_page",
            "entry_url": "https://example.com/page",
            "allowed_hosts": ["example.com"],
        },
    )
    assert response.status_code == 403


async def test_create_source_validates_security(client, admin_session):
    """Source creation validates SSRF policy - HTTP rejected."""
    response = await client.post(
        "/api/v1/admin/watch-sources",
        json={
            "name": "Bad Source",
            "source_type": "web_page",
            "entry_url": "http://example.com/page",
            "allowed_hosts": ["example.com"],
        },
        headers={"X-CSRF-Token": admin_session},
    )
    assert response.status_code == 422


async def test_create_source_validates_https(client, admin_session):
    """Source creation: HTTP URLs are rejected."""
    response = await client.post(
        "/api/v1/admin/watch-sources",
        json={
            "name": "HTTP Source",
            "source_type": "web_page",
            "entry_url": "http://http.example.com/path",
            "allowed_hosts": ["http.example.com"],
        },
        headers={"X-CSRF-Token": admin_session},
    )
    assert response.status_code == 422
