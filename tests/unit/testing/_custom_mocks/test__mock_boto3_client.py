"""Unit Tests for `wg_utilities.testing._custom_mocks.MockBoto3Client`."""
from __future__ import annotations

from datetime import datetime
from os import environ
from unittest.mock import patch

from boto3 import client
from dateutil.tz import tzutc
from freezegun import freeze_time
from moto import mock_s3
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_s3 import S3Client
from pytest import FixtureRequest, fixture, mark

from tests.conftest import YieldFixture
from wg_utilities.testing import MockBoto3Client


@fixture(scope="module", autouse=True)  # type: ignore[misc]
def _aws_credentials_env_vars() -> YieldFixture[None]:
    """Mock environment variables.

    This is done here instead of in`pyproject.toml` because `pytest-aws-config` blocks
    consuming AWS credentials from all env vars.
    """
    with patch.dict(
        environ,
        {
            "AWS_ACCESS_KEY_ID": "AKIATESTTESTTESTTEST",
            "AWS_SECRET_ACCESS_KEY": "T3ST/S3CuR17Y*K3Y[S7R1NG!?L00K5.L1K3.17!",
            "AWS_SECURITY_TOKEN": "ANYVALUEWEWANTINHERE",
            "AWS_SESSION_TOKEN": "ASLONGASITISNOTREAL",
            "AWS_DEFAULT_REGION": "eu-west-1",
        },
    ):
        yield


@fixture(scope="function", name="lambda_client")  # type: ignore[misc]
def _lambda_client() -> LambdaClient:
    """Fixture for creating a boto3 client instance for Lambda Functions."""
    return client("lambda")


@fixture(scope="function", name="mb3c")  # type: ignore[misc]
def _mb3c(request: FixtureRequest) -> MockBoto3Client:
    """Fixture for creating a MockBoto3Client instance."""

    if name_marker := request.node.get_closest_marker("mocked_operation_lookup"):
        mocked_operation_lookup = name_marker.args[0]
    else:
        mocked_operation_lookup = {}

    return MockBoto3Client(mocked_operation_lookup=mocked_operation_lookup)


@fixture(scope="function", name="s3_client")  # type: ignore[misc]
def _s3_client() -> S3Client:
    """Fixture for creating a boto3 client instance for S3."""
    return client("s3")


def test_instantiation() -> None:
    # pylint: disable=use-implicit-booleaness-not-comparison
    """Test that the class can be instantiated."""
    mb3c = MockBoto3Client()

    assert mb3c.mocked_operation_lookup == {}
    assert mb3c.boto3_calls == {}


def test_reset_boto3_calls(mb3c: MockBoto3Client) -> None:
    """Test that the boto3 calls are reset."""
    mb3c.boto3_calls = {"test": [{"test": "test"}]}

    mb3c.reset_boto3_calls()

    assert mb3c.boto3_calls == {}


@mark.mocked_operation_lookup(  # type: ignore[misc]
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
        "CreateBucket": "done",
        "ListFunctions": {"Functions": ["foo", "bar", "baz"]},
        "CreateFunction": "done",
    }
)
def test_boto3_calls_are_logged_correctly(
    mb3c: MockBoto3Client, s3_client: S3Client, lambda_client: LambdaClient
) -> None:
    """Test that the API calls are recorded correctly."""

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ):
        s3_client.list_buckets()
        s3_client.create_bucket(
            **(
                create_bucket_args := {
                    "ACL": "private",
                    "Bucket": "string",
                    "CreateBucketConfiguration": {"LocationConstraint": "af-south-1"},
                    "GrantFullControl": "string",
                    "GrantRead": "string",
                    "GrantReadACP": "string",
                    "GrantWrite": "string",
                    "GrantWriteACP": "string",
                    "ObjectLockEnabledForBucket": True,
                    "ObjectOwnership": "BucketOwnerPreferred",
                }
            )
        )
        lambda_client.list_functions()
        lambda_client.create_function(
            **(
                create_function_args := {
                    "FunctionName": "string",
                    "Runtime": "string",
                    "Role": "string",
                    "Handler": "string",
                    "Code": {"ZipFile": b"string"},
                    "Description": "string",
                    "Timeout": 123,
                    "MemorySize": 123,
                    "Publish": True,
                    "VpcConfig": {
                        "SubnetIds": ["string"],
                        "SecurityGroupIds": ["string"],
                    },
                    "Environment": {"Variables": {"string": "string"}},
                    "KMSKeyArn": "string",
                    "TracingConfig": {"Mode": "Active"},
                    "Tags": {"string": "string"},
                    "Layers": ["string"],
                    "FileSystemConfigs": [
                        {
                            "Arn": "string",
                            "LocalMountPath": "string",
                            "AuthorizationConfig": {
                                "AccessPointId": "string",
                                "IAM": "DISABLED",
                            },
                        }
                    ],
                    "DeadLetterConfig": {"TargetArn": "string"},
                    "ImageConfig": {"RepositoryAccessMode": "string"},
                    "PackageType": "Zip",
                    "CodeSigningConfigArn": "string",
                }
            )
        )

    assert mb3c.boto3_calls == {
        "ListBuckets": [{}],
        "CreateBucket": [create_bucket_args],
        "ListFunctions": [{}],
        "CreateFunction": [create_function_args],
    }


