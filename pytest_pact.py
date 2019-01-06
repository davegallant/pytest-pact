# -*- coding: utf-8 -*-

import json
import logging
import os
import requests
import pytest
from pactman import Consumer, Provider
from requests.auth import HTTPBasicAuth

PACTS = {}


def pytest_addoption(parser):
    parser.addoption(
        "--publish-pact",
        type=str,
        action="store",
        help="Upload generated pact file to pact broker with version",
    )


@pytest.fixture(scope="session", autouse=True)
def pact_publisher(request):
    def _publish():
        version = request.config.getoption("--publish-pact")
        if not request.session.testsfailed and version:
            for _, pact in PACTS.items():
                push_to_broker(version, pact["consumer"], pact["provider"])

    request.addfinalizer(_publish)


@pytest.fixture(scope="session")
def pact(request):
    def _pact(consumer, provider):

        pact_exists = PACTS.get(f"{consumer}{provider}")

        if pact_exists:
            return pact_exists.get("pact")

        new_pact = Consumer(consumer).has_pact_with(
            Provider(provider),
            host_name=ENV("APP_HOST"),
            pact_dir=ENV("PACT_DIR"),
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


def push_to_broker(version, consumer, provider):
    pact_file = f"{consumer}-{provider}-pact.json"
    pact_upload_url = f"{ENV('PACT_BROKER_URI')}/pacts/provider/{provider}/consumer/{consumer}/version/{version}"
    with open(os.path.join(ENV("PACT_DIR"), pact_file), "rb") as pact_file:
        pact_file_json = json.load(pact_file)

    basic_auth = HTTPBasicAuth(ENV("PACT_BROKER_USERNAME"), ENV("PACT_BROKER_PASSWORD"))
    logging.info("Uploading pact file to pact broker: %s", pact_upload_url)

    response = requests.put(pact_upload_url, auth=basic_auth, json=pact_file_json)
    if not response.ok:
        logging.error("Error uploading: %s", response.content)
        response.raise_for_status()

