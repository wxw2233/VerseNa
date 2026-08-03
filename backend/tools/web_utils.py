import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    pass


async def validate_public_http_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("只允许 http 和 https URL")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeUrlError("URL 主机无效或包含凭据")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise UnsafeUrlError("禁止访问本机或局域网主机")

    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            infos = await asyncio.to_thread(
                socket.getaddrinfo,
                hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise UnsafeUrlError(f"无法解析主机: {hostname}") from exc
        addresses = {ipaddress.ip_address(info[4][0].split("%", 1)[0]) for info in infos}

    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeUrlError("禁止访问私网、回环、链路本地或保留地址")
