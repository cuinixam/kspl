from pathlib import Path

from kspl.gui import SPLKConfigData


def test_spl_kconfig_data():
    this_dir = Path(__file__).parent.absolute()
    project_dir = this_dir / "data"
    kconfig_data = SPLKConfigData(project_dir)
    assert kconfig_data
    elements = kconfig_data.get_elements()
    assert len(elements) == 29
