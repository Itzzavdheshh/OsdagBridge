"""
tests/unit/test_transverse_plotting_task3.py
--------------------------------------------
Unit tests for Task III: Result Plotting for Transverse Members.

Verifies:
1. Transverse elements are correctly identified.
2. Longitudinal elements are strictly excluded from transverse results.
3. End Diaphragms and Intermediate Cross Bracings are included in one category.
4. All six force components (Fx, Vy, Vz, Tx, My, Mz) are extracted correctly.
5. All three displacement components (Dx, Dy, Dz) are extracted correctly.
6. Results change correctly with the selected load case.
7. Missing transverse results are handled safely.
8. Transverse Members appears in the plotting UI member dropdown.
9. Existing longitudinal plots still work without regression.
10. Tasks I and II remain unaffected (verified alongside full suite).
"""

import pytest
import numpy as np
import xarray as xr
from PySide6.QtWidgets import QApplication, QComboBox

from osdagbridge.core.bridge_types.plate_girder.results_data import (
    extract_transverse_member_results,
)
from osdagbridge.core.bridge_types.plate_girder.plot_generator import (
    build_figure_sfd,
    build_figure_bmd,
    build_figure_deflection,
    build_figure_grillage,
    FORCE_MAP,
    DISP_MAP,
)
from osdagbridge.core.bridge_types.plate_girder.ui_fields import (
    FrontendData,
)
from osdagbridge.core.utils.common import (
    KEY_ANALYSIS_MEMBER,
    KEY_TS_NO_OF_GIRDERS,
)
from osdagbridge.desktop.ui.docks.output_dock import OutputDock


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def realistic_bridge_model():
    """
    Realistic grillage geometry:
    3 longitudinal girders at Z = 1.0 (G1), Z = 3.0 (G2), Z = 5.0 (G3).
    Span = 20m with 3 stations:
      X = 0.0  (Start Support / End Diaphragm)
      X = 10.0 (Midspan / Intermediate Cross Bracing)
      X = 20.0 (End Support / End Diaphragm)
    """
    nodes = {
        # Station X = 0.0 (End Diaphragm 1)
        1: [0.0, 0.0, 1.0],
        2: [0.0, 0.0, 3.0],
        3: [0.0, 0.0, 5.0],
        # Station X = 10.0 (Intermediate Cross Bracing)
        4: [10.0, 0.0, 1.0],
        5: [10.0, 0.0, 3.0],
        6: [10.0, 0.0, 5.0],
        # Station X = 20.0 (End Diaphragm 2)
        7: [20.0, 0.0, 1.0],
        8: [20.0, 0.0, 3.0],
        9: [20.0, 0.0, 5.0],
    }

    members = {
        # Longitudinal girder elements (Z constant)
        101: [1, 4],  # G1 seg 1
        102: [4, 7],  # G1 seg 2
        103: [2, 5],  # G2 seg 1
        104: [5, 8],  # G2 seg 2
        105: [3, 6],  # G3 seg 1
        106: [6, 9],  # G3 seg 2
        # Transverse elements (Z varies)
        # End Diaphragms at X = 0.0
        201: [1, 2],
        202: [2, 3],
        # Intermediate Cross Bracings at X = 10.0
        203: [4, 5],
        204: [5, 6],
        # End Diaphragms at X = 20.0
        205: [7, 8],
        206: [8, 9],
    }

    groups = {
        "start_edge": [201, 202],
        "transverse_slab": [203, 204],
        "end_edge": [205, 206],
        "exterior_main_beam_1": [101, 102],
        "interior_main_beam": [103, 104],
        "exterior_main_beam_2": [105, 106],
    }

    return {"nodes": nodes, "members": members, "groups": groups}


