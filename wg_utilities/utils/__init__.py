from __future__ import annotations

__all__ = []

try:  # pragma: no cover
    from . import mqtt

    __all__ += ["mqtt"]
except ModuleNotFoundError as _err:  # pragma: no cover
    if "paho" in str(_err):
        import logging

        logging.exception(  # TODO (V6): Custom "extra not found" error
            "Extra dependency group `mqtt` required; install it with `pip install wg-utilities[mqtt]`"
        )

    raise
