import math
import os
import typing

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# Access the environment variables
directus_instance = os.getenv("DIRECTUS_INSTANCE")
directus_email = os.getenv("DIRECTUS_USERNAME")
directus_password = os.getenv("DIRECTUS_PASSWORD")
data_path = os.getenv("DATA_PATH")

# Construct folders paths
out_csv_path = f"{data_path}/out/csv"

# Create a session object for making requests
session = requests.Session()

# Send a POST request to the login endpoint
directus_login = f"{directus_instance}/auth/login"
response = session.post(directus_login, json={"email": directus_email, "password": directus_password})

# Test if connection is successful
if response.status_code == 200:
    print("Connection to Directus successful")

    # Construct the API endpoint
    collection_name = "Field_Data"
    directus_api = f"{directus_instance}/items/{collection_name}/"

    # Stores the access token
    data = response.json()["data"]
    directus_token = data["access_token"]

    # Construct headers with authentication token
    headers = {
        "Authorization": f"Bearer {directus_token}",
        "Content-Type": "application/json",
    }

    for root, _dirs, files in os.walk(out_csv_path):
        for filename in files:
            if filename.endswith(".csv") and filename != "SBL_20004_2022_EPSG:4326.csv":
                # Read each df
                constructed_path = root + "/" + filename
                df = pd.read_csv(constructed_path)

                # Skip empty files
                if df.empty:
                    continue

                # Add qfield project to dataframe
                project = root.split("/")[-1]
                df["qfield_project"] = project

                # Create an empty dictionary to store the fields to create
                observation: dict[str, typing.Any] = {}

                # Iterate over all columns in the dataframe
                for column in df.columns:
                    # Replace dots with underscores
                    column = column.replace(".", "_").replace("(", "").replace(")", "")
                    observation[column] = None

                # Iterate over each row in the DataFrame
                for i in range(len(df)):
                    # Convert each row to a dictionary
                    obs = df.iloc[i].to_dict()

                    # Convert problematic float values
                    for key, value in obs.items():
                        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                            obs[key] = None if math.isnan(value) else float(value)

                    # Update the observation dictionary with values from the current row
                    for col_name, value in obs.items():
                        if col_name == "geometry":
                            observation["geometry"] = {
                                "type": "Point",
                                "coordinates": [obs["latitude"], obs["longitude"]],
                            }
                        else:
                            observation[col_name.replace(".", "_").replace("(", "").replace(")", "")] = value

                    # Check if element is already added to the database
                    sample_code = obs["sample_id"]
                    directus_observation = f"{directus_api}?filter[sample_id][_eq]={sample_code}&&limit=1"
                    response_get = session.get(url=directus_observation, headers=headers)
                    if str(response_get.json()) != "{'data': []}":
                        data = response_get.json()["data"][0]
                        id_sample = data["id"]
                        directus_patch = f"{directus_api}/{id_sample}"
                        # Element exists, patch it
                        response_patch = session.patch(url=directus_patch, headers=headers, json=observation)
                        if response_patch.status_code != 200:
                            print(
                                f"Error patching {sample_code}, project {obs["qfield_project"]}, file {filename}: {response_patch.status_code} - {response_patch.text}"
                            )
                    else:
                        # Element doesn't exist, post it
                        response_post = session.post(url=directus_api, headers=headers, json=observation)
                        if response_post.status_code != 200:
                            print(
                                f"Error posting {sample_code}, project {obs["qfield_project"]}, file {filename}: {response_post.status_code} - {response_post.text}"
                            )
else:
    print("Connection to Directus failed")
    print(f"Error: {response.status_code} - {response.text}")
    exit()