@pytest.fixture
def realistic_xarray_dataset(realistic_bridge_model):
    """
    Realistic multi-loadcase OpenSees/ospgrillage xarray Dataset
    with all 6 force pairs and 3 displacement components.
    """
    elems = list(realistic_bridge_model["members"].keys())
    nodes = list(realistic_bridge_model["nodes"].keys())
    loadcases = ["1.0 DL", "1.0 DL + 1.0 LL"]

    force_comps = [
        "Vx_i", "Vx_j",
        "Vy_i", "Vy_j",
        "Vz_i", "Vz_j",
        "Mx_i", "Mx_j",
        "My_i", "My_j",
        "Mz_i", "Mz_j",
    ]
    disp_comps = ["x", "y", "z", "theta_x", "theta_y", "theta_z"]
    all_comps = force_comps + disp_comps

    f_data = np.zeros((len(loadcases), len(elems), len(all_comps)), dtype=float)
    for lc_idx, multiplier in enumerate([1.0, 2.5]):
        for e_idx, e_tag in enumerate(elems):
            base_val = float(e_tag) * multiplier
            f_data[lc_idx, e_idx, 0] = base_val * 10.0   # Vx_i (Fx)
            f_data[lc_idx, e_idx, 1] = -base_val * 10.0  # Vx_j
            f_data[lc_idx, e_idx, 2] = base_val * 25.0   # Vy_i (Vy)
            f_data[lc_idx, e_idx, 3] = -base_val * 25.0  # Vy_j
            f_data[lc_idx, e_idx, 4] = base_val * 15.0   # Vz_i (Vz)
            f_data[lc_idx, e_idx, 5] = -base_val * 15.0  # Vz_j
            f_data[lc_idx, e_idx, 6] = base_val * 5.0    # Mx_i (Tx)
            f_data[lc_idx, e_idx, 7] = -base_val * 5.0   # Mx_j
            f_data[lc_idx, e_idx, 8] = base_val * 8.0    # My_i (My)
            f_data[lc_idx, e_idx, 9] = -base_val * 8.0   # My_j
            f_data[lc_idx, e_idx, 10] = base_val * 50.0  # Mz_i (Mz)
            f_data[lc_idx, e_idx, 11] = -base_val * 50.0 # Mz_j

    d_data = np.zeros((len(loadcases), len(nodes), len(all_comps)), dtype=float)
    for lc_idx, multiplier in enumerate([1.0, 2.5]):
        for n_idx, n_tag in enumerate(nodes):
            val = float(n_tag) * 0.001 * multiplier
            # Indices 12, 13, 14 corresponding to x, y, z in all_comps
            d_data[lc_idx, n_idx, 12] = val * 0.5   # x (Dx)
            d_data[lc_idx, n_idx, 13] = -val * 2.0  # y (Dy sag)
            d_data[lc_idx, n_idx, 14] = val * 0.2   # z (Dz)

    ds = xr.Dataset(
        data_vars={
            "forces": (["Loadcase", "Element", "Component"], f_data),
            "displacements": (["Loadcase", "Node", "Component"], d_data),
        },
        coords={
            "Loadcase": loadcases,
            "Element": elems,
            "Node": nodes,
            "Component": all_comps,
        },
    )
    return ds


# =============================================================================
# UNIT TESTS
# =============================================================================

def test_transverse_elements_correctly_identified(realistic_bridge_model, realistic_xarray_dataset):
    """Requirement 1: Transverse elements are correctly identified."""
    results = extract_transverse_member_results(
        realistic_xarray_dataset,
        nodes=realistic_bridge_model["nodes"],
        members=realistic_bridge_model["members"],
    )
    expected_transverse = [201, 202, 203, 204, 205, 206]
    assert sorted(results["elements"]) == expected_transverse
    assert len(results["elements"]) == 6


def test_longitudinal_elements_strictly_excluded(realistic_bridge_model, realistic_xarray_dataset):
    """Requirement 2: Longitudinal elements are strictly excluded from transverse results."""
    results = extract_transverse_member_results(
        realistic_xarray_dataset,
        nodes=realistic_bridge_model["nodes"],
        members=realistic_bridge_model["members"],
    )
    longitudinal_elements = {101, 102, 103, 104, 105, 106}
    transverse_set = set(results["elements"])

    # Overlap must be completely empty
    intersection = longitudinal_elements.intersection(transverse_set)
    assert len(intersection) == 0, f"Longitudinal elements leaked into transverse: {intersection}"


