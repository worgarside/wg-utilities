from __future__ import annotations

__all__ = []

try:
    from . import mqtt

    __all__ += ["mqtt"]
except ModuleNotFoundError as _err:
    if "paho" in str(_err):
        raise ImportError(  # TODO (V6): Custom "extra not found" error
            "Extra dependency group `mqtt` required; install it with `pip install wg-utilities[mqtt]`"
        ) from _err

    raise
