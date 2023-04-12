"""Unit tests for the `MediaItem` class."""

from __future__ import annotations

from pathlib import Path

from pytest import LogCaptureFixture, fixture, mark

from tests.conftest import YieldFixture, read_json_file
from wg_utilities.clients.google_photos import GooglePhotosClient, MediaItem, MediaType


@fixture(scope="function", name="temp_dir_cleanup")
def _temp_dir_cleanup(temp_dir: Path) -> YieldFixture[None]:
    """Fixture for cleaning up the temporary directory.

    Currently skips:
    - **/oauth_credentials/**
    """
    yield

    for item in temp_dir.rglob("*"):
        if "oauth_credentials" in item.parts or not item.is_file():
            continue
        item.unlink()


def test_download_method_image(
    media_item_image: MediaItem,
    temp_dir: Path,
    temp_dir_cleanup: None,  # pylint: disable=unused-argument
) -> None:
    """Test the download method."""

    assert media_item_image.local_path == Path("undefined")

    media_item_image.download(target_directory=temp_dir)

    assert (
        media_item_image.local_path
        == temp_dir
        / media_item_image.creation_datetime.strftime("%Y/%m/%d")
        / media_item_image.filename
    )

    # Prove that the image was downloaded, and is actually a JPEG image
    with open(media_item_image.local_path, "rb") as image_file:
        assert image_file.read(3) == b"\xff\xd8\xff"


def test_download_method_video(
    media_item_video: MediaItem,
    temp_dir: Path,
    temp_dir_cleanup: None,  # pylint: disable=unused-argument
) -> None:
    """Test the download method."""

    assert media_item_video.local_path == Path("undefined")

    media_item_video.download(target_directory=str(temp_dir))

    assert (
        media_item_video.local_path
        == temp_dir
        / media_item_video.creation_datetime.strftime("%Y/%m/%d")
        / media_item_video.filename
    )

    # Prove that the video was downloaded, and is actually a MP4 video
    with open(media_item_video.local_path, "rb") as video_file:
        assert video_file.read(4) == b"\x00\x00\x00\x1c"


def test_download_method_no_force(
    media_item_image: MediaItem,
    temp_dir: Path,
    caplog: LogCaptureFixture,
    temp_dir_cleanup: None,  # pylint: disable=unused-argument
) -> None:
    """Test `download` behaves as expected with the `force_download` argument."""

    media_item_image.download(target_directory=temp_dir)

    original_path = media_item_image.local_path

    assert original_path.is_file()
    assert not caplog.records

    media_item_image.download(target_directory=temp_dir, force_download=True)

    assert original_path == media_item_image.local_path
    assert original_path.is_file()
    assert not caplog.records

    media_item_image.download(target_directory=temp_dir)

    assert original_path == media_item_image.local_path
    assert original_path.is_file()
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert (
        caplog.records[0].message
        == f"File already exists at `{original_path}` and `force_download` is `False`;"
        " skipping download."
    )


def test_bytes_property(
    media_item_image: MediaItem,
    temp_dir_cleanup: None,  # pylint: disable=unused-argument
) -> None:
    """Test the bytes property."""

    assert media_item_image.local_path == Path("undefined")

    # The bytes property downloads the file if it doesn't exist, causing the
    # `_local_path` attribute to be set by the time the second half of the
    # assertion is evaluated
    assert media_item_image.bytes == media_item_image.local_path.read_bytes()


def test_is_downloaded_property(
    media_item_image: MediaItem,
    temp_dir: Path,
    temp_dir_cleanup: None,  # pylint: disable=unused-argument
) -> None:
    """Test the is_downloaded property."""

    assert media_item_image.local_path == Path("undefined")
    assert not media_item_image.is_downloaded

    media_item_image.download(target_directory=temp_dir)

    assert media_item_image.is_downloaded


@mark.parametrize(
    ("mime_type", "expected_media_type"),
    (
        (
            "audio/aac",
            MediaType.UNKNOWN,
        ),
        (
            "application/x-abiword",
            MediaType.UNKNOWN,
        ),
        (
            "application/x-freearc",
            MediaType.UNKNOWN,
        ),
        (
            "image/avif",
            MediaType.IMAGE,
        ),
        (
            "video/x-msvideo",
            MediaType.VIDEO,
        ),
        (
            "image/bmp",
            MediaType.IMAGE,
        ),
        (
            "application/x-bzip",
            MediaType.UNKNOWN,
        ),
        (
            "text/css",
            MediaType.UNKNOWN,
        ),
        (
            "text/csv",
            MediaType.UNKNOWN,
        ),
        (
            "audio/mpeg",
            MediaType.UNKNOWN,
        ),
        (
            "video/mp4",
            MediaType.VIDEO,
        ),
        (
            "video/mpeg",
            MediaType.VIDEO,
        ),
        (
            "audio/ogg",
            MediaType.UNKNOWN,
        ),
        (
            "video/ogg",
            MediaType.VIDEO,
        ),
        (
            "font/otf",
            MediaType.UNKNOWN,
        ),
        (
            "image/png",
            MediaType.IMAGE,
        ),
        (
            "application/pdf",
            MediaType.UNKNOWN,
        ),
        (
            "image/svg+xml",
            MediaType.IMAGE,
        ),
        (
            "font/ttf",
            MediaType.UNKNOWN,
        ),
        (
            "text/plain",
            MediaType.UNKNOWN,
        ),
        (
            "audio/wav",
            MediaType.UNKNOWN,
        ),
        (
            "audio/webm",
            MediaType.UNKNOWN,
        ),
        (
            "video/webm",
            MediaType.VIDEO,
        ),
        (
            "image/webp",
            MediaType.IMAGE,
        ),
        (
            "font/woff",
            MediaType.UNKNOWN,
        ),
        (
            "application/xml",
            MediaType.UNKNOWN,
        ),
        (
            "application/zip",
            MediaType.UNKNOWN,
        ),
    ),
)
def test_media_type_property(
    mime_type: str,
    expected_media_type: MediaType,
    google_photos_client: GooglePhotosClient,
) -> None:
    """Test the media_type property."""

    media_item_json = read_json_file(
        # pylint: disable=line-too-long
        ":search/pagesize=100&albumid=aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json",
        host_name="google/photos/v1/mediaitems",
    )["mediaItems"][0]
    media_item_json["mimeType"] = mime_type

    media_item = MediaItem.from_json_response(
        media_item_json, google_client=google_photos_client
    )

    assert media_item.media_type == expected_media_type
