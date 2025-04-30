#!/usr/bin/env python3

import os
import re

import requests
from dotenv import load_dotenv
from qfieldcloud_sdk import sdk  # type: ignore[import-untyped]

# Loads environment variables
load_dotenv()

# Access the environment variables
instance = os.getenv("QFIELDCLOUD_INSTANCE")
username = os.getenv("QFIELDCLOUD_USERNAME")
password = os.getenv("QFIELDCLOUD_PASSWORD")
data_path = os.getenv("DATA_PATH")

# Construct urls
url = f"{instance}/api/v1/"
url_files = f"{instance}/api/v1/files/"

# Construct folders paths
in_gpkg_path = f"{data_path}/in/gpkg"
in_jpg_path = f"{data_path}/in/pictures"

# Server connection
client = sdk.Client(url=url)
credentials = client.login(username=username, password=password)

# Stores connection token
auth_token = credentials["token"]

if not auth_token:
    print("Error: Could not authenticate with the server")
    exit(1)

# Extracts the projects informations
projects = client.list_projects()
projects_names = []
projects_ids = []
for d in projects:
    for key, value in d.items():
        if key.startswith("id"):
            projects_ids.append(value)
        elif key.startswith("name"):
            projects_names.append(value)

# Constructs the gpkg urls
base_url = url_files
urls_gpkg_by_project = {}
for project in projects:
    project_name = project["name"]
    project_id = project["id"]
    project_files = client.list_remote_files(project_id=project_id)
    project_urls = []
    for file in project_files:
        file_name = file["name"]
        if file_name.endswith(".gpkg") and "map" not in file_name:
            url = f"{base_url}{project_id}/{file_name}"
            project_urls.append(url)
    urls_gpkg_by_project[project_name] = project_urls

# Sets the gpkg directory path for each project and creates the directories if they don't exist
base_gpkg_path = str(in_gpkg_path)
path_gpkg = {}
for name in projects_names:
    dir_path = os.path.join(base_gpkg_path, name)
    os.makedirs(dir_path, exist_ok=True)
    path_gpkg[name] = dir_path

# Downloads the gpkg files for each project
for prefix, urls_list in urls_gpkg_by_project.items():
    for url in urls_list:
        file_name = url.split("/")[-1]
        save_path = os.path.join(path_gpkg[prefix], file_name)
        response = requests.get(
            url,
            headers={"Authorization": f"Token {auth_token}", "Accept-Encoding": "gzip, deflate, br"},
            stream=True,
            timeout=10,
        )
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Downloaded {url}")
        else:
            print(f"Error downloading {url}")

# Creates the pictures directories names
file_dict = {}
for project in projects:
    project_name = project["name"]
    project_id = project["id"]
    project_files = client.list_remote_files(project_id=project_id)
    filenames = []
    for file in project_files:
        filename = re.search(r"(\w+)\.gpkg", file["name"])
        if filename:
            filenames.append(filename.group(1))
    file_dict[project_name] = filenames

# Constructs the pictures urls
urls_jpg_by_project = {}

for project in projects:
    project_name = project["name"]
    project_id = project["id"]
    project_files = client.list_remote_files(project_id=project_id)
    project_urls = []
    urls_jpg_by_layer: dict[str, list] = {}
    for file in project_files:
        file_name = file["name"]
        if file_name.endswith(".jpg"):
            url = f"{base_url}{project_id}/{file_name}"
            project_urls.append(url)
            layer_name = url.split("/")[8]
            if layer_name not in urls_jpg_by_layer:
                urls_jpg_by_layer[layer_name] = []
            urls_jpg_by_layer[layer_name].append(url)
    urls_jpg_by_project[project_name] = urls_jpg_by_layer

# Sets the jpg directories path for each project and creates the directories if they don't exist
base_jpg_path = str(in_jpg_path)
path_jpg: dict[str, dict] = {}
for project, files in file_dict.items():
    project_path = os.path.join(base_jpg_path, project)
    os.makedirs(project_path, exist_ok=True)
    path_jpg[project] = {}
    for file_name in files:
        file_path = os.path.join(project_path, file_name)
        os.makedirs(file_path, exist_ok=True)
        path_jpg[project][file_name] = file_path

# Downloads the jpg files for each project
for prefix, urls_jpg_by_layer in urls_jpg_by_project.items():
    for _layer_name, urls_list in urls_jpg_by_layer.items():
        # Loop over each url in the urls list
        for url in urls_list:
            # Extract the file name and directory name from the url
            after_dcim = url.split("/DCIM/")[1]

            dir_name, file_name = after_dcim.split("/", 1)

            # Create the directory path for the downloaded file
            try:
                save_dir = path_jpg[prefix][dir_name]
            except Exception as e:
                print(f"Error: Directory {dir_name} not found for project {prefix} - {e}")
                print(f"Skipping {url}")
                continue

            # Create the full path for the downloaded file
            save_path = os.path.join(save_dir, file_name.replace("/", "_"))

            # Download the file
            response = requests.get(
                url,
                headers={"Authorization": f"Token {auth_token}", "Accept-Encoding": "gzip, deflate, br"},
                stream=True,
                timeout=10,
            )
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"Downloaded {url}")
            else:
                print(f"Error downloading {url}")
            project_id = None
            for project in projects:
                if project["name"] == prefix:
                    project_id = project["id"]
                    break

            if project_id:
                # Delete the file on the server
                file_to_delete = os.path.join("DCIM", dir_name, file_name)
                result = client.delete_files(project_id=project_id, glob_patterns=[file_to_delete])
            else:
                print(f"Error: Project ID not found for project {prefix}")
