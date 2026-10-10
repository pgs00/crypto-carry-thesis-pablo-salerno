"""Authenticate the original continuous E3 ZIP before archived evidence tests."""

import pytest


@pytest.fixture(scope="session")
def authenticated_e3():
    from scripts.publish_thesis import load_source

    files, _ = load_source()
    return files
