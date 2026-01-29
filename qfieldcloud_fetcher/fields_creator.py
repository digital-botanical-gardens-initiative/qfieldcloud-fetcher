import argparse
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
data_path = os.getenv("DATA_PATH")

# Construct folders paths
out_csv_path = f"{data_path}/formatted_csv"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update Directus fields based on formatted CSVs.")
    parser.add_argument("--project", default=None, help="Only process a single project folder by name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.project:
        print(f"Filtering to project: {args.project}")

    # Create a session object for making requests
    session = requests.Session()

    # Send a POST request to the login endpoint
    directus_login = f"{directus_instance}/auth/login"
    response = session.post(directus_login, json={"email": directus_email, "password": directus_password})

    # Test if connection is successful
    if response.status_code == 200:
        print("Connection to Directus successful")

        # Stores the access token
        data = response.json()["data"]
        directus_token = data["access_token"]

        # Create an empty dictionary to store the column types
        field_types = {}

        # Mapping pandas dtypes to Directus types
        pandas_to_directus = {
            "int64": "integer",
            "float64": "float",
            "object": "string",
            "bool": "boolean",
            "datetime64[ns]": "datetime",
            "timedelta64[ns]": "duration",
        }

        file_count = 0
        # Iterate over all CSV files in the input folder and its subdirectories
        for root, _dirs, files in os.walk(out_csv_path):
            project = os.path.basename(root)
            if args.project and project != args.project:
                continue
            for filename in files:
                # Ignore old layer without sample_id and non-csv files
                if filename.endswith(".csv") and filename != "SBL_20004_2022_EPSG:4326.csv":
                    file_count += 1
                    constructed_path = root + "/" + filename
                    print(f"Inspecting {constructed_path}")
                    df = pd.read_csv(constructed_path)

                    # Skip empty files
                    if df.empty:
                        continue

                    # Add qfield project to dataframe
                    project = root.split("/")[-1]
                    df["qfield_project"] = project

                    # Iterate over all columns in the dataframe
                    for column in df.columns:
                        # Skip columns with all null values
                        if df[column].isnull().all():
                            continue

                        # Replace dots with underscores
                        new_column = column.replace(".", "_").replace("(", "").replace(")", "")
                        df.rename(columns={column: new_column}, inplace=True)

                        # Add types to dictionary if not already present
                        if new_column not in field_types:
                            if new_column.__contains__("comment"):
                                column_type = "text"
                            elif new_column.__contains__("geometry"):
                                column_type = "geometry.Point"
                            elif new_column.__contains__("date"):
                                column_type = "bigInteger"
                            else:
                                column_type = pandas_to_directus[str(df[new_column].dtype)]

                            field_types[new_column] = column_type

        print(f"Detected {len(field_types)} fields from {file_count} CSV files.")

        # Define api urls
        collection_name = "Field_Data"

        # Construct headers with authentication token
        headers = {"Authorization": f"Bearer {directus_token}", "Content-Type": "application/json"}
        post_url = f"{directus_instance}/fields/{collection_name}/"
        for key, value in field_types.items():
            field_url = f"{directus_instance}/fields/{collection_name}/{key}"
            response = session.get(field_url)

            if response.status_code == 200:
                print(f"Field {key} already exists")
            elif response.status_code == 403:
                print(f"Creating field {key} with type {value}")
                data = {"field": key, "type": value}
                response = session.post(post_url, json=data, headers=headers)
                if value == "geometry.Point":
                    # If field is of type geometry.Point, add a validation to correctly display map
                    validation = {"meta": {"validation": {"_and": [{key: {"_intersects_bbox": None}}]}}}
                    url_patch = f"{directus_instance}/fields/{collection_name}/{key}"
                    response = session.patch(url_patch, json=validation, headers=headers)
                    if response.status_code == 200:
                        print(f"validation correctly added for field {key}")
                    else:
                        print("error adding validation")
                if response.status_code != 200:
                    print(f"Error creating field: {response.status_code} - {response.text}")
            else:
                print(f"Error: {response.status_code} - {response.text}")

    else:
        print("Connection to Directus failed")
        print(f"Error: {response.status_code} - {response.text}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
