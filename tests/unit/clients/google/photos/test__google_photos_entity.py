"""Unit Test for `wg_utilities.clients.google_photos.GooglePhotosEntity`."""

from __future__ import annotations

from wg_utilities.clients.google_photos import GooglePhotosClient, GooglePhotosEntity

GooglePhotosEntity.model_rebuild()


def test_from_json_response_instantiation(
    google_photos_client: GooglePhotosClient,
) -> None:
    """Test instantiation of the GooglePhotosEntity class."""
    google_photos_entity = GooglePhotosEntity.from_json_response(
        {  # type: ignore[arg-type]
            "id": "test-id",
            "productUrl": "https://photos.google.com/lr/photo/test-id",
        },
        google_client=google_photos_client,
    )
    assert isinstance(google_photos_entity, GooglePhotosEntity)

    assert google_photos_entity.model_dump() == {
        "id": "test-id",
        "productUrl": "https://photos.google.com/lr/photo/test-id",
    }

    assert google_photos_entity.id == "test-id"
    assert (
        google_photos_entity.product_url == "https://photos.google.com/lr/photo/test-id"
    )
    assert google_photos_entity.google_client == google_photos_client
