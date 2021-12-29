"""Custom client for interacting with Spotify's Web API"""
from enum import Enum
from json import dumps

from requests import get

from spotipy import SpotifyOAuth


class AlbumType(Enum):
    """Enum for the different types of album Spotify supports"""

    SINGLE = "single"
    ALBUM = "album"
    COMPILATION = "compilation"


class SpotifyEntity:
    """Parent class for all Spotify entities (albums, artists, etc.)

    Args:
        json (dict): the JSON returned from the Spotify Web API which defines the
         entity
        spotify_client (SpotifyClient): a Spotify client, usually the one which
         retrieved this entity from the API
    """

    def __init__(self, json, spotify_client=None):
        self.json = json
        self._spotify_client = spotify_client

    @property
    def pretty_json(self):
        """
        Returns:
            str: a "pretty" version of the JSON, used for debugging etc.
        """
        return dumps(self.json, indent=4, default=str)

    @property
    def description(self):
        """
        Returns:
            str: the description of the entity
        """
        return self.json.get("description")

    @property
    def endpoint(self):
        """
        Returns:
            str: A link to the Web API endpoint providing full details of the entity
        """
        return self.json.get("href")

    @property
    def id(self):
        """
        Returns:
            str: The base-62 identifier for the entity
        """
        return self.json.get("id")

    @property
    def name(self):
        """
        Returns:
            str: the name of the entity
        """
        return self.json.get("name")

    def __gt__(self, other):
        return self.name.lower() > other.name.lower()

    def __lt__(self, other):
        return self.name.lower() < other.name.lower()

    def __str__(self):
        return f"{self.name} ({self.id})"


class User(SpotifyEntity):
    """A Spotify user, usually just the current user"""

    @property
    def name(self):
        """
        Returns:
            str: the display name of the User
        """

        return self.json.get("display_name")


class Track(SpotifyEntity):
    """A track on Spotify"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._artists = None

    @property
    def album(self):
        """
        Returns:
            Album: the album which this track is from
        """

        return Album(self.json.get("album", {}), self._spotify_client)

    @property
    def artists(self):
        """
        Returns:
            list(Artist): a list of the artists who contributed to this track
        """

        if not self._artists:
            self._artists = [
                Artist(item, self._spotify_client)
                for item in self.json.get("artists", [])
            ]

        return self._artists


class Artist(SpotifyEntity):
    """An artist on Spotify"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._albums = None

    @property
    def albums(self):
        """
        Returns:
            list: A list of albums this artist has contributed to
        """
        if not self._albums:
            self._albums = [
                Album(item, self._spotify_client)
                for item in self._spotify_client.get_items_from_url(
                    f"/artists/{self.id}/albums"
                )
            ]

        return self._albums


class Album(SpotifyEntity):
    """An album on Spotify"""

    def __init__(self, json, spotify_client=None):
        super().__init__(json, spotify_client)
        self._artists = None
        self._tracks = None

    @property
    def artists(self):
        """
        Returns:
            list: a list of artists that appear on this album
        """

        if not self._artists:
            self._artists = [
                Artist(item, self._spotify_client)
                for item in self.json.get("artists", [])
            ]

        return self._artists

    @property
    def tracks(self):
        """
        Returns:
            list: a list of tracks on this album
        """

        if not self._tracks:
            self._tracks = [
                Track(item, self._spotify_client)
                for item in self.json.get("tracks", {}).get("items", [])
            ]

            if next_url := self.json.get("next"):
                self._tracks.extend(
                    Track(item, self._spotify_client)
                    for item in self._spotify_client.get_items_from_url(next_url)
                )

        return self._tracks

    @property
    def type(self):
        """
        Returns:
            AlbumType: the type of album this is
        """

        return AlbumType[self.json.get("album_type", "").upper()]


