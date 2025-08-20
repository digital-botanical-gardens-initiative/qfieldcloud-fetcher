#!/usr/bin/env python3

import csv
import os
import re
import shutil
import subprocess
import json
from datetime import datetime

import requests
from dotenv import load_dotenv

# ---------------------------
# Small JSON helpers
# ---------------------------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json_atomic(obj, path):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

# ---------------------------
# Loads environment variables
# ---------------------------
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")
nextcloud = os.getenv("NEXTCLOUD_FOLDER")
if not data_path or not nextcloud:
    raise SystemExit("Missing DATA_PATH or NEXTCLOUD_FOLDER in environment")

# Construct folders paths
in_jpg_path = f"{data_path}/renamed_compressed_pictures"
out_csv_path = f"{data_path}/formatted_csv"
inat_jpg_path = f"{data_path}/inat_pictures"
nextcloud_path = f"{nextcloud}/pictures"

# Extra logs/inputs
mapping_path = os.path.join(data_path, "picture_map.json")   # produced by pictures_renamer.py
processed_ok_path = os.path.join(data_path, "processed_ok.json")

# Request to directus to obtain projects codes
collection_url = "https://emi-collection.unifr.ch/directus/items/Projects"
column = "project_id"
params = {"sort[]": f"{column}"}
session = requests.Session()
response = session.get(collection_url, params=params, timeout=30)
data = response.json()["data"]
project_names = [item[column] for item in data]

# Aggregate patterns and also include observation pattern (kept as in your original)
pattern = "(" + "|".join(project_names) + ")_[0-9]{6}|[0-9]{14}|obs_[0-9]6,20}_[0-9]{6,20}"

# Preload mapping/processed logs
mapping = load_json(mapping_path, {})
processed_ok = load_json(processed_ok_path, {})

