import subprocess
from datetime import datetime

from qfieldcloud_fetcher.pictures_metadata_editor import build_exiftool_command, is_thumbnail_ifd1_error


def test_is_thumbnail_ifd1_error_detects_exiftool_stderr():
    result = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="0 image files updated",
        stderr="Error: Error reading ThumbnailImage data in IFD1 - image.jpg",
    )

    assert is_thumbnail_ifd1_error(result)


def test_build_exiftool_command_can_drop_ifd1_thumbnail():
    command = build_exiftool_command(
        "/repo/qfieldcloud_fetcher/exiftool/exiftool",
        "emi_external_id:dbgi_012074",
        "emi_collector:Jane Doe",
        "emi_collector_orcid:0000-0000",
        "emi_collector_inat:jane",
        "46.8",
        "7.1",
        datetime(2026, 4, 29, 13, 1, 26),
        "/tmp/image.jpg",
        drop_ifd1_thumbnail=True,
    )

    assert command[1] == "-IFD1:ThumbnailImage="
    assert "-Subject=emi_collector:Jane Doe" in command
    assert "/tmp/image.jpg" in command
