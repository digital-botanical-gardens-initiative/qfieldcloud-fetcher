#!/usr/bin/env python3

import argparse
import os

import geopandas as gpd  # type: ignore[import-untyped]
import pandas as pd
from dotenv import load_dotenv

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")

# Construct folders paths
in_gpkg_path = f"{data_path}/in/gpkg"
in_csv_path = f"{data_path}/raw_csv"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert GPKG files to raw CSV files.")
    parser.add_argument("--project", default=None, help="Only process a single project folder by name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.project:
        print(f"Filtering to project: {args.project}")

    # Loop over the subfolders in the gpkg directory
    for subfolder in os.listdir(in_gpkg_path):
        if args.project and subfolder != args.project:
            continue

        subfolder_gpkg_path = os.path.join(in_gpkg_path, subfolder)

        # Check if subfolder_gpkg_path is a directory
        if not os.path.isdir(subfolder_gpkg_path):
            continue

        gpkg_files = [name for name in os.listdir(subfolder_gpkg_path) if name.endswith(".gpkg")]
        print(f"Processing gpkg files in subfolder: {subfolder} (count={len(gpkg_files)})")

        # Loop over the gpkg files in the subfolder
        for gpkg_name in gpkg_files:
            gpkg_path = os.path.join(subfolder_gpkg_path, gpkg_name)

            # Check if gpkg_path is a file and has the .gpkg extension
            if not os.path.isfile(gpkg_path):
                continue

            # Read the gpkg file with geopandas and concatenate all layers into one dataframe
            print(f"Converting {gpkg_name} to csv file")
            gdf = gpd.read_file(gpkg_path, layer=0)
            suffix = gdf.crs if hasattr(gdf, "geometry") and gdf.geometry.name in gdf.columns else "None"

            df = pd.concat([gdf], ignore_index=True)

            # Create the corresponding output directory for the csv file
            output_dir = os.path.join(in_csv_path, subfolder)
            os.makedirs(output_dir, exist_ok=True)

            # Write the concatenated dataframe to a single CSV file with columns
            output_csv_path = os.path.join(output_dir, f"{os.path.splitext(gpkg_name)[0]}_{suffix}.csv")
            with open(output_csv_path, "w") as f:
                f.write(",".join(df.columns) + "\n")
                df.to_csv(f, header=False, index=False)


if __name__ == "__main__":
    main()
