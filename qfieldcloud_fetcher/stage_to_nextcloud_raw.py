#!/usr/bin/env python3
import os
import json
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

def md5sum(path, chunk=4*1024*1024):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

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
    data_path = os.getenv("DATA_PATH")
    nextcloud_root = os.getenv("NEXTCLOUD_FOLDER")
    if not data_path or not nextcloud_root:
        raise SystemExit("Missing env vars DATA_PATH or NEXTCLOUD_FOLDER")

    in_jpg_path = os.path.join(data_path, "in", "pictures")
    raw_root = os.path.join(nextcloud_root, "pictures_raw")
    manifest_path = os.path.join(data_path, "pending_remote_deletes.json")  # from fetcher
    stage_log_path = os.path.join(data_path, "pictures_stage_log.json")

    manifest = load_json(manifest_path, [])
    stage_log = load_json(stage_log_path, {})

    # map local_path -> manifest entry (to attach remote_name/project_id)
    local_to_remote = {os.path.abspath(e.get("local_path","")): e for e in manifest if e.get("local_path")}

    copied = skipped = errors = 0
    for file in Path(in_jpg_path).rglob("*.jpg"):
        file = file.resolve()
        try:
            layer = file.parent.name
            project = file.parent.parent.name
        except Exception:
            layer, project = "unknown", "unknown"

        rel = f"{project}/{layer}/{file.name}"
        dest = Path(raw_root)/project/layer/file.name
        dest.parent.mkdir(parents=True, exist_ok=True)

        # skip if same size exists; still record
        if dest.exists() and dest.stat().st_size == file.stat().st_size:
            skipped += 1
            entry = stage_log.get(rel) or {}
            entry.update({
                "project": project, "layer": layer,
                "local_path": str(file), "raw_path": str(dest),
                "raw_md5": entry.get("raw_md5") or md5sum(dest),
                "staged_at": entry.get("staged_at") or datetime.utcnow().isoformat()+"Z",
                "remote_name": local_to_remote.get(str(file), {}).get("remote_name"),
                "project_id": local_to_remote.get(str(file), {}).get("project_id"),
            })
            stage_log[rel] = entry
            continue

        try:
            shutil.copy2(str(file), str(dest))
            if md5sum(file) != md5sum(dest):
                raise IOError("MD5 mismatch")
            copied += 1
            stage_log[rel] = {
                "project": project, "layer": layer,
                "local_path": str(file), "raw_path": str(dest),
                "raw_md5": md5sum(dest),
                "staged_at": datetime.utcnow().isoformat()+"Z",
                "remote_name": local_to_remote.get(str(file), {}).get("remote_name"),
                "project_id": local_to_remote.get(str(file), {}).get("project_id"),
            }
        except Exception as e:
            print(f"Error copying {file} -> {dest}: {e}")
            errors += 1

    save_json_atomic(stage_log, stage_log_path)
    print(f"Staging complete: copied={copied}, skipped={skipped}, errors={errors}")
    print(f"Raw stage log: {stage_log_path}")

if __name__ == "__main__":
    main()
