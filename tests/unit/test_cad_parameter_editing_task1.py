"""
Unit tests for TASK I: Interactive 2D CAD Parameter Editing
Tests hit-testing, inline editor lifecycle, validation, locked parameters,
and state synchronization across CAD views, InputDock, and AdditionalInputs.
"""

import sys
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtCore import Qt, QPointF, QPoint, QEvent
from PySide6.QtGui import QMouseEvent, QKeyEvent, QFocusEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from osdagbridge.core.bridge_types.plate_girder.defaults import (
    BASIC_INPUT_DICT,
    solve_extend_basic_input_dict,
)
from osdagbridge.core.utils.common import (
    KEY_SPAN,
    KEY_CARRIAGEWAY_WIDTH,
    KEY_FOOTPATH,
    KEY_INCLUDE_MEDIAN,
    KEY_DESIGN_MODE,
    KEY_TS_GIRDER_SPACING,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_DECK_OVERHANG,
    KEY_TS_OVERALL_WIDTH,
    KEY_MP_CB_SPACING,
)
from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget
from osdagbridge.desktop.ui.docks.cad_top_view import TopViewCADWidget
from osdagbridge.desktop.ui.docks.cad_dual_view import BridgeDualCADWidget
from osdagbridge.desktop.ui.dialogs.additional_input.drawings.cad_preview_widget import CadPreviewWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance for all GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def solved_input_dict():
    """Provide a realistic solved bridge input dictionary."""
    d = {
        KEY_SPAN: 30.0,
        KEY_CARRIAGEWAY_WIDTH: 7.5,
        KEY_FOOTPATH: "None",
        KEY_INCLUDE_MEDIAN: "No",
        KEY_DESIGN_MODE: "Standard",
    }
    solve_extend_basic_input_dict(d)
    return d


@pytest.fixture
def cross_section_widget(qapp, solved_input_dict):
    """Create a primed and rendered CrossSectionCADWidget."""
    w = CrossSectionCADWidget()
    w.resize(800, 600)
    w.show()
    w.show_dimensions = True
    w.show_carriageway_values = True
    w.update_params({
        'carriageway_width': float(solved_input_dict[KEY_CARRIAGEWAY_WIDTH]) * 1000,
        'girder_spacing': float(solved_input_dict[KEY_TS_GIRDER_SPACING]) * 1000,
        'deck_thickness': float(solved_input_dict[KEY_TS_DECK_THICKNESS]),
        'deck_overhang': float(solved_input_dict[KEY_TS_DECK_OVERHANG]) * 1000,
    })
    # Render offscreen to populate _dimension_labels
    pm = QPixmap(800, 600)
    w.render(pm)
    yield w
    w.close()


@pytest.fixture
def top_view_widget(qapp, solved_input_dict):
    """Create a primed and rendered TopViewCADWidget."""
    w = TopViewCADWidget()
    w.resize(800, 600)
    w.show()
    w.show_dimensions = True
    w.show_span_values = True
    w.show_carriageway_values = True
    w.update_params({
        'span_length': float(solved_input_dict[KEY_SPAN]) * 1000,
        'girder_spacing': float(solved_input_dict[KEY_TS_GIRDER_SPACING]) * 1000,
        'cross_bracing_spacing': float(solved_input_dict.get(KEY_MP_CB_SPACING, 3.5)) * 1000,
    })
    pm = QPixmap(800, 600)
    w.render(pm)
    yield w
    w.close()


def _make_dbl_click_event(pos: QPointF):
    """Create a QMouseEvent for double click."""
    return QMouseEvent(
        QEvent.MouseButtonDblClick,
        pos,
        QPointF(pos),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier
    )


def test_cross_section_registers_editable_and_locked_labels(cross_section_widget):
    """Verify CrossSectionCADWidget registers editable and locked dimension labels."""
    labels = cross_section_widget._dimension_labels
    assert len(labels) > 0, "No dimension labels registered during painting"

    registered_keys = {lbl['key']: lbl for lbl in labels}

    # Editable parameters must be registered with is_editable=True
    assert KEY_CARRIAGEWAY_WIDTH in registered_keys
    assert registered_keys[KEY_CARRIAGEWAY_WIDTH]['is_editable'] is True
    assert registered_keys[KEY_CARRIAGEWAY_WIDTH]['unit'] == 'm'

    assert KEY_TS_GIRDER_SPACING in registered_keys
    assert registered_keys[KEY_TS_GIRDER_SPACING]['is_editable'] is True
    assert registered_keys[KEY_TS_GIRDER_SPACING]['unit'] == 'm'

    assert KEY_TS_DECK_THICKNESS in registered_keys
    assert registered_keys[KEY_TS_DECK_THICKNESS]['is_editable'] is True
    assert registered_keys[KEY_TS_DECK_THICKNESS]['unit'] == 'mm'

    # Locked parameters must be registered with is_editable=False
    assert KEY_TS_DECK_OVERHANG in registered_keys
    assert registered_keys[KEY_TS_DECK_OVERHANG]['is_editable'] is False

    assert KEY_TS_OVERALL_WIDTH in registered_keys
    assert registered_keys[KEY_TS_OVERALL_WIDTH]['is_editable'] is False


