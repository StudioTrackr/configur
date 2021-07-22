## Configur
#### TOML-based configuration for Python

### Features
* TOML file configuration definition (supports nested tables, multiple environments)
* Fetching variables from AWS Parameter Store (SSM), secure or standard
* Override any configuration at runtime with an environment variable
* Simple logging config: easily set levels per package, special handling for AWS Lambda


#### Configuration
All configuration is defined in a single TOML file, e.g., `settings.toml` or `config.toml`. See
the [example](https://github.com/StudioTrackr/configur/blob/main/example.toml) for a better idea of how it's structured.

Certain secrets (e.g. passwords) that should not be checked into Git can be interpolated from
environment variables. If you declared an item as `my_var = "${EXAMPLE_VALUE}"`, you will
need to have an environment variable `EXAMPLE_VALUE` defined. Configur also come with `dotenv`, so feel free
to define a `.env` file for storing these environment variables.

To avoid passing secrets in plaintext in the run environment, you can also define variables in AWS Systems Manager
Parameter Store (SSM). To do so, simply prefix the value with `ssm:` in the TOML file, and the code will automatically
fetch and decode the param at runtime, assuming the proper credentials are available to get and decrypt the parameter.

These configuration files are parsed by the [TOML Kit](https://github.com/sdispater/tomlkit) library, and then stored 
as attributes on an object called [Settings](#Settings). 

Every settings.toml file must have a `default` table. These default values are shared across all environments.

```
[default]
output_file_name = "example.csv"
```

After the `default` table, a table for each environment should exist, e.g. "local", "dev", and "prod". These tables override
any values that exist in the `default` table with the same name; in other words - environment settings take precedence over default settings.
Below we have two environments, `local` and `dev`, each with a custom `database_username` variable. In `dev`, we override the default `output_file_name`.
```
[default]
output_file_name = "example.csv"

[local]
database_username = "local_user"

[dev]
output_file_name = "example_dev.csv"
database_username = "dev_user"
```

Since TOML and TOML Kit support nested tables/sections, we use them within the context of an environment. To declare a group of settings
for a given environment, prefix the table name with the name of the environment, e.g. `local.mysql`.

```
[default]
output_file_name = "example.csv"

[local]
    [local.mysql]
    username = "local_user"
    password = "secret password"
```

Read more below for how these values are accessed in Settings.

#### Settings
The [Settings](https://github.com/StudioTrackr/configur/blob/main/configur/config.py) class reads `settings.toml` files, and sets attributes on itself for 
every item in the config file. However, it will only ever load settings from the `default` table and the table (and its children) matching 
the current environment, e.g., `local`. The environment **must** be set with a variable `PROJECT_ENV`, otherwise the fallback 
is `local` so nothing will ever touch production by accident. The value of this variable needs to match a corresponding section in your `settings.toml` file,
but you are free to name environments as you wish. There's no difference if you call an environment `dev` or `sandbox` or `test`, so long as
you set `PROJECT_ENV=dev` or `PROJECT_ENV=sandbox` or `PROJECT_ENV=test`.

Initialization:
```
from configur import Settings
settings = Settings(config_filepath=custom_path + "settings.toml")
```

By default, it extracts the environment from the `PROJECT_ENV` variable, but you can override if needed by passing an `env` argument:
```
settings = Settings(config_filepath=custom_path + "settings.toml", env="dev")
```

After your config file is read, the default and environment-specific values are set to be accessible from the Settings object
in either dict-notation, or dot-notation. Inspired by [Dynaconf](https://www.dynaconf.com/), this means you can do the following:
```
# Get
settings.user
settings.get("user")
settings["user"]

# Get nested settings e.g. from [local.mysql] section of settings.toml
settings.mysql.user
settings.get("mysql").user
settings["mysql"]["user"]

# Set
settings.user = "admin"
settings["user"] = "admin"

# Iterate
for x in settings.items()
for x in settings.keys()
for x in settings.values()
```

This flexibility makes it easier to access settings vs always having to use dict-notation, get environment variables every time, 
or use ConfigParser and pass the section for every variable. 

Because Settings is a dict-like object, you can also set values to update config or store state as your job progresses. 
This can however introduce side effects since you are bringing state into functions, but it can be handy to throw variables in here
instead of passing them down a large tree of functions as standard arguments.

#### Logging
Configur provides a function `init_logging` which initializes handlers, formatters, and loggers with Python's logging.config.dictConfig.
Similar to Settings, you can pass a custom `env` argument but the default is your `PROJECT_ENV` environment variable.
We set the root log level based on your environment (local, dev = DEBUG, all others = INFO), but you can also pass this as an
override with the `root_level` argument, OR by setting an environment variable `ROOT_LOG_LEVEL`. We also expose the logging.config option
`disable_existing_loggers` as an argument, defaulted to False. 

##### Customizing module loggers: 
You can customize the log level for any module by passing a dictionary where keys are module names, and values are log levels. 
Example as read from `settings.toml`:

```
# settings.toml
[logging]
boto3 = "DEBUG"
botocore = "ERROR"

# main.py
init_logging(loggers=settings.logging)
```

##### Special Handling for AWS Lambda
Since AWS Lambda controls the logging environment, we can't/shouldn't set any custom formatters or logging config. What 
we can do though is set the overall log level. When running a lambda recipe, use the `is_lambda` option, which when set to True
will skip the dictConfig initialization and just call `logging.getLogger().setLevel(log_level)` with either the default
environment level, or a custom level passed in like `init_logging(level="DEBUG")`.