@mark.mocked_operation_lookup(  # type: ignore[misc]
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
        "CreateBucket": "done",
        "ListFunctions": {"Functions": ["foo", "bar", "baz"]},
        "CreateFunction": "done",
    }
)
def test_boto3_calls_get_correct_responses(
    mb3c: MockBoto3Client, s3_client: S3Client, lambda_client: LambdaClient
) -> None:
    """Test that the API calls are recorded correctly."""

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ):
        # No arguments this time, they're inconsequential
        list_bucket_res = s3_client.list_buckets()
        create_bucket_res = s3_client.create_bucket()
        list_functions = lambda_client.list_functions()
        create_function = lambda_client.create_function()

    assert list_bucket_res == {"Buckets": ["barry", "paul", "jimmy", "brian"]}
    assert create_bucket_res == "done"
    assert list_functions == {"Functions": ["foo", "bar", "baz"]}
    assert create_function == "done"


def test_reset_boto3_calls_argument(mb3c: MockBoto3Client) -> None:
    """Test that the boto3 calls are reset."""
    mb3c.boto3_calls = {"test": [{"test": "test"}]}

    mb3c.build_api_call(reset_boto3_calls=False)

    assert mb3c.boto3_calls == {"test": [{"test": "test"}]}

    mb3c.build_api_call()

    assert mb3c.boto3_calls == {}


def test_callable_override(mb3c: MockBoto3Client, lambda_client: LambdaClient) -> None:
    """Test that a callable override works properly."""

    counter = 0

    def _override(FunctionName: str, Qualifier: str) -> int:  # noqa: N803
        nonlocal counter

        assert FunctionName == "foo.bar.baz"
        assert Qualifier == "TEST"

        counter += 1
        return counter

    mb3c.mocked_operation_lookup = {"GetFunction": _override}

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ):
        for i in range(10):
            assert counter == i

            res = lambda_client.get_function(
                FunctionName="foo.bar.baz", Qualifier="TEST"
            )

            assert counter == res == i + 1


def test_callable_override_with_args_kwargs(
    mb3c: MockBoto3Client, lambda_client: LambdaClient
) -> None:
    """Test that a callable override works properly."""

    counter = 0

    # pylint: disable=invalid-name
    def _override(FunctionName: str, Qualifier: str, Counter: int) -> int:  # noqa: N803
        nonlocal counter

        assert FunctionName == "foo.bar.baz"
        assert Qualifier == "TEST"
        assert Counter == counter

        counter += len(FunctionName)
        return counter

    mb3c.mocked_operation_lookup = {"GetFunction": _override}

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ):
        for i in range(10):
            assert counter == i * len("foo.bar.baz")

            res = lambda_client.get_function(
                FunctionName="foo.bar.baz",
                Qualifier="TEST",
                # Added this to show new values will be passed through
                Counter=counter,
            )

            assert counter == res == (i + 1) * len("foo.bar.baz")


def test_nested_callable_override(
    mb3c: MockBoto3Client, lambda_client: LambdaClient
) -> None:
    """Test that a callable override works properly."""

    counter = 0

    def _override(FunctionName: str, Qualifier: str) -> int:  # noqa: N803
        nonlocal counter

        assert FunctionName == "foo.bar.baz"
        assert Qualifier == "TEST"

        counter += 1
        return counter

    mb3c.mocked_operation_lookup = {"GetFunction": {"value": _override}}

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ):
        for i in range(10):
            assert counter == i

            res = lambda_client.get_function(
                FunctionName="foo.bar.baz", Qualifier="TEST"
            )

            assert counter == i + 1
            assert res == {"value": counter}