def test_top_view_registers_editable_and_locked_labels(top_view_widget):
    """Verify TopViewCADWidget registers editable and locked dimension labels."""
    labels = top_view_widget._dimension_labels
    assert len(labels) > 0, "No dimension labels registered during painting"

    registered_keys = {lbl['key']: lbl for lbl in labels}

    # Editable parameters
    assert KEY_SPAN in registered_keys
    assert registered_keys[KEY_SPAN]['is_editable'] is True
    assert registered_keys[KEY_SPAN]['unit'] == 'm'

    assert KEY_TS_GIRDER_SPACING in registered_keys
    assert registered_keys[KEY_TS_GIRDER_SPACING]['is_editable'] is True
    assert registered_keys[KEY_TS_GIRDER_SPACING]['unit'] == 'm'

    # Locked parameter
    assert KEY_MP_CB_SPACING in registered_keys
    assert registered_keys[KEY_MP_CB_SPACING]['is_editable'] is False


def test_editable_labels_open_editor_with_current_value(cross_section_widget, top_view_widget):
    """Verify double-clicking each of the 4 editable labels opens QLineEdit with correct value."""
    # 1. Carriageway Width in Cross Section
    cw_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_CARRIAGEWAY_WIDTH)
    center = cw_label['rect'].center()
    dbl_click = _make_dbl_click_event(center)
    cross_section_widget.mouseDoubleClickEvent(dbl_click)

    assert cross_section_widget._editor is not None
    assert cross_section_widget._editor.isVisible()
    assert float(cross_section_widget._editor.text()) == pytest.approx(cw_label['value'], rel=1e-2)
    cross_section_widget._close_editor()

    # 2. Girder Spacing in Cross Section
    gs_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_TS_GIRDER_SPACING)
    center = gs_label['rect'].center()
    dbl_click = _make_dbl_click_event(center)
    cross_section_widget.mouseDoubleClickEvent(dbl_click)

    assert cross_section_widget._editor is not None
    assert float(cross_section_widget._editor.text()) == pytest.approx(gs_label['value'], rel=1e-2)
    cross_section_widget._close_editor()

    # 3. Deck Thickness in Cross Section
    dt_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_TS_DECK_THICKNESS)
    center = dt_label['rect'].center()
    dbl_click = _make_dbl_click_event(center)
    cross_section_widget.mouseDoubleClickEvent(dbl_click)

    assert cross_section_widget._editor is not None
    assert float(cross_section_widget._editor.text()) == pytest.approx(dt_label['value'], rel=1e-2)
    cross_section_widget._close_editor()

    # 4. Span Length in Top View
    span_label = next(l for l in top_view_widget._dimension_labels if l['key'] == KEY_SPAN)
    center = span_label['rect'].center()
    dbl_click = _make_dbl_click_event(center)
    top_view_widget.mouseDoubleClickEvent(dbl_click)

    assert top_view_widget._editor is not None
    assert float(top_view_widget._editor.text()) == pytest.approx(span_label['value'], rel=1e-2)
    top_view_widget._close_editor()


def test_locked_parameters_never_open_editor(cross_section_widget, top_view_widget):
    """Verify that double-clicking locked labels (Overhang, Overall Width, Bracing Spacing) does nothing."""
    # 1. Overhang (locked)
    oh_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_TS_DECK_OVERHANG)
    dbl_click = _make_dbl_click_event(oh_label['rect'].center())
    cross_section_widget.mouseDoubleClickEvent(dbl_click)
    assert cross_section_widget._editor is None

    # 2. Overall Bridge Width (locked)
    obw_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_TS_OVERALL_WIDTH)
    dbl_click = _make_dbl_click_event(obw_label['rect'].center())
    cross_section_widget.mouseDoubleClickEvent(dbl_click)
    assert cross_section_widget._editor is None

    # 3. Bracing Spacing (locked)
    bs_label = next(l for l in top_view_widget._dimension_labels if l['key'] == KEY_MP_CB_SPACING)
    dbl_click = _make_dbl_click_event(bs_label['rect'].center())
    top_view_widget.mouseDoubleClickEvent(dbl_click)
    assert top_view_widget._editor is None


