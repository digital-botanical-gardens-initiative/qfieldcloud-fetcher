import os

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# Access the environment variables
directus_instance = os.getenv("DIRECTUS_INSTANCE")
directus_email = os.getenv("DIRECTUS_USERNAME")
directus_password = os.getenv("DIRECTUS_PASSWORD")

# Define urls
directus_login = f"{directus_instance}/auth/login"
collection_name = "Field_Data"
directus_api = f"{directus_instance}/items/{collection_name}/"

# Create a session object for making requests
session = requests.Session()

# Send a POST request to the login endpoint
response = session.post(directus_login, json={"email": directus_email, "password": directus_password})


# Function to get parent field primary keys
def get_primary_key_field(sample_code: str) -> int:
    params = {
        "filter[sample_id][_eq]": sample_code,
        "fields": "id",
    }
    # Create a session object for making requests
    session = requests.Session()
    response = session.get("https://emi-collection.unifr.ch/directus/items/Field_Data/", params=params)
    if response.status_code == 200:
        data = response.json()
        if data["data"]:
            return int(data["data"][0]["id"])
        else:
            return -1
    else:
        return -1


# Function to get parent sample containers primary keys
def get_primary_key_container(sample_code: str) -> int:
    params = {"filter[container_id][_eq]": sample_code, "fields": "id"}
    # Create a session object for making requests
    session = requests.Session()
    response = session.get("https://emi-collection.unifr.ch/directus/items/Containers/", params=params)
    if response.status_code == 200:
        data = response.json()
        if data["data"]:
            return int(data["data"][0]["id"])
        else:
            return -1
    else:
        return -1


# Function to get parent dried samples data
def get_primary_key_dried(sample_code: int) -> int:
    params = {"filter[sample_container][_eq]": str(sample_code), "fields": "id"}
    # Create a session object for making requests
    session = requests.Session()
    response = session.get("https://emi-collection.unifr.ch/directus/items/Dried_Samples_Data/", params=params)
    if response.status_code == 200:
        data = response.json()
        if data["data"]:
            return int(data["data"][0]["id"])
        else:
            return -1
    else:
        return -1


# Test if connection is successful
if response.status_code == 200:
    print("Connection to Directus successful")

    # Stores the access token
    data = response.json()["data"]
    directus_token = data["access_token"]

    # Construct headers with authentication token
    headers = {
        "Authorization": f"Bearer {directus_token}",
        "Content-Type": "application/json",
    }

    response_get = session.get(f"{directus_api}?limit=-1")
    data = response_get.json()["data"]
    df = pd.DataFrame(data)
    for _index, row in df.iterrows():
        sample_id = row["sample_id"]
        if sample_id.startswith("obs_"):
            # Skip observations
            continue
        else:
            id_container = get_primary_key_container(sample_id)
            id_field = get_primary_key_field(sample_id)
            id_dried = get_primary_key_dried(int(id_container))
            directus_observation_dried = f"https://emi-collection.unifr.ch/directus/items/Dried_Samples_Data/{id_dried}"
            response_patch = session.patch(
                url=directus_observation_dried, headers=headers, json={"field_data": id_field}
            )
            if response_patch.status_code != 200:
                print(
                    f"Error linking {sample_id}: {response_patch.status_code} - Maybe the sample has not been dried yet."
                )

    print("Linking finished")
else:
    print("Connection to Directus failed")
    print(f"Error: {response.status_code} - {response.text}")
    exit()