def test_end_diaphragms_and_intermediate_cross_bracings_included(realistic_bridge_model, realistic_xarray_dataset):
    """Requirement 3: Both End Diaphragms and Intermediate Cross Bracings are included under one category."""
    results = extract_transverse_member_results(
        realistic_bridge_model,
        dataset=realistic_xarray_dataset,
    )
    # End diaphragms at start and end
    assert 201 in results["elements"]
    assert 202 in results["elements"]
    assert 205 in results["elements"]
    assert 206 in results["elements"]
    # Intermediate cross bracings
    assert 203 in results["elements"]
    assert 204 in results["elements"]

    # Check partition tracking
    assert sorted(results["end_diaphragm_elements"]) == [201, 202, 205, 206]
    assert sorted(results["cross_bracing_elements"]) == [203, 204]


def test_all_six_force_components_extracted(realistic_bridge_model, realistic_xarray_dataset):
    """Requirement 4: Fx, Vy, Vz, Tx, My, Mz are extracted correctly."""
    results = extract_transverse_member_results(
        realistic_xarray_dataset,
        nodes=realistic_bridge_model["nodes"],
        members=realistic_bridge_model["members"],
        loadcase="1.0 DL",
    )
    forces = results["forces"]
    for e_tag in [201, 202, 203, 204, 205, 206]:
        e_f = forces[e_tag]
        for comp in ["Fx", "Vy", "Vz", "Tx", "My", "Mz"]:
            assert comp in e_f, f"Missing force component {comp} for element {e_tag}"
            vi, vj = e_f[comp]
            assert isinstance(vi, (float, int))
            assert isinstance(vj, (float, int))

    # Test numerical accuracy for element 203 (base = 203 * 1.0)
    e203_f = forces[203]
    assert e203_f["Fx"][0] == pytest.approx(203.0 * 10.0)
    assert e203_f["Vy"][0] == pytest.approx(203.0 * 25.0)
    assert e203_f["Vz"][0] == pytest.approx(203.0 * 15.0)
    assert e203_f["Tx"][0] == pytest.approx(203.0 * 5.0)
    assert e203_f["My"][0] == pytest.approx(203.0 * 8.0)
    assert e203_f["Mz"][0] == pytest.approx(203.0 * 50.0)


def test_all_three_displacement_components_extracted(realistic_bridge_model, realistic_xarray_dataset):
    """Requirement 5: Dx, Dy, Dz are extracted correctly."""
    results = extract_transverse_member_results(
        realistic_xarray_dataset,
        nodes=realistic_bridge_model["nodes"],
        members=realistic_bridge_model["members"],
        loadcase="1.0 DL",
    )
    displacements = results["displacements"]
    # All nodes connected to transverse members
    all_transverse_nodes = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    for n in all_transverse_nodes:
        assert n in displacements
        n_d = displacements[n]
        for comp in ["Dx", "Dy", "Dz"]:
            assert comp in n_d, f"Missing displacement component {comp} for node {n}"

    # Test numerical accuracy for node 5 (val = 5 * 0.001 = 0.005)
    n5_d = displacements[5]
    assert n5_d["Dx"] == pytest.approx(0.005 * 0.5)
    assert n5_d["Dy"] == pytest.approx(-0.005 * 2.0)
    assert n5_d["Dz"] == pytest.approx(0.005 * 0.2)


def test_results_change_with_load_case(realistic_bridge_model, realistic_xarray_dataset):
    """Requirement 6: Results correspond accurately to the selected load case."""
    res_dl = extract_transverse_member_results(
        realistic_xarray_dataset,
        nodes=realistic_bridge_model["nodes"],
        members=realistic_bridge_model["members"],
        loadcase="1.0 DL",
    )
    res_comb = extract_transverse_member_results(
        realistic_xarray_dataset,
        nodes=realistic_bridge_model["nodes"],
        members=realistic_bridge_model["members"],
        loadcase="1.0 DL + 1.0 LL",
    )

    # In our fixture, combo values are 2.5x the DL values
    vy_dl = res_dl["forces"][201]["Vy"][0]
    vy_comb = res_comb["forces"][201]["Vy"][0]
    assert vy_comb == pytest.approx(vy_dl * 2.5)

    dy_dl = res_dl["displacements"][5]["Dy"]
    dy_comb = res_comb["displacements"][5]["Dy"]
    assert dy_comb == pytest.approx(dy_dl * 2.5)


