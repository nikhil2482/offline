"""Exit 0 only if this machine cannot reach the internet. Run inside the api container.

python -m offline.egress_check
"""

import socket
import sys

import httpx

_TARGETS = [("1.1.1.1", 443), ("8.8.8.8", 53)]


def reachable() -> list[str]:
    leaks = []
    for host, port in _TARGETS:
        try:
            with socket.create_connection((host, port), timeout=3):
                leaks.append(f"{host}:{port}")
        except OSError:
            pass
    try:
        httpx.get("https://pypi.org/simple/", timeout=5)
        leaks.append("https://pypi.org")
    except httpx.HTTPError:
        pass
    return leaks


def main() -> int:
    leaks = reachable()
    if leaks:
        print(f"FAIL: outbound connections succeeded to {', '.join(leaks)}")
        return 1
    print("PASS: no outbound network access")
    return 0


if __name__ == "__main__":
    sys.exit(main())
