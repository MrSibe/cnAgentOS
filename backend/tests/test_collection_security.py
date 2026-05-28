import pytest
from sqlalchemy import select

from cnagentos.api import ApiError
from cnagentos.models.entities import AuditLog, User
from cnagentos.services.collection_security import (
    sanitize_collection_error,
    validate_fetch_target,
    validate_rule_security,
    validate_source_policy,
)
from cnagentos.services.watch_audit import write_watch_audit


def resolver_for(records: dict[str, list[str]]):
    def resolve(host: str) -> list[str]:
        if host not in records:
            raise OSError("host not found")
        return records[host]

    return resolve


def assert_source_unsafe(fn, *args, **kwargs):
    with pytest.raises(ApiError) as exc_info:
        fn(*args, **kwargs)
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "SOURCE_UNSAFE"


def test_source_policy_accepts_https_allowed_public_host():
    validate_source_policy(
        "https://news.example.com/search?q=agriculture",
        ["news.example.com"],
        resolver=resolver_for({"news.example.com": ["93.184.216.34"]}),
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://news.example.com/search",
        "ftp://news.example.com/file",
        "https:///missing-host",
        "https://user:pass@news.example.com/search",
    ],
)
def test_source_policy_rejects_unsafe_url_shapes(url):
    assert_source_unsafe(
        validate_source_policy,
        url,
        ["news.example.com"],
        resolver=resolver_for({"news.example.com": ["93.184.216.34"]}),
    )


@pytest.mark.parametrize(
    "url,allowed_hosts",
    [
        ("https://localhost/status", ["localhost"]),
        ("https://127.0.0.1/status", ["127.0.0.1"]),
        ("https://[::1]/status", ["::1"]),
        ("https://10.0.0.5/status", ["10.0.0.5"]),
        ("https://172.16.0.5/status", ["172.16.0.5"]),
        ("https://192.168.1.5/status", ["192.168.1.5"]),
        ("https://169.254.169.254/latest", ["169.254.169.254"]),
        ("https://metadata.google.internal/latest", ["metadata.google.internal"]),
    ],
)
def test_source_policy_rejects_local_private_and_metadata_targets(url, allowed_hosts):
    assert_source_unsafe(
        validate_source_policy,
        url,
        allowed_hosts,
        resolver=resolver_for({host.strip("[]"): ["93.184.216.34"] for host in allowed_hosts}),
    )


def test_source_policy_rejects_dns_results_with_private_addresses():
    assert_source_unsafe(
        validate_source_policy,
        "https://news.example.com/search",
        ["news.example.com"],
        resolver=resolver_for({"news.example.com": ["93.184.216.34", "10.0.0.8"]}),
    )


def test_source_policy_rejects_unused_allowed_host_with_private_dns_result():
    assert_source_unsafe(
        validate_source_policy,
        "https://news.example.com/search",
        ["news.example.com", "internal.example.com"],
        resolver=resolver_for(
            {
                "news.example.com": ["93.184.216.34"],
                "internal.example.com": ["192.168.1.10"],
            }
        ),
    )


def test_fetch_target_rejects_hosts_outside_allowed_scope():
    assert_source_unsafe(
        validate_fetch_target,
        "https://redirect.example.net/story",
        ["news.example.com"],
        resolver=resolver_for({"redirect.example.net": ["93.184.216.34"]}),
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer secret"},
        {"Cookie": "session=secret"},
        {"Host": "internal"},
        {"Proxy-Authorization": "Basic secret"},
        {"X-Forwarded-For": "127.0.0.1"},
        {"Accept": "text/html\r\nX-Injected: yes"},
    ],
)
def test_rule_security_rejects_dangerous_headers(headers):
    assert_source_unsafe(
        validate_rule_security,
        headers,
        {"query": "{{query}}"},
        {"item_selector": ".news-item"},
    )


def test_rule_security_rejects_unsupported_headers():
    assert_source_unsafe(
        validate_rule_security,
        {"X-Custom-Header": "value"},
        {"query": "{{query}}"},
        {"item_selector": ".news-item"},
    )


def test_rule_security_rejects_unknown_template_variables():
    assert_source_unsafe(
        validate_rule_security,
        {"Accept": "text/html"},
        {"keyword": "{{secret}}"},
        {"item_selector": ".news-item"},
    )


@pytest.mark.parametrize(
    "extractor_config",
    [
        {"script": "return document.body"},
        {"item_selector": "<script>alert(1)</script>"},
        {"content_selector": "javascript:alert(1)"},
        {"transform": "eval(input)"},
    ],
)
def test_rule_security_rejects_script_like_extractors(extractor_config):
    assert_source_unsafe(
        validate_rule_security,
        {"Accept": "text/html"},
        {"keyword": "{{query}}"},
        extractor_config,
    )


def test_rule_security_accepts_safe_rule_configuration():
    validate_rule_security(
        {"Accept": "text/html", "User-Agent": "cnAgentOS collector"},
        {"keyword": "{{query}}", "page": 1},
        {
            "item_selector": ".news-item",
            "title_selector": ".title",
            "url_selector": "a@href",
            "content_selector": ".summary",
        },
    )


def test_rule_security_allows_non_executable_function_named_fields():
    validate_rule_security(
        {"Accept": "application/json"},
        {"keyword": "{{query}}"},
        {"my_function_transform": "title"},
    )


def test_sanitize_collection_error_never_returns_raw_sensitive_text():
    raw_error = (
        "failed GET https://news.example.com/search?token=secret with "
        "Authorization: Bearer secret and Cookie: session=secret"
    )
    sanitized = sanitize_collection_error(raw_error)
    body = str(sanitized)

    assert sanitized == {"error_code": "COLLECTION_FAILED", "summary": "采集执行失败"}
    assert "secret" not in body
    assert "Authorization" not in body
    assert "Cookie" not in body
    assert "token=" not in body


async def test_watch_data_permissions_remain_available(client, admin_session):
    response = await client.get("/api/v1/admin/permissions")
    codes = {item["code"] for item in response.json()["data"]}

    assert response.status_code == 200
    assert {
        "watch.sources.manage",
        "watch.tasks.run",
        "watch.tasks.view",
        "data.items.view",
        "data.items.manage",
    }.issubset(codes)


async def test_watch_audit_sanitizes_sensitive_detail(app):
    async with app.state.sessionmaker() as session:
        actor = await session.scalar(select(User).where(User.username == "root"))
        await write_watch_audit(
            session,
            actor,
            "watch.source.updated",
            "watch_source",
            "source-1",
            "rejected",
            {
                "entry_url": "https://news.example.com/search?token=secret",
                "auth_config": {"headers": {"Authorization": "Bearer secret"}},
                "request_headers": {"Cookie": "session=secret"},
                "error_code": "SOURCE_UNSAFE",
            },
            "127.0.0.1",
        )
        await session.commit()

        log = await session.scalar(
            select(AuditLog).where(AuditLog.action == "watch.source.updated")
        )

    assert log is not None
    assert log.detail["entry_url"] == "https://news.example.com/search"
    assert log.detail["auth_config"] == "[redacted]"
    assert log.detail["request_headers"] == "[redacted]"
    body = str(log.detail)
    assert "secret" not in body
    assert "Authorization" not in body
    assert "Cookie" not in body
    assert "token=" not in body