def test_escape_cancels_without_changing_anything(cross_section_widget):
    """Verify pressing Escape dismisses the editor without emitting any signal."""
    cw_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_CARRIAGEWAY_WIDTH)
    dbl_click = _make_dbl_click_event(cw_label['rect'].center())
    cross_section_widget.mouseDoubleClickEvent(dbl_click)

    assert cross_section_widget._editor is not None
    cross_section_widget._editor.setText("99.9")

    emitted_signals = []
    cross_section_widget.parameter_edit_requested.connect(lambda k, v: emitted_signals.append((k, v)))

    # Press Escape
    key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    cross_section_widget.eventFilter(cross_section_widget._editor, key_event)

    assert cross_section_widget._editor is None
    assert len(emitted_signals) == 0, "Signal emitted on Escape cancellation"


def test_enter_commits_exactly_once(cross_section_widget):
    """Verify pressing Enter commits the value once, and subsequent focus out does not duplicate."""
    cw_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_CARRIAGEWAY_WIDTH)
    dbl_click = _make_dbl_click_event(cw_label['rect'].center())
    cross_section_widget.mouseDoubleClickEvent(dbl_click)

    cross_section_widget._editor.setText("8.5")

    emitted_signals = []
    cross_section_widget.parameter_edit_requested.connect(lambda k, v: emitted_signals.append((k, v)))

    # Press Enter
    key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
    cross_section_widget.eventFilter(cross_section_widget._editor, key_event)

    assert len(emitted_signals) == 1
    assert emitted_signals[0] == (KEY_CARRIAGEWAY_WIDTH, "8.5")
    assert cross_section_widget._editor is None

    # Simulate subsequent FocusOut event
    focus_event = QFocusEvent(QEvent.FocusOut)
    cross_section_widget.eventFilter(cross_section_widget._editor, focus_event)

    assert len(emitted_signals) == 1, "Duplicate signal emitted after Enter + FocusOut"


def test_focus_loss_commits_exactly_once(cross_section_widget):
    """Verify clicking outside or losing focus commits the edit exactly once."""
    gs_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_TS_GIRDER_SPACING)
    dbl_click = _make_dbl_click_event(gs_label['rect'].center())
    cross_section_widget.mouseDoubleClickEvent(dbl_click)

    cross_section_widget._editor.setText("2.5")

    emitted_signals = []
    cross_section_widget.parameter_edit_requested.connect(lambda k, v: emitted_signals.append((k, v)))

    # Simulate FocusOut event
    focus_event = QFocusEvent(QEvent.FocusOut)
    cross_section_widget.eventFilter(cross_section_widget._editor, focus_event)

    assert len(emitted_signals) == 1
    assert emitted_signals[0] == (KEY_TS_GIRDER_SPACING, "2.5")
    assert cross_section_widget._editor is None


def test_escape_overrides_focus_loss(cross_section_widget):
    """Verify that pressing Escape cancels even if FocusOut occurs afterwards."""
    cw_label = next(l for l in cross_section_widget._dimension_labels if l['key'] == KEY_CARRIAGEWAY_WIDTH)
    dbl_click = _make_dbl_click_event(cw_label['rect'].center())
    cross_section_widget.mouseDoubleClickEvent(dbl_click)

    cross_section_widget._editor.setText("12.0")

    emitted_signals = []
    cross_section_widget.parameter_edit_requested.connect(lambda k, v: emitted_signals.append((k, v)))

    # Press Escape
    key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    cross_section_widget.eventFilter(cross_section_widget._editor, key_event)

    # FocusOut follows
    focus_event = QFocusEvent(QEvent.FocusOut)
    cross_section_widget.eventFilter(cross_section_widget._editor, focus_event)

    assert len(emitted_signals) == 0, "Signal emitted despite Escape cancellation"


