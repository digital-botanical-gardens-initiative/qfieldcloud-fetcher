import os

import pandas as pd
import requests
from dotenv import load_dotenv

# Loads .env variables
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

                # Define the threshold for text length
                threshold = 255

                # Create an empty dictionary to store the biggest values of each column
                longest_content = {}

                # Create an empty dictionary to store the fields to create
                observation = {}

                # Loop over the columns to create the dict
                for col_name in df.columns:
                    # Replace dots with underscores in field names
                    new_col_name = col_name.replace(".", "_")
                    # Add to the dictionary
                    observation[new_col_name] = col_name

                    # Find the longest content in the column
                    longest = df[col_name].astype(str).apply(len).max()

                    # Store the longest content for the column
                    if str(longest) != "nan":
                        longest_content[new_col_name] = longest
                    else:
                        longest_content[new_col_name] = 1

                # Request directus to create the columns
                for i in observation:
                    col_init = str.replace(str(observation[i]), "['", "")
                    col = str.replace(col_init, "']", "")
                    col_clean = str.replace(col, ".", "_")
                    df_type = str(df[col].dtype)
                    df_col_name = str(df[col].name)

                    # Replace types to match directus ones

                    if df_type == "object" and longest_content[i] < threshold:
                        dir_type = "string"
                    elif df_type == "int64" and longest_content[i] < threshold:
                        dir_type = "integer"
                    elif df_type == "bool" and longest_content[i] < threshold:
                        dir_type = "boolean"
                    elif df_type == "float64" and longest_content[i] < threshold:
                        dir_type = "float"
                    elif longest_content[i] >= threshold:
                        dir_type = "text"
                    else:
                        # If type is not handled by the ones already made, print it so we can integrate it easily
                        print(f"not handled type: {df_type}, longest content: {longest_content[i]}")
                    if df_col_name == "geojson.coordinates":
                        dir_type = "geometry.Point"

                    # Create patch url
                    url_patch = f"{directus_instance}/fields/{collection_name}/{col_clean}"

                    # Construct directus url
                    url = f"{directus_instance}/fields/{collection_name}"
                    # Create a field for each csv column
                    data = {"field": col_clean, "type": dir_type}

                    # Make directus request
                    response = requests.post(url, json=data, headers=headers, timeout=10)
                    # Check if adding is success
                    if response.status_code == 200:
                        # print(f"{col_clean} field created")
                        # If field is of type geometry.Point, add a validation to correctly display map
                        if dir_type == "geometry.Point":
                            validation = {"meta": {"validation": {"_and": [{col_clean: {"_intersects_bbox": None}}]}}}
                            response = requests.patch(url_patch, json=validation, headers=headers, timeout=10)
                            if response.status_code != 200:
                                # print(f"validation correctly added for field {col_clean}")
                                # else:
                                print("error adding validation")
                    # else print the type and the column name
                    elif response.status_code == 400:
                        response = requests.patch(url_patch, json=data, headers=headers, timeout=10)
                        if response.status_code != 200:
                            # print(f"field {col_clean} updated")
                            # print(dir_type)
                            # else:
                            print(f"error creating/updating field {col_clean}")
                    else:
                        print(response.status_code)
                        print(response.text)
                        print(dir_type)
                        print(col_clean)
