"""
Unit tests for Task II: Additional Inputs Dialog Validation & State Management.

Covers the 10 requirements:
1. Custom mode selected + empty field -> saving blocked.
2. Custom mode selected + whitespace-only field -> saving blocked.
3. Custom mode selected + valid field -> saving succeeds.
4. Non-Custom mode + empty custom field -> validation does not incorrectly block saving.
5. Editing an input sets is_modified=True.
6. Initial loading does not incorrectly set is_modified=True.
7. Successful save resets is_modified=False.
8. Closing modified dialog + Discard -> dialog closes.
9. Closing modified dialog + Cancel -> dialog remains open.
10. Closing unmodified dialog -> closes without warning.
Plus additional tests for CustomTitleBar close button and inactive tab validation.
"""
import sys
from unittest.mock import patch, MagicMock
import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtCore import Qt, QEvent

from osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs import AdditionalInputs
from osdagbridge.core.bridge_types.plate_girder.defaults import solve_extend_basic_input_dict
from osdagbridge.core.utils.common import (
    KEY_SPAN, KEY_CARRIAGEWAY_WIDTH, KEY_FOOTPATH, KEY_INCLUDE_MEDIAN,
    KEY_DESIGN_MODE, KEY_LL_FOOTPATH_PRESSURE, KEY_CB_TYPE, KEY_CB_WIDTH,
    KEY_MD_TYPE, KEY_MD_WIDTH, KEY_MP_GIRDER_DEPTH,
)
from osdagbridge.desktop.ui.dialogs.additional_input.ui_builder.common_ui_builder import AdaptiveWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance for all GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="module")
def solved_input_dict():
    """Provide a realistic 539-key solved bridge input dictionary."""
    d = {
        KEY_SPAN: 30.0,
        KEY_CARRIAGEWAY_WIDTH: 7.5,
        KEY_FOOTPATH: "None",
        KEY_INCLUDE_MEDIAN: "No",
        KEY_DESIGN_MODE: "Optimized",
    }
    solve_extend_basic_input_dict(d)
    return d


@pytest.fixture(scope="module")
def dialog(qapp, solved_input_dict):
    """Instantiate and prime AdditionalInputs with default solved dictionary."""
    ai = AdditionalInputs()
    ai.set_input_dictionary(solved_input_dict)
    return ai


@pytest.fixture(autouse=True)
def reset_dialog_state(dialog, solved_input_dict):
    """Reset dialog inputs and modification state before and after each test."""
    dialog._loading = True
    try:
        fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
        if fp_mode:
            fp_mode.setCurrentText("As per IRC 6")
        fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
        if fp_val:
            fp_val.setText("")

        md_type = dialog.findChild(QComboBox, KEY_MD_TYPE)
        if md_type:
            md_type.setCurrentText("IRC 5 - Raised Kerb")

        cb_type = dialog.findChild(QComboBox, KEY_CB_TYPE)
        if cb_type:
            cb_type.setCurrentText("IRC 5 - RCC Crash Barrier")

        dialog.design_mode_trigger("Optimized")
        dialog.set_input_dictionary(dict(solved_input_dict))
        dialog.tabs.setCurrentIndex(0)
    finally:
        dialog._loading = False
        dialog.is_modified = False
    yield
    dialog._loading = True
    try:
        fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
        if fp_mode:
            fp_mode.setCurrentText("As per IRC 6")
        fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
        if fp_val:
            fp_val.setText("")

        md_type = dialog.findChild(QComboBox, KEY_MD_TYPE)
        if md_type:
            md_type.setCurrentText("IRC 5 - Raised Kerb")

        cb_type = dialog.findChild(QComboBox, KEY_CB_TYPE)
        if cb_type:
            cb_type.setCurrentText("IRC 5 - RCC Crash Barrier")

        dialog.design_mode_trigger("Optimized")
        dialog.set_input_dictionary(dict(solved_input_dict))
        dialog.tabs.setCurrentIndex(0)
    finally:
        dialog._loading = False
        dialog.is_modified = False


def test_initial_loading_sets_is_modified_false(dialog):
    """Requirement 6: Initial loading does not incorrectly set is_modified=True."""
    assert dialog.is_modified is False


def test_editing_input_sets_is_modified_true(dialog):
    """Requirement 5: Editing an input sets is_modified=True."""
    assert dialog.is_modified is False
    fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
    assert fp_mode is not None
    fp_mode.setCurrentText("Custom")
    assert dialog.is_modified is True


