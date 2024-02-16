"""Unit Tests for `wg_utilities.testing._custom_mocks.MockBoto3Client`."""

from __future__ import annotations

from datetime import datetime
from os import environ
from unittest.mock import patch

import pytest
from boto3 import client
from dateutil.tz import tzutc
from freezegun import freeze_time
from moto import mock_s3  # type: ignore[import-not-found]
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_s3 import S3Client

from tests.conftest import YieldFixture
from wg_utilities.testing import MockBoto3Client


@pytest.fixture(scope="module", autouse=True)
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


@pytest.fixture(name="lambda_client")
def lambda_client_() -> LambdaClient:
    """Fixture for creating a boto3 client instance for Lambda Functions."""
    return client("lambda")


@pytest.fixture(name="mb3c")
def mb3c_(request: pytest.FixtureRequest) -> MockBoto3Client:
    """Fixture for creating a MockBoto3Client instance."""

    if name_marker := request.node.get_closest_marker("mocked_operation_lookup"):
        mocked_operation_lookup = name_marker.args[0]
    else:
        mocked_operation_lookup = {}

    return MockBoto3Client(mocked_operation_lookup=mocked_operation_lookup)


@pytest.fixture(name="s3_client")
def s3_client_() -> S3Client:
    """Fixture for creating a boto3 client instance for S3."""
    return client("s3")


def test_instantiation() -> None:
    """Test that the class can be instantiated."""
    mb3c = MockBoto3Client()

    assert mb3c.mocked_operation_lookup == {}
    assert mb3c.boto3_calls == {}


def test_reset_boto3_calls(mb3c: MockBoto3Client) -> None:
    """Test that the boto3 calls are reset."""
    mb3c.boto3_calls = {"test": [{"test": "test"}]}

    mb3c.reset_boto3_calls()

    assert mb3c.boto3_calls == {}


@pytest.mark.mocked_operation_lookup(
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
        "CreateBucket": "done",
        "ListFunctions": {"Functions": ["foo", "bar", "baz"]},
        "CreateFunction": "done",
    },
)
def test_boto3_calls_are_logged_correctly(
    mb3c: MockBoto3Client,
    s3_client: S3Client,
    lambda_client: LambdaClient,
) -> None:
    """Test that the API calls are recorded correctly."""

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ):
        s3_client.list_buckets()
        s3_client.create_bucket(
            ACL="private",
            Bucket="string",
            CreateBucketConfiguration={"LocationConstraint": "af-south-1"},
            GrantFullControl="string",
            GrantRead="string",
            GrantReadACP="string",
            GrantWrite="string",
            GrantWriteACP="string",
            ObjectLockEnabledForBucket=True,
            ObjectOwnership="BucketOwnerPreferred",
        )
        lambda_client.list_functions()
        lambda_client.create_function(
            FunctionName="string",
            Runtime="python3.9",
            Role="string",
            Handler="string",
            Code={"ZipFile": b"string"},
            Description="string",
            Timeout=123,
            MemorySize=123,
            Publish=True,
            VpcConfig={
                "SubnetIds": ["string"],
                "SecurityGroupIds": ["string"],
            },
            Environment={"Variables": {"string": "string"}},
            KMSKeyArn="string",
            TracingConfig={"Mode": "Active"},
            Tags={"string": "string"},
            Layers=["string"],
            FileSystemConfigs=[
                {
                    "Arn": "string",
                    "LocalMountPath": "string",
                },
            ],
            DeadLetterConfig={"TargetArn": "string"},
            PackageType="Zip",
            CodeSigningConfigArn="string",
        )

    assert mb3c.boto3_calls == {
        "ListBuckets": [{}],
        "CreateBucket": [
            {
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
            },
        ],
        "ListFunctions": [{}],
        "CreateFunction": [
            {
                "FunctionName": "string",
                "Runtime": "python3.9",
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
                    },
                ],
                "DeadLetterConfig": {"TargetArn": "string"},
                "PackageType": "Zip",
                "CodeSigningConfigArn": "string",
            },
        ],
    }


