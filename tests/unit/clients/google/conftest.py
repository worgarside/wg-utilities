"""Fixtures for Google clients."""
from __future__ import annotations

from json import loads
from pathlib import Path
from re import fullmatch

from pydantic.fields import Field
from pytest import FixtureRequest, fixture
from requests_mock import Mocker

from tests.conftest import (
    FLAT_FILES_DIR,
    YieldFixture,
    get_flat_file_from_url,
    read_json_file,
)
from wg_utilities.clients.google_calendar import Calendar, Event, GoogleCalendarClient
from wg_utilities.clients.google_drive import (
    Directory,
    Drive,
    File,
    GoogleDriveClient,
    ItemMetadataRetrieval,
)
from wg_utilities.clients.google_fit import DataSource, GoogleFitClient
from wg_utilities.clients.google_photos import Album, GooglePhotosClient, MediaItem
from wg_utilities.clients.oauth_client import OAuthCredentials


@fixture(scope="function", name="calendar")
def _calendar(google_calendar_client: GoogleCalendarClient) -> Calendar:
    """Fixture for a Google Calendar instance."""
    return Calendar.from_json_response(
        read_json_file("v3/calendars/primary.json", host_name="google/calendar"),
        google_client=google_calendar_client,
    )


@fixture(scope="function", name="data_source")
def _data_source(google_fit_client: GoogleFitClient) -> DataSource:
    """Fixture for a Google Fit DataSource instance."""
    return DataSource(
        # pylint: disable=line-too-long
        data_source_id="derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
        google_client=google_fit_client,
    )


@fixture(scope="function", name="directory")
def _directory(drive: Drive, google_drive_client: GoogleDriveClient) -> Directory:
    # pylint: disable=protected-access
    """Fixture for a Google Drive Directory instance."""
    diry = Directory.from_json_response(
        read_json_file(
            "v3/files/7tqryz0a9oyjfzf1cpbmllsblj-ohbi1e/fields=%2a.json",
            host_name="google/drive",
        ),
        google_client=google_drive_client,
        host_drive=drive,
        parent=drive,
        _block_describe_call=True,
    )

    drive._all_files = Field(exclude=True, default_factory=list)
    drive._files = Field(exclude=True, default_factory=list)

    drive._all_directories = Field(exclude=True, default_factory=list)
    drive._directories = Field(exclude=True, default_factory=list)

    return diry


@fixture(scope="function", name="drive_comparison_entity_lookup")
def _drive_comparison_entity_lookup(
    drive: Drive, google_drive_client: GoogleDriveClient
) -> dict[str, Drive | File | Directory]:
    """Lookup for Google Drive entities, makes assertions easier to write."""

    lookup: dict[str, Drive | File | Directory] = {}

    for file in (FLAT_FILES_DIR / "json/google/drive/v3/files").rglob("*"):
        if file.is_file() and file.name == "fields=%2a.json":
            file_json: dict[str, str] = loads(file.read_text())

            if file_json["mimeType"] == Directory.MIME_TYPE:
                if file_json["name"] == "My Drive":
                    continue
                cls: type[File | Directory] = Directory
            else:
                cls = File

            lookup[file_json["name"]] = cls.from_json_response(
                file_json,
                google_client=google_drive_client,
                host_drive=drive,
                _block_describe_call=True,
            )

    lookup[drive.name] = drive

    return lookup


@fixture(scope="function", name="drive")
def _drive(google_drive_client: GoogleDriveClient) -> Drive:
    """Fixture for a Google Drive instance."""
    return Drive.from_json_response(
        read_json_file("v3/files/root/fields=%2a.json", host_name="google/drive"),
        google_client=google_drive_client,
    )


@fixture(scope="function", name="event")
def _event(google_calendar_client: GoogleCalendarClient, calendar: Calendar) -> Event:
    """Fixture for a Google Calendar event."""
    return Event.from_json_response(
        read_json_file(
            "v3/calendars/google-user@gmail.com/events/jt171go86rkonwwkyd5q7m84mm.json",
            host_name="google/calendar",
        ),
        google_client=google_calendar_client,
        calendar=calendar,
    )


@fixture(scope="function", name="file")
def _file(
    drive: Drive, directory: Directory, google_drive_client: GoogleDriveClient
) -> File:
    # pylint: disable=protected-access
    """Fixture for a Google Drive File instance."""

    file = File.from_json_response(
        read_json_file(
            "v3/files/1x9xhqui0chzagahgr1d0lion2jj5mzo-wu7l5fhcn4b/fields=%2a.json",
            host_name="google/drive",
        ),
        google_client=google_drive_client,
        host_drive=drive,
        parent=directory,
        _block_describe_call=True,
    )

    # Don't "dirty" the `directory` fixture
    directory._files = Field(exclude=True, default_factory=list)
    drive._all_files = Field(exclude=True, default_factory=list)

    return file


