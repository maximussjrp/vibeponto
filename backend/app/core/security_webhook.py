"""
Security helper for webhook URL validation and SSRF prevention.
"""

import ipaddress
import socket
import urllib.parse
from typing import List, Set

from app.core.config import settings


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


def validate_webhook_url(url: str, allow_http: bool = False) -> str:
    """
    Validate a webhook URL against SSRF attack vectors.
    
    Checks:
    - Scheme must be HTTPS (or HTTP if explicit allow_http or development environment)
    - Hostname must be present
    - Hostname / IP must not resolve to loopback, private, link-local, or cloud metadata ranges.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL do webhook deve ser fornecida")

    parsed = urllib.parse.urlparse(url.strip())
    
    # Validate scheme
    scheme = parsed.scheme.lower()
    is_dev = getattr(settings, "ENVIRONMENT", "development") in ("development", "test")
    
    if allow_http or is_dev:
        allowed_schemes = {"http", "https"}
    else:
        allowed_schemes = {"https"}
        
    if scheme not in allowed_schemes:
        raise ValueError(f"Esquema de URL '{scheme}' não permitido. Use HTTPS.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL do webhook inválida: domínio não informado")

    # Lowercase hostname check for obvious loopback names
    lower_host = hostname.lower()
    if lower_host in ("localhost", "localhost.localdomain", "127.0.0.1", "::1"):
        raise ValueError("Endereço de destino não permitido (loopback)")

    # Attempt to parse hostname directly as IP or resolve via DNS
    try:
        # Check if direct IP literal
        ip_obj = ipaddress.ip_address(hostname)
        if is_ip_forbidden(ip_obj):
            raise ValueError(f"Endereço IP '{hostname}' não é permitido para webhooks")
    except ValueError as e:
        if "não é permitido" in str(e):
            raise
        # Not a direct IP literal, resolve DNS records
        port = parsed.port or (443 if scheme == "https" else 80)
        resolved_ips = resolve_hostname_ips(hostname, port)
        
        if not resolved_ips:
            raise ValueError(f"Nenhum endereço IP encontrado para '{hostname}'")
            
        for ip_str in resolved_ips:
            # Strip IPv6 zone index if present
            clean_ip_str = ip_str.split("%")[0]
            try:
                ip_obj = ipaddress.ip_address(clean_ip_str)
                if is_ip_forbidden(ip_obj):
                    raise ValueError(f"O domínio '{hostname}' resolveu para IP não permitido ({clean_ip_str})")
            except ValueError as ip_err:
                if "não permitido" in str(ip_err):
                    raise
                raise ValueError(f"Endereço IP inválido resolvido: {clean_ip_str}") from ip_err

    return url.strip()