def test_invalid_empty_and_non_numeric_input_rejected(qapp, solved_input_dict):
    """Verify empty, whitespace, non-numeric, and out-of-range inputs are rejected."""
    from osdagbridge.desktop.ui.template_page import CustomWindow
    from osdagbridge.desktop.ui.dialogs.custom_messagebox import CustomMessageBox

    win = CustomWindow.__new__(CustomWindow)
    win.input_dict = dict(solved_input_dict)
    win.input_dock = MagicMock()
    win.cad_comp_widget = MagicMock()
    win._additional_inputs_dialog = None
    win.update_cad_from_inputs = MagicMock()

    with patch.object(CustomMessageBox, "exec", return_value=None) as mock_dialog:
        # 1. Empty string
        res = win.on_cad_parameter_edited(KEY_SPAN, "")
        assert res is False
        assert mock_dialog.called

        # 2. Whitespace string
        mock_dialog.reset_mock()
        res = win.on_cad_parameter_edited(KEY_CARRIAGEWAY_WIDTH, "   ")
        assert res is False
        assert mock_dialog.called

        # 3. Non-numeric string
        mock_dialog.reset_mock()
        res = win.on_cad_parameter_edited(KEY_TS_DECK_THICKNESS, "invalid_num")
        assert res is False
        assert mock_dialog.called

        # 4. Out-of-range: Span < 10m
        mock_dialog.reset_mock()
        res = win.on_cad_parameter_edited(KEY_SPAN, "5.0")
        assert res is False
        assert mock_dialog.called

        # 5. Out-of-range: Deck thickness > 500mm
        mock_dialog.reset_mock()
        res = win.on_cad_parameter_edited(KEY_TS_DECK_THICKNESS, "800.0")
        assert res is False
        assert mock_dialog.called

    # Ensure baseline input_dict was never corrupted
    assert win.input_dict[KEY_SPAN] == 30.0
    assert win.input_dict[KEY_CARRIAGEWAY_WIDTH] == 7.5


def test_valid_input_updates_input_dict_and_synchronizes(qapp, solved_input_dict):
    """Verify valid inputs update input_dict, re-solve geometry, and trigger redraw."""
    from osdagbridge.desktop.ui.template_page import CustomWindow

    win = CustomWindow.__new__(CustomWindow)
    win.input_dict = dict(solved_input_dict)
    win.input_dock = MagicMock()
    win.input_dock.input_widget = QWidget()
    span_edit = QLineEdit(win.input_dock.input_widget)
    span_edit.setObjectName(KEY_SPAN)
    win.cad_comp_widget = MagicMock()
    win._additional_inputs_dialog = None
    win.update_cad_from_inputs = MagicMock()

    # Valid edit: Span 35.0 m
    res = win.on_cad_parameter_edited(KEY_SPAN, "35.0")
    assert res is True
    assert win.input_dict[KEY_SPAN] == 35.0
    assert span_edit.text() == "35.0"
    win.cad_comp_widget.update_from_osdag_inputs.assert_called_with(win.input_dict)

    # Valid edit: Girder Spacing 2.4 m -> recalculates overhang
    initial_overhang = win.input_dict[KEY_TS_DECK_OVERHANG]
    res = win.on_cad_parameter_edited(KEY_TS_GIRDER_SPACING, "2.4")
    assert res is True
    assert win.input_dict[KEY_TS_GIRDER_SPACING] == 2.4
    # With 4 girders and 8.4m overall width, spacing 2.4m derives overhang = (8.4 - 3*2.4)/2 = 0.6m
    assert win.input_dict[KEY_TS_DECK_OVERHANG] == pytest.approx(0.6, abs=1e-3)
    assert win.input_dict[KEY_TS_DECK_OVERHANG] != initial_overhang


def test_girder_spacing_synchronization_across_both_views(qapp, solved_input_dict):
    """Verify updating Girder Spacing from either view propagates to both CAD views."""
    dual_cad = BridgeDualCADWidget()
    dual_cad.update_from_osdag_inputs(solved_input_dict)

    initial_gs = dual_cad.cross_section_widget.params['girder_spacing']
    assert initial_gs == dual_cad.top_view_widget.params['girder_spacing']

    # Update input dict with new girder spacing
    updated_dict = dict(solved_input_dict)
    updated_dict[KEY_TS_GIRDER_SPACING] = 2.4
    solve_extend_basic_input_dict(updated_dict, changed_field='spacing')

    dual_cad.update_from_osdag_inputs(updated_dict)

    assert dual_cad.cross_section_widget.params['girder_spacing'] == pytest.approx(2400.0)
    assert dual_cad.top_view_widget.params['girder_spacing'] == pytest.approx(2400.0)


def test_preview_widget_editing_disabled(qapp):
    """Verify that the CrossSectionCADWidget in AdditionalInputs preview is non-editable."""
    preview = CadPreviewWidget()
    assert preview._cross.enable_parameter_editing is False
    assert preview._cross.show_dimensions is False

    # Simulate double click
    dbl_click = _make_dbl_click_event(QPointF(50, 50))
    preview._cross.mouseDoubleClickEvent(dbl_click)
    assert preview._cross._editor is None