@fixture(scope="function", name="google_calendar_client")
def _google_calendar_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> GoogleCalendarClient:
    """Fixture for `GoogleCalendarClient` instance."""

    (
        creds_cache_path := temp_dir
        / "oauth_credentials/google_calendar_credentials.json"
    ).write_text(fake_oauth_credentials.model_dump_json())

    return GoogleCalendarClient(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        creds_cache_path=creds_cache_path,
    )


@fixture(scope="function", name="google_drive_client")
def _google_drive_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> GoogleDriveClient:
    """Fixture for `GoogleDriveClient` instance."""

    (
        creds_cache_path := temp_dir / "oauth_credentials/google_drive_credentials.json"
    ).write_text(fake_oauth_credentials.model_dump_json())

    return GoogleDriveClient(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        creds_cache_path=creds_cache_path,
        item_metadata_retrieval=ItemMetadataRetrieval.ON_INIT,
    )


@fixture(scope="function", name="google_fit_client")
def _google_fit_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> GoogleFitClient:
    """Fixture for `GoogleFitClient` instance."""

    (
        creds_cache_path := temp_dir / "oauth_credentials/google_fit_credentials.json"
    ).write_text(fake_oauth_credentials.model_dump_json())

    return GoogleFitClient(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        creds_cache_path=creds_cache_path,
    )


@fixture(scope="function", name="google_photos_album")
def _google_photos_album(google_photos_client: GooglePhotosClient) -> Album:
    """Fixture for a Google Photos Album."""

    return Album.from_json_response(
        read_json_file(
            # pylint: disable=line-too-long
            "aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json",
            host_name="google/photos/v1/albums",
        ),
        google_client=google_photos_client,
    )


@fixture(scope="function", name="google_photos_client")
def _google_photos_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> GooglePhotosClient:
    """Fixture for `GooglePhotosClient` instance."""

    (
        creds_cache_path := temp_dir
        / "oauth_credentials/google_photos_credentials.json"
    ).write_text(fake_oauth_credentials.model_dump_json())

    return GooglePhotosClient(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        creds_cache_path=creds_cache_path,
    )


@fixture(scope="function", name="media_item_image")
def _media_item_image(
    google_photos_client: GooglePhotosClient,
) -> YieldFixture[MediaItem]:
    """Fixture for a `MediaItem` instance with an image MIME type."""

    image = MediaItem.from_json_response(
        read_json_file(
            (
                # pylint: disable=line-too-long
                json_path := ":search/pagesize=100&albumid=aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json"  # noqa: E501
            ),
            host_name="google/photos/v1/mediaitems",
        )["mediaItems"][0],
        google_client=google_photos_client,
    )

    assert image.mime_type == "image/jpeg", (
        "Incorrect MIME type for image fixture. Has the file "
        f"`tests/flat_files/json/google/photos/{json_path}` been edited recently?"
    )

    yield image

    # The `bytes` property downloads the file to the default location; this just cleans
    # it up
    (Path.cwd() / image.creation_datetime.strftime("%Y/%m/%d") / image.filename).unlink(
        missing_ok=True
    )


@fixture(scope="function", name="media_item_video")
def _media_item_video(google_photos_client: GooglePhotosClient) -> MediaItem:
    """Fixture for a `MediaItem` instance with a video MIME type."""

    video = MediaItem.from_json_response(
        read_json_file(
            (  # pylint: disable=line-too-long
                json_path := ":search/pagesize=100&albumid=aeaj_ygjq7orbkhxtxqtvky_nf_thtkex5ygvq6m1-qcy0wwmoosefqrmt5el2hakuossonw3jll.json"  # noqa: E501
            ),
            host_name="google/photos/v1/mediaitems",
        )["mediaItems"][15],
        google_client=google_photos_client,
    )

    assert video.mime_type == "video/mp4", (
        "Incorrect MIME type for video fixture. Has the file "
        f"`tests/flat_files/json/google/photos/{json_path}` been edited recently?"
    )

    return video


