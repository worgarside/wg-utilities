"""Custom mocks (classes or functions) for use in Unit Tests."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from botocore.client import BaseClient

from wg_utilities.functions import traverse_dict

ORIG_API_CALL: Callable[..., dict[str, str]] = BaseClient._make_api_call  # type: ignore[attr-defined]


class MockBoto3Client:
    """boto3.client for mock usage.

    Class for adding custom mocks for boto3 when moto doesn't support the
    operation.

    Usage:
        >>> from unittest.mock import patch
        >>>
        >>> def test_something():
        >>>     mocked_operation_lookup = {
        >>>         "operation_name": "response",
        >>>     }
        >>>     mock_boto3_client = MockBoto3Client(mocked_operation_lookup)
        >>>
        >>>     with patch(
        >>>         MockBoto3Client.PATCH_METHOD,
        >>>         mock_boto3_client.build_api_call(),
        >>>     ):
        >>> # Do something that calls the mocked operation
        >>>         assert mock_boto3_client.boto3_calls == {
        >>>             "operation_name": [{"kwarg": "value"}],
        >>>         }

    """

    PATCH_METHOD = "botocore.client.BaseClient._make_api_call"

    def __init__(
        self,
        mocked_operation_lookup: (
            None | dict[str, object | Callable[..., object]]
        ) = None,
    ):
        self.mocked_operation_lookup = mocked_operation_lookup or {}

        self.boto3_calls: dict[str, list[dict[Any, Any]]] = {}

    def reset_boto3_calls(self) -> None:
        """Reset the boto3 calls to an empty dict."""
        self.boto3_calls = {}

    def build_api_call(
        self,
        *,
        lookup_overrides: dict[str, object | Callable[..., Any]] | None = None,
        reset_boto3_calls: bool = True,
    ) -> Callable[[BaseClient, str, dict[str, Any]], object]:
        """Build an API call for use in stubs.

        Wrapper function for the API call. Also resets the internal log of boto3
        calls as this is a new API call

        Args:
            lookup_overrides (dict): any overrides to be applied for this specific API
                call
            reset_boto3_calls (bool): option for resetting boto3 calls

        Returns:
            function: the mocked API call
        """
        if reset_boto3_calls:
            self.reset_boto3_calls()

        def api_call(
            client: BaseClient,
            operation_name: str,
            kwargs: dict[str, Any],
        ) -> object:
            """Inner function of this mock, which is the actual mock function itself.

            Args:
                client (BaseClient): the client making the (mocked) request
                operation_name (str): the AWS operation being requested
                kwargs (dict): any keyword arguments being passed to AWS

            Returns:
                object: a (mocked) response from AWS

            Raises:
                Exception: if an operation is requested that isn't mocked by this
                 class or by moto
                KeyError: when a KeyError is caught, but it isn't for the above
                 reason, it's just re-raised
            """
            if lookup_overrides is not None:
                # If the response override is a function (so we can dynamically set the
                # response value) then call it - otherwise just return it
                # This needs to be in here because if the override _is_ callable,
                # then we need to call it on each API call to update values etc.
                for operation, response_override in lookup_overrides.items():
                    self.mocked_operation_lookup[operation] = (
                        response_override()
                        if callable(response_override)
                        else response_override
                    )

            self.boto3_calls.setdefault(operation_name, []).append(kwargs)

            if (
                mocked_operation := self.mocked_operation_lookup.get(operation_name)
            ) is not None:
                mocked_operation = deepcopy(mocked_operation)
                if isinstance(mocked_operation, dict):
                    traverse_dict(
                        mocked_operation,
                        target_type=Callable,  # type: ignore[arg-type]
                        target_processor_func=lambda value, **_: value(**kwargs),
                        pass_on_fail=False,
                    )
                elif callable(mocked_operation):
                    return mocked_operation(**kwargs)

                return mocked_operation

            try:
                return ORIG_API_CALL(client, operation_name, kwargs)
            except KeyError as exc:  # pragma: no cover
                if str(exc) == "'DEFAULT'":
                    raise NotImplementedError(
                        f"Operation `{operation_name}` not supported by moto yet",
                    ) from exc
                raise

        return api_call
