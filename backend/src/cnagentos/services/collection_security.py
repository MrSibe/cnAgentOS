import ipaddress
import re
import socket
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from cnagentos.api import ApiError


MAX_REDIRECTS = 3
DEFAULT_ALLOWED_TEMPLATE_FIELDS = frozenset({"query"})

_TEMPLATE_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
_DANGEROUS_HEADER_NAMES = {
    "authorization",
    "cookie",
    "host",
    "proxy-authorization",
    "proxy-connection",
}
_ALLOWED_REQUEST_HEADER_NAMES = {
    "accept",
    "accept-language",
    "content-type",
    "if-modified-since",
    "if-none-match",
    "user-agent",
}
_SCRIPT_PATTERNS = (
    "<script",
    "javascript:",
    "vbscript:",
    "data:text/html",
    "eval(",
    "function(",
    "${",
    "{%",
)
_LOCAL_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
}

AddressResolver = Callable[[str], Iterable[str]]


def _source_unsafe(field: str, reason: str) -> ApiError:
    return ApiError(422, "SOURCE_UNSAFE", "采集目标未通过安全校验", {field: reason})


def _normalize_host(host: str) -> str:
    value = host.strip().rstrip(".").lower()
    if not value:
        raise _source_unsafe("host", "主机名不能为空")
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise _source_unsafe("host", "主机名格式无效") from exc


