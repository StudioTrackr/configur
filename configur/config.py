import logging
import os
import re
from typing import Any

from box import Box
from dotenv import find_dotenv, load_dotenv
from tomlkit import parse, items

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError
    _boto_available = True
except ImportError:
    logger.warning("boto3 is not installed - install it to use SSM parameters.")
    _boto_available = False


class Settings:
    """Settings class that can be accessed using either dict notation (settings.get('abc')) or
    dot notation (settings.snowflake.password). Reads from toml file and requires a table/section
    called 'default', along with a table/section for each environment, e.g. [local], [dev], [prod].
    Supports nested tables with dot notation, e.g. [local.snowflake].
    Inspired by ConfigParser and DynaConf.
    """

    TOML_TO_BUILTIN_MAP = {
        items.String: str,
        items.Bool: bool,
        items.Integer: int,
        items.Float: float,
    }

    INTERNAL_ATTRS = ["_store", "_ssm", "env"]

    def __init__(self, config_filepath: str = None, env: str = os.getenv("PROJECT_ENV", "local")):
        self._store = Box()
        self.env = env
        self._ssm = boto3.client("ssm") if _boto_available else None

        # Load from .env file if exists. Will set env variables for use in .ini files.
        load_dotenv(find_dotenv(usecwd=True), verbose=True)

        if config_filepath:
            self.load(config_filepath)

    def load(self, config_filepath: str):
        if not os.path.exists(config_filepath):
            raise OSError("Could not load the default or provided settings file.")

        self.clear()

        with open(config_filepath, "r") as f:
            settings_data = parse(f.read())

        if "default" not in settings_data:
            raise Exception("Settings file missing required section 'default'")

        for table, items in settings_data.items():
            if table.startswith(self.env) or table == "default":
                for k, v in items.items():
                    self._set_value_from_config(k, v)

    def clear(self):
        self._store = Box()

    def _set_value_from_config(self, name: str, value: Any, parent: str = None):
        # If an env var exists, it takes precedence over everything else
        if name.upper() in os.environ and not parent:
            self.set_attr(name, os.getenv(name.upper()), parent)
        # Or if there's an env var for nested child attr, such as PARENT_CHILD, it takes precedence over orig value
        elif parent and f"{parent.upper()}_{name.upper()}" in os.environ:
            self._set_from_parent_env_var(name, value, parent)
        # If the value is a dict, recursively call this fcn to un-nest it's fields and set them.
        elif isinstance(value, dict):
            for k, v in value.items():
                self._set_value_from_config(k, v, name)
        # If the value defined in toml is "${MY_VAR}", it must be set from env var. Check it exists and set it.
        elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            self._set_from_env_var_interpolation(name, value, parent)
        # If value defined with "ssm:" prefix, try fetching it from SSM parameter store.
        elif isinstance(value, str) and value.startswith("ssm:"):
            self._set_from_ssm(name, value, parent)
        # Otherwise, it should be standard type that can be set directly.
        else:
            self.set_attr(name, value, parent)

    def _set_from_env_var_interpolation(self, name: str, value: Any, parent: str = None):
        """Expecting environment variable with the value between ${}. If not found, variable is set to None."""
        var_name = re.findall(r'\${(.*?)}', value)[0]

        if var_name in os.environ:
            self.set_attr(name, os.getenv(var_name), parent)
        else:
            self.set_attr(name, None, parent)

    def _set_from_parent_env_var(self, name: str, value: Any, parent: str = None):
        """Allows overriding nested attributes by setting env var as PARENT_CHILD."""
        attr = os.getenv(f"{parent.upper()}_{name.upper()}")
        try:
            if type(value) in self.TOML_TO_BUILTIN_MAP:
                attr = self.TOML_TO_BUILTIN_MAP[type(value)](attr)
            elif type(value) == bool:
                attr = attr.lower() == "true"
            else:
                attr = type(value)(attr)
        except ValueError:
            logger.info(f"Could not cast setting {parent}.{name} with value {attr} to type {type(value)}")
            pass
        self.set_attr(name, attr, parent)

    def _set_from_ssm(self, name: str, value: Any, parent: str = None):
        """Gets parameter from ssm, where value starts with `ssm:` """
        if not _boto_available:
            raise ImportError("boto3 not available and is required to read from SSM.")

        try:
            param = self._ssm.get_parameter(
                Name=value.replace("ssm:", ""),
                WithDecryption=True
            )

            if param.get("Parameter"):
                self.set_attr(name, param["Parameter"]["Value"], parent)
        except ClientError as e:
            # Best effort to load parameter
            logger.error(e)

    def set_attr(self, name: str, value: Any, parent: str = None):
        if type(value) in self.TOML_TO_BUILTIN_MAP:
            value = self.TOML_TO_BUILTIN_MAP[type(value)](value)

        if isinstance(value, dict):
            value = Box(value)

        if parent:
            if parent not in self._store:
                self._store[parent] = Box()

            self._store[parent][name] = value
        else:
            self._store[name] = value

    def __dir__(self):
        """Enable auto-complete for code editors"""
        return (
            self.INTERNAL_ATTRS
            + [k.lower() for k in self._store.keys()]
        )

    def __getattr__(self, name):
        """Allow getting keys from self._store using dot notation"""
        if name in self.INTERNAL_ATTRS:
            return super(Settings, self).__getattribute__(name)
        value = getattr(self._store, name)
        return value

    def __setattr__(self, name, value):
        """Allow `settings.FOO = 'value'` while keeping internal attrs."""
        if name in self.INTERNAL_ATTRS:
            super(Settings, self).__setattr__(name, value)
        else:
            self.set_attr(name, value)

    def __contains__(self, item):
        """Respond to `item in settings`"""
        return item.upper() in self._store or item.lower() in self._store

    def __getitem__(self, item):
        """Allow getting variables as dict keys `settings['KEY']`"""
        value = self._store.get(item)
        if value is None:
            raise KeyError(f"{item} does not exist")
        return value

    def __setitem__(self, key, value):
        """Allow `settings['KEY'] = 'value'`"""
        self.set_attr(key, value)

    def __iter__(self):
        """Redirects to store object"""
        yield from self._store

    def items(self):
        """Redirects to store object"""
        return self._store.items()

    def keys(self):
        """Redirects to store object"""
        return self._store.keys()

    def values(self):
        """Redirects to store object"""
        return self._store.values()
