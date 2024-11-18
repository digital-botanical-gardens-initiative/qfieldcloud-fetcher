import math
import os
import typing

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# Define the Directus instance, mail and password from .env
directus_instance = os.getenv("DIRECTUS_INSTANCE")
directus_login = f"{directus_instance}/auth/login"

# Define the collection name and API url
collection_name = "Field_Data"
directus_api = f"{directus_instance}/items/{collection_name}"
directus_email = os.getenv("DIRECTUS_EMAIL")
directus_password = os.getenv("DIRECTUS_PASSWORD")

# Create a session object for making requests
session = requests.Session()

# Send a POST request to the login endpoint
response = session.post(directus_login, json={"email": directus_email, "password": directus_password})

# Test if connection is successful
if response.status_code == 200:
    # Stores the access token
    data = response.json()["data"]
    directus_token = data["access_token"]

    # Construct headers with authentication token
    headers = {
        "Authorization": f"Bearer {directus_token}",
        "Content-Type": "application/json",
    }

    out_csv_path = str(os.getenv("OUT_CSV_PATH"))

    # Iterate over all CSV files in the input folder and its subdirectories
    for root, _dirs, files in os.walk(out_csv_path):
        for filename in files:
            # Retrieve project name
            project = root.split("/")[-1]

            # Ignore old layer without sample_id
            if filename.endswith(".csv") and filename != "SBL_20004_2022_EPSG:4326.csv":
                # Read each df
                constructed_path = root + "/" + filename
                df = pd.read_csv(constructed_path)

                # Add qfield project to dataframe
                df["qfield_project"] = project

                # Create an empty dictionary to store the fields to create
                observation: dict[str, typing.Any] = {}

                # Format each observation for directus
                for col_name in df.columns:
                    # Replace dots with underscores in field names
                    new_col_name = col_name.replace(".", "_")
                    # Add to the dictionary
                    observation[new_col_name] = None  # Initialize with None

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
                        observation[col_name.replace(".", "_")] = value

                    # Send the POST request to create or update the fields
                    response = session.post(url=directus_api, headers=headers, json=observation)
                    # Check if the request was successful
                    if response.status_code == 400:
                        sample_code = obs["sample_id"]
                        response_get = session.get(f"{directus_api}?filter[sample_id][_eq]={sample_code}&&limit=1")
                        if str(response_get.json()) != "{'data': []}":
                            data = response_get.json()["data"][0]
                            id_sample = data["id"]
                            directus_observation = f"{directus_api}/{id_sample}"
                            response2 = session.patch(url=directus_observation, headers=headers, json=observation)
                            if response2.status_code != 200:
                                print(f"Error: {response2.status_code} - {response2.text}")
                        else:
                            print(str(obs["sample_id"]) + " contains non unique fields.")
                    elif response.status_code != 400 and response.status_code != 200:
                        print(f"Error: {response.status_code} - {response.text}")
                        print(obs["sample_id"])
                        print(filename)
                        print(obs)
