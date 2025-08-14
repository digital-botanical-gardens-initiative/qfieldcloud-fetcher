#!/usr/bin/env python3
import os
import sys
import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=6,
        connect=6,
        read=6,
        backoff_factor=1.2,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST", "PATCH"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=50)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def api_get(session: requests.Session, url: str, params: Optional[dict] = None) -> dict:
    r = session.get(url, params=params, timeout=(10, 60))
    if r.status_code != 200:
        raise RuntimeError(f"GET {url} failed: {r.status_code} {r.text[:500]}")
    return r.json()


def api_patch(session: requests.Session, url: str, json_body: Any) -> dict:
    r = session.patch(url, json=json_body, timeout=(10, 120))
    if r.status_code not in (200, 204):
        raise RuntimeError(f"PATCH {url} failed: {r.status_code} {r.text[:500]}")
    return r.json() if r.text else {}


def chunked(seq: List[Any], n: int) -> List[List[Any]]:
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def main(argv: List[str]) -> int:
    # --- very small argparse (no dependency) ---
    import argparse
    parser = argparse.ArgumentParser(
        description="Link Dried_Samples_Data.field_data to Field_Data using container/sample codes."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview updates without applying them.")
    parser.add_argument("--summary-file", default=None, help="Path to write a JSON summary.")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for API updates and lookups.")
    args = parser.parse_args(argv)

    load_dotenv()

    base = os.getenv("DIRECTUS_INSTANCE")  # e.g. https://emi-collection.unifr.ch/directus
    email = os.getenv("DIRECTUS_USERNAME")
    password = os.getenv("DIRECTUS_PASSWORD")
    data_path = os.getenv("DATA_PATH", ".")

    if not base or not email or not password:
        print("Missing DIRECTUS_* env vars", file=sys.stderr)
        return 1

    summary_path = args.summary_file or os.path.join(data_path, "last_directus_link_summary.json")

    items = f"{base}/items"
    login = f"{base}/auth/login"

    session = make_session()

    # --- login ---
    r = session.post(login, json={"email": email, "password": password}, timeout=(10, 30))
    if r.status_code != 200:
        print(f"Connection to Directus failed: {r.status_code} {r.text[:300]}", file=sys.stderr)
        _write_summary(summary_path, {
            "ok": False, "error": f"login_failed:{r.status_code}", "dry_run": args.dry_run
        })
        return 1

    token = r.json()["data"]["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    print("Connection to Directus successful")

    # --- 1) Get only dried rows needing linking (field_data is null) ---
    dried_url = f"{items}/Dried_Samples_Data"
    dried_params = {
        "filter[field_data][_null]": "true",
        # expand the related container to get its id and container_id in one query
        "fields": "id,sample_container.id,sample_container.container_id",
        "limit": -1,
    }
    dried_rows = api_get(session, dried_url, params=dried_params).get("data", [])

    pending_total = len(dried_rows)
    if pending_total == 0:
        print("Nothing to link: no Dried_Samples_Data with field_data == null")
        _write_summary(summary_path, {
            "ok": True,
            "dry_run": args.dry_run,
            "pending": 0,
            "prepared_updates": 0,
            "applied_updates": 0,
            "skipped_obs": 0,
            "unmatched": 0,
        })
        return 0

    # Build target list
    sample_codes: List[str] = []
    dried_targets: List[Tuple[int, str]] = []  # (dried_id, sample_code)
    skipped_obs = 0

    for row in dried_rows:
        dried_id = row.get("id")
        container = row.get("sample_container") or {}
        sample_code = container.get("container_id")
        if not dried_id or not sample_code:
            continue
        if isinstance(sample_code, str) and sample_code.startswith("obs_"):
            skipped_obs += 1
            continue
        sample_codes.append(str(sample_code))
        dried_targets.append((int(dried_id), str(sample_code)))

    if not dried_targets:
        print("Nothing to link after filtering (e.g., only obs_* present).")
        _write_summary(summary_path, {
            "ok": True,
            "dry_run": args.dry_run,
            "pending": pending_total,
            "prepared_updates": 0,
            "applied_updates": 0,
            "skipped_obs": skipped_obs,
            "unmatched": 0,
        })
        return 0

    # --- 2) Resolve Field_Data IDs for those sample_ids (batched) ---
    field_map: Dict[str, int] = {}
    field_url = f"{items}/Field_Data"
    unique_codes = sorted(set(sample_codes))

    for batch in chunked(unique_codes, args.batch_size):
        params = {
            "filter[sample_id][_in]": ",".join(batch),
            "fields": "id,sample_id",
            "limit": -1,
        }
        data = api_get(session, field_url, params=params).get("data", [])
        for rec in data:
            sid = rec.get("sample_id")
            fid = rec.get("id")
            if sid is not None and fid is not None:
                field_map[str(sid)] = int(fid)

    # --- 3) Build updates for dried rows with a matching Field_Data ID ---
    updates = []
    unmatched = 0
    for dried_id, code in dried_targets:
        fid = field_map.get(code)
        if fid is not None:
            updates.append({"id": dried_id, "field_data": fid})
        else:
            unmatched += 1

    prepared = len(updates)

    if prepared == 0:
        print("No updates to apply (no matches found).")
        _write_summary(summary_path, {
            "ok": True,
            "dry_run": args.dry_run,
            "pending": pending_total,
            "prepared_updates": 0,
            "applied_updates": 0,
            "skipped_obs": skipped_obs,
            "unmatched": unmatched,
        })
        return 0

    if args.dry_run:
        print(f"DRY RUN: would update {prepared} Dried_Samples_Data records.")
        _write_summary(summary_path, {
            "ok": True,
            "dry_run": True,
            "pending": pending_total,
            "prepared_updates": prepared,
            "applied_updates": 0,
            "skipped_obs": skipped_obs,
            "unmatched": unmatched,
            # optional: list a small sample of planned updates
            "example_updates": updates[:5],
        })
        return 0

    # --- 4) Apply in batches ---
    applied = 0
    for batch in chunked(updates, args.batch_size):
        api_patch(session, dried_url, json_body=batch)
        applied += len(batch)

    print(f"Linking finished — updated {applied} Dried_Samples_Data records.")
    _write_summary(summary_path, {
        "ok": True,
        "dry_run": False,
        "pending": pending_total,
        "prepared_updates": prepared,
        "applied_updates": applied,
        "skipped_obs": skipped_obs,
        "unmatched": unmatched,
    })
    return 0


def _write_summary(path: str, obj: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
