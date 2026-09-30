#!/usr/bin/env python3

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "evals" / "fixtures"
OUTPUT = ROOT / "artifacts" / "ai-quality"


def jwt_claims(token: str) -> dict:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception as exc:
        raise SystemExit("STOP: invalid benchmark JWT structure") from exc


def multipart_body(path: Path):
    boundary = "----HSAAIBenchmark" + uuid.uuid4().hex

    chunks = []

    fields = {
        "visibility": "workspace",
        "classification": "internal",
        "tags": "benchmark,controlled,arabic",
    }

    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n'
                "\r\n"
                f"{value}\r\n"
            ).encode()
        )

    chunks.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; '
            f'filename="{path.name}"\r\n'
            "Content-Type: text/markdown; charset=utf-8\r\n"
            "\r\n"
        ).encode()
    )

    chunks.append(path.read_bytes())
    chunks.append(f"\r\n--{boundary}--\r\n".encode())

    return boundary, b"".join(chunks)


def upload(base_url: str, token: str, path: Path) -> dict:
    boundary, body = multipart_body(path)

    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/documents/upload",
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"{path.name}: unexpected HTTP {response.status}"
                )
            return json.load(response)

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:600]
        raise RuntimeError(
            f"{path.name}: upload HTTP {exc.code}: {body}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "RAG_BENCHMARK_BASE_URL",
            "http://127.0.0.1:8030",
        ),
    )
    args = parser.parse_args()

    token = os.getenv("RAG_BENCHMARK_TOKEN", "").strip()

    if not token:
        raise SystemExit("STOP: RAG_BENCHMARK_TOKEN is required")

    claims = jwt_claims(token)

    tenant = claims.get("tenant_id")
    workspace = claims.get("workspace_id")

    if not isinstance(tenant, str) or not tenant.strip():
        raise SystemExit("STOP: tenant_id claim missing")

    if not isinstance(workspace, str) or not workspace.strip():
        raise SystemExit("STOP: workspace_id claim missing")

    fixtures = sorted(FIXTURES.glob("*.md"))

    if len(fixtures) != 6:
        raise SystemExit(
            f"STOP: expected exactly 6 benchmark fixtures, found {len(fixtures)}"
        )

    results = []

    for path in fixtures:
        started = time.perf_counter()
        result = upload(args.base_url, token, path)
        elapsed_ms = (time.perf_counter() - started) * 1000

        if result.get("status") != "indexed":
            raise SystemExit(
                f"STOP: {path.name} was not confirmed indexed"
            )

        if result.get("filename") != path.name:
            raise SystemExit(
                f"STOP: filename mismatch for {path.name}"
            )

        if result.get("tenant_id") != tenant:
            raise SystemExit(
                f"STOP: tenant scope mismatch for {path.name}"
            )

        if result.get("workspace_id") != workspace:
            raise SystemExit(
                f"STOP: workspace scope mismatch for {path.name}"
            )

        chunks = int(result.get("chunks") or 0)

        if chunks < 1:
            raise SystemExit(
                f"STOP: no indexed chunks for {path.name}"
            )

        results.append(
            {
                "filename": path.name,
                "doc_id": result.get("doc_id"),
                "chunks": chunks,
                "status": result.get("status"),
                "elapsed_ms": round(elapsed_ms, 2),
            }
        )

        print(
            f"PASS: {path.name} indexed "
            f"({chunks} chunks)"
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)

    report = {
        "authenticated": True,
        "tenant": tenant,
        "workspace": workspace,
        "fixture_count": len(results),
        "documents": results,
    }

    (OUTPUT / "corpus_ingestion.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("PASS: controlled Arabic benchmark corpus indexed")
    print("PASS: benchmark corpus scope verified")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
