#!/usr/bin/env python3

import os

from dotenv import load_dotenv
from PIL import Image

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")

# Construct folders paths
in_jpg_path = f"{data_path}/in/pictures"


def compress_image(filepath: str) -> None:
    max_size = 5000000  # 5MB
    img = Image.open(filepath)
    if os.path.getsize(filepath) <= max_size:
        print(f"{filepath} is already small enough.")
        return
    else:
        print(f"Compressing {filepath}...")
        img.save(filepath, optimize=True, quality=80)
        while os.path.getsize(filepath) > max_size:
            img.save(filepath, optimize=True, quality=img.info["quality"] - 5)
        print(f"{filepath} compressed successfully.")


for root, _dirs, files in os.walk(in_jpg_path):
    for filename in files:
        if filename.endswith(".jpg"):
            filepath = os.path.join(root, filename)
            compress_image(filepath)
