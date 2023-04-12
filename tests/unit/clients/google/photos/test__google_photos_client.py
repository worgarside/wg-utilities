# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.google_photos.GooglePhotosClient`."""
from __future__ import annotations

from pytest import raises
from requests_mock import Mocker

from wg_utilities.clients import GooglePhotosClient
from wg_utilities.clients.google_photos import Album
from wg_utilities.clients.oauth_client import OAuthCredentials


def test_instantiation(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test that the `GooglePhotosClient` class can be instantiated."""

    client = GooglePhotosClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
    )

    assert isinstance(client, GooglePhotosClient)


def test_get_album_by_id_no_albums(
    google_photos_client: GooglePhotosClient,
    google_photos_album: Album,
    mock_requests: Mocker,
) -> None:
    """Test the `get_album_by_id` method with no known albums."""

    album = google_photos_client.get_album_by_id(album_id=google_photos_album.id)

    assert album == google_photos_album
    assert google_photos_client._albums == [google_photos_album]
    assert (
        mock_requests.last_request
        and mock_requests.last_request.url
        == f"https://photoslibrary.googleapis.com/v1/albums/{google_photos_album.id}"
    )


def test_get_album_by_id_known_album(
    google_photos_client: GooglePhotosClient,
    google_photos_album: Album,
    mock_requests: Mocker,
) -> None:
    """Test the `get_album_by_id` method with a known album."""

    # Populate the `_albums` property
    assert len(google_photos_client.albums) == 55

    mock_requests.reset_mock()

    assert (
        google_photos_client.get_album_by_id(album_id=google_photos_album.id)
        == google_photos_album
    )
    assert google_photos_album in google_photos_client._albums
    assert not mock_requests.request_history
    assert len(google_photos_client._albums) == 55


def test_get_album_by_id_unknown_album(
    google_photos_client: GooglePhotosClient,
    google_photos_album: Album,
    mock_requests: Mocker,
) -> None:
    """Test the `get_album_by_id` method with an album not in the cached list."""

    # Populate the `_albums` property
    assert len(google_photos_client.albums) == 55

    # Remove the album from the cached list
    assert google_photos_album in google_photos_client._albums
    google_photos_client._albums.remove(google_photos_album)
    assert google_photos_album not in google_photos_client._albums

    mock_requests.reset_mock()

    assert (
        google_photos_client.get_album_by_id(album_id=google_photos_album.id)
        == google_photos_album
    )
    assert google_photos_album in google_photos_client._albums
    assert (
        mock_requests.last_request
        and mock_requests.last_request.url
        == f"https://photoslibrary.googleapis.com/v1/albums/{google_photos_album.id}"
    )


def test_get_album_by_name(
    google_photos_client: GooglePhotosClient,
    google_photos_album: Album,
    mock_requests: Mocker,
) -> None:
    """Test the `get_album_by_name` method."""

    album = google_photos_client.get_album_by_name(album_name="Projects")

    assert album == google_photos_album
    assert len(google_photos_client._albums) == 55
    # Two requests: 55 albums, 50 albums per page
    assert len(mock_requests.request_history) == 2


def test_get_album_by_name_bad_name(
    google_photos_client: GooglePhotosClient,
) -> None:
    """Test the `get_album_by_name` method with a bad album name."""

    with raises(FileNotFoundError) as exc_info:
        google_photos_client.get_album_by_name(album_name="Naughty Pics of My Cat")

    assert (
        str(exc_info.value)
        == "Unable to find album with name 'Naughty Pics of My Cat'."
    )


def test_albums_property_no_known_albums(
    google_photos_client: GooglePhotosClient,
    google_photos_album: Album,
    mock_requests: Mocker,
) -> None:
    """Test the `albums` property."""

    assert not hasattr(google_photos_client, "_albums")
    assert not hasattr(google_photos_client, "_album_count")

    albums = google_photos_client.albums

    assert google_photos_client._album_count == len(albums) == 55
    assert all(isinstance(album, Album) for album in albums)

    mock_requests.reset_mock()
    # Shouldn't make another request as `_album_count` is set
    assert google_photos_album in google_photos_client.albums
    assert not mock_requests.request_history


def test_albums_property_some_known_albums(
    google_photos_client: GooglePhotosClient,
    google_photos_album: Album,
    mock_requests: Mocker,
) -> None:
    """Test the `albums` property with some known albums."""

    assert not hasattr(google_photos_client, "_albums")
    assert not hasattr(google_photos_client, "_album_count")

    _ = google_photos_client.get_album_by_id(album_id=google_photos_album.id)

    assert len(google_photos_client._albums) == 1
    assert not hasattr(google_photos_client, "_album_count")

    # Now repeat previous test; all behaviour should match.

    albums = google_photos_client.albums

    assert google_photos_client._album_count == len(albums) == 55
    assert all(isinstance(album, Album) for album in albums)

    mock_requests.reset_mock()
    # Shouldn't make another request as `_album_count` is set
    assert google_photos_album in google_photos_client.albums
    assert not mock_requests.request_history

    # Extra test to ensure it isn't a dumb appendment of all albums onto pre-cached
    # albums (i.e. no duplicates)
    assert len([album.id for album in google_photos_client._albums]) == len(
        {album.id for album in google_photos_client._albums}
    )
