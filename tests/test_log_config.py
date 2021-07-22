import logging.config

import pytest

from configur.logging_config import init_logging


@pytest.fixture(autouse=True)
def reset_logger():
    # Reset any existing logging
    logging.root = logging.RootLogger(logging.WARNING)
    logging.root.manager.loggerDict = {}
    yield


def test_init_logging_levels():
    assert logging.getLogger().level == logging.WARNING

    init_logging(env="local")

    assert logging.getLogger().level == logging.DEBUG

    init_logging(env="qa")

    assert logging.getLogger().level == logging.INFO

    init_logging(env="prod")

    assert logging.getLogger().level == logging.INFO

    init_logging(env="dev")

    assert logging.getLogger().level == logging.DEBUG

    init_logging(env="local", root_level="ERROR")

    assert logging.getLogger().level == logging.ERROR

    with pytest.raises(Exception):
        init_logging(root_level="FAKE_LEVEL")


def test_init_logging_additional_loggers():
    loggers = logging.root.manager.loggerDict

    init_logging()
    assert loggers.get("boto3")
    assert loggers["boto3"].level == logging.INFO

    init_logging(loggers={"boto3": "DEBUG"})
    assert loggers["boto3"].level == logging.DEBUG

    with pytest.raises(Exception):
        init_logging(loggers={"boto3": "FAKE_LEVEL"})
