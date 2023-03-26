# pylint: disable=protected-access
"""Unit Tests for `clients.google_photos.Album`."""
from __future__ import annotations

from unittest.mock import patch

from pydantic import ValidationError
from pytest import mark
from requests import post

from tests.conftest import read_json_file
from wg_utilities.clients.google_photos import Album, GooglePhotosClient


def test_from_json_response_instantiation(
    google_photos_client: GooglePhotosClient,
) -> None:
    """Test instantiation of the Album class."""
    album = Album.from_json_response(
        read_json_file(
            # pylint: disable=line-too-long
            "aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json",
            host_name="google/photos/v1/albums",
        ),
        google_client=google_photos_client,
    )
    assert isinstance(album, Album)

    assert (
        album.cover_photo_base_url
        # pylint: disable=line-too-long
        == "https://lh3.googleusercontent.com/lr/RCCo5khGXpMEWzP4nn72QAVJxlUYiOBzJ1LikuRx1kwb8wSfUTnYjvAAdewR7fIyoh1h0tB7joBeifwKlbZmuooazBfyTqOdEms0raTswrYgDV27f3gi2aiBsdC933xCPuQDIbY1251NFgPd1HIZzADjHkMNlUYoGZgXjLKnYEFK2T-8uLjqOo3TmsNfzLZIVsaglu0FTRDK498vjSFSxwP5EXcciDfyD8KVUmuibBVYpGxNxV3F2Yc1dkqSrTq3kkTL3Yb9Zfd-M3MtuF4fxBADkYUK0Nr2i7bwdVCMPCJaCsFCzt5wgRxcNDJPcqK5T2sLQ3o3Fymc-aADt10Wc5omQ2zgHuIVoyyP25YC9DrzYqoUCQIvQ8KxDhV059pUkI2urVFJLbQYFPPHYZ5MGsyFVwgKoxbcuYceZncJ9GpPHw7pF2Y3gkw3I-_c0s8jILOvcvgCW-zczAIkXk1jqaK5af0gHJhsx4md35390JVOB9klZuogqE1NoDqsNlT0GdRaQRM-z8DGRjCX0GynjQF0dz3NBchorYRRYawHd1dOiNsZ9Clr30e7eOhCaFuHbR1Khjh9IGTPUxB74jdyUV7JBaHcJ3OBFQt53u6qTPjvPMilsLazJpLGS6p_BE3a6Dj7_2yYdkJJz7xVZKPbJP_gJ3ONx_YPUOgVV_VoTkrk6R-075Z4DhXEWhpr1zBg64IPiwg-i3EOut2OLChX0q_sgS2iPUIG1kfGNsyt7tpvAUBjDUv96rzgl9FwEJCauACTFemkfil3tlocUhW4cS-43BdOgApKFGCde4B1UHklAUNm78zfHrr_4tC9xQV7v9TmHFfDSf7EEp70PP2Wc03xH--tJELAqhhQWKkJbPMn518cYrnrsJx7MMjCfgraCXhJLRJPHAvwEUMDuPcZZvYARpTFnkhROBeTMOUIhHYyiLSHznoH0AGIHthp9h15kse9TiJGzZDcrd4AwVX-ccYhhRWN9-1m8YWDq9YZqq82-UBiusQMSjqIYQHMED5dnPkSeEqq"  # noqa: E501
    )
    assert (
        album.cover_photo_media_item_id
        # pylint: disable=line-too-long
        == "KEIr_NhmxOL1PmdmoHPxJiI5a54rR1y7TaS5Qqugk8YeEn01fOOdP6Bx7INDgwnUaCewI4hCfSHVgWtRt5ePYDL9XirPhtXp5g"
    )
    assert album.is_writeable is None
    assert album.media_items_count == 80
    assert album.share_info is None
    assert album.title == "Projects"


@mark.parametrize(  # type: ignore[misc]
    ("title", "expected"),
    (
        (
            "Title ",
            "Title",
        ),
        (
            " Title",
            "Title",
        ),
        (
            "Title",
            "Title",
        ),
        ("", ValueError("Album title cannot be empty.")),
    ),
)
def test_album_title_validation(
    google_photos_client: GooglePhotosClient,
    title: str,
    expected: str | ValidationError,
) -> None:
    """Test validation of the album title."""

    album_json = read_json_file(
        # pylint: disable=line-too-long
        "aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json",
        host_name="google/photos/v1/albums",
    )

    album_json["title"] = title

    try:
        actual = Album.from_json_response(
            album_json,
            google_client=google_photos_client,
        ).title
    except ValidationError as exc:
        assert repr(exc.raw_errors[0].exc) == repr(expected)  # type: ignore[union-attr]
    else:
        assert actual == expected


def test_media_items_property(
    google_photos_album: Album,
) -> None:
    """Test the media_items property."""

    assert not hasattr(google_photos_album, "_media_items")

    with patch.object(
        google_photos_album.google_client,
        "get_items",
        wraps=google_photos_album.google_client.get_items,
    ) as mock_get_items:
        media_items = google_photos_album.media_items

        mock_get_items.assert_called_once_with(
            "/mediaItems:search",
            method_override=post,
            list_key="mediaItems",
            params={"albumId": google_photos_album.id, "pageSize": 100},
        )

        mock_get_items.reset_mock()

        _ = google_photos_album.media_items

        mock_get_items.assert_not_called()

    assert len(media_items) == google_photos_album.media_items_count
    assert google_photos_album._media_items == media_items
    assert all(item in google_photos_album for item in media_items)
