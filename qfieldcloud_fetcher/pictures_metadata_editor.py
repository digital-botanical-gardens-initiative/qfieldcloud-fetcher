#!/usr/bin/env python3

from dotenv import load_dotenv
import os
import csv
import re
import subprocess
from datetime import datetime

import requests

#Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")

# Construct folders paths
in_jpg_path = f"{data_path}/renamed_compressed_pictures"
out_csv_path = f"{data_path}/formatted_csv"
out_jpg_path = f"{data_path}/formatted_pictures"

# Request to directus to obtain projects codes
collection_url = "https://emi-collection.unifr.ch/directus/items/Projects"
column = 'project_id'
params = {'sort[]': f'{column}'}
session = requests.Session()
response = session.get(collection_url, params=params)
data = response.json()['data']
project_names = [item[column] for item in data]

# Aggregate patterns and also include observation pattern
pattern = "(" + "|".join(project_names) + ")_[0-9]{6}|[0-9]{14}|obs_[0-9]6,20}_[0-9]{6,20}"

# Loop over pictures
for root, dirs, files in os.walk(in_jpg_path):
    for file in files:
        if file.lower().endswith('.jpg'):
            # Get picture path
            picture_path = os.path.join(root, file)

            # Extract unique id with pattern
            unique_id = re.search(pattern, file).group()
            unique_prefixed = 'emi_external_id:' + unique_id

            # Get corresponding CSV file
            csv_filename = os.path.join(out_csv_path, os.path.basename(os.path.dirname(root)), os.path.basename(root) + '_EPSG:4326.csv')

            # Check if CSV file exists
            if not os.path.isfile(csv_filename):
                print(f"No corresponding CSV file found for {picture_path}")
                continue

            # Get picture metadata from CSV file
            with open(csv_filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Match the corresponding data
                    if 'sample_id' in row and row['sample_id'] and row['sample_id'] == unique_id:
                        date = row['date']
                        # Check if a date exists. If not, skip the picture
                        if date == '':
                            print(f"No data found for {unique_id}")
                            continue

                        # Get and format data
                        formatted_date = datetime.strptime(date, '%Y%m%d%H%M%S')
                        collector = row['collector_fullname']
                        collector_prefix = 'emi_collector:' + collector
                        inat_upload = row['inat_upload']
                        is_wild = row['is_wild']
                        is_wild_prefix = {'emi_is_wild:': is_wild}
                        orcid = row['collector_orcid']
                        orcid_prefix = 'emi_collector_orcid:' + orcid
                        inat = row['collector_inat']
                        inat_prefix = 'emi_collector_inat:' + inat
                        lon = row['longitude']
                        lat = row['latitude']

                # Write metadata using exiftool
                command = f"./exiftool/exiftool -Subject={unique_prefixed} -Subject=\"{collector_prefix}\" -Subject={orcid_prefix} -Subject={inat_prefix} -EXIF:GPSLongitude*={lon} -EXIF:GPSLatitude*={lat} -EXIF:DateTimeOriginal=\"{formatted_date}\" {picture_path} -overwrite_original"
                subprocess.run(command, shell=True)