def test_missing_or_empty_transverse_results_handled_safely():
    """Requirement 7: Empty or missing data structures do not raise exceptions."""
    # Completely empty dataset
    res_empty = extract_transverse_member_results(None)
    assert res_empty["elements"] == []
    assert res_empty["nodes"] == []
    assert res_empty["forces"] == {}
    assert res_empty["displacements"] == {}

    # Dataset with nodes and members but no forces
    nodes = {1: [0.0, 0.0, 1.0], 2: [0.0, 0.0, 3.0]}
    members = {10: [1, 2]}
    res_nodes_only = extract_transverse_member_results(nodes=nodes, members=members)
    assert res_nodes_only["elements"] == [10]
    assert res_nodes_only["nodes"] == [1, 2]
    assert res_nodes_only["forces"][10]["Fx"] == (0.0, 0.0)
    assert res_nodes_only["displacements"][1]["Dx"] == 0.0


def test_transverse_members_in_ui_dropdown(qapp):
    """Requirement 8: 'Transverse Members' appears in the member-selection UI."""
    # 1. Check PlateGirderUIFields output schema
    fields = FrontendData()
    out_vals = fields.output_values()
    member_field = next(f for f in out_vals if f[0] == KEY_ANALYSIS_MEMBER)
    assert "Transverse Members" in member_field[3]

    # 2. Check OutputDock refresh_member_dropdown()
    class DummyBackend:
        def __init__(self):
            self.input_dict = {KEY_TS_NO_OF_GIRDERS: 3}
        def output_values(self):
            return FrontendData().output_values()

    backend = DummyBackend()
    dock = OutputDock(backend=backend)
    dock.refresh_member_dropdown()

    combo = dock._w(KEY_ANALYSIS_MEMBER)
    assert combo is not None
    items = [combo.itemText(i) for i in range(combo.count())]
    assert "Transverse Members" in items
    assert "All" in items
    assert "G1" in items
    assert "G2" in items
    assert "G3" in items


def test_transverse_member_plotting_generation(realistic_bridge_model, realistic_xarray_dataset):
    """Requirement 9: plot_generator renders Transverse Members and existing girders."""
    nodes = realistic_bridge_model["nodes"]
    members = realistic_bridge_model["members"]
    ds = realistic_xarray_dataset.sel(Loadcase="1.0 DL")

    # 1. SFD plot with Transverse Members
    fig_sfd, summary_sfd = build_figure_sfd(
        ds, "Vy", nodes, members, selected_girder="Transverse Members"
    )
    assert fig_sfd is not None
    assert "Transverse Members" in summary_sfd

    # 2. BMD plot with Transverse Members
    fig_bmd, summary_bmd = build_figure_bmd(
        ds, "Mz", nodes, members, selected_girder="Transverse Members"
    )
    assert fig_bmd is not None
    assert "Transverse Members" in summary_bmd

    # 3. Deflection plot with Transverse Members
    fig_defl, summary_defl = build_figure_deflection(
        ds, "Dy", nodes, members, selected_girder="Transverse Members"
    )
    assert fig_defl is not None
    assert "Transverse Members" in summary_defl

    # 4. Grillage model with Transverse Members
    fig_grill = build_figure_grillage(
        nodes, members, selected_girder="Transverse Members"
    )
    assert fig_grill is not None

    # 5. Verify existing longitudinal girder plot still works cleanly
    fig_g1, summary_g1 = build_figure_sfd(
        ds, "Vy", nodes, members, selected_girder="G1"
    )
    assert fig_g1 is not None
    assert "G1" in summary_g1
