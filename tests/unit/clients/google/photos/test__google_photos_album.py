# pylint: disable=protected-access
"""Unit Tests for `clients.google_photos.Album`."""
from __future__ import annotations

from unittest.mock import patch

from pydantic import ValidationError
from pytest import mark
from requests import post

from conftest import read_json_file
from wg_utilities.clients.google_photos import Album, GooglePhotosClient


def test_from_json_response_instantiation(
    google_photos_client: GooglePhotosClient,
) -> None:
    """Test instantiation of the Album class."""
    album = Album.from_json_response(
        read_json_file(
            # pylint: disable=line-too-long
            "v1/albums/aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json",
            host_name="google/photos",
        ),
        google_client=google_photos_client,
    )
    assert isinstance(album, Album)

    assert (
        album.cover_photo_base_url
        # pylint: disable=line-too-long
        == "https://lh3.googleusercontent.com/lr/AVc_9_kRocc2n6UNB-1HOqXTZBDQ9ZW-HhbvOif5EUtOpc6cxdofFF8sqglAPtX4PBWc9zhQfebmWwA-mR85YryW-BDXc4w5tOCdJ7_nzJ9ArvcAkT7iRCKtaOajvOuoKupEgslFgxz0kvJMUPCsBeV6D7Qh2J14rsvbfjX27PhNRGKQhjdmPbmmjwU2zmgaWVmW5gl2F1WQ5fBugTgIHfjKfZGLfjOdDjVFH9J0poZlEz5iDQflILYdPBrAV4PV0YYJGbKWNSb48Ns6l9wyYS0Xfcol3p6jmHAY-7wcuvHHNw_dtZd0v4ABOdXME_2VlC0V1o0jKGYAV-2B-97oaBzSEq66_TbU88tYNzDzl42X2FONkvjYmpNtBj34Hoy3oZFBytkd-QwhsJEUdNX3Kv6BpmB-tnreVNArgQuP4o8WiotkrC1elfyjbT-bYdzK-z_vRljgN2_Ft8F3tPk9x_3bX2uxrWZXT88FC5p28fXMVcbbhQoYyioSnlteLp1EW1AGD48ptzOBRV0mzB3xdxXOH3q-sIfaTdcd2S3UVfR9zQuJAePGvT_d3MWSPE6LT-BpWHXS6gF9gKZyGgknw1B0NsBEuQaqK2Su3kRq2hzCu-VLReY1K7OY91QUfXikpTDBXDTnr2_hM8-INfRYKC5FS9O7oIlnwCHd2UXIV-kQrmkW7DtWcMQCPAOUAK1aRocTip8C9WHlCrbbZ-uYAyuIryb8ukqXypjymUiyWutoMJnjHZPjEhslghVrufyTS6jK4AIS6y0Fc6ZkW4CyGn1wHvqa7ovGsxoWJsPCKmzi_13DJLrXNUn9ROuZTaKo4YF7bzSm2eNZHbZvPykmD0XaU7yoZG6xHC-n_tRfg6Br-iZ1BLmR93GmUBYDbEAxG8Mwr6N6lgpQJaYt_zGFUGa5VPjG8ErnEl2XZssf6y29spThcpx_Jq_gnZRnIs4bPAsF0my5GFcUcax5NiG5BTVK_ksPDQ7wcTnU7SBRGQBA73gatWQ0q5cWdpKsSWku4ZokFFB4TOQlnyDfaFuMfDsaH0adfT3Pgi9OuNcZye1zB80kfH08NpvhgI402nwwGI"  # noqa: E501
    )
    assert (
        album.cover_photo_media_item_id
        # pylint: disable=line-too-long
        == "KEIr_NhmxOL1PmdmoHPxJiI5a54rR1y7TaS5Qqugk8YeEn01fOOdP6Bx7INDgwnUaCewI4hCfSHVgWtRt5ePYDL9XirPhtXp5g"
    )
    assert album.is_writeable is None
    assert album.media_items_count == 68
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
        "v1/albums/aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json",
        host_name="google/photos",
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
