import os
from collections import abc

import boto3
import pytest
from moto import mock_ssm

from configur.config import Settings


def test_load():
    with pytest.raises(OSError):
        Settings().load("fake_file.toml")

    settings = Settings(config_filepath="example.toml")
    assert settings.project_name == "configur"

    # set arbitrary value to ensure it gets removed in next load
    settings.test = 123
    settings.load("example.toml")

    assert not hasattr(settings, "test")


def test_clear():
    settings = Settings(config_filepath="example.toml")
    assert settings.project_name == "configur"

    settings.clear()

    assert not hasattr(settings, "project_name")


def test_set_value_from_config_env_var():
    settings = Settings()

    # name in env, env var is used instead of defined value
    os.environ["PROJECT_NAME"] = "abc"
    settings._set_value_from_config("project_name", "test")
    assert settings.project_name == "abc"
    del os.environ["PROJECT_NAME"]


def test_set_value_from_config_env_var_parent():
    settings = Settings()

    # parent_child in env, it precedes set value
    os.environ["PARENT_CHILD"] = "abc"
    settings._set_value_from_config("child", "test", parent="parent")
    assert settings.parent.child == "abc"
    del os.environ["PARENT_CHILD"]

    os.environ["PARENT_CHILD"] = "false"
    settings._set_value_from_config("child", True, parent="parent")
    assert settings.parent.child is False
    del os.environ["PARENT_CHILD"]

    os.environ["PARENT_CHILD"] = "abc"
    settings._set_value_from_config("child", 123, parent="parent")
    assert settings.parent.child == "abc"
    del os.environ["PARENT_CHILD"]


def test_set_value_from_config_dict():
    settings = Settings()

    # value is dict
    settings._set_value_from_config("new_table", {"a": 1, "b": 2})
    assert settings.new_table.a == 1
    assert settings.new_table.b == 2


def test_set_value_from_config_float():
    settings = Settings()

    # value is float
    settings._set_value_from_config("new_float", 0.2)
    assert settings.new_float == 0.2


def test_set_value_from_config_int():
    settings = Settings()

    # value is int
    settings._set_value_from_config("new_int", 205)
    assert settings.new_int == 205


def test_set_value_from_config_env_string_interpolation():
    settings = Settings()

    # value is ${ENVIRONMENT_VARIABLE} format
    settings._set_value_from_config("env_var", "${SOME_ENV_VAR}")
    assert settings.env_var is None

    os.environ["SOME_ENV_VAR"] = "abc"
    settings._set_value_from_config("env_var", "${SOME_ENV_VAR}")
    assert settings.env_var == "abc"
    del os.environ["SOME_ENV_VAR"]


@mock_ssm
def test_set_value_from_config_ssm():
    settings = Settings()

    ssm = boto3.client('ssm')
    ssm.put_parameter(
        Name="/data/test/my_var",
        Value="test",
        Type="SecureString",
    )

    # ssm value
    settings._set_value_from_config("ssm_var", "ssm:/data/test/my_var")
    assert settings.ssm_var == "test"


def test_set_attr():
    settings = Settings(config_filepath="example.toml")

    assert not hasattr(settings, "test_var")
    settings.set_attr("test_var", "abc")
    assert hasattr(settings, "test_var")

    assert not hasattr(settings, "parent")
    settings.set_attr("child", "abc", "parent")

    assert hasattr(settings, "parent")
    assert hasattr(settings.parent, "child")

    settings.set_attr("test_dict", {"abc": 123})
    assert settings.test_dict.abc == 123


def test_getattr():
    settings = Settings(config_filepath="example.toml")

    assert settings.__getattr__("project_name") == "configur"
    assert settings.get("project_name") == "configur"
    assert settings.project_name == "configur"

    assert settings.__getattr__("_store") == settings._store


def test_setattr():
    settings = Settings(config_filepath="example.toml")
    assert isinstance(settings._store, dict)
    settings.__setattr__("_store", 123)
    assert isinstance(settings._store, int)


def test_contains():
    settings = Settings(config_filepath="example.toml")
    assert "project_name" in settings


def test_getitem():
    settings = Settings(config_filepath="example.toml")
    assert settings["project_name"]

    with pytest.raises(KeyError):
        assert settings["fake_var"]


def test_setitem():
    settings = Settings(config_filepath="example.toml")
    assert settings["project_name"] == "configur"

    settings["project_name"] = "foo"

    assert settings["project_name"] != "configur"


def test_items():
    settings = Settings(config_filepath="example.toml")

    assert issubclass(type(settings.items()), abc.ItemsView)
    assert settings.items() == settings._store.items()


def test_keys():
    settings = Settings(config_filepath="example.toml")

    assert issubclass(type(settings.keys()), abc.KeysView)
    assert settings.keys() == settings._store.keys()


def test_values():
    settings = Settings(config_filepath="example.toml")

    assert issubclass(type(settings.values()), abc.ValuesView)
    assert str(settings.values()) == str(settings._store.values())
