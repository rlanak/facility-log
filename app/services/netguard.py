"""Outgoing requests to an address someone typed in Configurações.

On the web, settings are shared by everyone with the role, and the server
calls whatever address is saved there (the cloud API of the capture). Left
alone, any member could point it at the server's own network — another
machine behind the firewall, the cloud provider's metadata address — and use
the app to reach what they can't (SSRF). So in web mode those requests only
go to public internet addresses:

- the address is refused when saved if it names a private one;
- at request time the check is on the address actually connected to, before
  anything is sent — a name that resolved to a public address when saved and
  to a private one later doesn't get through;
- redirects are never followed (a public address answering "go to
  http://10.0.0.1/" would be the same hole).

Local mode is the user's own PC talking to its own network (LM Studio, a
remote Ollama on the LAN): nothing is blocked there. A web server that
really has its API on a private address sets FACILITY_LOG_ALLOW_PRIVATE_URLS=1.
"""

import http.client
import ipaddress
import os
import socket
import urllib.error
import urllib.parse
import urllib.request


class BlockedAddress(OSError):
    """The address is not on the public internet."""


def public_only() -> bool:
    from app import auth

    return auth.config.enabled and os.environ.get("FACILITY_LOG_ALLOW_PRIVATE_URLS", "").strip() != "1"


def _is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%")[0])  # "fe80::1%eth0"
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    # is_global is False for loopback, private, link-local (169.254.169.254,
    # the cloud metadata address), CGNAT 100.64/10 (VPN meshes), reserved...
    return ip.is_global


def check_url(url: str) -> None:
    """Raises BlockedAddress when `url` names (or resolves to) an address
    outside the public internet. Does nothing where public_only() is off."""
    if not public_only():
        return
    parts = urllib.parse.urlsplit(url.strip())
    host = parts.hostname
    if parts.scheme not in ("http", "https") or not host:
        raise BlockedAddress(url)
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise BlockedAddress(f"{host}: {exc}") from exc
    if not infos or not all(_is_public(info[4][0]) for info in infos):
        raise BlockedAddress(host)


def _check_peer(sock) -> None:
    if public_only() and not _is_public(sock.getpeername()[0]):
        sock.close()
        raise BlockedAddress("private address")


class _HTTPConnection(http.client.HTTPConnection):
    def connect(self):
        super().connect()
        _check_peer(self.sock)


class _HTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        super().connect()
        _check_peer(self.sock)


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_HTTPConnection, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_HTTPSConnection, req)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # urllib then raises the 3xx as an HTTPError


_opener = urllib.request.build_opener(_HTTPHandler, _HTTPSHandler, _NoRedirect)


def urlopen(req, timeout: float):
    """urllib.request.urlopen for an address that came from the settings."""
    return _opener.open(req, timeout=timeout)
