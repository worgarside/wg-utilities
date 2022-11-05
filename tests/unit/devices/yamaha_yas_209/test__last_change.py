"""Unit Tests for `wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.LastChange`."""
from __future__ import annotations

from json import loads
from typing import Literal

from pydantic import ValidationError
from pytest import mark, raises

from conftest import (
    fix_colon_keys,
    yamaha_yas_209_last_change_av_transport_events,
    yamaha_yas_209_last_change_rendering_control_events,
)
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import (
    LastChangeAVTransport,
    LastChangeRenderingControl,
)


@mark.parametrize(  # type: ignore[misc]
    [
        "last_change_dict",
    ],
    yamaha_yas_209_last_change_rendering_control_events(),
)
def test_last_change_rendering_control_parsing(
    last_change_dict: dict[Literal["Event"], object],
) -> None:
    """Test that `from_last_change` returns the expected values (RenderingControl)."""
    last_change = LastChangeRenderingControl.parse(last_change_dict)

    assert last_change.dict() == last_change_dict


@mark.parametrize(  # type: ignore[misc]
    [
        "last_change_dict",
    ],
    yamaha_yas_209_last_change_av_transport_events(),
)
def test_last_change_keeps_extra_data_av_transport(
    last_change_dict: dict[Literal["Event"], object]
) -> None:
    """Just testing Pydantic's `Extra.allow` feature really."""

    last_change = LastChangeAVTransport.parse(last_change_dict)

    assert (
        fix_colon_keys(last_change.dict())
        == last_change_dict
        # You can never be too safe... :)
        == fix_colon_keys(loads(last_change.json()))
    )


@mark.parametrize(  # type: ignore[misc]
    [
        "last_change_dict",
    ],
    yamaha_yas_209_last_change_rendering_control_events(),
)
def test_last_change_keeps_extra_data_rendering_control(
    last_change_dict: dict[Literal["Event"], object]
) -> None:
    """Just testing Pydantic's `Extra.allow` feature really."""

    last_change = LastChangeRenderingControl.parse(last_change_dict)

    assert (
        fix_colon_keys(last_change.dict())
        == last_change_dict
        # You can never be too safe... :)
        == fix_colon_keys(loads(last_change.json()))
    )


def test_last_change_throws_error_with_two_keys() -> None:
    """Test that a `lastChange` object with >1 top-level keys is treated as invalid."""

    last_change_dict = {
        "Event": {"foo": "bar"},
        "baz": "ham",
        "spam": "eggs",
    }

    with raises(ValidationError) as exc_info:
        LastChangeAVTransport.parse(last_change_dict)  # type: ignore[arg-type]

    assert exc_info.value.errors() == [
        {
            "loc": ("baz",),
            "msg": "extra fields not permitted",
            "type": "value_error",
        },
        {
            "loc": ("spam",),
            "msg": "extra fields not permitted",
            "type": "value_error",
        },
    ]
