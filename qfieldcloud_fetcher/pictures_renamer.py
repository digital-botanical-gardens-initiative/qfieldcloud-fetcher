#!/usr/bin/env python3

import os
import re
import shutil
import json
from pathlib import Path

from dotenv import load_dotenv

def _load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def _save_json_atomic(obj, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    tmp.replace(p)

def _sanitize_basename(name: str) -> str:
    # replace spaces with underscores, keep underscores/digits/letters
    base = name.replace(" ", "_")
    base = re.sub(r"[^\w\s]", "", base)  # drop non-alnum/underscore
    base = re.sub(r"__+", "_", base)     # collapse multiple underscores
    base = base.strip("_")
    return base or "unnamed"

def _unique_filename(dirpath: str, filename: str) -> str:
    """If filename exists in dirpath, append _1, _2, ... until it's unique."""
    base, ext = os.path.splitext(filename)
    i = 1
    candidate = filename
    while os.path.exists(os.path.join(dirpath, candidate)):
        candidate = f"{base}_{i}{ext}"
        i += 1
    return candidate

# --- env ---
load_dotenv()
data_path = os.getenv("DATA_PATH")
if not data_path:
    raise SystemExit("Missing DATA_PATH in environment")

# --- IO paths ---
in_jpg_path = os.path.join(data_path, "in", "pictures")
out_jpg_path = os.path.join(data_path, "renamed_pictures")
mapping_path = os.path.join(data_path, "picture_map.json")

# Preload mapping once (we'll update and save incrementally)
mapping = _load_json(mapping_path, {})

VALID_EXTS = {".jpg", ".jpeg"}

for root, _dirs, files in os.walk(in_jpg_path):
    # Determine layer & project from folder structure
    layer = os.path.basename(root)
    project = os.path.basename(os.path.dirname(root))

    # Skip the top-level if it's the project container (no files directly there)
    for filename in files:
        # skip hidden/system files
        if filename.startswith("."):
            continue

        base, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        if ext_lower not in VALID_EXTS:
            continue  # only process JPG/JPEG

        # Build sanitized new filename
        sanitized = _sanitize_basename(base) + ext_lower

        src_path = os.path.join(root, filename)

        # First, rename in place (in the staging 'in' tree) to the sanitized name
        # If the sanitized name is identical, this is a no-op
        src_sanitized_path = os.path.join(root, sanitized)
        try:
            if filename != sanitized:
                # If sanitized name already exists in source dir, make it unique *in source dir*
                if os.path.exists(src_sanitized_path):
                    sanitized = _unique_filename(root, sanitized)
                    src_sanitized_path = os.path.join(root, sanitized)
                os.rename(src_path, src_sanitized_path)
            else:
                src_sanitized_path = src_path
        except Exception as e:
            print(f"Error renaming in place {src_path} -> {src_sanitized_path}: {e}")
            continue

        # Prepare destination folder: DATA_PATH/renamed_pictures/<project>/<layer>
        processed_folder = os.path.join(out_jpg_path, project, layer)
        os.makedirs(processed_folder, exist_ok=True)

        # Ensure destination name is unique in the processed folder
        new_filename = _unique_filename(processed_folder, os.path.basename(src_sanitized_path))
        dest_path = os.path.join(processed_folder, new_filename)

        try:
            shutil.move(src_sanitized_path, dest_path)
            print(f"File {new_filename} processed successfully")

            # --- Update the mapping only after a successful move ---
            original_filename = filename  # original name as fetched from DCIM
            key = f"{project}/{layer}/{original_filename}"
            mapping[key] = {
                "project": project,
                "layer": layer,
                "original": original_filename,
                "renamed": new_filename,
                "renamed_rel": f"{project}/{layer}/{new_filename}",
            }
            _save_json_atomic(mapping, mapping_path)

        except Exception as e:
            print(f"Error moving file {src_sanitized_path} -> {dest_path}: {e}")
            # Try to put it back to original name (best-effort)
            try:
                if src_sanitized_path != src_path and os.path.exists(src_sanitized_path):
                    os.rename(src_sanitized_path, src_path)
            except Exception:
                pass
