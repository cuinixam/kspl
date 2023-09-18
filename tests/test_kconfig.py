import os
import textwrap
from pathlib import Path

import pytest

from kspl.kconfig import (
    ConfigElement,
    ConfigElementType,
    ConfigurationData,
    KConfig,
    TriState,
)


@pytest.fixture
def configuration_data():
    return ConfigurationData(
        [
            ConfigElement(ConfigElementType.STRING, "NAME", "John Smith"),
            ConfigElement(ConfigElementType.BOOL, "STATUS_SET", TriState.Y),
            ConfigElement(ConfigElementType.BOOL, "STATUS_NOT_SET", TriState.N),
            ConfigElement(ConfigElementType.INT, "MY_INT", 13),
            ConfigElement(ConfigElementType.HEX, "MY_HEX", 0x10),
        ]
    )


def test_create_configuration_data(tmp_path: Path) -> None:
    feature_model_file = tmp_path / "my_file.txt"
    feature_model_file.write_text(
        """
    config NAME
        string "Description"
        default "John Smith"
    config STATUS
        bool "Description"
        default y
    config NOT_SET
        bool "Description"
        default n
    """
    )
    iut = KConfig(feature_model_file)
    assert iut.config.elements[0].type == ConfigElementType.STRING
    assert iut.config.elements[0].value == "John Smith"
    assert iut.config.elements[1].type == ConfigElementType.BOOL
    assert iut.config.elements[1].name == "STATUS"
    assert iut.config.elements[1].value == TriState.Y
    assert iut.config.elements[2].type == ConfigElementType.BOOL
    assert iut.config.elements[2].name == "NOT_SET"
    assert iut.config.elements[2].value == TriState.N


def test_create_configuration_data_with_variables(tmp_path: Path) -> None:
    feature_model_file = tmp_path / "my_file.txt"
    feature_model_file.write_text(
        """
    config NAME
        string "Description"
        default "John Smith"
    config REFERENCING
        string "Reference another KConfig value here"
        default "Variable: ${NAME}, environment variable: ${ENV:MY_ENV_VAR}"
    """
    )
    # define MY_ENV_VAR environment variable
    os.environ["MY_ENV_VAR"] = "MY_ENV_VAR_VALUE"
    iut = KConfig(feature_model_file)
    assert iut.config.elements[0].value == "John Smith"
    assert iut.config.elements[1].type == ConfigElementType.STRING
    assert (
        iut.config.elements[1].value
        == "Variable: John Smith, environment variable: MY_ENV_VAR_VALUE"
    )


def test_boolean_without_description(tmp_path: Path) -> None:
    """
    A configuration without description can not be selected by the user
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
    mainmenu "This is the main menu"
        menu "First menu"
            config FIRST_BOOL
                bool
            config FIRST_NAME
                string "You can select this"
            config SECOND_NAME
                string
        endmenu
    """,
    )
    user_config = tmp_path / "user.txt"
    user_config.write_text(
        textwrap.dedent(
            """
    CONFIG_FIRST_BOOL=y
    CONFIG_FIRST_NAME="Dude"
    CONFIG_SECOND_NAME="King"
    """
        ),
    )

    iut = KConfig(feature_model_file, user_config)
    assert iut.config.elements == [
        ConfigElement(ConfigElementType.STRING, "FIRST_NAME", "Dude")
    ]


def test_boolean_with_description(tmp_path: Path) -> None:
    """
    A configuration with description can be selected by the user
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
    mainmenu "This is the main menu"
        menu "First menu"
            config FIRST_BOOL
                bool "You can select this"
            config FIRST_NAME
                string "You can select this also"
        endmenu
    """,
    )
    user_config = tmp_path / "user.txt"
    user_config.write_text(
        textwrap.dedent(
            """
    CONFIG_FIRST_BOOL=y
    CONFIG_FIRST_NAME="Dude"
    """
        ),
    )

    iut = KConfig(feature_model_file, user_config)
    assert iut.config.elements == [
        ConfigElement(ConfigElementType.BOOL, "FIRST_BOOL", TriState.Y),
        ConfigElement(ConfigElementType.STRING, "FIRST_NAME", "Dude"),
    ]


def test_hex(tmp_path: Path) -> None:
    """
    A configuration with description can be selected by the user
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
        menu "First menu"
            config MY_HEX
                hex
                default 0x00FF
                help
                    my hex value
        endmenu
    """,
    )

    iut = KConfig(feature_model_file)
    assert iut.config.elements == [ConfigElement(ConfigElementType.HEX, "MY_HEX", 0xFF)]


def test_define_boolean_choices(tmp_path: Path) -> None:
    """
    Using a boolean choice will define a boolean for every value.
    Only the choices with a 'prompt' are selectable.
    There is a warning generated for choices without a 'prompt'.
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
    choice APP_VERSION
        prompt "application version"
        default APP_VERSION_1
        help
            Currently there are several application version supported.
            Select the one that matches your needs.

        config APP_VERSION_1
            bool
            prompt "app v1"
        config APP_VERSION_2
            bool
            prompt "app v2"
        # This is not selectable because it has no prompt
        config APP_VERSION_3
            bool
    endchoice
    """,
    )
    user_config = tmp_path / "user.txt"
    user_config.write_text(
        textwrap.dedent(
            """
    CONFIG_APP_VERSION="APP_VERSION_1"
    """
        ),
    )

    iut = KConfig(feature_model_file, user_config)
    assert iut.config.elements == [
        ConfigElement(ConfigElementType.BOOL, "APP_VERSION_1", TriState.Y),
        ConfigElement(ConfigElementType.BOOL, "APP_VERSION_2", TriState.N),
    ]


