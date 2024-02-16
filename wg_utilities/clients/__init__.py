"""Useful clients for commonly accessed APIs/services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .json_api_client import JsonApiClient

try:
    from .google_calendar import GoogleCalendarClient
    from .google_drive import IMR, GoogleDriveClient, ItemMetadataRetrieval
    from .google_fit import GoogleFitClient
    from .google_photos import GooglePhotosClient
    from .monzo import MonzoClient
    from .oauth_client import OAuthClient
    from .spotify import SpotifyClient
    from .truelayer import TrueLayerClient
except ImportError as exc:  # pragma: no cover
    # This is to allow JSONApiClient to still be imported without the other clients'
    # dependencies being installed. The TYPE_CHECKING check is to prevent mypy from
    # thinking that the clients are all `_NotImplemented`.
    if not TYPE_CHECKING:
        import_exc = exc
        _NOT_IMPLEMENTED_ERROR = NotImplementedError(
            "This entity is not implemented, please install `wg-utilities[clients]`",
        )

        class _NotImplementedMeta(type):
            def __getattribute__(cls, _: str) -> Any:
                raise _NOT_IMPLEMENTED_ERROR from import_exc

        class _NotImplemented(metaclass=_NotImplementedMeta):
            def __init__(self, *_: Any, **__: Any) -> None:
                raise _NOT_IMPLEMENTED_ERROR from import_exc

        GoogleCalendarClient = _NotImplemented
        GoogleDriveClient = _NotImplemented
        GoogleFitClient = _NotImplemented
        GooglePhotosClient = _NotImplemented
        ItemMetadataRetrieval = _NotImplemented
        IMR = _NotImplemented
        MonzoClient = _NotImplemented
        OAuthClient = _NotImplemented
        SpotifyClient = _NotImplemented
        TrueLayerClient = _NotImplemented


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
