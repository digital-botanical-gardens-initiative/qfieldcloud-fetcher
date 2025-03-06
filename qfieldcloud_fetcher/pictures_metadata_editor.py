#!/usr/bin/env python3

import csv
import os
import re
import shutil
import subprocess
from datetime import datetime

import requests
from dotenv import load_dotenv

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")
nextcloud_path = os.getenv("NEXTCLOUD_FOLDER")

# Construct folders paths
in_jpg_path = f"{data_path}/renamed_compressed_pictures"
out_csv_path = f"{data_path}/formatted_csv"
inat_jpg_path = f"{data_path}/inat_pictures"

# Request to directus to obtain projects codes
collection_url = "https://emi-collection.unifr.ch/directus/items/Projects"
column = "project_id"
params = {"sort[]": f"{column}"}
session = requests.Session()
response = session.get(collection_url, params=params)
data = response.json()["data"]
project_names = [item[column] for item in data]

# Aggregate patterns and also include observation pattern
pattern = "(" + "|".join(project_names) + ")_[0-9]{6}|[0-9]{14}|obs_[0-9]6,20}_[0-9]{6,20}"

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
                print("No unique identifier detected in {file}, skipping.")
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
            with open(csv_filename) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Match the corresponding data
                    if "sample_id" in row and row["sample_id"] and row["sample_id"] == unique_id:
                        date = row["date"]
                        # Check if a date exists. If not, skip the picture
                        if date == "":
                            print(f"No data found for {unique_id}")
                            continue

                        # Get and format data
                        formatted_date = datetime.strptime(date, "%Y%m%d%H%M%S")
                        collector = row["collector_fullname"]
                        collector_prefix = "emi_collector:" + collector
                        inat_upload = row["inat_upload"]
                        is_wild = row["is_wild"]
                        is_wild_prefix = {"emi_is_wild:": is_wild}
                        orcid = row["collector_orcid"]
                        orcid_prefix = "emi_collector_orcid:" + orcid
                        inat = row["collector_inat"]
                        inat_prefix = "emi_collector_inat:" + inat
                        lon = row["longitude"]
                        lat = row["latitude"]

            # Write metadata using exiftool
            command = f'./exiftool/exiftool -Subject={unique_prefixed} -Subject="{collector_prefix}" -Subject={orcid_prefix} -Subject={inat_prefix} -EXIF:GPSLongitude*={lon} -EXIF:GPSLatitude*={lat} -EXIF:DateTimeOriginal="{formatted_date}" {picture_path} -overwrite_original'
            try:
                result = subprocess.run(command, shell=True, capture_output=True)  # noqa: S602
                print(f"Medata for {file} successfully edited")
            except subprocess.CalledProcessError as e:
                print(f"Error adding metadata to {file}: {e.stderr}")
                continue

            # Prepare iNaturalist import folder
            if inat_upload == "1":
                # Construct inat folder
                inat_folder = os.path.join(inat_jpg_path, unique_id)
                # Add if sample is wild or not in picture path
                inat_file = "wild_" + file if is_wild == "1" else file
                # Move file to new folder
                os.makedirs(inat_folder, exist_ok=True)
                shutil.copy(picture_path, os.path.join(inat_folder, inat_file))
                print(f"{file} copied to iNaturalist import folder")
            else:
                print(f"Skipping copying {file} to iNaturalist folder, upload set to false")

            # Add files to NextCloud
            nextcloud_jpg_path = os.path.join(str(nextcloud_path), project, layer)
            os.makedirs(nextcloud_jpg_path, exist_ok=True)
            shutil.move(picture_path, os.path.join(nextcloud_jpg_path, file))
            print(f"{file} added to NextCloud")
        else:
            print(f"Skipping {file} as it is not a picture.")
