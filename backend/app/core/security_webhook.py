"""
Security helper for webhook URL validation, SSRF prevention, and TOCTOU/DNS Rebinding mitigation.
"""

import ipaddress
import logging
import socket
import urllib.parse
from typing import List, Tuple

import httpx
from app.core.config import settings

logger = logging.getLogger("app.security.webhook")

FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),         # Unspecified
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918 Private
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / AWS Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918 Private
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918 Private
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
    ipaddress.ip_network("::/128"),            # Unspecified IPv6
    ipaddress.ip_network("::1/128"),           # Loopback IPv6
    ipaddress.ip_network("fe80::/10"),         # Link-local IPv6
    ipaddress.ip_network("ff00::/8"),          # Multicast IPv6
]


class PinningAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """
    HTTP Transport subclass that pins TCP/TLS connections to a pre-validated IP address
    while keeping the original hostname for TLS SNI server verification and the Host header.
    Prevents TOCTOU (Time of Check to Time of Use) / DNS Rebinding attacks.
    """
    def __init__(self, target_ip: str, original_host: str, **kwargs):
        super().__init__(**kwargs)
        self.target_ip = target_ip
        self.original_host = original_host

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Override URL host for low-level connection to target_ip
        request.url = request.url.copy_with(host=self.target_ip)
        request.headers["Host"] = self.original_host
        request.extensions["sni_hostname"] = self.original_host
        return await super().handle_async_request(request)


def create_pinned_client(
    target_ip: str,
    original_host: str,
    timeout: float = 5.0,
    **kwargs
) -> httpx.AsyncClient:
    """
    Create an AsyncClient configured with IP pinning, verify=True, and follow_redirects=False.
    """
    transport = PinningAsyncHTTPTransport(
        target_ip=target_ip,
        original_host=original_host,
        verify=kwargs.pop("verify", True),
    )
    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,
        timeout=timeout,
        **kwargs
    )


def is_ip_forbidden(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address falls into any forbidden/private/loopback range."""
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True

    for net in FORBIDDEN_NETWORKS:
        if ip in net:
            return True

    return False


def resolve_hostname_ips(hostname: str, port: int = 443) -> List[str]:
    """Resolve A and AAAA DNS records for a given hostname."""
    try:
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ips = list({info[4][0] for info in addr_info})
        return ips
    except socket.gaierror as e:
        raise ValueError(f"Não foi possível resolver o domínio '{hostname}'") from e


def validate_webhook_url(url: str, allow_http: bool = False) -> Tuple[str, str, str, int]:
    """
    Validate a webhook URL against SSRF attack vectors and userinfo tricks.

    Returns tuple: (clean_url, hostname, target_ip, port)
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL do webhook deve ser fornecida")

    stripped_url = url.strip()
    parsed = urllib.parse.urlparse(stripped_url)

    # 1. Reject Userinfo (e.g. https://user:pass@host or https://127.0.0.1@example.com)
    if parsed.username or parsed.password or "@" in (parsed.netloc.split(":")[0] if ":" in parsed.netloc else parsed.netloc):
        raise ValueError("URLs de webhook contendo credenciais ou caracteres '@' não são permitidas")

    # 2. Validate scheme
    scheme = parsed.scheme.lower()
    is_dev = getattr(settings, "ENVIRONMENT", "development") in ("development", "test")

    if allow_http or is_dev:
        allowed_schemes = {"http", "https"}
    else:
        allowed_schemes = {"https"}

    if scheme not in allowed_schemes:
        raise ValueError(f"Esquema de URL '{scheme}' não permitido. Use HTTPS.")

    # 3. Validate hostname
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL do webhook inválida: domínio não informado")

    lower_host = hostname.lower().strip(".")
    if lower_host in ("localhost", "localhost.localdomain", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError("Endereço de destino não permitido (loopback/unspecified)")

    port = parsed.port or (443 if scheme == "https" else 80)
    target_ip = None

    # 4. Direct IP literal check or DNS resolution
    try:
        ip_obj = ipaddress.ip_address(lower_host)
        if is_ip_forbidden(ip_obj):
            raise ValueError(f"Endereço IP '{lower_host}' não é permitido para webhooks")
        target_ip = str(ip_obj)
    except ValueError as e:
        if "não é permitido" in str(e):
            raise

        # Resolve A and AAAA DNS records
        resolved_ips = resolve_hostname_ips(hostname, port)
        if not resolved_ips:
            raise ValueError(f"Nenhum endereço IP encontrado para '{hostname}'")

        for ip_str in resolved_ips:
            clean_ip_str = ip_str.split("%")[0]
            try:
                ip_obj = ipaddress.ip_address(clean_ip_str)
                if is_ip_forbidden(ip_obj):
                    raise ValueError(f"O domínio '{hostname}' resolveu para IP não permitido ({clean_ip_str})")
            except ValueError as ip_err:
                if "não permitido" in str(ip_err):
                    raise
                raise ValueError(f"Endereço IP inválido resolvido: {clean_ip_str}") from ip_err

        target_ip = resolved_ips[0].split("%")[0]

    return stripped_url, hostname, target_ip, port
