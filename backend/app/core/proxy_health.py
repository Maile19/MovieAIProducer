"""SOCKS5 Proxy Health and Handshake Diagnostic Utility.

Verifies live connectivity and RFC 1928 compliance of the Android SOCKS5 reverse tunnel.
Performs an active handshake (\\x05\\x01\\x00 -> \\x05\\x00) to ensure the Android SOCKS5
daemon is responsive, distinguishing an active tunnel from an empty or dangling local port.
Includes exact 2-byte read loop, deadlined timeouts, soft retries, and in-memory TTL caching.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Any
from urllib.parse import urlparse

DEFAULT_SOCKS5_URL = "socks5://127.0.0.1:10808"

# In-memory TTL cache for successful health checks to avoid tunnel port contention
_HEALTH_CACHE: dict[str, tuple[dict[str, Any], float]] = {}
_HEALTH_CACHE_LOCK = threading.Lock()


def parse_socks5_url(proxy_url: str | None) -> tuple[str, int]:
    """Parse socks5 proxy URL into host and port.

    Falls back to 127.0.0.1:10808 if proxy_url is empty, invalid, or legacy port 1080.
    """
    if not proxy_url or not proxy_url.strip():
        return ("127.0.0.1", 10808)

    clean_url = proxy_url.strip()
    if not clean_url.startswith(("socks5://", "socks5h://")):
        clean_url = f"socks5://{clean_url}"

    try:
        parsed = urlparse(clean_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 10808
        if port == 1080 and host in ("127.0.0.1", "localhost"):
            port = 10808
        return (host, port)
    except Exception:
        return ("127.0.0.1", 10808)


def recv_exact(sock: socket.socket, num_bytes: int, deadline: float) -> bytes:
    """Read exactly num_bytes from socket respecting the total socket deadline.

    Prevents partial-packet false-negatives over segmented mobile/KCP reverse tunnels.
    """
    buf = bytearray()
    while len(buf) < num_bytes:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise socket.timeout("Socket deadline reached while reading exact bytes")
        sock.settimeout(max(remaining, 0.05))
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


def check_socks5_health(
    proxy_url: str | None = None,
    timeout: float = 3.5,
    retries: int = 1,
    backoff: float = 0.3,
) -> dict[str, Any]:
    """Perform a live TCP connect AND RFC 1928 SOCKS5 handshake (\\x05\\x01\\x00 -> \\x05\\x00).

    Uses an exact 2-byte read loop and handles transient cellular tunnel jitter with 1 soft retry.
    """
    host, port = parse_socks5_url(proxy_url)
    effective_url = f"socks5://{host}:{port}"

    last_result: dict[str, Any] | None = None

    for attempt in range(retries + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        t0 = time.perf_counter()
        deadline = t0 + timeout

        try:
            s.connect((host, port))
            # SOCKS5 handshake request:
            # \x05: SOCKS version 5
            # \x01: 1 authentication method supported
            # \x00: Method 0 (No authentication required)
            s.sendall(b"\x05\x01\x00")

            resp = recv_exact(s, 2, deadline)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            if resp == b"\x05\x00":
                return {
                    "healthy": True,
                    "status": "online",
                    "host": host,
                    "port": port,
                    "proxy_url": effective_url,
                    "latency_ms": latency_ms,
                    "detail": f"SOCKS5 handshake berhasil ({latency_ms}ms). HP Android terhubung & responsive.",
                }
            else:
                resp_hex = resp.hex() if resp else "empty"
                last_result = {
                    "healthy": False,
                    "status": "offline",
                    "host": host,
                    "port": port,
                    "proxy_url": effective_url,
                    "latency_ms": latency_ms,
                    "detail": f"Handshake SOCKS5 gagal: respon server tidak valid ({resp_hex}).",
                }
        except ConnectionRefusedError:
            last_result = {
                "healthy": False,
                "status": "offline",
                "host": host,
                "port": port,
                "proxy_url": effective_url,
                "latency_ms": None,
                "detail": f"Koneksi ditolak pada {host}:{port}. Tunnel frps port {port} tertutup (aplikasi SOCKS5 HP Android kemungkinan mati).",
            }
        except socket.timeout:
            last_result = {
                "healthy": False,
                "status": "offline",
                "host": host,
                "port": port,
                "proxy_url": effective_url,
                "latency_ms": None,
                "detail": f"Timeout {timeout}s saat menghubungkan ke {host}:{port}. HP Android tidak merespons handshake.",
            }
        except Exception as e:
            last_result = {
                "healthy": False,
                "status": "offline",
                "host": host,
                "port": port,
                "proxy_url": effective_url,
                "latency_ms": None,
                "detail": f"Error koneksi SOCKS5: {e}",
            }
        finally:
            try:
                s.close()
            except Exception:
                pass

        if attempt < retries:
            time.sleep(backoff)

    return last_result or {
        "healthy": False,
        "status": "offline",
        "host": host,
        "port": port,
        "proxy_url": effective_url,
        "latency_ms": None,
        "detail": "Koneksi SOCKS5 gagal setelah percobaan ulang.",
    }


def get_cached_socks5_health(
    proxy_url: str | None = None,
    ttl_seconds: float = 5.0,
) -> dict[str, Any]:
    """Return cached healthy proxy status if within TTL, avoiding tunnel port contention during active renders."""
    host, port = parse_socks5_url(proxy_url)
    cache_key = f"{host}:{port}"
    now = time.monotonic()

    with _HEALTH_CACHE_LOCK:
        cached = _HEALTH_CACHE.get(cache_key)
        if cached:
            cached_result, cached_ts = cached
            if (now - cached_ts) < ttl_seconds and cached_result.get("healthy"):
                # Return fresh copy
                return dict(cached_result)

    result = check_socks5_health(proxy_url, timeout=3.5, retries=1, backoff=0.3)

    with _HEALTH_CACHE_LOCK:
        if result.get("healthy"):
            _HEALTH_CACHE[cache_key] = (result, now)
        else:
            _HEALTH_CACHE.pop(cache_key, None)

    return result
