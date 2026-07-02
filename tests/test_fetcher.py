from qfieldcloud_fetcher.fetcher import jpg_layer_and_file_name


def test_jpg_layer_and_file_name_with_layer():
    assert jpg_layer_and_file_name("DCIM/observations/IMG_0001.JPG") == ("observations", "IMG_0001.JPG")


def test_jpg_layer_and_file_name_with_flat_dcim_file():
    assert jpg_layer_and_file_name("DCIM/IMG_0001.JPG") == ("unknown", "IMG_0001.JPG")


def test_jpg_layer_and_file_name_with_url_and_nested_file_path():
    url = "https://example.org/qfieldcloud/api/v1/files/project-id/DCIM/observations/subdir/IMG_0001.JPG"

    assert jpg_layer_and_file_name(url) == ("observations", "subdir/IMG_0001.JPG")


def test_jpg_layer_and_file_name_without_dcim():
    assert jpg_layer_and_file_name("IMG_0001.JPG") == ("unknown", "IMG_0001.JPG")
