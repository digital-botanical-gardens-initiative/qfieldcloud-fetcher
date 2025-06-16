#!/usr/bin/env python3

import os

import geopandas  # type: ignore[import-untyped]
import pandas as pd
import pyproj
from dotenv import load_dotenv

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")
nextcloud = os.getenv("NEXTCLOUD_FOLDER")

# Construct folders paths
in_csv_path = f"{data_path}/raw_csv"
out_csv_path = f"{data_path}/formatted_csv"
nextcloud_path = f"{nextcloud}/csv"


def convert_csv_coordinates(root: str, filename: str, project: str) -> None:
    """
    Converts the coordinates in a CSV file to EPSG:4326.
    The base CRS system is inferred from the filename.
    The converted CSV file is saved in the specified output folder
    while preserving the directory structure of the input folder.
    """
    csv_file_path = os.path.join(root, filename)

    # Extract the base CRS system from the filename
    file_name = os.path.splitext(os.path.basename(csv_file_path))[0]
    base_crs = file_name.split("_")[-1]
    file_name = file_name.replace(f"_{base_crs}", "")

    # Load the CSV file into a pandas dataframe
    try:
        df = pd.read_csv(csv_file_path)
    except pd.errors.EmptyDataError:
        print(f"Skipping {csv_file_path} (empty CSV file)")
        return
    except pd.errors.ParserError:
        print(f"Skipping {csv_file_path} (invalid CSV file)")
        return

    # Check if the dataframe contains the x_coord and y_coord columns
    if not all(col in df.columns for col in ["x_coord", "y_coord"]):
        print(f"Skipping {csv_file_path} (missing x_coord or y_coord columns)")
        return

    # Define the input and output CRS systems using the pyproj library
    in_crs = pyproj.CRS.from_string(base_crs)
    out_crs = pyproj.CRS("EPSG:4326")

    # Convert the coordinates using the pyproj library
    transformer = pyproj.Transformer.from_crs(in_crs, out_crs, always_xy=True)
    df["latitude"], df["longitude"] = transformer.transform(df["x_coord"].values, df["y_coord"].values)

    # Apply transformation to the geometry column
    df["geometry"] = geopandas.GeoDataFrame(
        geometry=geopandas.points_from_xy(x=df["longitude"], y=df["latitude"]), crs="EPSG:4326"
    )

    # Convert nan in is_wild to 0
    if "is_wild" in df.columns:
        df["is_wild"] = (
            df["no_name_on_list"]
            .fillna(0)
            .astype(bool)   # convert everything to boolean first
            .astype(int)    # then to 0 or 1
        )

    # Convert nan in inat_upload to 1
    if "inat_upload" in df.columns:
        df["inat_upload"] = (
            df["no_name_on_list"]
            .fillna(0)
            .astype(bool)   # convert everything to boolean first
            .astype(int)    # then to 0 or 1
        )

    # Convert nan in no_name_on_list to 0
    if "no_name_on_list" in df.columns:
        df["no_name_on_list"] = (
            df["no_name_on_list"]
            .fillna(0)
            .astype(bool)   # convert everything to boolean first
            .astype(int)    # then to 0 or 1
        )



    # Attribute sample_id to observations
    # Fill NA in 'sample_id' with a pattern based on 'latitude' and 'longitude'
    if "sample_id" in df.columns:
        df["sample_id"] = (
            df["sample_id"]
            .fillna(
                "obs_"
                + df["latitude"].astype(str).str.replace(".", "")
                + "_"
                + df["longitude"].astype(str).str.replace(".", "")
            )
            .astype(str)
        )

    # Extract the CRS from the output pyproj object and replace the original CRS in the output filename
    out_crs_str = out_crs.to_string()
    output_file_name = f"{file_name}_{out_crs_str}.csv"

    # Save the converted coordinates to a new CSV file in the specified output folder
    output_file_path = os.path.join(out_csv_path, project, output_file_name)

    # Add csv to formatted folder
    os.makedirs(os.path.join(out_csv_path, project), exist_ok=True)
    df.to_csv(output_file_path, index=False)
    print(f"{filename} successfully converted")

    # Add csv to NextCloud
    nextcloud_csv_path = os.path.join(nextcloud_path, project)
    os.makedirs(nextcloud_csv_path, exist_ok=True)
    df.to_csv(os.path.join(nextcloud_csv_path, output_file_name), index=False)
    print(f"{output_file_name} added to NextCloud")


# Iterate over all CSV files in the input folder and its subdirectories
for root, _dirs, files in os.walk(in_csv_path):
    for filename in files:
        if filename.endswith(".csv"):
            # Get project
            project = os.path.basename(root)
            # Convert the CSV file and save the result in the output folder
            convert_csv_coordinates(root, filename, project)
