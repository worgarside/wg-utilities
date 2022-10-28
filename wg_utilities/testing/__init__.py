"""Pytest fixtures that can be used across projects."""

from __future__ import annotations

from ._custom_mocks import MockBoto3Client

__all__ = ["MockBoto3Client"]
