#!/usr/bin/env python3
"""Sync BatteryPass models from batterypass/BatteryPassDataModel into this fork.

For each discovered model and version:
  1. Downloads the .ttl source file, saved as {ModelName}.ttl (correctly named).
  2. Relies on generate.sh (called from the workflow) to produce gen/ artifacts.
     Because the TTL is saved with the right name, generate.sh outputs files as
     {ModelName}-schema.json, {ModelName}.json, etc. — matching our convention.
  3. Creates metadata.json with {"status": "release"} if not already present.

Run from the root of the sldt-semantic-models repository:
    GITHUB_TOKEN=<pat> python .github/scripts/sync_battery_pass.py

The workflow calls generate.sh on each written TTL file after this script exits.
"""

import base64
import hashlib
import os
import re
import sys
from pathlib import Path

import requests

BATTERY_PASS_REPO = "batterypass/BatteryPassDataModel"
BATTERY_PASS_BASE = "BatteryPass"
API_BASE = "https://api.github.com"
METADATA_CONTENT = '{ "status" : "release" }\n'


def get_session() -> requests.Session:
    session = requests.Session()
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["X-GitHub-Api-Version"] = "2022-11-28"
    return session


def _get_with_retry(session: requests.Session, url: str) -> requests.Response:
    """GET with automatic retry on rate-limit (HTTP 403/429)."""
    import time

    for attempt in range(5):
        resp = session.get(url)
        if resp.status_code in (403, 429):
            reset_at = int(resp.headers.get("x-ratelimit-reset", 0))
            wait = max(reset_at - int(time.time()), 1) if reset_at else 2 ** attempt
            print(f"  Rate-limited. Waiting {wait}s before retry {attempt + 1}/5 ...")
            time.sleep(wait)
            continue
        return resp
    resp.raise_for_status()
    return resp


def list_contents(session: requests.Session, path: str) -> list:
    url = f"{API_BASE}/repos/{BATTERY_PASS_REPO}/contents/{path}"
    resp = _get_with_retry(session, url)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


def download_file(session: requests.Session, path: str) -> bytes | None:
    url = f"{API_BASE}/repos/{BATTERY_PASS_REPO}/contents/{path}"
    resp = _get_with_retry(session, url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"])
    return None


def to_snake_case(name: str) -> str:
    """Convert PascalCase to snake_case. E.g. CarbonFootprint -> carbon_footprint."""
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


def file_changed(path: Path, content: bytes) -> bool:
    if not path.exists():
        return True
    return hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(content).digest()


def sync_version(
    session: requests.Session,
    bp_model_path: str,
    model_name: str,
    our_dir: Path,
    version: str,
    changed_ttls: list,
) -> None:
    """Download the TTL for one (model, version) and write it as {ModelName}.ttl.

    Appends the written TTL path to changed_ttls so the workflow can run
    generate.sh on it.  Creates metadata.json if absent.
    """
    version_path = f"{bp_model_path}/{version}"

    version_contents = list_contents(session, version_path)
    ttl_files = [
        e for e in version_contents
        if e["type"] == "file" and e["name"].endswith(".ttl")
    ]
    if not ttl_files:
        print(f"  [{model_name} {version}] SKIP — no .ttl file found")
        return

    source_ttl_name = ttl_files[0]["name"]
    print(f"  [{model_name} {version}] source TTL: {source_ttl_name}")

    ttl_content = download_file(session, f"{version_path}/{source_ttl_name}")
    if ttl_content is None:
        print(f"  [{model_name} {version}] SKIP — could not download TTL")
        return

    our_version_dir = our_dir / version
    our_version_dir.mkdir(parents=True, exist_ok=True)

    ttl_path = our_version_dir / f"{model_name}.ttl"
    if file_changed(ttl_path, ttl_content):
        ttl_path.write_bytes(ttl_content)
        print(f"  [{model_name} {version}] wrote {ttl_path.relative_to(Path.cwd())}")
        changed_ttls.append(str(ttl_path.relative_to(Path.cwd())))
    else:
        print(f"  [{model_name} {version}] unchanged {ttl_path.name}")

    metadata_path = our_version_dir / "metadata.json"
    if not metadata_path.exists():
        metadata_path.write_text(METADATA_CONTENT, encoding="utf-8")
        print(f"  [{model_name} {version}] created metadata.json")


def main() -> None:
    session = get_session()
    repo_root = Path.cwd()
    changed_ttls: list = []

    print(f"Discovering models in {BATTERY_PASS_REPO}/{BATTERY_PASS_BASE}/ ...\n")
    base_contents = list_contents(session, BATTERY_PASS_BASE)

    model_dirs = sorted(
        (e for e in base_contents if e["type"] == "dir" and e["name"].startswith("io.BatteryPass.")),
        key=lambda e: e["name"],
    )

    if not model_dirs:
        print("ERROR: No io.BatteryPass.* folders found. Check repo path and token.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(model_dirs)} model folder(s):")
    for e in model_dirs:
        print(f"  {e['name']}")
    print()

    for entry in model_dirs:
        bp_folder = entry["name"]                            # io.BatteryPass.CarbonFootprint
        model_name = bp_folder.rsplit(".", 1)[-1]            # CarbonFootprint
        our_dir_name = f"io.batterypass.{to_snake_case(model_name)}"  # io.batterypass.carbon_footprint
        our_dir = repo_root / our_dir_name
        bp_model_path = f"{BATTERY_PASS_BASE}/{bp_folder}"

        print(f"=== {model_name}  ->  {our_dir_name}")

        version_entries = list_contents(session, bp_model_path)
        versions = sorted(
            e["name"] for e in version_entries
            if e["type"] == "dir" and re.match(r"^\d+\.\d+", e["name"])
        )

        if not versions:
            print("  No version folders found — skipping\n")
            continue

        print(f"  Versions: {versions}")
        for version in versions:
            sync_version(session, bp_model_path, model_name, our_dir, version, changed_ttls)
        print()

    # Write the list of changed TTL paths to a file so the workflow can
    # iterate over them and call generate.sh on each one.
    changed_ttls_file = repo_root / ".battery_pass_changed_ttls"
    changed_ttls_file.write_text("\n".join(changed_ttls) + ("\n" if changed_ttls else ""), encoding="utf-8")

    print(f"Done. {len(changed_ttls)} TTL file(s) new/updated.")
    if changed_ttls:
        print("Changed TTLs:")
        for p in changed_ttls:
            print(f"  {p}")
    else:
        print("Nothing changed.")


if __name__ == "__main__":
    main()
