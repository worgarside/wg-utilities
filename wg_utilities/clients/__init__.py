"""Useful clients for commonly accessed APIs/services."""

from __future__ import annotations

from .google_calendar import GoogleCalendarClient
from .google_drive import IMR, GoogleDriveClient, ItemMetadataRetrieval
from .google_fit import GoogleFitClient
from .google_photos import GooglePhotosClient
from .json_api_client import JsonApiClient
from .monzo import MonzoClient
from .oauth_client import OAuthClient
from .spotify import SpotifyClient
from .truelayer import TrueLayerClient

__all__ = [
    "GoogleCalendarClient",
    "GoogleDriveClient",
    "GoogleFitClient",
    "GooglePhotosClient",
    "ItemMetadataRetrieval",
    "IMR",
    "JsonApiClient",
    "MonzoClient",
    "OAuthClient",
    "SpotifyClient",
    "TrueLayerClient",
]
