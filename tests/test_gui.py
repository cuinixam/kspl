from pathlib import Path
from unittest.mock import MagicMock, call

from kspl.config_slurper import SPLKConfigData
from kspl.gui import MainView


def test_spl_kconfig_data():
    this_dir = Path(__file__).parent.absolute()
    project_dir = this_dir / "data"
    kconfig_data = SPLKConfigData(project_dir)
    assert kconfig_data
    elements = kconfig_data.get_elements()
    assert len(elements) == 29


def test_on_close_quits_loop_without_destroying():
    view = MainView.__new__(MainView)
    view.root = MagicMock()
    view._on_close()
    assert view.root.mock_calls == [call.quit()]


def test_mainloop_does_not_destroy_the_window():
    # destroy() dispatches the <Configure> events that crash customtkinter at teardown;
    # the one-shot CLI window is reclaimed by process exit instead.
    view = MainView.__new__(MainView)
    view.root = MagicMock()
    view.mainloop()
    assert view.root.mock_calls == [call.mainloop()]
