# This script is there in case we need to edit the metadata of the pictures in the inat_pictures
# folder due to a change in the metadata format or previous errors in the classical pipeline.

#!/usr/bin/env python3

import os
import subprocess
from datetime import datetime

import pandas as pd
import requests
from dotenv import load_dotenv

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")
nextcloud = os.getenv("NEXTCLOUD_FOLDER")

# Construct folders paths
in_jpg_path = f"{data_path}/inat_pictures"
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

dfs = []

# Get common dataframe
for root, _dirs, files in os.walk(out_csv_path):
    for filename in files:
        file = root + "/" + filename
        df = pd.read_csv(file)
        dfs.append(df)

# Concatenate, automatically aligning columns
df = pd.concat(dfs, ignore_index=True, sort=False)

# Loop over pictures
for dirs in os.walk(in_jpg_path):
    for folder in dirs[1]:
        root = os.path.join(in_jpg_path, folder)
        print(f"Processing folder: {root}")
        row = df[df["sample_id"] == folder].iloc[0]

        if row.empty:
            print(f"No data found for folder {folder}, skipping.")
            continue

        unique_prefixed = "emi_external_id:" + row["sample_id"]

        date = str(int(row["date"]))
        if date == "":
            date = str(datetime.now().strftime("%Y%m%d%H%M%S"))
        formatted_date = datetime.strptime(date, "%Y%m%d%H%M%S")

        collector = row["collector_fullname"]
        collector_prefixed = "emi_collector:" + collector

        is_wild = bool(row["is_wild"])
        is_wild_prefixed = {"emi_is_wild:": is_wild}

        value = row["collector_orcid"]
        if pd.notna(value):  # check for not NaN (pd.notna works with pandas/numpy)
            if isinstance(value, float):
                value = str(int(value))
            else:
                value = str(value)
            
            orcid = value
            orcid_prefixed = f"emi_collector_orcid:{orcid}"
        else:
            orcid = ""
            orcid_prefixed = f"emi_collector_orcid:{orcid}"

        inat = str(row["collector_inat"])
        inat_prefixed = "emi_collector_inat:" + inat

        lon = row["longitude"]
        lat = row["latitude"]

        for file in os.listdir(root):
            if not file.lower().endswith(".jpg"):
                print(f"Skipping {file}, not a picture.")
                continue

            picture_path = os.path.join(root, file)

            # Write metadata using exiftool
            command = (
                f"./exiftool/exiftool -Subject={unique_prefixed} "
                f'-Subject="{collector_prefixed}" '
                f"-Subject={orcid_prefixed} "
                f"-Subject={inat_prefixed} "
                f"-EXIF:GPSLongitude*={lat} "
                f"-EXIF:GPSLatitude*={lon} "
                f'-EXIF:DateTimeOriginal="{formatted_date}" '
                f"{picture_path} -overwrite_original"
            )
            try:
                result = subprocess.run(command, shell=True, capture_output=True)  # noqa: S602
                print(f"Medata for {file} successfully edited")
            except subprocess.CalledProcessError as e:
                print(f"Error adding metadata to {file}: {e.stderr}")
                continue
