"""This module contains any custom mocks (classes or functions) for use in Unit Tests
within this project and others"""
from typing import Any, Callable, Dict, List, Optional, Union

from botocore.client import BaseClient

# noinspection PyProtectedMember
# pylint: disable=protected-access
ORIG_API_CALL: Callable[..., Dict[str, str]] = BaseClient._make_api_call  # type: ignore


class MockBoto3Client:
    """Class for adding custom mocks for boto3 when moto doesn't support the
    operation"""

    def __init__(
        self,
        mocked_operation_lookup: Optional[
            Dict[str, Union[str, Callable[..., Any]]]
        ] = None,
    ):
        self.mocked_operation_lookup = mocked_operation_lookup or {}

        self.boto3_calls: Dict[str, List[Dict[Any, Any]]] = {}

    def reset_boto3_calls(self) -> None:
        """Resets the boto3 calls to an empty dict"""
        self.boto3_calls = {}

    def build_api_call(
        self,
        lookup_overrides: Optional[Dict[str, Union[str, Callable[..., Any]]]] = None,
        reset_boto3_calls: bool = True,
    ) -> Callable[[BaseClient, str, Dict[str, Any]], Union[Dict[str, str], str]]:
        """Wrapper function for the API call. Also resets the internal log of boto3
        calls as this is a new API call

        Args:
            lookup_overrides (dict): any overrides to be applied for this specific API
             call
            reset_boto3_calls (bool): option for resetting boto3 calls

        Returns:
            function: the mocked API call
        """
        lookup_overrides_ = lookup_overrides or {}

        if reset_boto3_calls:
            self.reset_boto3_calls()

        def api_call(
            client: BaseClient, operation_name: str, kwargs: Dict[str, Any]
        ) -> Union[Dict[str, str], str]:
            """Inner function of this mock, which is the actual mock function itself.

            Args:
                client (BaseClient): the client making the (mocked) request
                operation_name (str): the AWS operation being requested
                kwargs (dict): any keyword arguments being passed to AWS

            Returns:
                dict: a (mocked) response from AWS

            Raises:
                Exception: if an operation is requested that isn't mocked by this
                 class or by moto
                KeyError: when a KeyError is caught, but it isn't for the above
                 reason, it's just re-raised
            """

            # If the response override is a function (so we can dynamically set the
            # response value) then call it - otherwise just return it
            # This needs to be in here because if the override _is_ callable,
            # then we need to call it on each API call to update values etc.
            for operation, response_override in lookup_overrides_.items():
                self.mocked_operation_lookup[operation] = (
                    response_override()
                    if callable(response_override)
                    else response_override
                )

            self.boto3_calls.setdefault(operation_name, []).append(kwargs)

            if (
                mocked_operation := self.mocked_operation_lookup.get(operation_name)
            ) is not None:
                if callable(mocked_operation):
                    return mocked_operation(kwargs)  # type: ignore

                return mocked_operation

            try:
                return ORIG_API_CALL(client, operation_name, kwargs)
            except KeyError as exc:
                if str(exc) == "'DEFAULT'":
                    raise Exception(
                        f"Operation `{operation_name}` not supported by moto yet"
                    ) from exc
                raise

        return api_call
