from unittest.mock import MagicMock, Mock

import pytest

from kspl.config_slurper import VariantViewData
from kspl.gui import ColumnManager


def create_mock_tree() -> Mock:
    """Create a properly configured mock tree that supports item assignment."""
    mock_tree = MagicMock()
    # Configure the mock to handle dictionary-style access
    mock_tree.__setitem__ = Mock()
    mock_tree.__getitem__ = Mock(return_value=[])
    return mock_tree


@pytest.fixture
def sample_variants() -> list[VariantViewData]:
    return [
        VariantViewData("variant1", {"config1": "value1"}),
        VariantViewData("variant2", {"config2": "value2"}),
        VariantViewData("variant3", {"config3": "value3"}),
    ]


def test_init() -> None:
    mock_tree = create_mock_tree()
    manager = ColumnManager(mock_tree)

    assert manager.tree is mock_tree
    assert manager.all_columns == []
    assert manager.visible_columns == []
    assert manager.header_texts == {}
    assert manager.selected_column_id is None
    assert manager.column_vars == {}


def test_update_columns_first_time(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)

    assert column_manager.all_columns == ["variant1", "variant2", "variant3"]
    assert column_manager.visible_columns == ["variant1", "variant2", "variant3"]
    assert column_manager.header_texts == {"variant1": "variant1", "variant2": "variant2", "variant3": "variant3"}
    assert column_manager.selected_column_id is None


def test_update_columns_preserves_existing_visible() -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    initial_variants = [
        VariantViewData("variant1", {}),
        VariantViewData("variant2", {}),
    ]
    column_manager.update_columns(initial_variants)
    column_manager.visible_columns = ["variant2"]

    new_variants = [
        VariantViewData("variant2", {}),
        VariantViewData("variant3", {}),
    ]
    column_manager.update_columns(new_variants)

    assert column_manager.all_columns == ["variant2", "variant3"]
    assert column_manager.visible_columns == ["variant2", "variant3"]


def test_update_columns_clears_selection(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.selected_column_id = "some_column"

    column_manager.update_columns(sample_variants)

    assert column_manager.selected_column_id is None


def test_set_selected_column_success(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)

    result = column_manager.set_selected_column("variant1")

    assert result is True
    assert column_manager.selected_column_id == "variant1"
    mock_tree.heading.assert_called_with("variant1", text="✅variant1")


def test_set_selected_column_invalid_column(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)

    result = column_manager.set_selected_column("invalid_column")

    assert result is False
    assert column_manager.selected_column_id is None


def test_clear_selection(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)
    column_manager.set_selected_column("variant1")

    column_manager.clear_selection()

    assert column_manager.selected_column_id is None
    mock_tree.heading.assert_called_with("variant1", text="variant1")


def test_clear_selection_no_selection() -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.clear_selection()

    assert column_manager.selected_column_id is None


def test_get_column_from_click_position_valid(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)
    mock_tree.identify_column.return_value = "#2"

    result = column_manager.get_column_from_click_position(100)

    assert result == "variant2"


def test_get_column_from_click_position_invalid_column_id(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)
    mock_tree.identify_column.return_value = ""

    result = column_manager.get_column_from_click_position(100)

    assert result is None


def test_get_column_from_click_position_first_column(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)
    mock_tree.identify_column.return_value = "#0"

    result = column_manager.get_column_from_click_position(100)

    assert result is None


def test_get_column_from_click_position_out_of_range(sample_variants: list[VariantViewData]) -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_columns(sample_variants)
    mock_tree.identify_column.return_value = "#10"

    result = column_manager.get_column_from_click_position(100)

    assert result is None


def test_update_visible_columns() -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    var1 = Mock()
    var1.get.return_value = True
    var2 = Mock()
    var2.get.return_value = False
    var3 = Mock()
    var3.get.return_value = True

    column_manager.column_vars = {
        "col1": var1,
        "col2": var2,
        "col3": var3,
    }

    column_manager.update_visible_columns()

    assert column_manager.visible_columns == ["col1", "col3"]
    mock_tree.__setitem__.assert_called_with("displaycolumns", ["col1", "col3"])


def test_update_visible_columns_empty_vars() -> None:
    mock_tree = create_mock_tree()
    column_manager = ColumnManager(mock_tree)

    column_manager.update_visible_columns()

    assert column_manager.visible_columns == []
    mock_tree.__setitem__.assert_called_with("displaycolumns", [])
