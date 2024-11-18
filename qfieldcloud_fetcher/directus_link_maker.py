import os

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


# Function to get parent sample containers primary keys
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


# Function to get parent sample containers primary keys
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


# Function to get parent sample containers primary keys
def get_primary_key_ext(sample_code: int) -> int:
    print(sample_code)
    params = {"filter[parent_sample_container][_eq]": str(sample_code), "fields": "id"}
    # Create a session object for making requests
    session = requests.Session()
    response = session.get("https://emi-collection.unifr.ch/directus/items/Extraction_Data/", params=params)
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
        id_container = get_primary_key_container(sample_id)
        id_field = get_primary_key_field(sample_id)
        id_dried = get_primary_key_dried(int(id_container))
        id_ext = get_primary_key_ext(int(id_container))
        directus_observation_dried = f"https://emi-collection.unifr.ch/directus/items/Dried_Samples_Data/{id_dried}"
        response_patch = session.patch(url=directus_observation_dried, headers=headers, json={"field_data": id_field})
        print(
            f"sample id: {sample_id}, id container: {id_container}, id field: {id_field}, id dried: {id_dried}, id ext: {id_ext}"
        )
        if response_patch.status_code != 200:
            print(
                f"sample id: {sample_id}, id: {id}, error: {response_patch.status_code}, message: {response_patch.text}"
            )
        directus_observation_ext = f"https://emi-collection.unifr.ch/directus/items/Extraction_Data/{id_ext}"
        response_patch_ext = session.patch(url=directus_observation_ext, headers=headers, json={"field_data": id_field})
        if response_patch.status_code != 200:
            print(
                f"sample id: {sample_id}, id: {id}, error: {response_patch_ext.status_code}, message: {response_patch_ext.text}"
            )