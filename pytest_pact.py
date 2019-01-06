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
        "--pact-broker",
        action="store",
        dest="broker_host",
        help="URI of the pact broker",
        type=str,
    )
    group.addoption(
        "--pact-broker-user",
        action="store",
        dest="broker_user",
        help="Pact broker username",
        type=str,
    )
    group.addoption(
        "--pact-broker-password",
        action="store",
        dest="broker_password",
        help="Pact broker password",
        type=str,
    )


@pytest.fixture(scope="session", autouse=True)
def pact_publisher(request, pytestconfig, pact_dir):
    def _publish():
        version = pytestconfig.getoption("--publish-pact")
        if not request.session.testsfailed and version:
            for _, pact in PACTS.items():
                push_to_broker(
                    broker_host=pytestconfig.getoption("broker_host"),
                    broker_user=pytestconfig.getoption("broker_user"),
                    broker_password=pytestconfig.getoption("broker_password"),
                    consumer=pact["consumer"],
                    pact_dir=pact_dir,
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
            host_name=pytestconfig.getoption("broker_host"),
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


def push_to_broker(
    broker_host, broker_user, broker_password, pact_dir, consumer, provider, version
):
    """Publish pacts to the pact broker."""
    pact_file = f"{consumer}-{provider}-pact.json"
    pact_upload_url = (
        f"{broker_host}/pacts/provider/{provider}/consumer/{consumer}/version/{version}"
    )
    with open(os.path.join(pact_dir, pact_file), "rb") as pact_file:
        pact_file_json = json.load(pact_file)

    basic_auth = requests.auth.HTTPBasicAuth(broker_user, broker_password)
    logging.info("Uploading pact file to pact broker: %s", pact_upload_url)

    response = requests.put(pact_upload_url, auth=basic_auth, json=pact_file_json)
    if not response.ok:
        logging.error("Error uploading: %s", response.content)
        response.raise_for_status()