def test_custom_mode_empty_field_blocks_save(dialog):
    """Requirement 1: Custom mode selected + empty field -> saving blocked and identifies parameter."""
    fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
    fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
    assert fp_mode is not None and fp_val is not None

    fp_val.setText("")
    fp_mode.setCurrentText("Custom")

    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is False
    assert err_msg is not None
    assert "Footpath Pressure" in err_msg

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_box.return_value = mock_instance
        dialog._save_inputs()

        mock_box.assert_called_once()
        call_kwargs = mock_box.call_args[1]
        assert "Validation Error" in call_kwargs.get("title", "")
        assert "Footpath Pressure" in call_kwargs.get("text", "")
        # Dialog should remain modified because save was blocked
        assert dialog.is_modified is True


def test_custom_mode_whitespace_field_blocks_save(dialog):
    """Requirement 2: Custom mode selected + whitespace-only field -> saving blocked."""
    fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
    fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
    assert fp_mode is not None and fp_val is not None

    fp_val.setText("     ")
    fp_mode.setCurrentText("Custom")

    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is False
    assert "Footpath Pressure" in err_msg


def test_custom_mode_valid_field_allows_save(dialog):
    """Requirement 3: Custom mode selected + valid field -> saving succeeds."""
    fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
    fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
    assert fp_mode is not None and fp_val is not None

    fp_val.setText("5.0")
    fp_mode.setCurrentText("Custom")

    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is True
    assert err_msg is None

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_box.return_value = mock_instance
        dialog._save_inputs()

        mock_box.assert_called_once()
        call_kwargs = mock_box.call_args[1]
        assert call_kwargs.get("title") == "Saved"


def test_non_custom_mode_empty_field_allows_save(dialog):
    """Requirement 4: Non-Custom mode + empty custom field -> validation does not incorrectly block saving."""
    fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
    fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
    assert fp_mode is not None and fp_val is not None

    # Clear custom input text while in standard non-custom mode
    fp_mode.setCurrentText("As per IRC 6")
    fp_val.setText("")

    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is True
    assert err_msg is None


def test_successful_save_resets_is_modified_false(dialog):
    """Requirement 7: Successful save resets is_modified=False."""
    fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
    fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
    assert fp_mode is not None and fp_val is not None

    fp_mode.setCurrentText("As per IRC 6")
    dialog.is_modified = False
    fp_val.setText("4.0")
    fp_mode.setCurrentText("Custom")
    assert dialog.is_modified is True

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_box.return_value = mock_instance
        dialog._save_inputs()

    assert dialog.is_modified is False


def test_closing_modified_dialog_discard_closes(dialog):
    """Requirement 8: Closing modified dialog + Discard -> dialog closes and resets working dict."""
    dialog.is_modified = True
    ev = QCloseEvent()

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = "Discard"
        mock_box.return_value = mock_instance

        dialog.closeEvent(ev)

        assert ev.isAccepted() is True
        assert dialog.is_modified is False
        mock_box.assert_called_once()
        assert "You have unsaved changes" in mock_box.call_args[1].get("text", "")


def test_closing_modified_dialog_cancel_keeps_open(dialog):
    """Requirement 9: Closing modified dialog + Cancel -> dialog remains open."""
    dialog.is_modified = True
    ev = QCloseEvent()

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = "Cancel"
        mock_box.return_value = mock_instance

        dialog.closeEvent(ev)

        assert ev.isAccepted() is False
        assert dialog.is_modified is True


def test_closing_unmodified_dialog_closes_without_warning(dialog):
    """Requirement 10: Closing unmodified dialog -> closes without warning."""
    dialog.is_modified = False
    ev = QCloseEvent()

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        dialog.closeEvent(ev)
        assert ev.isAccepted() is True
        mock_box.assert_not_called()


def test_titlebar_close_button_routes_to_close_event(dialog):
    """Ensure CustomTitleBar close button triggers closeEvent confirmation."""
    dialog.is_modified = True

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = "Cancel"
        mock_box.return_value = mock_instance

        dialog.title_bar.btn_close.click()

        mock_box.assert_called_once()
        assert "You have unsaved changes" in mock_box.call_args[1].get("text", "")
        assert dialog.is_modified is True


def test_inactive_tab_custom_field_does_not_block_save(dialog):
    """Validation must ignore custom fields in disabled/inactive tabs (e.g. Median when include_median=No)."""
    # KEY_INCLUDE_MEDIAN is 'No', so Median subtab is disabled
    dialog.refresh_typical_section()
    md_type = dialog.findChild(QComboBox, KEY_MD_TYPE)
    md_width = dialog.findChild(QLineEdit, KEY_MD_WIDTH)
    if md_type and md_width:
        md_type.setCurrentText("Custom")
        md_width.setText("")
        # Because the median tab is disabled, it should not block save
        is_valid, err_msg = dialog._validate_custom_inputs()
        assert is_valid is True
        assert err_msg is None


