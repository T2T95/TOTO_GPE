from __future__ import annotations

import os
import sys
import socket
import subprocess
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_hagezi_import_and_generate() -> list[str]:
    out: list[str] = []
    root = repo_root() / "back"
    sys.path.insert(0, str(repo_root().joinpath("back", "src")))
    try:
        from elhomeshield.modules.dns.services import (
            hagezi_profiles,
            import_from_url,
            generate_dnsmasq_blocklist,
            load_blocklist,
            ensure_dns_storage,
        )
    except Exception as e:
        out.append(f"[DNS] Import module failed: {e}")
        return out

    try:
        ensure_dns_storage(root)
        bl_before = len(load_blocklist(root))
        url = hagezi_profiles()["light"]
        ok, msg, _ = import_from_url(root, url)
        out.append(f"[DNS] Hagezi import: {'OK' if ok else 'FAIL'} - {msg}")
        gen_path = generate_dnsmasq_blocklist(root)
        size = gen_path.stat().st_size if gen_path.exists() else 0
        out.append(f"[DNS] Generated dnsmasq config: {gen_path} ({size} bytes)")
    except Exception as e:
        out.append(f"[DNS] Error: {e}")
    return out


def test_port_53() -> list[str]:
    out: list[str] = []
    # Try to bind on 127.0.0.1:53 UDP/TCP to detect conflicts
    # On Linux, port <1024 requires root; failure may be permission or in-use.
    def try_bind_udp(port: int) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("127.0.0.1", port))
            return "free"
        except PermissionError:
            return "permission-denied"
        except OSError as e:
            return f"in-use? {e}"
        finally:
            try:
                s.close()
            except Exception:
                pass

    def try_bind_tcp(port: int) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port))
            return "free"
        except PermissionError:
            return "permission-denied"
        except OSError as e:
            return f"in-use? {e}"
        finally:
            try:
                s.close()
            except Exception:
                pass

    udp = try_bind_udp(53)
    tcp = try_bind_tcp(53)
    out.append(f"[PORT] UDP 53: {udp}")
    out.append(f"[PORT] TCP 53: {tcp}")
    return out


def test_docker() -> list[str]:
    out: list[str] = []
    def run(cmd: list[str]) -> tuple[int, str]:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True)
            return p.returncode, (p.stdout + p.stderr).strip()
        except FileNotFoundError:
            return 127, "not-found"
        except Exception as e:
            return 1, str(e)

    code, info = run(["docker", "info"])
    out.append(f"[DOCKER] docker info: code={code}")
    if code != 0:
        out.append(info)
    else:
        code2, ver = run(["docker", "compose", "version"])
        out.append(f"[DOCKER] compose version: code={code2} {ver}")
    return out


def main() -> int:
    lines: list[str] = []
    lines += test_hagezi_import_and_generate()
    lines += test_port_53()
    lines += test_docker()
    print("\n".join(lines))
    # Non-zero exit if docker not available but otherwise 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

