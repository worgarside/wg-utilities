# WG Utilities
[![Code Style](https://img.shields.io/badge/code%20style-black-black)](https://github.com/worgarside/wg-utilities)
[![codecov](https://codecov.io/gh/worgarside/wg-utilities/branch/develop/graph/badge.svg?token=5IJW9KBSV6)](https://codecov.io/gh/worgarside/wg-utilities)
[![GitHub](https://img.shields.io/github/v/tag/worgarside/wg-utilities?logo=github&sort=semver)](https://github.com/worgarside/wg-utilities)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/worgarside/wg-utilities/develop.svg)](https://results.pre-commit.ci/latest/github/worgarside/wg-utilities/develop)
[![PyPI](https://img.shields.io/pypi/v/wg-utilities.svg?logo=python)](https://pypi.python.org/pypi/wg-utilities)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v1.json)](https://github.com/charliermarsh/ruff)
[![image](https://img.shields.io/pypi/pyversions/wg-utilities.svg)](https://pypi.python.org/pypi/wg-utilities)
[![CI](https://github.com/worgarside/wg-utilities/actions/workflows/ci_deployment.yml/badge.svg?branch=main&event=push)](https://github.com/worgarside/wg-utilities/actions/workflows/ci_deployment.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=worgarside_wg-utilities&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=worgarside_wg-utilities)

Loads of useful stuff for the things I do :)

## To-Do List
 - [ ] Finish README
 - [x] Add Coverage Badge
 - [ ] Sphinx docs

## Environment Variables

| Name | Description | Default |
|------|-------------|---------|
| `HA_LOG_ENDPOINT` | The HomeAssistant **host** to send logs to | `homeassistant.local:8001` |
| `SUPPRESS_WG_UTILS_IGNORANCE` | If set to `"1"`, will suppress warnings about ignored exceptions caught in the `on_exception` [decorator](https://github.com/worgarside/wg-utilities/blob/main/wg_utilities/exceptions/__init__.py#L67) | `null` |
| `WG_UTILITIES_CREDS_CACHE_DIR` | The directory to store the credentials cache in | `<App Data Dir>/WgUtilities/oauth_credentials/` |
| `WG_UTILITIES_HEADLESS_MODE` | If set to `"1"`, allows a callback to be provided to OAuth clients instead of opening the auth link directly in the browser. Useful for running on headless devices. | `"-"` |
| `ITEM_WAREHOUSE_HOST` | The host to use for the [Item Warehouse API](https://github.com/worgarside/addon-item-warehouse-api) | `http://homeassistant.local` |
| `ITEM_WAREHOUSE_PORT` | The port to use for the [Item Warehouse API](https://github.com/worgarside/addon-item-warehouse-api) | `8002` |
| `WAREHOUSE_HANDLER_BACKOFF_MAX_TRIES` | The maximum number of times to retry a request to the [Item Warehouse API](https://github.com/worgarside/addon-item-warehouse-api) | `∞` |
| `WAREHOUSE_HANDLER_BACKOFF_TIMEOUT` | The maximum number of seconds to keep retrying requests to the [Item Warehouse API](https://github.com/worgarside/addon-item-warehouse-api) | `86400` |

### Unit Test Coverage

[![Fancy coverage chart](https://codecov.io/gh/worgarside/wg-utilities/branch/develop/graphs/tree.svg?token=5IJW9KBSV6)](https://codecov.io/gh/worgarside/wg-utilities)