@pytest.mark.mocked_operation_lookup(
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
        "CreateBucket": "done",
        "ListFunctions": {"Functions": ["foo", "bar", "baz"]},
        "CreateFunction": "done",
    },
)
def test_boto3_calls_get_correct_responses(
    mb3c: MockBoto3Client,
    s3_client: S3Client,
    lambda_client: LambdaClient,
) -> None:
    """Test that the API calls are recorded correctly."""

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ):
        # No arguments this time, they're inconsequential
        list_bucket_res = s3_client.list_buckets()
        create_bucket_res = s3_client.create_bucket()  # type: ignore[call-arg]
        list_functions = lambda_client.list_functions()
        create_function = lambda_client.create_function()  # type: ignore[call-arg]

    assert list_bucket_res == {"Buckets": ["barry", "paul", "jimmy", "brian"]}  # type: ignore[comparison-overlap]
    assert create_bucket_res == "done"  # type: ignore[comparison-overlap]
    assert list_functions == {"Functions": ["foo", "bar", "baz"]}  # type: ignore[comparison-overlap]
    assert create_function == "done"  # type: ignore[comparison-overlap]


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

            res = lambda_client.get_function(FunctionName="foo.bar.baz", Qualifier="TEST")

            assert counter == res == i + 1  # type: ignore[comparison-overlap]


def test_callable_override_with_args_kwargs(
    mb3c: MockBoto3Client,
    lambda_client: LambdaClient,
) -> None:
    """Test that a callable override works properly."""

    counter = 0

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
                Counter=counter,  # type: ignore[call-arg]
            )

            assert counter == res == (i + 1) * len("foo.bar.baz")  # type: ignore[comparison-overlap]


def test_nested_callable_override(
    mb3c: MockBoto3Client,
    lambda_client: LambdaClient,
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

            res = lambda_client.get_function(FunctionName="foo.bar.baz", Qualifier="TEST")

            assert counter == i + 1
            assert res == {"value": counter}  # type: ignore[comparison-overlap]


@mock_s3  # type: ignore[misc]
@pytest.mark.mocked_operation_lookup(
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
    },
)
def test_non_mocked_calls_still_go_to_aws(
    mb3c: MockBoto3Client,
    s3_client: S3Client,
) -> None:
    """Test that non-mocked calls still go to AWS."""
    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(),
    ), freeze_time(frozen_time := datetime.utcnow().replace(microsecond=0)):
        s3_client.create_bucket(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )

        assert s3_client.list_buckets()["Buckets"] == [  # type: ignore[comparison-overlap]
            "barry",
            "paul",
            "jimmy",
            "brian",
        ]

        # Remove the mock, so we can ge a real response (from moto) with the same
        # request
        mb3c.mocked_operation_lookup = {}

        assert s3_client.list_buckets()["Buckets"] == [
            {"CreationDate": frozen_time.replace(tzinfo=tzutc()), "Name": "test-bucket"},
        ]


@mock_s3  # type: ignore[misc]
@pytest.mark.mocked_operation_lookup(
    {
        "ListBuckets": {"Buckets": ["barry", "paul", "jimmy", "brian"]},
    },
)
def test_lookup_overrides_in_api_call_builder(
    mb3c: MockBoto3Client,
    s3_client: S3Client,
) -> None:
    """Test `lookup_overrides` work as expected when passed to `build_api_call`."""

    with patch(MockBoto3Client.PATCH_METHOD, mb3c.build_api_call()):
        assert s3_client.list_buckets() == {  # type: ignore[comparison-overlap]
            "Buckets": ["barry", "paul", "jimmy", "brian"],
        }

    with patch(
        MockBoto3Client.PATCH_METHOD,
        mb3c.build_api_call(lookup_overrides={"ListBuckets": {"Buckets": ["foo"]}}),
    ):
        assert s3_client.list_buckets() == {"Buckets": ["foo"]}  # type: ignore[comparison-overlap]


# This is a test I tried to write to test the `except KeyError` block in the `api_call`
# method, but I couldn't get it to work (or I can't remember which moto operations
# return "'DEFAULT'"), so I'm leaving it here for now


"""
@mock_pinpoint  # type: ignore[misc]
@pytest.mark.mocked_operation_lookup(
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
    ), freeze_time(frozen_time := datetime.utcnow().replace(microsecond=0)):
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

        with pytest.raises(NotImplementedError) as exc_info:
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
