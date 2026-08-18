#!/usr/bin/env python3
"""Export TLS-inspection CAs from the live pypi.org chain (and macOS keychain).

Writes PEM files into certs/ so the Docker image can trust Netskope/Zscaler/etc.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERTS = ROOT / "certs"


def _split_pems(text: str) -> list[str]:
    out: list[str] = []
    for chunk in text.split("-----BEGIN CERTIFICATE-----")[1:]:
        body = chunk.split("-----END CERTIFICATE-----")[0]
        out.append(
            "-----BEGIN CERTIFICATE-----" + body + "-----END CERTIFICATE-----\n"
        )
    return out


def _openssl_meta(pem: str) -> str:
    proc = subprocess.run(
        ["openssl", "x509", "-noout", "-subject", "-issuer", "-dates"],
        input=pem,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else ""


def _is_leaf(info: str) -> bool:
    compact = info.replace(" ", "")
    return "CN=pypi.org" in compact or "CN = pypi.org" in info


def _safe_cn(info: str) -> str:
    for line in info.splitlines():
        if "subject=" not in line.lower() and not line.lower().startswith("subject"):
            continue
        token = "CN"
        if token not in line:
            continue
        cn = line.split("CN", 1)[1].lstrip("= /").split(",")[0].split("/")[0].strip()
        if cn:
            return "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in cn)[:80]
    return "ca"


def _run(cmd: list[str] | str, shell: bool = False) -> str:
    try:
        return subprocess.check_output(cmd, shell=shell, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main() -> int:
    CERTS.mkdir(exist_ok=True)
    chain = _run(
        "echo | openssl s_client -showcerts -connect pypi.org:443 -servername pypi.org 2>/dev/null",
        shell=True,
    )
    if "BEGIN CERTIFICATE" not in chain:
        print("could not fetch pypi.org certificate chain", file=sys.stderr)
        return 1

    keychain = ""
    for name in ("goskope", "Netskope", "Zscaler", "ns-swg"):
        keychain += _run(["security", "find-certificate", "-a", "-p", "-c", name])

    seen: set[str] = set()
    written = 0
    for pem in _split_pems(chain) + _split_pems(keychain):
        info = _openssl_meta(pem)
        if not info or _is_leaf(info):
            continue
        digest = hashlib.sha256(pem.encode()).hexdigest()[:12]
        if digest in seen:
            continue
        seen.add(digest)
        dest = CERTS / f"{_safe_cn(info)}-{digest}.crt"
        dest.write_text(pem)
        written += 1
        print(f"wrote {dest.relative_to(ROOT)}")
        print(f"  {info.strip().replace(chr(10), ' | ')}")

    if written == 0:
        print("no extra CAs found (pypi.org is not being intercepted?)", file=sys.stderr)
        return 1
    print(f"\n{written} CA file(s) in certs/. Rebuild: docker compose up --build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
