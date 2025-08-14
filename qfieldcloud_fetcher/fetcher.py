#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from qfieldcloud_sdk import sdk  # type: ignore[import-untyped]

# ---------------------------
# CLI & state
# ---------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Fetch QFieldCloud projects. In incremental mode, if any GPKG changes in a project, re-download the whole project. Always starts with a fresh local dir."
    )
    p.add_argument(
        "--mode",
        choices=["incremental", "all"],
        default="incremental",
        help="Download mode: 'incremental' (default) or 'all'.",
    )
    p.add_argument(
        "--state-file",
        default=None,
        help="Path to JSON state file (defaults to DATA_PATH/state.json).",
    )
    return p.parse_args()

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_state(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {"last_pull": None, "files": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: Dict[str, Any], path: str) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

# ---------------------------
# HTTP session & downloader
# ---------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=6,
        connect=6,
        read=6,
        backoff_factor=1.2,
        status_forcelist=(502, 503, 504, 522, 524),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

SESSION = make_session()

def file_md5(path: str, chunk_size: int = 4 * 1024 * 1024) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def download_with_retries(
    url: str, dest_path: str, auth_header: str, expected_md5: Optional[str], max_attempts: int = 6
) -> bool:
    """
    Robust, resumable downloader:
    - Writes to dest_path+'.part'
    - Attempts resume with Range if partial exists
    - Retries on network/stream errors
    - Verifies MD5 at the end (if provided)
    """
    headers_base = {"Authorization": auth_header, "Accept": "*/*"}
    tmp_path = dest_path + ".part"

    for attempt in range(1, max_attempts + 1):
        try:
            resume_from = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
            tried_fresh = False

            while True:
                headers = dict(headers_base)
                if resume_from > 0:
                    headers["Range"] = f"bytes={resume_from}-"

                safe_url = requests.utils.requote_uri(url)
                with SESSION.get(safe_url, headers=headers, stream=True, timeout=(15, 120)) as r:
                    if resume_from > 0 and r.status_code == 200:
                        r.close()
                        with suppress(Exception):
                            os.remove(tmp_path)
                        resume_from = 0
                        if tried_fresh:
                            raise IOError("Server ignored Range resume twice")
                        tried_fresh = True
                        continue

                    if r.status_code not in (200, 206):
                        if r.status_code in (502, 503, 504, 522, 524):
                            raise IOError(f"Transient HTTP {r.status_code} for {url}")
                        raise IOError(f"HTTP {r.status_code} for {url}")

                    mode = "ab" if (resume_from > 0 and r.status_code == 206) else "wb"
                    with open(tmp_path, mode) as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                # ✅ finished streaming this attempt
                break

            if expected_md5:
                local_md5 = file_md5(tmp_path).lower()
                if local_md5 != expected_md5.lower():
                    raise IOError(f"MD5 mismatch: got {local_md5}, expected {expected_md5}")

            os.replace(tmp_path, dest_path)
            print(f"Downloaded {url}")
            return True

        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError,
                IOError) as e:
            if attempt >= max_attempts:
                print(f"ERROR: {e} (giving up) for {url}")
                with suppress(Exception):
                    os.remove(tmp_path)
                return False
            sleep = min(30, 1.2 ** attempt)
            print(f"Warn: {e} — retry {attempt}/{max_attempts} in {sleep:.1f}s for {url}")
            time.sleep(sleep)
    return False

