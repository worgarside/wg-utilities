"""Fixtures for the Spotify client tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from re import IGNORECASE
from re import compile as compile_regex
from typing import TYPE_CHECKING

import pytest

from tests.conftest import FLAT_FILES_DIR, get_flat_file_from_url, read_json_file
from wg_utilities.clients.spotify import Album as SpotifyAlbum
from wg_utilities.clients.spotify import (
    Artist,
    Playlist,
    SpotifyClient,
    SpotifyEntity,
    Track,
    User,
)

if TYPE_CHECKING:
    from pathlib import Path

    from requests_mock import Mocker
    from requests_mock.request import _RequestObjectProxy
    from requests_mock.response import _Context

    from wg_utilities.clients._spotify_types import SpotifyBaseEntityJson
    from wg_utilities.clients.oauth_client import OAuthCredentials
    from wg_utilities.functions.json import JSONObj


def snapshot_id_request(playlist_id: str, jwt: str) -> dict[str, str | dict[str, str]]:
    """Create a `mock_requests` request for assertions."""
    return {
        "method": "GET",
        "url": f"{SpotifyClient.BASE_URL}/playlists/{playlist_id}?fields=snapshot_id",
        "headers": {"Authorization": f"Bearer {jwt}"},
    }


def spotify_create_playlist_callback(
    request: _RequestObjectProxy,
    _: _Context,
) -> JSONObj:
    """Provide fake responses for mock requests to create a new playlist.

    Args:
        request (_RequestObjectProxy): the request object from the `requests` session
        _: the context object from the `requests` session (unused)

    Returns:
        JSONObj: the JSON response
    """
    res = read_json_file("spotify/v1/users/worgarside/playlists.json")

    res["collaborative"] = request.json()["collaborative"] is True
    res["public"] = request.json()["public"] is True

    return res


@pytest.fixture(name="spotify_album")
def spotify_album_(spotify_client: SpotifyClient) -> SpotifyAlbum:
    """Fixture for creating a Spotify `Album` instance.

    3210 (Ross from Friends Remix)
    https://open.spotify.com/track/5U5X1TnRhnp9GogRfaE9XQ
    """
    return SpotifyAlbum.from_json_response(
        read_json_file("v1/albums/4julBAGYv4WmRXwhjJ2LPD.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@pytest.fixture(name="spotify_artist")
def spotify_artist_(spotify_client: SpotifyClient) -> Artist:
    """Fixture for creating a Spotify `Artist` instance.

    Ross from Friends
    https://open.spotify.com/artist/1Ma3pJzPIrAyYPNRkp3SUF
    """
    return Artist.from_json_response(
        read_json_file("v1/artists/1Ma3pJzPIrAyYPNRkp3SUF.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@pytest.fixture(name="spotify_client")
def spotify_client_(
    fake_oauth_credentials: OAuthCredentials,
    temp_dir: Path,
    mock_requests: Mocker,  # noqa: ARG001
) -> SpotifyClient:
    """Fixture for creating a `SpotifyClient` instance."""
    (
        creds_cache_path := temp_dir / "oauth_credentials/oauth_credentials.json"
    ).write_text(fake_oauth_credentials.model_dump_json(exclude_none=True))

    return SpotifyClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        log_requests=True,
        creds_cache_path=creds_cache_path,
    )


@pytest.fixture(name="spotify_entity")
def spotify_entity_(
    spotify_client: SpotifyClient,
) -> SpotifyEntity[SpotifyBaseEntityJson]:
    """Fixture for creating a `SpotifyEntity` instance."""
    return SpotifyEntity.from_json_response(
        {
            "href": f"{SpotifyClient.BASE_URL}/artists/0gxyHStUsqpMadRV0Di1Qt",
            "id": "0gxyHStUsqpMadRV0Di1Qt",
            "uri": "spotify:artist:0gxyHStUsqpMadRV0Di1Qt",
            "external_urls": {
                "spotify": "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt",
            },
        },
        spotify_client=spotify_client,
    )


@pytest.fixture(name="spotify_playlist")
def spotify_playlist_(spotify_client: SpotifyClient) -> Playlist:
    """Fixture for creating a `Playlist` instance.

    Chill Electronica
    https://open.spotify.com/playlist/2lMx8FU0SeQ7eA5kcMlNpX
    """
    playlist = Playlist.from_json_response(
        read_json_file("v1/playlists/2lmx8fu0seq7ea5kcmlnpx.json", host_name="spotify"),
        spotify_client=spotify_client,
    )

    playlist._live_snapshot_id = playlist.snapshot_id
    playlist._live_snapshot_id_timestamp = datetime.now(UTC) + timedelta(hours=21)

    return playlist


@pytest.fixture(name="spotify_playlist_alt")
def spotify_playlist_alt_(spotify_client: SpotifyClient) -> Playlist:
    """Fixture for creating an an alternate `Playlist` instance.

    JAMBOX Jams
    https://open.spotify.com/playlist/4Vv023MaZsc8NTWZ4WJvIL
    """
    return Playlist.from_json_response(
        read_json_file("v1/playlists/4vv023mazsc8ntwz4wjvil.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@pytest.fixture(name="spotify_track")
def spotify_track_(spotify_client: SpotifyClient) -> Track:
    """Fixture for creating a `Track` instance."""
    return Track.from_json_response(
        read_json_file("v1/tracks/27cgqh0vrhvem61ugtnord.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@pytest.fixture(name="spotify_user")
def spotify_user_(spotify_client: SpotifyClient) -> User:
    """Fixture for creating a Spotify User instance."""
    return User.from_json_response(
        read_json_file("v1/me.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@pytest.fixture(name="mock_requests", autouse=True)
def mock_requests_(mock_requests_root: Mocker) -> Mocker:
    """Fixture for mocking sync HTTP requests."""
    for path_object in (spotify_dir := FLAT_FILES_DIR / "json" / "spotify" / "v1").rglob(
        "*",
    ):
        if path_object.is_dir():
            mock_requests_root.get(
                SpotifyClient.BASE_URL + "/" + str(path_object.relative_to(spotify_dir)),
                json=get_flat_file_from_url,
            )

    for pattern in (
        # Matches `https://api.spotify.com/v1/<entity_type>s/<entity_id>`
        compile_regex(
            r"^https:\/\/api\.spotify\.com\/v1\/(playlists|tracks|albums|artists|audio\-features|users)\/([a-z0-9]{4,22})$",
            flags=IGNORECASE,
        ),
        # Matches `https://api.spotify.com/v1/artists/<entity_id>/albums`
        compile_regex(
            r"^https:\/\/api\.spotify\.com\/v1\/artists/([a-z0-9]{22})/albums(\?limit=50)?$",
            flags=IGNORECASE,
        ),
    ):
        mock_requests_root.get(
            pattern,
            json=get_flat_file_from_url,
        )

    # Special case because it goes to a single file, not a directory with
    # querystring-files
    mock_requests_root.get(
        SpotifyClient.BASE_URL + "/me/player/currently-playing",
        json=get_flat_file_from_url,
    )

    for method in ("post", "put", "delete"):
        for entity_type in ("albums", "following", "tracks"):
            mock_requests_root.register_uri(
                method,
                f"{SpotifyClient.BASE_URL}/me/{entity_type}",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
            )

        mock_requests_root.register_uri(
            method,
            # Matches `/v1/playlists/<playlist id>/followers`
            compile_regex(
                r"^https:\/\/api\.spotify\.com\/v1\/playlists/([a-z0-9]{22})/followers",
                flags=IGNORECASE,
            ),
            status_code=HTTPStatus.OK,
            reason=HTTPStatus.OK.phrase,
        )

        mock_requests_root.register_uri(
            method,
            # Matches `/v1/playlists/<playlist id>/tracks`
            compile_regex(
                r"^https:\/\/api\.spotify\.com\/v1\/playlists/([a-z0-9]{22})/tracks",
                flags=IGNORECASE,
            ),
            status_code=HTTPStatus.OK,
            reason=HTTPStatus.OK.phrase,
            json={"snapshot_id": "MTAsZDVmZjMjJhZTVmZjcxOGNlMA=="},
        )

    mock_requests_root.post(
        f"{SpotifyClient.BASE_URL}/users/worgarside/playlists",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json=spotify_create_playlist_callback,
    )

    return mock_requests_root
