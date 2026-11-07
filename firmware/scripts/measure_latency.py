"""Time scans from the Mac the way the board sends them: TLS 1.2, the same
request headers (including X-Bin-Token) and the board's 64 KB send buffer.

usage (from firmware/):
  BIN_TOKEN=<token> python3 scripts/measure_latency.py sim/photos/*.jpg
The server address comes from include/local_settings.h; --url overrides it.
SEND_BUFFER=5760 mimics the old Arduino-only build.
"""

import argparse
import os
import re
import socket
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

FIRMWARE = Path(__file__).resolve().parent.parent
SEND_BUFFER = int(os.environ.get("SEND_BUFFER", "65534"))


def firmware_value(pattern, path):
    if path.exists():
        match = re.search(pattern, path.read_text())
        if match:
            return match.group(1)
    return None


def open_connection(url):
    port = url.port or (443 if url.scheme == "https" else 80)
    t0 = time.perf_counter()
    address = socket.getaddrinfo(url.hostname, port, socket.AF_INET, socket.SOCK_STREAM)[0][4]
    t_dns = time.perf_counter()
    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUFFER)
    raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    raw.connect(address)
    t_tcp = time.perf_counter()
    conn = raw
    if url.scheme == "https":
        context = ssl.create_default_context()
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        conn = context.wrap_socket(raw, server_hostname=url.hostname)
    t_tls = time.perf_counter()
    return conn, (t_dns - t0, t_tcp - t_dns, t_tls - t_tcp)


def post(conn, url, token, version, body):
    host = url.hostname if url.port is None else f"{url.hostname}:{url.port}"
    head = (
        f"POST {url.path or '/'} HTTP/1.1\r\nHost: {host}\r\n"
        f"User-Agent: aware-bin/{version}\r\nX-Bin-Token: {token}\r\n"
        f"Content-Type: image/jpeg\r\nContent-Length: {len(body)}\r\n"
        "Connection: keep-alive\r\n\r\n"
    ).encode()
    t0 = time.perf_counter()
    conn.sendall(head + body)
    t_sent = time.perf_counter()
    reader = conn.makefile("rb")
    status_line = reader.readline()
    t_first = time.perf_counter()
    length = 0
    closes = False
    while True:
        line = reader.readline().strip().lower()
        if not line:
            break
        if line.startswith(b"content-length:"):
            length = int(line.split(b":")[1])
        if line.startswith(b"connection:") and b"close" in line:
            closes = True
    reply = reader.read(length)
    t_done = time.perf_counter()
    status = status_line.split()[1].decode() if status_line else "no reply"
    return status, reply, closes, (t_sent - t0, t_first - t_sent, t_done - t_first)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--url", help="server address (default: LOCAL_SERVER_URL in include/local_settings.h)")
    args = parser.parse_args()

    token = os.environ.get("BIN_TOKEN", "")
    if not token:
        sys.exit("Set BIN_TOKEN, for example: BIN_TOKEN=<token> python3 scripts/measure_latency.py ...")
    address = args.url or firmware_value(r'#define LOCAL_SERVER_URL "([^"]+)"', FIRMWARE / "include/local_settings.h")
    if not address:
        sys.exit("No server address: pass --url or set LOCAL_SERVER_URL in include/local_settings.h")
    url = urlparse(address)
    if url.scheme not in ("http", "https") or not url.hostname:
        sys.exit("The address must start with https:// or http://")
    version = firmware_value(r'#define FIRMWARE_VERSION "([^"]+)"', FIRMWARE / "include/config.h") or "unknown"

    photos = [p.read_bytes() for p in args.photos]
    print(f"send buffer {SEND_BUFFER} B, TLS 1.2, {len(photos)} photo(s)")
    failed = False
    for mode in ("new connection each time", "one kept-open connection"):
        print(f"== {mode}")
        conn = None
        for body in photos:
            connect = (0.0, 0.0, 0.0)
            if conn is None or mode.startswith("new"):
                if conn:
                    conn.close()
                conn, connect = open_connection(url)
            status, reply, closes, (send, wait, read) = post(conn, url, token, version, body)
            total = sum(connect) + send + wait + read
            print(
                f"{len(body) // 1024:4d} KB  dns {connect[0] * 1000:4.0f}  tcp {connect[1] * 1000:4.0f}  "
                f"tls {connect[2] * 1000:4.0f}  send {send * 1000:5.0f}  wait {wait * 1000:5.0f}  "
                f"read {read * 1000:3.0f}  total {total * 1000:5.0f} ms  [{status}] "
                f"{reply[:60].decode(errors='replace')}"
            )
            if status in ("401", "403"):
                sys.exit("The server refused the token: check BIN_TOKEN.")
            if status != "200":
                failed = True
            if closes:
                conn.close()
                conn = None
        if conn:
            conn.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
