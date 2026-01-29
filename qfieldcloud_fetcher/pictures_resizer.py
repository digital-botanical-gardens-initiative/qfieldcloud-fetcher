#!/usr/bin/env python3

import argparse
import os
import shutil
import tempfile
from typing import Optional

from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError

# Try to enable HEIF/HEIC support transparently
try:
    from pillow_heif import register_heif_opener  # type: ignore
    register_heif_opener()
except Exception:
    # If not installed, HEIF files will raise UnidentifiedImageError and be skipped with a message
    pass

# Loads environment variables
load_dotenv()

# Access the environment variables
data_path = os.getenv("DATA_PATH")

# Construct folders paths
in_jpg_path = f"{data_path}/renamed_pictures"
out_jpg_path = f"{data_path}/renamed_compressed_pictures"

# Max file size (bytes)
MAX_SIZE = 5_000_000  # 5 MB
# Compression bounds
QUALITY_START = 85
QUALITY_MIN = 30
QUALITY_STEP = 5


def _save_jpeg_to_tmp(img: Image.Image, tmp_dir: str, base_name: str, quality: int) -> str:
    """Save image as JPEG into a temp path and return the filepath."""
    # Ensure proper mode
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Normalize orientation from EXIF (avoids rotated results)
    img = ImageOps.exif_transpose(img)

    tmp_path = os.path.join(tmp_dir, f"{os.path.splitext(base_name)[0]}.__tmp__.jpg")
    # Use progressive+optimize for better size at same quality
    img.save(tmp_path, format="JPEG", quality=quality, optimize=True, progressive=True)
    return tmp_path


def compress_image(root: str, filename: str, layer: str, project: str) -> None:
    filepath = os.path.join(root, filename)
    processed_folder = os.path.join(out_jpg_path, project, layer)
    os.makedirs(processed_folder, exist_ok=True)

    # If already small enough, just move as-is
    try:
        current_size = os.path.getsize(filepath)
    except FileNotFoundError:
        print(f"⚠️ Missing file, skipping: {filepath}")
        return

    if current_size <= MAX_SIZE:
        # Move file to new folder
        dst = os.path.join(processed_folder, filename)
        shutil.move(filepath, dst)
        print(f"{filepath} is already small enough.")
        return

    # Open the image (handle unreadable images gracefully)
    try:
        img = Image.open(filepath)
    except UnidentifiedImageError:
        print(f"⚠️ Skipping (unreadable image; consider installing pillow-heif for HEIF/HEIC): {filepath}")
        return
    except Exception as e:
        print(f"⚠️ Skipping (error opening): {filepath} — {e}")
        return

    print(f"Compressing {filepath}...")

    # Work in a temp directory to avoid corrupting originals if something fails
    with tempfile.TemporaryDirectory() as tmpdir:
        quality = QUALITY_START
        best_tmp_path: Optional[str] = None
        best_size = float("inf")

        # Try decreasing qualities until under target or we hit the lower bound
        while quality >= QUALITY_MIN:
            tmp_out = _save_jpeg_to_tmp(img, tmpdir, filename, quality)
            out_size = os.path.getsize(tmp_out)

            # Track best (smallest) so far even if still > MAX_SIZE
            if out_size < best_size:
                best_size = out_size
                best_tmp_path = tmp_out

            if out_size <= MAX_SIZE:
                break

            quality -= QUALITY_STEP

        # If for some reason saving failed
        if not best_tmp_path or not os.path.exists(best_tmp_path):
            print(f"⚠️ Failed to compress (no output written): {filepath}")
            return

        # Decide destination filename: keep .jpg extension
        dest_path = os.path.join(processed_folder, os.path.splitext(filename)[0] + ".jpg")

        # Move the best temp file into place
        os.replace(best_tmp_path, dest_path)

    # Only after successful write do we remove the original from input tree
    try:
        os.remove(filepath)
    except Exception:
        # Not critical; continue
        pass

    final_size = os.path.getsize(dest_path)
    if final_size <= MAX_SIZE:
        print(f"{dest_path} compressed successfully.")
    else:
        # This can happen for extremely large images; still moved the best attempt
        print(f"⚠️ {dest_path} could not reach ≤ {MAX_SIZE} bytes; kept best effort ({final_size} bytes).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compress renamed pictures for downstream use.")
    parser.add_argument("--project", default=None, help="Only process a single project folder by name.")
    parser.add_argument("--progress-every", type=int, default=100, help="Print progress every N files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.project:
        print(f"Filtering to project: {args.project}")

    processed = 0
    for root, _dirs, files in os.walk(in_jpg_path):
        # Get layer
        layer = os.path.basename(root)
        # Get project
        project = os.path.basename(os.path.dirname(root))
        if args.project and project != args.project:
            continue
        for filename in files:
            # Your pipeline only targets JPG-named files; HEIF wrongly named as .jpg will still be handled
            if filename.lower().endswith(".jpg"):
                compress_image(root, filename, layer, project)
                processed += 1
                if args.progress_every > 0 and processed % args.progress_every == 0:
                    print(f"Compression progress: processed={processed}")

    print(f"Compression complete: processed={processed}")


if __name__ == "__main__":
    main()