@fixture(scope="function", name="simple_file")
def _simple_file(
    drive: Drive, directory: Directory, google_drive_client: GoogleDriveClient
) -> File:
    """Fixture for a Google Drive File instance."""

    simple_file = File.from_json_response(
        read_json_file(
            # pylint: disable=line-too-long
            "v3/files/1x9xhqui0chzagahgr1d0lion2jj5mzo-wu7l5fhcn4b/fields=id%2c+name%2c+parents%2c+mimetype%2c+kind.json",
            host_name="google/drive",
        ),
        google_client=google_drive_client,
        host_drive=drive,
        parent=directory,
        _block_describe_call=True,
    )

    # Don't "dirty" the `directory` fixture
    directory._files = Field(  # pylint: disable=protected-access
        exclude=True, default_factory=list
    )

    return simple_file


@fixture(scope="function", name="mock_requests", autouse=True)
def _mock_requests(
    mock_requests_root: Mocker,
    request: FixtureRequest,
) -> YieldFixture[Mocker]:
    """Fixture for mocking sync HTTP requests."""

    if fullmatch(
        r"^tests/unit/clients/google/calendar/test__[a-z_]+\.py$",
        request.node.parent.name,
    ):
        for path_object in (
            google_dir := FLAT_FILES_DIR / "json" / "google" / "calendar" / "v3"
        ).rglob("*"):
            if path_object.is_dir() or (
                path_object.is_file() and "=" not in path_object.name
            ):
                mock_requests_root.get(
                    GoogleCalendarClient.BASE_URL
                    + "/"
                    + str(path_object.relative_to(google_dir).with_suffix("")),
                    json=get_flat_file_from_url,
                )
    elif fullmatch(
        r"^tests/unit/clients/google/drive/test__[a-z_]+\.py$",
        request.node.parent.name,
    ):
        for path_object in (
            google_dir := FLAT_FILES_DIR / "json" / "google" / "drive" / "v3"
        ).rglob("*"):
            if path_object.is_dir() or (
                path_object.is_file() and "=" not in path_object.name
            ):
                mock_requests_root.get(
                    GoogleDriveClient.BASE_URL
                    + "/"
                    + str(path_object.relative_to(google_dir).with_suffix("")),
                    json=get_flat_file_from_url,
                )
    elif fullmatch(
        r"^tests/unit/clients/google/fit/test__[a-z_]+\.py$",
        request.node.parent.name,
    ):
        for path_object in (
            google_dir := FLAT_FILES_DIR / "json" / "google" / "fitness" / "v1"
        ).rglob("*"):
            if path_object.is_dir() or (
                path_object.is_file() and "=" not in path_object.name
            ):
                mock_requests_root.get(
                    GoogleFitClient.BASE_URL
                    + "/"
                    + str(path_object.relative_to(google_dir)).replace(".json", ""),
                    json=get_flat_file_from_url,
                )
    elif fullmatch(
        r"^tests/unit/clients/google/photos/test__[a-z_]+\.py$",
        request.node.parent.name,
    ):
        for path_object in (
            google_dir := FLAT_FILES_DIR / "json" / "google" / "photos" / "v1"
        ).rglob("*"):
            if path_object.is_dir() or (
                path_object.is_file() and "=" not in path_object.name
            ):
                (
                    mock_requests_root.post
                    if path_object.name.lower().startswith("mediaitems:")
                    else mock_requests_root.get
                )(
                    GooglePhotosClient.BASE_URL
                    + "/"
                    + str(path_object.relative_to(google_dir)).replace(".json", ""),
                    json=get_flat_file_from_url,
                )

        image_bytes = (
            FLAT_FILES_DIR.parent / "binary_files/2019/03/17/IMG_20190317_172652.jpg"
        ).read_bytes()

        mock_requests_root.get(
            # pylint: disable=line-too-long
            "https://lh3.googleusercontent.com/lr/OJIb5lbwSSP1sLh0smnNn4t6NxEFCmE2_XhYPH2bOFAYgwSsQYsoooNCmkpa230eyef3yLiRGS8swyaKaOIkSXy74GrCcYcnAezDRHR9mGDo6HDpYHEZkXudGIs2rQm0MXnxdeEGF_OWBD5RJL3BfIU8Z8b32iDLbxCmZBDl30TDWHYwuZawJFHsQ0jFeUAQpFxkIofpVJ-UdgwS9PHhRj6tYtkmFaPN29EASKvNZel4COGYvxUGppOKZ20U-zaOIE-ZikXmGxsSFPWvytTDNfuC2trKk3z8kRG2nmWpPZRdoYASXWTMqNVdoEW4PRFZzo7HTVoNQcZHieHWype2InDFM7kof4l6tEhV645VUgWLOx0nwbpLDO9hCS0-abhSNdEFToadpAGWnXHAG8y6q34DjGbQMogYVcO1AyL2ZZH3Qr-aq69VWnJ0L-hCOvrwPT7CnWvBPrd2Nkzs2ZINvUOuHWZGzLUMmH-MzvBtvZKu_dJkRtCF45ua1gRJH3Lan6eWUaEsGFW5OIsIHtR-r8mIKq0angbEX0Il5K7HIFjp0paXVuLUE9Q4BJcSqmndZhiSkkM2GosvWPpsEP3Vk-9tV4YNPN98Pqg4zOaWjPbsBDmwRFxsLMfZOZDqpKLqRccdod-ef4Dl1LNdt3MVQCyv75yvXlxShzy4ph6xa0vvuBco9C211f4EhuxPz2FB1YoAV55P5C1_dM3oifLgPG5RLxaRlu_siC4Id3dhD2nsjaso_rl1ML2wwjW7caMx_uDEopO6iZGRtGYqbq8TLyI5mvcC-pGx0jsIoWeeKaGJf4mSchhC9UHPYuKt7qO-Nh6N4zvNscBEsD7suWElJ5Vq1psvr_Fx92ElHWAoJFvdRMJC6dKXJdsUyI4MvLGGZbi-w4BoQ1krTn0ag-cmIPRvXXjHsN2Jr8cQvtMaiWf8QZ9BBFmaD7T8z6B0Iz3fMYxL9k-BU0rycXe9NfAmBfUg1qI_M2IUfwRYpk0FmQZOmSLLAUYpZ2J7WG7TAGW-rjL-moej=w4640-h2610",
            content=image_bytes,
        )

        video_bytes = (
            FLAT_FILES_DIR.parent / "binary_files/2019/04/04/VID_20190404_205947.mp4"
        ).read_bytes()

        mock_requests_root.get(
            # pylint: disable=line-too-long
            "https://lh3.googleusercontent.com/lr/CWNg8lw8ttG1XAmhCFwe8tVcdTBme9dyDDOE5pc33fqZU26yrmO1i3qcLE90xW5u-pOnL9C1ODZhhUg3kP9P1xZEIwjFGeik3OZD-X7sKMXwsjVxuQ4MtoOY-uRhgo3HIPDsuDwu2KDJnGVlDDS8Ygad3SPDGzMDO2J44_-RnU8UWP0u966PqGF9-ApgVKX2SOldCn9I5v7mp0V_r7E7n_kgpHqLW2trukMKUu33RlBj8BYhQ8E6ds8OTS8SF88MKSeWBvrYdrjRbKbFwA41O5lKYhgUmWw0gq6vVIoNNdCBeov2Ait0aDR4uWVdTOlK7LFeAQb-0MAMNPVmbTas5hbeJt2Zm6Hw4pfIJAbeccgAxLDwAq4QpWDzsULaaIEJsHSIZL9WvwWMfxSv6nEVKiw8ggMJrTQ6ylj3UnsG4R_dzbD4G_E1WdH79JRn_ObKoVlumFrrFXx513-VreXkIL86wyVawiGOK-YEzvrFWZxNcWDPTuI3Advbq_k3MxFD5XJGliWyNqEq0DuZ2E-hidb8iByv5W6RC3ffXqQJ_e_ghpUYP5Tk68g3UzN_CI57mtXxwQ9ZzHMJJGVBndRp-xG2cdYMb_R6M6JDxQhvDoPgma0Uzu_Ih3wdHi1aeHDBxDXFyTB2H0n8kK4bPTMEUZqGimrEE7vzu0CS_jops8RnOJJFS773ToILVtTzmTrNoelNkw1W9SiWPrYSnWV8sI1iS2Z_qI4anqjBz8z7VVn8OJWeLGgH52SSAFA3xHXhTdrn8L3OMMKYSpVomIV9_Es2HHmCvH3U-SPgtzCPDM13C9qcrKetDpDzCz-XoS0mGElaMPFSQGrjJMp58dMD5uloMbtAkOqWwucrEfT6zZVe1UX25aDcJqO-sH_5_hRbtaWbzm1yp1izRSM8T3QCKW8H4iI6K8rQfitBP51Ur_Uk1MmxHuUMHqw9lOGMdDZxZFE8XH3Et01DY8EoRe7kqmfw9JevMxA2RADNjncXKyY5jco0QzjvW1t6TcPq4zNxkqcSrw6M=dv",
            content=video_bytes,
        )

    yield mock_requests_root
