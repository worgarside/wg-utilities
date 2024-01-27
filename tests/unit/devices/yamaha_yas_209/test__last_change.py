"""Unit Tests for `wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.LastChange`."""
from __future__ import annotations

from json import loads
from typing import Literal

import pytest

from tests.unit.devices.yamaha_yas_209.conftest import (
    fix_colon_keys,
    yamaha_yas_209_last_change_av_transport_events,
    yamaha_yas_209_last_change_rendering_control_events,
)
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import (
    LastChangeAVTransport,
    LastChangeRenderingControl,
)


@pytest.mark.parametrize(
    "last_change_dict",
    yamaha_yas_209_last_change_rendering_control_events(),
)
def test_last_change_rendering_control_parsing(
    last_change_dict: dict[Literal["Event"], object],
) -> None:
    """Test that `from_last_change` returns the expected values (RenderingControl)."""
    last_change = LastChangeRenderingControl.parse(last_change_dict)

    assert last_change.model_dump() == last_change_dict


@pytest.mark.parametrize(
    "last_change_dict",
    [event[0] for event in yamaha_yas_209_last_change_av_transport_events()],  # type: ignore[index]
)
def test_last_change_keeps_extra_data_av_transport(
    last_change_dict: dict[Literal["Event"], object]
) -> None:
    """Just testing Pydantic's `Extra.allow` feature really."""

    last_change = LastChangeAVTransport.parse(last_change_dict)

    assert (
        fix_colon_keys(last_change.model_dump())
        == last_change_dict
        # You can never be too safe... :)
        == fix_colon_keys(loads(last_change.model_dump_json()))
    )


@pytest.mark.parametrize(
    "last_change_dict",
    yamaha_yas_209_last_change_rendering_control_events(),
)
def test_last_change_keeps_extra_data_rendering_control(
    last_change_dict: dict[Literal["Event"], object]
) -> None:
    """Just testing Pydantic's `Extra.allow` feature really."""

    last_change = LastChangeRenderingControl.parse(last_change_dict)

    assert (
        fix_colon_keys(last_change.model_dump())
        == last_change_dict
        # You can never be too safe... :)
        == fix_colon_keys(loads(last_change.model_dump_json()))
    )


def test_last_change_throws_error_with_two_keys() -> None:
    """Test that a `lastChange` object with >1 top-level keys is treated as invalid."""

    last_change_dict = {
        "Event": {"foo": "bar"},
        "baz": "ham",
        "spam": "eggs",
    }

    with pytest.raises(ValueError) as exc_info:
        LastChangeAVTransport.parse(last_change_dict)  # type: ignore[arg-type]

    assert exc_info.value.args[0] == "Extra fields not permitted: ['baz', 'spam']"
