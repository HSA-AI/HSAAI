#!/usr/bin/env python3

import argparse
import base64
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


def docker(*args) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "keycloak", *args],
        capture_output=True,
        text=True,
    )

    if result.returncode:
        raise SystemExit(
            "STOP: Keycloak administration command failed"
        )

    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    run_id = os.environ.get("GITHUB_RUN_ID", "")

    if not run_id.isdigit():
        raise SystemExit("STOP: invalid GITHUB_RUN_ID")

    login = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "keycloak",
            "sh",
            "-ec",
            '/opt/keycloak/bin/kcadm.sh config credentials '
            '--server http://localhost:8080 '
            '--realm master '
            '--user "$KEYCLOAK_ADMIN" '
            '--password "$KEYCLOAK_ADMIN_PASSWORD" '
            ">/dev/null",
        ],
        capture_output=True,
        text=True,
    )

    if login.returncode:
        raise SystemExit(
            "STOP: Keycloak admin authentication failed"
        )

    clients = json.loads(
        docker(
            "/opt/keycloak/bin/kcadm.sh",
            "get",
            "clients",
            "-r",
            "hsaai",
            "-q",
            "clientId=hsaai-api",
        )
    )

    matches = [
        item
        for item in clients
        if item.get("clientId") == "hsaai-api"
    ]

    if len(matches) != 1:
        raise SystemExit(
            "STOP: hsaai-api client not found uniquely"
        )

    client = matches[0]

    if not client.get("serviceAccountsEnabled"):
        raise SystemExit(
            "STOP: hsaai-api service account is disabled"
        )

    client_id = client["id"]

    secret_data = json.loads(
        docker(
            "/opt/keycloak/bin/kcadm.sh",
            "get",
            f"clients/{client_id}/client-secret",
            "-r",
            "hsaai",
        )
    )

    secret = secret_data.get("value")

    if not secret:
        raise SystemExit("STOP: client secret unavailable")

    service_user = json.loads(
        docker(
            "/opt/keycloak/bin/kcadm.sh",
            "get",
            f"clients/{client_id}/service-account-user",
            "-r",
            "hsaai",
        )
    )

    user_id = service_user.get("id")

    if not user_id:
        raise SystemExit(
            "STOP: service account user unavailable"
        )

    benchmark_tenant = "ci-benchmark-tenant-" + run_id
    benchmark_workspace = "ci-benchmark-workspace-" + run_id

    attributes = dict(service_user.get("attributes") or {})

    attributes["tenant_id"] = [benchmark_tenant]
    attributes["workspace_id"] = [benchmark_workspace]

    update = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "keycloak",
            "/opt/keycloak/bin/kcadm.sh",
            "update",
            f"users/{user_id}",
            "-r",
            "hsaai",
            "-s",
            "attributes="
            + json.dumps(
                attributes,
                separators=(",", ":"),
            ),
        ],
        capture_output=True,
        text=True,
    )

    if update.returncode:
        raise SystemExit(
            "STOP: benchmark scope update failed"
        )

    endpoint = (
        "http://127.0.0.1:8080/realms/hsaai/"
        "protocol/openid-connect/token"
    )

    payload = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": "hsaai-api",
            "client_secret": secret,
        }
    ).encode()

    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:
        token_response = json.load(response)

    token = token_response.get("access_token")

    if not token:
        raise SystemExit("STOP: no access token issued")

    try:
        encoded = token.split(".")[1]
        encoded += "=" * (-len(encoded) % 4)
        claims = json.loads(
            base64.urlsafe_b64decode(encoded)
        )
    except Exception as exc:
        raise SystemExit(
            "STOP: invalid JWT structure"
        ) from exc

    if claims.get("tenant_id") != benchmark_tenant:
        raise SystemExit(
            "STOP: benchmark tenant claim mismatch"
        )

    if claims.get("workspace_id") != benchmark_workspace:
        raise SystemExit(
            "STOP: benchmark workspace claim mismatch"
        )

    if not isinstance(claims.get("exp"), (int, float)):
        raise SystemExit("STOP: JWT expiration missing")

    if claims["exp"] <= time.time():
        raise SystemExit("STOP: benchmark JWT already expired")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(token, encoding="utf-8")
    output.chmod(0o600)

    print("PASS: authenticated benchmark JWT issued")
    print("PASS: isolated benchmark tenant/workspace configured")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