@mock_s3  # type: ignore[misc]
@mark.mocked_operation_lookup(  # type: ignore[misc]
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
    }
)
def test_non_mocked_calls_still_go_to_aws(
    mb3c: MockBoto3Client,
    s3_client: S3Client,
) -> None:
    """Test that non-mocked calls still go to AWS."""
    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ), freeze_time(frozen_time := datetime.now().replace(microsecond=0)):
        s3_client.create_bucket(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )

        assert s3_client.list_buckets()["Buckets"] == [
            "barry",
            "paul",
            "jimmy",
            "brian",
        ]

        # Remove the mock, so we can ge a real response (from moto) with the same
        # request
        mb3c.mocked_operation_lookup = {}

        assert s3_client.list_buckets()["Buckets"] == [
            {"CreationDate": frozen_time.replace(tzinfo=tzutc()), "Name": "test-bucket"}
        ]


@mock_s3  # type: ignore[misc]
@mark.mocked_operation_lookup(  # type: ignore[misc]
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
    }
)
def test_lookup_overrides_in_api_call_builder(
    mb3c: MockBoto3Client, s3_client: S3Client
) -> None:
    """Test `lookup_overrides` work as expected when passed to `build_api_call`."""

    with patch(MockBoto3Client.PATCH_METHOD, mb3c.build_api_call()):
        assert s3_client.list_buckets() == {
            "Buckets": ["barry", "paul", "jimmy", "brian"]
        }

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(lookup_overrides={"ListBuckets": {"Buckets": ["foo"]}}),
    ):
        assert s3_client.list_buckets() == {"Buckets": ["foo"]}


# This is a test I tried to write to test the `except KeyError` block in the `api_call`
# method, but I couldn't get it to work (or I can't remember which moto operations
# return "'DEFAULT'"), so I'm leaving it here for now

# pylint: disable=pointless-string-statement
"""
@mock_pinpoint  # type: ignore[misc]
@mark.mocked_operation_lookup(  # type: ignore[misc]
    {
        "GetApp": {
            "ApplicationResponse": {
                "Arn": "string",
                "Id": "string",
                "Name": "string",
                "tags": {"string": "string"},
                "CreationDate": "string",
            }
        }
    }
)
def test_non_moto_supported_operations_raise_exception(
    mb3c: MockBoto3Client, pinpoint_client: PinpointClient
) -> None:
    "Test that non-moto supported operations raise an exception."
    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ), freeze_time(frozen_time := datetime.now().replace(microsecond=0)):
        # Prove moto is working
        res = pinpoint_client.create_app(
            CreateApplicationRequest={
                "Name": "test-app",
            }
        )

        # This changes every time, so we can't test it
        app_id = res["ApplicationResponse"]["Id"]

        assert res == {
            "ApplicationResponse": {
                "Arn": f"arn:aws:mobiletargeting:us-east-1:"
                "123456789012:apps/{app_id}",
                "CreationDate": frozen_time.timestamp(),
                "Id": app_id,
                "Name": "test-app",
            },
            "ResponseMetadata": {
                "HTTPHeaders": {},
                "HTTPStatusCode": 201,
                "RetryAttempts": 0,
            },
        }

        # Prove the MockBoto3Client is working
        res = pinpoint_client.get_app(ApplicationId=app_id)

        assert res == {
            "ApplicationResponse": {
                "Arn": "string",
                "Id": "string",
                "Name": "string",
                "tags": {"string": "string"},
                "CreationDate": "string",
            }
        }

        # Finally prove that the non-moto, non-mocked supported operation raises an
        # exception

        with raises(NotImplementedError) as exc_info:
            # I've just picked something I think moto are unlikely to support any time
            # soon!
            pinpoint_client.verify_otp_message(
                ApplicationId=app_id,
                VerifyOTPMessageRequestParameters={
                    "DestinationIdentity": "string",
                    "Otp": "string",
                    "ReferenceId": "string",
                },
            )

        assert (
            str(exc_info.value)
            == "Operation 'VerifyOTPMessage' is not supported by moto yet"
        )
"""