def test_define_string_choices(tmp_path: Path) -> None:
    """
    A choice can only be of type bool or tristate.
    One can use string but a warning will be issued.
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
    choice APP_VERSION
        prompt "application version"
        default APP_VERSION_1
        help
            Currently there are several application version supported.
            Select the one that matches your needs.

        config APP_VERSION_1
            string
            prompt "app v1"
        config APP_VERSION_2
            string
            prompt "app v2"
    endchoice
    """,
    )
    user_config = tmp_path / "user.txt"
    user_config.write_text(
        textwrap.dedent(
            """
    CONFIG_APP_VERSION="APP_VERSION_1"
    CONFIG_APP_VERSION_1="VERSION_NEW"
    """
        ),
    )

    iut = KConfig(feature_model_file, user_config)
    assert iut.config.elements == [
        ConfigElement(ConfigElementType.STRING, "APP_VERSION_1", "VERSION_NEW"),
        ConfigElement(ConfigElementType.STRING, "APP_VERSION_2", ""),
    ]


def test_define_tristate_choices(tmp_path: Path) -> None:
    """
    For KConfig, `bool` and `tristate` types are represented as JSON Booleans,
    the third `tristate` state is not supported.
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
    choice APP_VERSION
        prompt "application version"
        default APP_VERSION_1
        help
            Currently there are several application version supported.
            Select the one that matches your needs.

        config APP_VERSION_1
            tristate
            prompt "app v1"
        config APP_VERSION_2
            tristate
            prompt "app v2"
    endchoice
    """,
    )
    user_config = tmp_path / "user.txt"
    user_config.write_text(
        textwrap.dedent(
            """
    CONFIG_APP_VERSION="APP_VERSION_1"
    """
        ),
    )

    iut = KConfig(feature_model_file, user_config)
    assert iut.config.elements == [
        ConfigElement(ConfigElementType.BOOL, "APP_VERSION_1", TriState.Y),
        ConfigElement(ConfigElementType.BOOL, "APP_VERSION_2", TriState.N),
    ]


def test_config_including_other_config(tmp_path: Path) -> None:
    """
    Including other configuration files with 'source' works only as relative paths to the main file folder :(
    See how 'common.txt' must include 'new.txt' with its relative path to the main file.
    One can also use:
        * 'rsource' - for paths relative to the current file
        * 'osource' - for files that might not exist
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
    menu "First menu"
        config FIRST_BOOL
            bool "You can select FIRST_BOOL"
        config FIRST_NAME
            string "You can select FIRST_NAME"
    endmenu
    source "common/common.txt"
    """,
    )
    file = tmp_path / "common/common.txt"
    file.parent.mkdir(parents=True)
    file.write_text(
        """
    config COMMON_BOOL
        bool "You can select COMMON_BOOL"
        default n
    source "new/new.txt"
    """
    )
    file = tmp_path / "new/new.txt"
    file.parent.mkdir(parents=True)
    file.write_text(
        """
    config NEW_BOOL
        bool "You can select NEW_BOOL"
        default n
    """
    )
    user_config = tmp_path / "user.txt"
    user_config.write_text(
        textwrap.dedent(
            """
    CONFIG_FIRST_BOOL=y
    CONFIG_FIRST_NAME="Dude"
    CONFIG_COMMON_BOOL=y
    CONFIG_NEW_BOOL=y
    """
        ),
    )
    iut = KConfig(feature_model_file, user_config)
    assert iut.config.elements == [
        ConfigElement(ConfigElementType.BOOL, "FIRST_BOOL", TriState.Y),
        ConfigElement(ConfigElementType.STRING, "FIRST_NAME", "Dude"),
        ConfigElement(ConfigElementType.BOOL, "COMMON_BOOL", TriState.Y),
        ConfigElement(ConfigElementType.BOOL, "NEW_BOOL", TriState.Y),
    ]


def test_config_including_other_configs_based_on_env_vars(tmp_path: Path) -> None:
    """
    One can refer to environment variables when including other files
    """
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
    menu "First menu"
        config FIRST_BOOL
            bool "You can select FIRST_BOOL"
        config FIRST_NAME
            string "You can select FIRST_NAME"
    endmenu
    source "$(COMMON_PATH)/common.txt"
    """,
    )
    file = tmp_path / "common/common.txt"
    file.parent.mkdir(parents=True)
    file.write_text(
        """
    config COMMON_BOOL
        bool "You can select COMMON_BOOL"
        default n
    """
    )
    user_config = tmp_path / "user.txt"
    user_config.write_text(
        textwrap.dedent(
            """
    CONFIG_FIRST_BOOL=y
    CONFIG_FIRST_NAME="Dude"
    CONFIG_COMMON_BOOL=y
    """
        ),
    )
    os.environ["COMMON_PATH"] = "common"
    iut = KConfig(feature_model_file, user_config)
    assert iut.config.elements == [
        ConfigElement(ConfigElementType.BOOL, "FIRST_BOOL", TriState.Y),
        ConfigElement(ConfigElementType.STRING, "FIRST_NAME", "Dude"),
        ConfigElement(ConfigElementType.BOOL, "COMMON_BOOL", TriState.Y),
    ]


def test_extract_elements_with_levels():
    this_dir = Path(__file__).parent.absolute()
    kconfig_model_file = this_dir / "data" / "KConfig"
    assert kconfig_model_file.is_file()
    kconfig = KConfig(kconfig_model_file)
    assert 29 == len(kconfig.elements)
    # check how many elements of type MENU are there
    assert 10 == len([e for e in kconfig.elements if e.type == ConfigElementType.MENU])
