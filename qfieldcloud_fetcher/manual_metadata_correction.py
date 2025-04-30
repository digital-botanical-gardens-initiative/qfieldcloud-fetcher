#!/usr/bin/env python3

import csv
import os
import re
import subprocess
from datetime import datetime

import requests
from dotenv import load_dotenv

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")

# Construct folder path
inat_jpg_path = f"{data_path}/inat_pictures"
out_csv_path = f"{data_path}/formatted_csv"

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
for root, _dirs, files in os.walk(inat_jpg_path):
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
            csv_filename = "/media/data/qfieldcloud_data/data/formatted_csv/jbuf/heloise_coen_EPSG:4326.csv"

            found = False

            # Get picture metadata from CSV file
            with open(csv_filename) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Match the corresponding data
                    if "sample_id" in row and row["sample_id"] and row["sample_id"].replace(" ", "") == unique_id:
                        found = True
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

                        # Stop iterating when match is found
                        break

            if not found:
                print(f"found: {found}")
                print(f"No data found for {unique_id}")
                continue

            # Write metadata using exiftool
            command = f'./exiftool/exiftool -Subject={unique_prefixed} -Subject="{collector_prefix}" -Subject={orcid_prefix} -Subject={inat_prefix} -EXIF:GPSLongitude*={lat} -EXIF:GPSLatitude*={lon} -EXIF:DateTimeOriginal="{formatted_date}" {picture_path} -overwrite_original'
            try:
                result = subprocess.run(command, shell=True, capture_output=True)  # noqa: S602
                print(result)
                print(f"Medata for {file} successfully edited")
            except subprocess.CalledProcessError as e:
                print(f"Error adding metadata to {file}: {e.stderr}")
                continue
        else:
            print(f"Skipping {file} as it is not a picture.")