# Loop over pictures
for root, _dirs, files in os.walk(in_jpg_path):
    for file in files:
        if file.lower().endswith(".jpg"):
            # Get layer
            layer = os.path.basename(root)
            # Get project
            project = os.path.basename(os.path.dirname(root))

            # Get picture path
            picture_path = os.path.join(root, file)

            # Extract unique id with pattern
            match = re.search(pattern, file)
            if match:
                unique_id = match.group()
            else:
                print(f"No unique identifier detected in {file}, skipping.")
                continue

            unique_prefixed = "emi_external_id:" + unique_id

            # Get corresponding CSV file
            csv_filename = os.path.join(
                out_csv_path, os.path.basename(os.path.dirname(root)), os.path.basename(root) + "_EPSG:4326.csv"
            )

            # Check if CSV file exists
            if not os.path.isfile(csv_filename):
                print(f"No corresponding CSV file found for {picture_path}")
                continue

            # Get picture metadata from CSV file
            found = False
            with open(csv_filename, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Match the corresponding data
                    if "sample_id" in row and row["sample_id"] and row["sample_id"] == unique_id:
                        found = True
                        date = row.get("date", "")
                        # Check if a date exists. If not, use now
                        if date == "":
                            date = datetime.now().strftime("%Y%m%d%H%M%S")

                        # Get and format data
                        formatted_date = datetime.strptime(date, "%Y%m%d%H%M%S")
                        collector = row.get("collector_fullname", "")
                        collector_prefix = "emi_collector:" + collector
                        inat_upload = row.get("inat_upload", "")
                        is_wild = row.get("is_wild", "")
                        # (kept, though unused)
                        is_wild_prefix = {"emi_is_wild:": is_wild}
                        orcid = row.get("collector_orcid", "")
                        orcid_prefix = "emi_collector_orcid:" + orcid
                        inat = row.get("collector_inat", "")
                        inat_prefix = "emi_collector_inat:" + inat
                        lon = row.get("longitude", "")
                        lat = row.get("latitude", "")

                        # Stop iterating when match is found
                        break

            if not found:
                print(f"No data found for {unique_id}")
                continue

            # --- ExifTool call (debug-friendly, same arguments you used) ---
            here = os.path.dirname(os.path.abspath(__file__))
            exif_bin = os.path.join(here, "exiftool", "exiftool")  # absolute path to vendored script/binary
            env = os.environ.copy()

            # If vendored Perl script with lib/ exists, make sure Perl can find modules
            vend_lib = os.path.join(here, "exiftool", "lib")
            if os.path.isdir(vend_lib):
                env["PERL5LIB"] = vend_lib + (os.pathsep + env["PERL5LIB"] if "PERL5LIB" in env else "")

            # Build the exact same command you had before
            command = (
                f'"{exif_bin}" '  # quote path to handle spaces
                f'-Subject={unique_prefixed} '
                f'-Subject="{collector_prefix}" '
                f'-Subject={orcid_prefix} '
                f'-Subject={inat_prefix} '
                f'-EXIF:GPSLongitude*={lat} '
                f'-EXIF:GPSLatitude*={lon} '
                f'-EXIF:DateTimeOriginal="{formatted_date}" '
                f'"{picture_path}" -overwrite_original'
            )

            # Run and show full diagnostics on failure
            result = subprocess.run(command, shell=True, capture_output=True, text=True, env=env)  # noqa: S602
            if result.returncode != 0:
                print(f"ExifTool FAILED for {file} (exit={result.returncode})")
                if result.stdout.strip():
                    print("STDOUT:", result.stdout.strip())
                if result.stderr.strip():
                    print("STDERR:", result.stderr.strip())
                # Don’t crash the pipeline; just skip this file
                continue

            print(f"Metadata for {file} successfully edited")


            # Prepare iNaturalist import folder
            if inat_upload == "1":
                # Add if sample is wild or not in folder path
                folder = os.path.join(inat_jpg_path, unique_id)
                inat_folder = os.path.join(inat_jpg_path, "wild", unique_id) if is_wild == "1" else folder
                # Move file to new folder
                os.makedirs(inat_folder, exist_ok=True)
                try:
                    shutil.copy2(picture_path, os.path.join(inat_folder, file))
                    print(f"{file} copied to iNaturalist import folder")
                except Exception as e:
                    print(f"Error copying {file} to iNaturalist folder: {e}")
            else:
                print(f"Skipping copying {file} to iNaturalist folder, upload set to false")

            # Add files to NextCloud
            nextcloud_jpg_path = os.path.join(str(nextcloud_path), project, layer)
            os.makedirs(nextcloud_jpg_path, exist_ok=True)
            dest_path = os.path.join(nextcloud_jpg_path, file)
            try:
                shutil.move(picture_path, dest_path)
                print(f"{file} added to NextCloud")
            except Exception as e:
                print(f"Error moving {file} to NextCloud: {e}")
                continue

            # ---------------------------
            # Mark processed OK (link renamed -> original DCIM name)
            # ---------------------------
            # Find original filename from mapping (produced by pictures_renamer.py)
            original = None
            # Try direct key (unlikely with our schema)
            direct_key = f"{project}/{layer}/{file}"
            m = mapping.get(direct_key)
            if isinstance(m, dict) and m.get("original"):
                original = m["original"]
            else:
                # Search by value 'renamed' == current file
                for k, v in mapping.items():
                    if (
                        isinstance(v, dict)
                        and v.get("project") == project
                        and v.get("layer") == layer
                        and v.get("renamed") == file
                    ):
                        original = v.get("original")
                        break
            if not original:
                original = file  # fallback

            proc_key = f"{project}/{layer}/{original}"
            processed_ok[proc_key] = {
                "project": project,
                "layer": layer,
                "original": original,
                "final_name": file,
                "final_path": dest_path,
                "ok_at": datetime.utcnow().isoformat() + "Z",
            }
            try:
                save_json_atomic(processed_ok, processed_ok_path)
            except Exception as e:
                print(f"Warning: could not update processed_ok.json: {e}")

        else:
            print(f"Skipping {file}, not a picture.")