# ---------------------------
# QFieldCloud helpers
# ---------------------------
def extract_md5_and_version(file_entry: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Prefer MD5/version_id from the 'versions' list where is_latest == true.
    Fallback to top-level md5sum/version_id if versions are absent.
    """
    versions = file_entry.get("versions") or []
    latest = next((v for v in versions if v.get("is_latest")), None)
    if latest:
        return latest.get("md5sum"), latest.get("version_id")
    return file_entry.get("md5sum"), file_entry.get("version_id")

def url_project_id(file_url: str) -> Optional[str]:
    try:
        parts = file_url.split("/api/v1/files/", 1)[1].split("/", 1)
        return parts[0]
    except Exception:
        return None

# ---------------------------
# Main logic
# ---------------------------
def main():
    args = parse_args()

    load_dotenv()
    instance = os.getenv("QFIELDCLOUD_INSTANCE")
    username = os.getenv("QFIELDCLOUD_USERNAME")
    password = os.getenv("QFIELDCLOUD_PASSWORD")
    data_path = os.getenv("DATA_PATH")

    if not all([instance, username, password, data_path]):
        raise SystemExit("Missing env vars: QFIELDCLOUD_INSTANCE, QFIELDCLOUD_USERNAME, QFIELDCLOUD_PASSWORD, DATA_PATH")

    api_base = f"{instance}/api/v1/"
    files_base = f"{instance}/api/v1/files/"
    in_gpkg_path = os.path.join(data_path, "in", "gpkg")
    in_jpg_path  = os.path.join(data_path, "in", "pictures")

    # ✳️ marker & summary
    marker_path  = os.path.join(data_path, ".qfc_changed")
    summary_path = os.path.join(data_path, "last_fetch_summary.json")

    state_path = args.state_file or os.path.join(data_path, "state.json")
    state = load_state(state_path)
    state_files: Dict[str, Dict[str, Any]] = state.get("files", {})

    # Connect
    client = sdk.Client(url=f"{api_base}")
    credentials = client.login(username=username, password=password)
    auth_token = credentials.get("token")
    if not auth_token:
        raise SystemExit("Error: Could not authenticate with the server")
    auth_header = f"Token {auth_token}"

    projects = client.list_projects()
    proj_id_to_name = {p["id"]: p["name"] for p in projects}

    # Build maps
    gpkg_urls_by_project: Dict[str, list[str]] = {}
    gpkg_md5_by_url: Dict[str, str] = {}
    jpg_urls_by_project: Dict[str, Dict[str, list[str]]] = {}
    meta_by_url: Dict[str, Dict[str, Any]] = {}

    for project in projects:
        proj_id = project["id"]
        project_files = client.list_remote_files(project_id=proj_id)

        gpkg_urls: list[str] = []
        for f in project_files:
            fname = f.get("name", "")
            if fname.endswith(".gpkg") and "map" not in fname:
                file_url = f"{files_base}{proj_id}/{fname}"
                md5, vid = extract_md5_and_version(f)
                if md5:
                    gpkg_md5_by_url[file_url] = md5
                gpkg_urls.append(file_url)
                meta_by_url[file_url] = {"md5": md5, "version_id": vid, "size": f.get("size"), "name": fname}
        gpkg_urls_by_project[proj_id] = gpkg_urls

        by_layer: Dict[str, list[str]] = {}
        for f in project_files:
            fname = f.get("name", "")
            if fname.endswith(".jpg"):
                file_url = f"{files_base}{proj_id}/{fname}"
                if "/DCIM/" in file_url:
                    after_dcim = file_url.split("/DCIM/", 1)[1]
                    layer_name = after_dcim.split("/", 1)[0]
                else:
                    layer_name = "unknown"
                by_layer.setdefault(layer_name, []).append(file_url)
                md5, vid = extract_md5_and_version(f)
                meta_by_url[file_url] = {"md5": md5, "version_id": vid, "size": f.get("size"), "name": fname}
        jpg_urls_by_project[proj_id] = by_layer

    # Detect changed projects (compare GPKGs only)
    prev_gpkg_by_project: Dict[str, Dict[str, str]] = {}
    for url, info in state_files.items():
        if not url.endswith(".gpkg"):
            continue
        pid = url_project_id(url)
        if not pid:
            continue
        prev_gpkg_by_project.setdefault(pid, {})[url] = (info.get("md5") or "")

    changed_projects: set[str] = set()
    for pid, urls in gpkg_urls_by_project.items():
        current = {u: gpkg_md5_by_url.get(u, "") for u in urls}
        prev = prev_gpkg_by_project.get(pid, {})
        if set(current.keys()) != set(prev.keys()):
            changed_projects.add(pid)
            continue
        for u, md5 in current.items():
            if not md5 or prev.get(u, "") != md5:
                changed_projects.add(pid)
                break

    if args.mode == "all":
        projects_to_fetch = list(gpkg_urls_by_project.keys())
    else:
        if not state_files:  # first run
            projects_to_fetch = list(gpkg_urls_by_project.keys())
        else:
            projects_to_fetch = list(changed_projects)

    # Always start with clean local
    for base in (in_gpkg_path, in_jpg_path):
        with suppress(FileNotFoundError):
            shutil.rmtree(base)
        os.makedirs(base, exist_ok=True)

    # No changes → fresh dirs, clear marker, update state snapshot, exit 0
    if not projects_to_fetch:
        print("No project changed. Local directories are empty (fresh start).")
        with suppress(FileNotFoundError):
            os.remove(marker_path)
        new_state_files: Dict[str, Dict[str, Any]] = {}
        for pid, urls in gpkg_urls_by_project.items():
            for u in urls:
                md5 = gpkg_md5_by_url.get(u)
                if md5:
                    new_state_files[u] = {"md5": md5}
        state["files"] = new_state_files
        state["last_pull"] = utcnow_iso()
        save_state(state, state_path)
        summary = {
            "mode": args.mode,
            "had_changes": False,
            "projects_selected": [],
            "downloaded_files": 0,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        return

    print("Projects to fetch:", ", ".join(f"{proj_id_to_name[pid]}({pid})" for pid in projects_to_fetch))

    # Download selected projects fully
    all_ok = True
    downloaded_files = 0
    new_state_files: Dict[str, Dict[str, Any]] = {}

    for pid in projects_to_fetch:
        pname = proj_id_to_name[pid]
        gpkg_dir = os.path.join(in_gpkg_path, pname)
        jpg_base = os.path.join(in_jpg_path, pname)
        os.makedirs(gpkg_dir, exist_ok=True)
        os.makedirs(jpg_base, exist_ok=True)

        # GPKGs
        for file_url in gpkg_urls_by_project.get(pid, []):
            filename = os.path.basename(file_url)
            dest = os.path.join(gpkg_dir, filename)
            remote_md5 = gpkg_md5_by_url.get(file_url)
            ok = download_with_retries(file_url, dest, f"Token {auth_token}", remote_md5)
            if ok:
                downloaded_files += 1
                new_state_files[file_url] = {"md5": (remote_md5 or file_md5(dest)), "downloaded_at": utcnow_iso()}
            else:
                all_ok = False

        # Prepare layer subdirs by GPKG stems (nice organization)
        stems = [os.path.splitext(os.path.basename(u))[0] for u in gpkg_urls_by_project.get(pid, [])]
        layer_dirs = {s: os.path.join(jpg_base, s) for s in stems}
        for d in layer_dirs.values():
            os.makedirs(d, exist_ok=True)

        # JPGs (download all), then delete on server
        for layer_name, urls in jpg_urls_by_project.get(pid, {}).items():
            save_dir = layer_dirs.get(layer_name) or os.path.join(jpg_base, layer_name)
            os.makedirs(save_dir, exist_ok=True)
            for file_url in urls:
                # local name
                if "/DCIM/" in file_url:
                    after_dcim = file_url.split("/DCIM/", 1)[1]
                    _dir_name, file_name = after_dcim.split("/", 1)
                else:
                    file_name = os.path.basename(file_url)
                dest = os.path.join(save_dir, file_name.replace("/", "_"))

                meta = meta_by_url.get(file_url, {})
                remote_md5 = meta.get("md5")
                ok = download_with_retries(file_url, dest, f"Token {auth_token}", remote_md5)
                if ok:
                    downloaded_files += 1
                    # delete on server
                    try:
                        # safer: use the exact name/path from metadata if present
                        name_in_project = meta.get("name") or os.path.join("DCIM", layer_name, file_name)
                        client.delete_files(project_id=pid, glob_patterns=[name_in_project])
                    except Exception as e:
                        print(f"Warning: couldn't delete remote {meta.get('name')} in project {pid}: {e}")
                else:
                    all_ok = False

    # Update state to current snapshot (GPKGs only)
    for pid, urls in gpkg_urls_by_project.items():
        for u in urls:
            md5 = gpkg_md5_by_url.get(u)
            if md5:
                new_state_files.setdefault(u, {"md5": md5})

    state["files"] = new_state_files
    state["last_pull"] = utcnow_iso()
    save_state(state, state_path)

    # Write summary + marker
    had_changes = bool(projects_to_fetch) and all_ok
    summary = {
        "mode": args.mode,
        "had_changes": had_changes,
        "projects_selected": [proj_id_to_name[p] for p in projects_to_fetch],
        "downloaded_files": downloaded_files,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if had_changes:
        with open(marker_path, "w", encoding="utf-8") as f:
            f.write("changed\n")
    else:
        with suppress(FileNotFoundError):
            os.remove(marker_path)

    if not all_ok:
        print("Some downloads failed — not triggering downstream pipeline.")
        sys.exit(1)

    print(f"Done. Mode={args.mode}. Refreshed projects: {', '.join(summary['projects_selected'])}")
    print(f"Summary: {summary_path}  Marker: {marker_path}")

if __name__ == "__main__":
    main()
