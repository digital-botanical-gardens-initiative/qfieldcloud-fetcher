#!/usr/bin/env python3
import os, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from qfieldcloud_sdk import sdk  # type: ignore[import-untyped]

def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json_atomic(obj, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    tmp.replace(p)

def main():
    load_dotenv()
    instance = os.getenv("QFIELDCLOUD_INSTANCE")
    username = os.getenv("QFIELDCLOUD_USERNAME")
    password = os.getenv("QFIELDCLOUD_PASSWORD")
    data_path = os.getenv("DATA_PATH")
    nextcloud_root = os.getenv("NEXTCLOUD_FOLDER")
    if not all([instance, username, password, data_path, nextcloud_root]):
        raise SystemExit("Missing env vars: QFIELDCLOUD_INSTANCE, QFIELDCLOUD_USERNAME, QFIELDCLOUD_PASSWORD, DATA_PATH, NEXTCLOUD_FOLDER")

    manifest_path = os.path.join(data_path, "pending_remote_deletes.json")
    processed_ok_path = os.path.join(data_path, "processed_ok.json")

    manifest = load_json(manifest_path, [])
    processed_ok = load_json(processed_ok_path, {})

    client = sdk.Client(url=f"{instance}/api/v1/")
    token = client.login(username=username, password=password).get("token")
    if not token:
        raise SystemExit("Error: Could not authenticate with the server")

    keep = []
    deleted_remote = removed_raw = kept = 0

    for e in manifest:
        proj_id = e.get("project_id")
        proj_name = e.get("project_name")
        remote_name = e.get("remote_name")  # DCIM/layer/IMG_123.jpg

        try:
            after = remote_name.split("DCIM/", 1)[1]
            layer, original = after.split("/", 1)
        except Exception:
            layer, original = ("unknown", "unknown")

        # Conditions to allow cleanup:
        # 1) processed_ok says this original is fully processed
        key = f"{proj_name}/{layer}/{original}"
        is_processed = bool(processed_ok.get(key))

        # 2) raw copy exists (we will remove it now)
        raw_path = Path(nextcloud_root) / "pictures_raw" / proj_name / layer / original
        raw_exists = raw_path.exists()

        if is_processed and raw_exists:
            try:
                client.delete_files(project_id=proj_id, glob_patterns=[remote_name])
                deleted_remote += 1
            except Exception as ex:
                print(f"Warning: remote delete failed for {remote_name} in project {proj_id}: {ex}")
                keep.append(e); kept += 1; continue

            try:
                raw_path.unlink(missing_ok=True)
                removed_raw += 1
            except Exception as ex:
                print(f"Warning: couldn't remove raw {raw_path}: {ex}")

        else:
            keep.append(e); kept += 1

    save_json_atomic(keep, manifest_path)
    print(f"Finalize: remote_deleted={deleted_remote}, raw_removed={removed_raw}, still_pending={kept}")
    ts_path = os.path.join(data_path, ".last_finalize")
    with open(ts_path, "w", encoding="utf-8") as f:
        f.write(datetime.utcnow().isoformat()+"Z")
    print(f"Wrote: {ts_path}")

if __name__ == "__main__":
    main()