class Playlist(SpotifyEntity):
    """A Spotify playlist"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tracks = None

    @property
    def tracks(self):
        """
        Returns:
            list: a list of tracks in this playlist
        """

        if not self._tracks:
            self._tracks = [
                Track(item.get("track", {}), self._spotify_client)
                for item in self._spotify_client.get_items_from_url(
                    f"/playlists/{self.id}/tracks"
                )
            ]

        return self._tracks

    @property
    def owner(self):
        """
        Returns:
            User: the Spotify user who owns this playlist
        """

        return User(self.json.get("owner", {}))

    def __gt__(self, other):
        if self.name.lower() == other.name.lower():
            if self.owner.id == self._spotify_client.current_user.id:
                return False

            if other.owner.id == self._spotify_client.current_user.id:
                return True

        return self.name.lower() > other.name.lower()

    def __lt__(self, other):
        if self.name.lower() == other.name.lower():

            if self.owner.id == self._spotify_client.current_user.id:
                return True

            if other.owner.id == self._spotify_client.current_user.id:
                return False

        return self.name.lower() < other.name.lower()

    def __str__(self):
        return f"{self.name} ({self.id}) - owned by {self.owner}"


class SpotifyClient:
    """Custom client for interacting with Spotify's Web API. For authentication
    purposes either an already-instantiated OAuth manager or the relevant credentials
    must be provided

    Args:
        client_id (str): the application's client ID
        client_secret (str): the application's client secret
        redirect_uri (str): the redirect URI for the applications
        oauth_manager (SpotifyOAuth): an already-instantiated OAuth manager which
         provides authentication for all API interactions
    """

    BASE_URL = "https://api.spotify.com/v1"

    def __init__(
        self,
        *,
        client_id=None,
        client_secret=None,
        redirect_uri="http://localhost:8080",
        oauth_manager=None,
    ):
        self.oauth_manager = oauth_manager or SpotifyOAuth(
            client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri
        )

        self._playlists = None
        self._current_user = None

    def _get(self, url, params=None):
        """Wrapper for get requests which covers authentication, URL parsing, etc etc

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """

        if not url.startswith(("http", "https")):
            url = f"{self.BASE_URL}{url}"

        res = get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
                "Host": "api.spotify.com",
            },
            params=params or {},
        )

        res.raise_for_status()

        return res

    def get_items_from_url(self, url, params=None, hard_limit=1000000):
        """Retrieve a list of items from a given URL, including pagination

        Args:
            url (str): the API endpoint which we're listing
            params (dict): any params to pass with the API request
            hard_limit (int): a hard limit to apply to the number of items returned (as
             opposed to the "soft" limit of 50 imposed by the API)

        Returns:
            list: a list of dicts representing the Spotify items
        """

        params = params or {}
        if "limit" not in params:
            params["limit"] = 50

        res = self._get(url, params=params)

        items = res.json().get("items", [])

        while (next_url := res.json().get("next")) and len(items) < hard_limit:
            res = self._get(next_url, params=params)
            items.extend(res.json().get("items", []))

        return items[:hard_limit]

    @property
    def access_token(self):
        """
        Returns:
            str: the web API access token
        """
        return self.oauth_manager.get_access_token(as_dict=False)

    @property
    def playlists(self):
        """
        Returns:
            list: a list of playlists owned by the current user
        """

        if not self._playlists:
            self._playlists = [
                Playlist(item, self)
                for item in self.get_items_from_url("/me/playlists")
            ]

        return self._playlists

    def get_playlists_by_name(self, name, return_all=False):
        """Gets Playlist instance(s) which have the given name

        Args:
            name (str): the name of the target playlist(s)
            return_all (bool): playlist names aren't unique - but most people keep them
             unique within their own collection of playlists. This boolean can be used
             to return either a list of all matching playlists, or just the single
             found playlist

        Returns:
            Union([list, Playlist]): the matched playlist(s)
        """

        matched_playlists = sorted(filter(lambda p: p.name == name, self.playlists))

        # Return a list of all matches
        if return_all:
            return matched_playlists

        try:
            return matched_playlists[0]
        except IndexError:
            pass

        return None

    def get_album_by_id(self, id_):
        """Get an album from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the album

        Returns:
            Album: an instantiated Album, from the API's response
        """

        return Album(self._get(f"/albums/{id_}").json(), self)

    def get_artist_by_id(self, id_):
        """Get an artist from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the artist

        Returns:
            Artist: an instantiated Artist, from the API's response
        """

        return Artist(self._get(f"/artists/{id_}").json(), self)

    def get_playlist_by_id(self, id_):
        """Get a playlist from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the playlist

        Returns:
            Playlist: an instantiated Playlist, from the API's response
        """

        if self._playlists:
            for plist in self.playlists:
                if plist.id == id_:
                    return plist

        return Playlist(self._get(f"/playlists/{id_}").json(), self)

    def get_track_by_id(self, id_):
        """Get a track from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the track

        Returns:
            Track: an instantiated Track, from the API's response
        """

        return Track(self._get(f"/tracks/{id_}").json(), self)

    @property
    def current_user(self):
        """Gets the current user's info

        Returns:
            User: an instance of the current Spotify user
        """
        if not self._current_user:
            self._current_user = User(self._get(f"{self.BASE_URL}/me").json())

        return self._current_user
