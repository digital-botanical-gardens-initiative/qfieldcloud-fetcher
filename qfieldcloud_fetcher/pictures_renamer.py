#!/usr/bin/env python3

import os
import re

from dotenv import load_dotenv

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")

# Construct folders paths
in_jpg_path = f"{data_path}/in/pictures"
out_jpg_path = f"{data_path}/renamed_pictures"

for root, _dirs, files in os.walk(in_jpg_path):
    for filename in files:
        # split the filename into base and extension
        base, ext = os.path.splitext(filename)
        # replace spaces with underscores in the base filename
        base = base.replace(" ", "_")
        # remove non-alphanumeric characters from base filename
        base = re.sub(r"[^\w\s]", "", base)
        # join the modified base filename and original extension
        new_filename = base + ext
        # rename file
        os.rename(os.path.join(root, filename), os.path.join(root, new_filename))
