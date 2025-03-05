#!/usr/bin/env python3

import os
import shutil

from dotenv import load_dotenv
from PIL import Image

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")

# Construct folders paths
in_jpg_path = f"{data_path}/renamed_pictures"
out_jpg_path = f"{data_path}/renamed_compressed_pictures"


def compress_image(root: str, filename: str, layer: str, project: str) -> None:
    # Set maximum file size
    max_size = 5000000  # 5MB
    # Construct file path
    filepath = os.path.join(root, filename)
    # Construct path to new folder
    processed_folder = os.path.join(out_jpg_path, project, layer)
    # Check that path exists
    os.makedirs(processed_folder, exist_ok=True)
    img = Image.open(filepath)
    if os.path.getsize(filepath) <= max_size:
        # Move file to new folder
        shutil.move(filepath, os.path.join(processed_folder, filename))
        print(f"{filepath} is already small enough.")
        return
    else:
        print(f"Compressing {filepath}...")
        img.save(filepath, optimize=True, quality=80)
        while os.path.getsize(filepath) > max_size:
            img.save(filepath, optimize=True, quality=img.info["quality"] - 5)
        # Move file to new folder
        shutil.move(filepath, os.path.join(processed_folder, filename))
        print(f"{filepath} compressed successfully.")


for root, _dirs, files in os.walk(in_jpg_path):
    for filename in files:
        # Get layer
        layer = os.path.basename(root)
        # Get project
        project = os.path.basename(os.path.dirname(root))
        if filename.endswith(".jpg"):
            compress_image(root, filename, layer, project)
