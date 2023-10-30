import os
import textwrap
from argparse import Namespace
from pathlib import Path

import pytest

from kspl.generate import CMakeWriter, GenerateCommand, HeaderWriter, JsonWriter
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


def test_header_writer(tmp_path: Path, configuration_data: ConfigurationData) -> None:
    header_file = tmp_path / "my_file.h"
    writer = HeaderWriter(header_file)
    writer.write(configuration_data)
    assert header_file.read_text() == textwrap.dedent(
        """\
    /** @file */
    #ifndef __autoconf_h__
    #define __autoconf_h__

    /** NAME */
    #define CONFIG_NAME "John Smith"
    /** STATUS_SET */
    #define CONFIG_STATUS_SET 1
    /** MY_INT */
    #define CONFIG_MY_INT 13
    /** MY_HEX */
    #define CONFIG_MY_HEX 0x10

    #endif /* __autoconf_h__ */
    """
    )


def test_header_file_written_when_changed(tmp_path: Path) -> None:
    os.environ["HowDoYouLikeThis"] = "ThisIsCool"
    feature_model_file = tmp_path / "kconfig.txt"
    feature_model_file.write_text(
        """
        menu "First menu"
            config FIRST_BOOL
                bool "You can select FIRST_BOOL"
        endmenu
        """
    )

    user_config = tmp_path / "user.config"
    user_config.write_text(
        textwrap.dedent(
            """\
            CONFIG_FIRST_BOOL=y
        """
        )
    )
    header_file = tmp_path / "my_file.h"
    config = KConfig(feature_model_file, user_config).collect_config_data()

    writer = HeaderWriter(header_file)
    writer.write(config)

    assert header_file.exists()
    timestamp = header_file.stat().st_mtime
    writer.write(config)
    assert (
        header_file.stat().st_mtime == timestamp
    ), "the file shall not be written if content is not changed"
    header_file.write_text("Modified content")
    writer.write(config)
    assert (
        header_file.read_text() != "Modified content"
    ), "the file should have been updated because the content changed"


def test_json_writer(configuration_data: ConfigurationData) -> None:
    writer = JsonWriter(Path("my_file.json"))
    assert writer.generate_content(configuration_data) == textwrap.dedent(
        """\
    {
        "features": {
            "NAME": "John Smith",
            "STATUS_SET": true,
            "STATUS_NOT_SET": false,
            "MY_INT": 13,
            "MY_HEX": 16
        }
    }"""
    )


def test_cmake_writer(configuration_data: ConfigurationData) -> None:
    writer = CMakeWriter(Path("my_file.cmake"))
    assert writer.generate_content(configuration_data) == textwrap.dedent(
        """\
        set(NAME "John Smith")
        set(STATUS_SET "True")
        set(STATUS_NOT_SET "False")
        set(MY_INT "13")
        set(MY_HEX "16")"""
    )


def test_generate(tmp_path: Path) -> None:
    """
    KConfigLib can generate the configuration as C-header file (like autoconf.h)
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
    header_file = tmp_path.joinpath("gen/header.h")
    json_file = tmp_path.joinpath("gen/features.json")
    cmake_file = tmp_path.joinpath("gen/features.cmake")

    GenerateCommand().run(
        Namespace(
            **{
                "kconfig_model_file": f"{feature_model_file}",
                "kconfig_config_file": f"{user_config}",
                "out_header_file": f"{header_file}",
                "out_json_file": f"{json_file}",
                "out_cmake_file": f"{cmake_file}",
            }
        )
    )
    assert json_file.exists()
    assert cmake_file.exists()
    assert header_file.exists()
