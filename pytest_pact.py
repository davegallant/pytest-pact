# -*- coding: utf-8 -*-

import json
import logging
import os
import requests
import pytest
from pactman import Consumer, Provider

PACTS = {}


def pytest_addoption(parser):

    group = parser.getgroup("pact", "interact with your pact broker through pytest")

    group.addoption(
        "--publish-pact",
        action="store",
        # dest="version",
        help="Upload generated pact file to pact broker with specified version",
        type=str,
    )
    group.addoption(
        "--pact-host",
        action="store",
        dest="pact_host",
        help="hostname of the pact broker",
        type=str,
    )
    group.addoption(
        "--pact-port",
        action="store",
        default=80,
        dest="pact_port",
        help="port of the pact broker",
        type=str,
    )
    group.addoption(
        "--pact-user",
        action="store",
        dest="pact_user",
        help="username for the pact broker",
        type=str,
    )
    group.addoption(
        "--pact-password",
        action="store",
        dest="pact_password",
        help="password for the pact broker",
        type=str,
    )


@pytest.fixture(scope="session", autouse=True)
def pact_publisher(request, pytestconfig, pact_dir):
    def _publish():
        version = pytestconfig.getoption("--publish-pact")
        if not request.session.testsfailed and version:
            for _, pact in PACTS.items():
                publish_to_broker(
                    consumer=pact["consumer"],
                    pact_dir=pact_dir,
                    pact_host=pytestconfig.getoption("pact_host"),
                    pact_password=pytestconfig.getoption("pact_password"),
                    pact_port=pytestconfig.getoption("pact_port"),
                    pact_user=pytestconfig.getoption("pact_user"),
                    provider=pact["provider"],
                    version=version,
                )

    request.addfinalizer(_publish)


@pytest.fixture(scope="session")
def pact_dir(tmpdir_factory):
    """Temporary directory that will store pacts for the session."""
    return tmpdir_factory.mktemp("pacts")


@pytest.fixture(scope="session")
def pact(pytestconfig, pact_dir):
    def _pact(consumer, provider):

        pact_exists = PACTS.get(f"{consumer}{provider}")

        if pact_exists:
            return pact_exists.get("pact")

        new_pact = Consumer(consumer).has_pact_with(
            Provider(provider),
            host_name=pytestconfig.getoption("pact_host"),
            pact_dir=pact_dir,
            port=8155,
            version="3.0.0",
        )

        PACTS.update(
            {
                f"{consumer}{provider}": {
                    "pact": new_pact,
                    "consumer": consumer,
                    "provider": provider,
                }
            }
        )
        return new_pact

    return _pact


def publish_to_broker(
    pact_host,
    pact_port,
    pact_user,
    pact_password,
    pact_dir,
    consumer,
    provider,
    version,
):
    """Publish pacts to the pact broker."""
    pact_file = f"{consumer}-{provider}-pact.json"
    pact_upload_url = f"http://{pact_host}:{pact_port}/pacts/provider/{provider}/consumer/{consumer}/version/{version}"
    with open(os.path.join(pact_dir, pact_file), "rb") as pact_file:
        pact_file_json = json.load(pact_file)

    basic_auth = requests.auth.HTTPBasicAuth(pact_user, pact_password)
    logging.info("Uploading pact file to pact broker: %s", pact_upload_url)

    response = requests.put(pact_upload_url, auth=basic_auth, json=pact_file_json)
    if not response.ok:
        logging.error("Error uploading: %s", response.content)
        response.raise_for_status()