def test_adaptive_widget_custom_mode_validation(dialog):
    """AdaptiveWidget fields (e.g. girder depth) validate when KEY_DESIGN_MODE is Custom."""
    dialog.design_mode_trigger("Custom")
    depth_adaptive = None
    for aw in dialog.findChildren(AdaptiveWidget):
        if getattr(aw, "_field_id", "") == KEY_MP_GIRDER_DEPTH:
            depth_adaptive = aw
            break

    assert depth_adaptive is not None
    current_w = depth_adaptive.currentWidget()
    assert isinstance(current_w, QLineEdit)

    # Empty value in Custom design mode
    current_w.setText("")
    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is False
    assert "Depth" in err_msg

    # Valid value
    current_w.setText("1800")
    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is True


def test_escape_key_routes_to_close_event_confirmation(dialog):
    """Ensure pressing Escape key on modified dialog triggers confirmation and does not duplicate."""
    dialog.is_modified = True
    dialog.show()

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = "Cancel"
        mock_box.return_value = mock_instance

        key_ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        dialog.keyPressEvent(key_ev)

        assert mock_box.call_count == 1
        assert "You have unsaved changes" in mock_box.call_args[1].get("text", "")
        assert dialog.isVisible() is True


def test_escape_key_closes_unmodified_without_warning(dialog):
    """Ensure pressing Escape key on unmodified dialog closes without warning."""
    dialog.is_modified = False
    dialog.show()

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        key_ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        dialog.keyPressEvent(key_ev)

        assert mock_box.call_count == 0
        assert dialog.isVisible() is False


def test_empty_custom_field_on_non_selected_tab_blocks_save(dialog):
    """Targeted Test 1-4 & 6:
    1. Put a Custom field with an empty value in an enabled tab (Loading tab).
    2. Switch to a different tab (Typical Section tab).
    3. Attempt to save.
    4. Verify saving is blocked and the missing parameter is identified.
    6. Verify a Custom field in an enabled but non-selected tab does block saving.
    """
    # Put empty custom field under Loading (tab index 2)
    dialog.tabs.setCurrentIndex(2)
    fp_mode = dialog.findChild(QComboBox, KEY_LL_FOOTPATH_PRESSURE + ".mode")
    fp_val = dialog.findChild(QLineEdit, KEY_LL_FOOTPATH_PRESSURE + ".value")
    assert fp_mode is not None and fp_val is not None
    fp_val.setText("")
    fp_mode.setCurrentText("Custom")

    # Switch away to top-level tab 0 (Typical Section)
    dialog.tabs.setCurrentIndex(0)
    assert dialog.tabs.currentIndex() == 0

    with patch("osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs.CustomMessageBox") as mock_box:
        mock_instance = MagicMock()
        mock_box.return_value = mock_instance
        dialog._save_inputs()

        mock_box.assert_called_once()
        call_kwargs = mock_box.call_args[1]
        assert "Validation Error" in call_kwargs.get("title", "")
        assert "Footpath Pressure" in call_kwargs.get("text", "")
        assert dialog.is_modified is True


def test_custom_field_in_disabled_tab_does_not_block_save(dialog):
    """Targeted Test 5: A Custom field in a disabled tab does not block saving."""
    # Ensure Median tab is disabled (KEY_INCLUDE_MEDIAN = 'No')
    dialog.working_input_dict[KEY_INCLUDE_MEDIAN] = "No"
    dialog.refresh_typical_section()

    md_type = dialog.findChild(QComboBox, KEY_MD_TYPE)
    md_width = dialog.findChild(QLineEdit, KEY_MD_WIDTH)
    assert md_type is not None and md_width is not None
    md_type.setCurrentText("Custom")
    md_width.setText("")

    # Because median tab is disabled, save should not be blocked
    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is True
    assert err_msg is None


def test_field_in_hidden_conditional_section_does_not_block_save(dialog):
    """Targeted Test 7: A field in a genuinely hidden or disabled conditional section
    does not cause an incorrect validation error.
    """
    dialog.design_mode_trigger("Optimized")
    # In Optimized design mode, Section Properties card is hidden
    for aw in dialog.findChildren(AdaptiveWidget):
        if getattr(aw, "_field_id", "") == KEY_MP_GIRDER_DEPTH:
            w = aw.currentWidget()
            if isinstance(w, QLineEdit):
                w.setText("")
    is_valid, err_msg = dialog._validate_custom_inputs()
    assert is_valid is True
    assert err_msg is None