def _ip_address_for(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def _ensure_public_ip(address: str, field: str) -> None:
    try:
        ip = ipaddress.ip_address(address.strip("[]"))
    except ValueError as exc:
        raise _source_unsafe(field, "解析结果不是有效 IP 地址") from exc
    if not ip.is_global:
        raise _source_unsafe(field, "目标解析到非公网地址")


def _default_resolver(host: str) -> Iterable[str]:
    records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    addresses = set()
    for record in records:
        sockaddr = record[4]
        if sockaddr:
            addresses.add(str(sockaddr[0]))
    return addresses


def _ensure_hostname_is_allowed(host: str) -> None:
    if host in _LOCAL_HOSTNAMES or host.endswith(".localhost") or host.endswith(".local"):
        raise _source_unsafe("host", "不允许访问本地域名")
    literal_ip = _ip_address_for(host)
    if literal_ip is not None and not literal_ip.is_global:
        raise _source_unsafe("host", "不允许访问非公网 IP")


def _validate_allowed_hosts(allowed_hosts: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for item in allowed_hosts:
        if "://" in item or "/" in item or ":" in item or "*" in item:
            raise _source_unsafe("allowed_hosts", "仅支持精确主机名，不支持协议、端口、路径或通配符")
        host = _normalize_host(item)
        _ensure_hostname_is_allowed(host)
        normalized.add(host)
    if not normalized:
        raise _source_unsafe("allowed_hosts", "至少配置一个允许访问的主机")
    return normalized


def _validate_url(url: str, allowed_hosts: set[str], resolver: AddressResolver) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise _source_unsafe("entry_url", "首版仅允许 HTTPS 地址")
    if parsed.username or parsed.password:
        raise _source_unsafe("entry_url", "URL 不允许包含用户名或密码")
    if not parsed.hostname:
        raise _source_unsafe("entry_url", "URL 必须包含主机名")

    host = _normalize_host(parsed.hostname)
    _ensure_hostname_is_allowed(host)
    if host not in allowed_hosts:
        raise _source_unsafe("entry_url", "主机不在允许访问范围内")

    _validate_host_resolution(host, resolver, "entry_url")
    return host


def _validate_host_resolution(host: str, resolver: AddressResolver, field: str) -> None:
    literal_ip = _ip_address_for(host)
    if literal_ip is not None:
        _ensure_public_ip(str(literal_ip), field)
        return

    try:
        addresses = list(resolver(host))
    except OSError as exc:
        raise _source_unsafe(field, "主机名解析失败") from exc
    if not addresses:
        raise _source_unsafe(field, "主机名没有可用解析结果")
    for address in addresses:
        _ensure_public_ip(address, field)


def validate_source_policy(
    entry_url: str,
    allowed_hosts: Iterable[str],
    *,
    resolver: AddressResolver | None = None,
) -> None:
    """Validate a saved source before credentials or rules are persisted."""
    normalized_hosts = _validate_allowed_hosts(allowed_hosts)
    active_resolver = resolver or _default_resolver
    for host in normalized_hosts:
        _validate_host_resolution(host, active_resolver, "allowed_hosts")
    _validate_url(entry_url, normalized_hosts, active_resolver)


def validate_fetch_target(
    url: str,
    allowed_hosts: Iterable[str],
    *,
    resolver: AddressResolver | None = None,
) -> None:
    """Validate a concrete fetch URL before a request or redirect hop."""
    normalized_hosts = _validate_allowed_hosts(allowed_hosts)
    _validate_url(url, normalized_hosts, resolver or _default_resolver)


def _assert_no_control_chars(value: str, field: str) -> None:
    if "\r" in value or "\n" in value:
        raise _source_unsafe(field, "不允许包含换行控制字符")


def _validate_headers(headers: Mapping[str, Any] | None) -> None:
    if not headers:
        return
    for raw_name, raw_value in headers.items():
        name = str(raw_name).strip()
        lowered = name.lower()
        _assert_no_control_chars(name, "request_headers")
        _assert_no_control_chars(str(raw_value), "request_headers")
        if (
            lowered in _DANGEROUS_HEADER_NAMES
            or lowered.startswith("proxy-")
            or lowered.startswith("x-forwarded-")
        ):
            raise _source_unsafe("request_headers", "包含不允许由规则配置的请求头")
        if lowered not in _ALLOWED_REQUEST_HEADER_NAMES:
            raise _source_unsafe("request_headers", "包含不支持的请求头")


def _validate_templates(value: Any, allowed_fields: frozenset[str], field: str) -> None:
    if isinstance(value, str):
        _assert_no_control_chars(value, field)
        placeholders = set(_TEMPLATE_RE.findall(value))
        if "{{" in value and not placeholders:
            raise _source_unsafe(field, "模板占位符格式无效")
        invalid = placeholders - allowed_fields
        if invalid:
            raise _source_unsafe(field, "包含未支持的模板变量")
    elif isinstance(value, Mapping):
        for nested in value.values():
            _validate_templates(nested, allowed_fields, field)
    elif isinstance(value, list):
        for nested in value:
            _validate_templates(nested, allowed_fields, field)
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise _source_unsafe(field, "仅支持 JSON 标量、数组或对象")


def _validate_no_script_config(value: Any, field: str) -> None:
    if isinstance(value, str):
        lowered = value.lower()
        if any(pattern in lowered for pattern in _SCRIPT_PATTERNS):
            raise _source_unsafe(field, "解析配置不得包含脚本或任意表达式")
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            lowered_key = str(key).lower()
            if re.search(r"^(script|eval|function)($|[_-])|[_-](script|eval|function)$", lowered_key):
                raise _source_unsafe(field, "解析配置不得包含脚本字段")
            _validate_no_script_config(nested, field)
    elif isinstance(value, list):
        for nested in value:
            _validate_no_script_config(nested, field)
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise _source_unsafe(field, "仅支持 JSON 标量、数组或对象")


def validate_rule_security(
    request_headers: Mapping[str, Any] | None,
    request_params: Mapping[str, Any] | None,
    extractor_config: Mapping[str, Any],
    *,
    allowed_template_fields: Iterable[str] = DEFAULT_ALLOWED_TEMPLATE_FIELDS,
) -> None:
    """Validate rule configuration before it can be saved or enabled."""
    fields = frozenset(allowed_template_fields)
    _validate_headers(request_headers)
    _validate_templates(request_params or {}, fields, "request_params")
    _validate_no_script_config(extractor_config, "extractor_config")


def sanitized_url(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return "[redacted-url]"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def sanitize_collection_error(error: Exception | str) -> dict[str, str]:
    if isinstance(error, ApiError):
        code = error.code
    elif isinstance(error, str) and re.fullmatch(r"[A-Z0-9_]{2,40}", error):
        code = error
    else:
        code = "COLLECTION_FAILED"
    summaries = {
        "SOURCE_UNSAFE": "采集目标未通过安全校验",
        "TIMEOUT": "采集请求超时",
        "UPSTREAM_ERROR": "外部来源返回错误",
        "VALIDATION_ERROR": "采集配置无效",
        "COLLECTION_FAILED": "采集执行失败",
    }
    return {"error_code": code, "summary": summaries.get(code, "采集执行失败")}
