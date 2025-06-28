from dataclasses import dataclass
from pathlib import Path
from typing import Any

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from kspl.kconfig import EditableConfigElement, KConfig


@dataclass
class VariantViewData:
    """A variant is a set of configuration values for a KConfig model."""

    name: str
    config_dict: dict[str, Any]


@dataclass
class VariantData:
    name: str
    config: KConfig

    def find_element(self, element_name: str) -> EditableConfigElement | None:
        return self.config.find_element(element_name)


class SPLKConfigData:
    def __init__(self, project_root_dir: Path) -> None:
        self.project_root_dir = project_root_dir.absolute()
        variant_config_files = self._search_variant_config_file(self.project_root_dir)
        if not self.kconfig_model_file.is_file():
            raise UserNotificationException(f"File {self.kconfig_model_file} does not exist.")
        self.model = KConfig(self.kconfig_model_file)
        if variant_config_files:
            self.variant_configs: list[VariantData] = [VariantData(self._get_variant_name(file), KConfig(self.kconfig_model_file, file)) for file in variant_config_files]
        else:
            self.variant_configs = [VariantData("Default", self.model)]
        self.logger = logger.bind()

    @property
    def kconfig_model_file(self) -> Path:
        return self.project_root_dir / "KConfig"

    def get_elements(self) -> list[EditableConfigElement]:
        return self.model.elements

    def get_variants(self) -> list[VariantViewData]:
        variants = []

        for variant in self.variant_configs:
            variants.append(
                VariantViewData(
                    variant.name,
                    {config_elem.name: config_elem.value for config_elem in variant.config.elements if not config_elem.is_menu},
                )
            )
        return variants

    def _get_variant_name(self, file: Path) -> str:
        return file.relative_to(self.project_root_dir / "variants").parent.as_posix()

    def _search_variant_config_file(self, project_dir: Path) -> list[Path]:
        """Finds all files called 'config.txt' in the variants directory and returns a list with their paths."""
        return list((project_dir / "variants").glob("**/config.txt"))

    def find_variant_config(self, variant_name: str) -> VariantData | None:
        for variant in self.variant_configs:
            if variant.name == variant_name:
                return variant
        return None

    def refresh_data(self) -> None:
        """Refresh the KConfig data by reloading all configuration files."""
        variant_config_files = self._search_variant_config_file(self.project_root_dir)
        if not self.kconfig_model_file.is_file():
            raise UserNotificationException(f"File {self.kconfig_model_file} does not exist.")

        # Reload the model
        self.model = KConfig(self.kconfig_model_file)

        # Reload variant configurations
        if variant_config_files:
            self.variant_configs = [VariantData(self._get_variant_name(file), KConfig(self.kconfig_model_file, file)) for file in variant_config_files]
        else:
            self.variant_configs = [VariantData("Default", self.model)]

        self.logger.info(f"Refreshed data: found {len(self.variant_configs)} variants")
