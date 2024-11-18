#!/usr/bin/env python3

import os
import re

from dotenv import load_dotenv

# Loads environment variables
load_dotenv()

# Access the environment variables
in_jpg_path = os.getenv("IN_JPG_PATH")

root_folder = str(in_jpg_path)

for root, _dirs, files in os.walk(root_folder):
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
