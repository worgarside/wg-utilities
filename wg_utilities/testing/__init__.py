"""A module for any Pytest fixtures that can be used across projects"""

from ._custom_mocks import MockBoto3Client

__all__ = ["MockBoto3Client"]
