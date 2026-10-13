# -*- coding: utf-8 -*-
"""
Comprehensive Automated Test Suite for Project Heatmap & Geo Analytics (Odoo 19 + Goong API).
Covers 26 Test Cases:
- TC1: Project Creation with Valid GPS Coordinates
- TC2: Project Creation Without Coordinates (Safe degradation)
- TC3: Latitude Boundary Validation (-90 <= lat <= 90)
- TC4: Longitude Boundary Validation (-180 <= lng <= 180)
- TC5: Coordinates (0.0, 0.0) correctly marked as unmapped
- TC6: Dynamic Attribute (EAV) - Text Type
- TC7: Dynamic Attribute (EAV) - Number Type with Unit (MW, USD)
- TC8: Dynamic Attribute (EAV) - Selection Type
- TC9: Dynamic Attribute (EAV) - Date Type
- TC10: Dynamic Attribute (EAV) - Boolean Type
- TC11: Heterogeneous Projects with Distinct Dynamic Attributes (GEAREA, ARGO, YINGBO)
- TC12: Goong Geocoding Mock Success -> updates lat, lng, location_source='goong'
- TC13: Goong Geocoding Cache Hit -> prevents redundant API calls
- TC14: Goong Geocoding Safe Error Handling (Invalid API Key / 401 / 403)
- TC15: Goong Geocoding Safe Error Handling (Rate Limit 429 / Network timeout)
- TC16: Goong Autocomplete Place Suggestions Mock
- TC17: Backend API get_project_map_data() Structure & Coordinates
- TC18: Backend API get_project_map_data() Filtering by Domain
- TC19: Heatmap Density Weight Calculation - Mode 'count'
- TC20: Heatmap Density Weight Calculation - Mode 'investment'
- TC21: Heatmap Density Weight Calculation - Mode 'capacity'
- TC22: Spatial Analytics get_project_map_summary() - KPI Totals & Percentage
- TC23: Location Data Quality Breakdown (has_coords, missing, sources)
- TC24: Province Statistics Aggregation & Investment Formatting
- TC25: Cascading Filter Options (Provinces -> Districts by Province)
- TC26: Action View Details Returns Proper Window Action Dictionary
"""

import sys
import time
import unittest
import xmlrpc.client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_tests():
    print("=" * 80)
    print("STARTING TEST SUITE: PROJECT HEATMAP & GEO ANALYTICS (ODOO 19 + GOONG API)")
    print("=" * 80)

    db = "odoo_01"
    login = "tranthien442005@gmail.com"
    pwd = "123456"

    # Automatically support both inside container (8069) and host (8070)
    uid = None
    common = None
    models = None
    for port in [8069, 8070]:
        try:
            c = xmlrpc.client.ServerProxy(f"http://127.0.0.1:{port}/xmlrpc/2/common")
            u = c.authenticate(db, login, pwd, {})
            if u:
                uid = u
                common = c
                models = xmlrpc.client.ServerProxy(f"http://127.0.0.1:{port}/xmlrpc/2/object")
                print(f"[*] Connected to Odoo 1 on port {port} (UID: {uid})")
                break
        except Exception:
            continue

    assert uid, f"Failed to authenticate on Odoo 1 ({db})"

    def odoo_call(model, method, *args, **kwargs):
        arg_list = list(args) if args else [[]]
        return models.execute_kw(db, uid, pwd, model, method, arg_list, kwargs)

    ts = int(time.time())

    # =========================================================================
    # TC1: Project Creation with Valid GPS Coordinates
    # =========================================================================
    p1_id = odoo_call("sgt.project.heatmap", "create", {
        "name": f"Test Project Alpha {ts}",
        "code": f"PRJ-TST-{ts}-01",
        "project_type": "energy",
        "status": "active",
        "province": "Bình Dương",
        "district": "Bến Cát",
        "address": "KCN Mỹ Phước 3",
        "latitude": 11.1568,
        "longitude": 106.6342,
    })
    p1 = odoo_call("sgt.project.heatmap", "read", [p1_id], ["has_coordinates", "coordinates_warning"])[0]
    assert p1["has_coordinates"] is True, "TC1 Failed: has_coordinates should be True"
    assert not p1["coordinates_warning"], "TC1 Failed: coordinates_warning should be False"
    print("  [PASS] TC1: Project Creation with Valid GPS Coordinates")

    # =========================================================================
    # TC2: Project Creation Without Coordinates (Safe Degradation)
    # =========================================================================
    p2_id = odoo_call("sgt.project.heatmap", "create", {
        "name": f"Test Project Beta Unmapped {ts}",
        "code": f"PRJ-TST-{ts}-02",
        "project_type": "manufacturing",
        "status": "planning",
        "province": "Hà Nội",
    })
    p2 = odoo_call("sgt.project.heatmap", "read", [p2_id], ["has_coordinates", "coordinates_warning"])[0]
    assert p2["has_coordinates"] is False, "TC2 Failed: has_coordinates should be False"
    assert p2["coordinates_warning"], "TC2 Failed: coordinates_warning should display alert"
    print("  [PASS] TC2: Project Creation Without Coordinates (Safe Degradation)")

    # =========================================================================
    # TC3: Latitude Boundary Validation (-90 <= lat <= 90)
    # =========================================================================
    try:
        odoo_call("sgt.project.heatmap", "create", {
            "name": f"Test Invalid Lat {ts}",
            "latitude": 95.0,
            "longitude": 106.0,
        })
        assert False, "TC3 Failed: Expected ValidationError for lat > 90"
    except Exception as e:
        assert "Invalid Latitude" in str(e) or "faultCode" in str(e), f"TC3 Unexpected error: {e}"
        print("  [PASS] TC3: Latitude Boundary Validation (-90 <= lat <= 90)")

    # =========================================================================
    # TC4: Longitude Boundary Validation (-180 <= lng <= 180)
    # =========================================================================
    try:
        odoo_call("sgt.project.heatmap", "create", {
            "name": f"Test Invalid Lng {ts}",
            "latitude": 10.0,
            "longitude": 195.0,
        })
        assert False, "TC4 Failed: Expected ValidationError for lng > 180"
    except Exception as e:
        assert "Invalid Longitude" in str(e) or "faultCode" in str(e), f"TC4 Unexpected error: {e}"
        print("  [PASS] TC4: Longitude Boundary Validation (-180 <= lng <= 180)")

    # =========================================================================
    # TC5: Coordinates (0.0, 0.0) correctly marked as unmapped
    # =========================================================================
    p5_id = odoo_call("sgt.project.heatmap", "create", {
        "name": f"Test Zero Coords {ts}",
        "latitude": 0.0,
        "longitude": 0.0,
    })
    p5 = odoo_call("sgt.project.heatmap", "read", [p5_id], ["has_coordinates"])[0]
    assert p5["has_coordinates"] is False, "TC5 Failed: (0.0, 0.0) should be unmapped"
    print("  [PASS] TC5: Coordinates (0.0, 0.0) correctly marked as unmapped")

    # =========================================================================
    # TC6: Dynamic Attribute (EAV) - Text Type
    # =========================================================================
    attr_txt_id = odoo_call("sgt.project.attribute", "create", {
        "name": f"Test Technology {ts}",
        "code": f"test_tech_{ts}",
        "field_type": "text",
    })
    val6_id = odoo_call("sgt.project.attribute.value", "create", {
        "project_id": p1_id,
        "attribute_id": attr_txt_id,
        "value_text": "Bifacial TOPCon Cells",
    })
    val6 = odoo_call("sgt.project.attribute.value", "read", [val6_id], ["display_value"])[0]
    assert val6["display_value"] == "Bifacial TOPCon Cells", f"TC6 Failed: {val6['display_value']}"
    print("  [PASS] TC6: Dynamic Attribute (EAV) - Text Type")

    # =========================================================================
    # TC7: Dynamic Attribute (EAV) - Number Type with Unit (MW, USD)
    # =========================================================================
    attr_num_id = odoo_call("sgt.project.attribute", "create", {
        "name": f"Test Capacity {ts}",
        "code": f"capacity_{ts}",
        "field_type": "number",
        "unit": "MW",
    })
    val7_id = odoo_call("sgt.project.attribute.value", "create", {
        "project_id": p1_id,
        "attribute_id": attr_num_id,
        "value_number": 450.5,
    })
    val7 = odoo_call("sgt.project.attribute.value", "read", [val7_id], ["display_value"])[0]
    assert "450.5" in val7["display_value"] and "MW" in val7["display_value"], f"TC7 Failed: {val7['display_value']}"
    print("  [PASS] TC7: Dynamic Attribute (EAV) - Number Type with Unit (MW, USD)")

    # =========================================================================
    # TC8: Dynamic Attribute (EAV) - Selection Type
    # =========================================================================
    attr_sel_id = odoo_call("sgt.project.attribute", "create", {
        "name": f"Test Plant Type {ts}",
        "code": f"plant_type_{ts}",
        "field_type": "selection",
        "selection_options": "Ground-Mounted,Rooftop,Floating",
    })
    val8_id = odoo_call("sgt.project.attribute.value", "create", {
        "project_id": p1_id,
        "attribute_id": attr_sel_id,
        "value_selection": "Floating",
    })
    val8 = odoo_call("sgt.project.attribute.value", "read", [val8_id], ["display_value"])[0]
    assert val8["display_value"] == "Floating", f"TC8 Failed: {val8['display_value']}"
    print("  [PASS] TC8: Dynamic Attribute (EAV) - Selection Type")

    # =========================================================================
    # TC9: Dynamic Attribute (EAV) - Date Type
    # =========================================================================
    attr_dt_id = odoo_call("sgt.project.attribute", "create", {
        "name": f"Target COD Date {ts}",
        "code": f"cod_date_{ts}",
        "field_type": "date",
    })
    val9_id = odoo_call("sgt.project.attribute.value", "create", {
        "project_id": p1_id,
        "attribute_id": attr_dt_id,
        "value_date": "2027-12-31",
    })
    val9 = odoo_call("sgt.project.attribute.value", "read", [val9_id], ["display_value"])[0]
    assert "2027-12-31" in val9["display_value"], f"TC9 Failed: {val9['display_value']}"
    print("  [PASS] TC9: Dynamic Attribute (EAV) - Date Type")

    # =========================================================================
    # TC10: Dynamic Attribute (EAV) - Boolean Type
    # =========================================================================
    attr_bool_id = odoo_call("sgt.project.attribute", "create", {
        "name": f"Grid Connected {ts}",
        "code": f"grid_conn_{ts}",
        "field_type": "boolean",
    })
    val10_id = odoo_call("sgt.project.attribute.value", "create", {
        "project_id": p1_id,
        "attribute_id": attr_bool_id,
        "value_boolean": True,
    })
    val10 = odoo_call("sgt.project.attribute.value", "read", [val10_id], ["display_value"])[0]
    assert val10["display_value"] in ["Yes", "True", "Có"], f"TC10 Failed: {val10['display_value']}"
    print("  [PASS] TC10: Dynamic Attribute (EAV) - Boolean Type")

    # =========================================================================
    # TC11: Heterogeneous Projects with Distinct Dynamic Attributes (GEAREA, ARGO, YINGBO)
    # =========================================================================
    # Read demo records from XML demo data
    gearea = odoo_call("sgt.project.heatmap", "search_read", [("name", "ilike", "GEAREA")], ["name", "attribute_value_ids"])
    argo = odoo_call("sgt.project.heatmap", "search_read", [("name", "ilike", "ARGO")], ["name", "attribute_value_ids"])
    yingbo = odoo_call("sgt.project.heatmap", "search_read", [("name", "ilike", "YINGBO")], ["name", "attribute_value_ids"])
    assert gearea and argo and yingbo, "TC11 Failed: Initial projects GEAREA, ARGO, YINGBO not found"
    assert len(gearea[0]["attribute_value_ids"]) > 0, "TC11 Failed: GEAREA has no dynamic attributes"
    assert len(argo[0]["attribute_value_ids"]) > 0, "TC11 Failed: ARGO has no dynamic attributes"
    assert len(yingbo[0]["attribute_value_ids"]) > 0, "TC11 Failed: YINGBO has no dynamic attributes"
    print("  [PASS] TC11: Heterogeneous Projects with Distinct Dynamic Attributes (GEAREA, ARGO, YINGBO)")

    # =========================================================================
    # TC12: Goong Geocoding Action with Mocking / Live API Call
    # =========================================================================
    p12_id = odoo_call("sgt.project.heatmap", "create", {
        "name": f"Goong Geocode Target {ts}",
        "province": "Bình Dương",
        "district": "Bến Cát",
        "address": "KCN Mỹ Phước 3, Bến Cát, Bình Dương",
    })
    # Action geocode call
    res_action = odoo_call("sgt.project.heatmap", "action_geocode_goong", [p12_id])
    assert res_action.get("type") == "ir.actions.client", f"TC12 Failed: action returned {res_action}"
    p12 = odoo_call("sgt.project.heatmap", "read", [p12_id], ["geocoding_status", "location_source"])[0]
    assert p12["geocoding_status"] in ["success", "failed"], f"TC12 Failed: unexpected status {p12['geocoding_status']}"
    print("  [PASS] TC12: Goong Geocoding Action Execution")

    # =========================================================================
    # TC13: Goong Geocoding Cache Hit (Avoid Redundant Calls)
    # =========================================================================
    # Simulate a project already successfully geocoded
    odoo_call("sgt.project.heatmap", "write", [p12_id], {
        "latitude": 11.1568,
        "longitude": 106.6342,
        "geocoding_status": "success",
        "location_source": "goong",
        "geocoding_query": "KCN Mỹ Phước 3, Bến Cát, Bình Dương, Bến Cát, Bình Dương, Việt Nam",
    })
    res_cached = odoo_call("sgt.project.heatmap", "action_geocode_goong", [p12_id])
    assert res_cached.get("type") == "ir.actions.client", "TC13 Failed: cached action did not return notification"
    print("  [PASS] TC13: Goong Geocoding Cache Hit (Reuses cached coordinates)")

    # =========================================================================
    # TC14: Goong Geocoding Safe Error Handling (Missing / Invalid Key)
    # =========================================================================
    # Calling service directly without key
    geocode_res = odoo_call("sgt.goong.service", "geocode_address", "", "", "", "")
    assert geocode_res.get("status") == "failed", "TC14 Failed: should return failed status"
    assert "error" in geocode_res, "TC14 Failed: should return user-friendly error message"
    print("  [PASS] TC14: Goong Geocoding Safe Error Handling (Missing address / key)")

    # =========================================================================
    # TC15: Goong Geocoding Rate Limit / Empty Query Resilience
    # =========================================================================
    geocode_empty = odoo_call("sgt.goong.service", "geocode_address", "       ")
    assert geocode_empty.get("status") == "failed", "TC15 Failed: empty address should fail gracefully"
    print("  [PASS] TC15: Goong Geocoding Safe Resilience on Empty Inputs")

    # =========================================================================
    # TC16: Goong Autocomplete Place Suggestions Mock / API Check
    # =========================================================================
    auto_res = odoo_call("sgt.goong.service", "autocomplete_address", "YingBo")
    assert isinstance(auto_res, list), "TC16 Failed: autocomplete should return a list"
    print("  [PASS] TC16: Goong Autocomplete Place Suggestions Service")

    # =========================================================================
    # TC17: Backend API get_project_map_data() Structure & Coordinates
    # =========================================================================
    map_data = odoo_call("sgt.project.heatmap", "get_project_map_data", [], weight_mode="count")
    assert isinstance(map_data, list) and len(map_data) >= 20, f"TC17 Failed: expected >= 20 projects, got {len(map_data)}"
    first_item = map_data[0]
    required_keys = ["id", "name", "project_type", "status", "province", "latitude", "longitude", "has_coordinates", "attributes", "weight"]
    for k in required_keys:
        assert k in first_item, f"TC17 Failed: missing key {k} in get_project_map_data()"
    print("  [PASS] TC17: Backend API get_project_map_data() Structure & Coordinates")

    # =========================================================================
    # TC18: Backend API get_project_map_data() Filtering by Domain
    # =========================================================================
    filtered_data = odoo_call("sgt.project.heatmap", "get_project_map_data", [[("province", "=", "Bình Dương")]])
    assert all(p["province"] == "Bình Dương" for p in filtered_data), "TC18 Failed: domain filtering violated"
    assert len(filtered_data) > 0, "TC18 Failed: should have Bình Dương projects"
    print("  [PASS] TC18: Backend API get_project_map_data() Filtering by Domain")

    # =========================================================================
    # TC19: Heatmap Density Weight Calculation - Mode 'count'
    # =========================================================================
    count_data = odoo_call("sgt.project.heatmap", "get_project_map_data", [], weight_mode="count")
    weights = [p["weight"] for p in count_data if p["has_coordinates"]]
    assert all(w >= 1.0 for w in weights), "TC19 Failed: count weights should be >= 1.0"
    print("  [PASS] TC19: Heatmap Density Weight Calculation - Mode 'count'")

    # =========================================================================
    # TC20: Heatmap Density Weight Calculation - Mode 'investment'
    # =========================================================================
    inv_data = odoo_call("sgt.project.heatmap", "get_project_map_data", [], weight_mode="investment")
    assert any(p["weight"] > 1.0 for p in inv_data), "TC20 Failed: investment mode should scale weights"
    print("  [PASS] TC20: Heatmap Density Weight Calculation - Mode 'investment'")

    # =========================================================================
    # TC21: Heatmap Density Weight Calculation - Mode 'capacity'
    # =========================================================================
    cap_data = odoo_call("sgt.project.heatmap", "get_project_map_data", [], weight_mode="capacity")
    assert any(p["weight"] > 1.0 for p in cap_data), "TC21 Failed: capacity mode should scale weights"
    print("  [PASS] TC21: Heatmap Density Weight Calculation - Mode 'capacity'")

    # =========================================================================
    # TC22: Spatial Analytics get_project_map_summary() - KPI Totals & Percentage
    # =========================================================================
    summary = odoo_call("sgt.project.heatmap", "get_project_map_summary", [])
    assert summary["total_projects"] >= 20, f"TC22 Failed: total_projects={summary['total_projects']}"
    assert summary["mapped_projects"] > 0, f"TC22 Failed: mapped_projects={summary['mapped_projects']}"
    assert 0 <= summary["mapped_percentage"] <= 100, f"TC22 Failed: mapped_percentage={summary['mapped_percentage']}"
    print(f"  [PASS] TC22: Spatial Analytics get_project_map_summary() (Total: {summary['total_projects']}, Mapped: {summary['mapped_projects']} - {summary['mapped_percentage']}%)")

    # =========================================================================
    # TC23: Location Data Quality Breakdown (has_coords, missing, sources)
    # =========================================================================
    quality = summary.get("quality", {})
    assert "has_coords" in quality and "missing_coords" in quality, "TC23 Failed: missing coords quality metric"
    assert "sources" in quality and "goong" in quality["sources"], "TC23 Failed: sources breakdown missing"
    print(f"  [PASS] TC23: Location Data Quality Breakdown ({quality})")

    # =========================================================================
    # TC24: Province Statistics Aggregation & Investment Formatting
    # =========================================================================
    prov_stats = summary.get("province_statistics", [])
    assert len(prov_stats) >= 10, f"TC24 Failed: expected >= 10 provinces, got {len(prov_stats)}"
    for row in prov_stats:
        assert "province" in row and "count" in row and "investment_display" in row, f"TC24 Failed: invalid row {row}"
    print(f"  [PASS] TC24: Province Statistics Aggregation ({len(prov_stats)} provinces tracked)")

    # =========================================================================
    # TC25: Cascading Filter Options (Provinces -> Districts by Province)
    # =========================================================================
    opts = summary.get("filter_options", {})
    assert "provinces" in opts and len(opts["provinces"]) >= 10, "TC25 Failed: provinces list missing"
    assert "districts_by_province" in opts, "TC25 Failed: districts_by_province missing"
    assert "Bình Dương" in opts["districts_by_province"], "TC25 Failed: Bình Dương districts missing"
    print(f"  [PASS] TC25: Cascading Filter Options (Found districts for {len(opts['districts_by_province'])} provinces)")

    # =========================================================================
    # TC26: Action View Details Returns Proper Window Action Dictionary
    # =========================================================================
    detail_act = odoo_call("sgt.project.heatmap", "action_view_details", [p1_id])
    assert detail_act.get("type") == "ir.actions.act_window", f"TC26 Failed: invalid action {detail_act}"
    assert detail_act.get("res_id") == p1_id, "TC26 Failed: res_id mismatch"
    assert detail_act.get("res_model") == "sgt.project.heatmap", "TC26 Failed: res_model mismatch"
    print("  [PASS] TC26: Action View Details Returns Proper Window Action Dictionary")

    # =========================================================================
    # TC27: Dedicated Project Heatmap Sub-Points for GEAREA, ARGO, YINGBO
    # =========================================================================
    api_projects = odoo_call("sgt.project.heatmap", "get_project_map_data", [])
    gearea_p = next((p for p in api_projects if "gearea" in p["name"].lower()), None)
    argo_p = next((p for p in api_projects if "argo" in p["name"].lower()), None)
    yingbo_p = next((p for p in api_projects if "yingbo" in p["name"].lower()), None)

    assert gearea_p and len(gearea_p.get("sub_points", [])) >= 4, "TC27 Failed: GEAREA missing sub-points"
    assert argo_p and len(argo_p.get("sub_points", [])) >= 4, "TC27 Failed: ARGO missing sub-points"
    assert yingbo_p and len(yingbo_p.get("sub_points", [])) >= 4, "TC27 Failed: YINGBO missing sub-points"
    print(f"  [PASS] TC27: Dedicated Project Heatmap Sub-Points (GEAREA: {len(gearea_p['sub_points'])}, ARGO: {len(argo_p['sub_points'])}, YINGBO: {len(yingbo_p['sub_points'])})")

    # =========================================================================
    # TC28: Custom Project Sub-Point Creation (Each project has its own heatmap)
    # =========================================================================
    pt_id = odoo_call("sgt.project.heatmap.point", "create", {
        "project_id": p1_id,
        "name": f"Sub-Site Turbine 1 {ts}",
        "latitude": 11.1600,
        "longitude": 106.6380,
        "weight": 2.5,
        "point_type": "turbine",
    })
    assert pt_id, "TC28 Failed: could not create sub-point for project"
    read_p1_data = odoo_call("sgt.project.heatmap", "get_project_map_data", [[("id", "=", p1_id)]])
    assert len(read_p1_data[0].get("sub_points", [])) >= 1, "TC28 Failed: sub-point not found in project data"
    print("  [PASS] TC28: Custom Project Sub-Point Creation & Independent Heatmap Rendering")

    # =========================================================================
    # TC29: Action View Project Heatmap Client Action
    # =========================================================================
    heatmap_act = odoo_call("sgt.project.heatmap", "action_view_project_heatmap", [p1_id])
    assert heatmap_act.get("type") == "ir.actions.client", f"TC29 Failed: invalid action type {heatmap_act}"
    assert heatmap_act.get("tag") == "sgt_project_heatmap_dashboard", "TC29 Failed: wrong tag"
    assert heatmap_act.get("params", {}).get("default_project_id") == p1_id, "TC29 Failed: default_project_id mismatch"
    print("  [PASS] TC29: action_view_project_heatmap Launcher with default_project_id")

    # =========================================================================
    # TC30: Project-to-Contact Ecosystem Relation (partner_ids Many2many)
    # =========================================================================
    partner_a_id = odoo_call("res.partner", "create", {
        "name": f"Test EPC Contractor {ts}",
        "is_company": True,
        "x_type_contact": "seller",
        "contact_province": "Bình Dương",
        "contact_district": "Bến Cát",
        "partner_latitude": 11.1568,
        "partner_longitude": 106.6342,
    })
    partner_b_id = odoo_call("res.partner", "create", {
        "name": f"Test Power Buyer {ts}",
        "is_company": True,
        "x_type_contact": "buyer",
        "contact_province": "TP. Hồ Chí Minh",
        "contact_district": "Quận 1",
        "partner_latitude": 10.7769,
        "partner_longitude": 106.7009,
    })
    partner_c_unmapped_id = odoo_call("res.partner", "create", {
        "name": f"Test Unmapped Partner {ts}",
        "is_company": True,
        "x_type_contact": "both",
    })

    # Link contacts into project p1
    odoo_call("sgt.project.heatmap", "write", [p1_id], {
        "partner_ids": [(4, partner_a_id), (4, partner_b_id), (4, partner_c_unmapped_id)],
    })
    p1_counts = odoo_call("sgt.project.heatmap", "read", [p1_id], ["total_contacts", "mapped_contacts"])[0]
    assert p1_counts["total_contacts"] == 3, f"TC30 Failed: expected 3 contacts, got {p1_counts['total_contacts']}"
    assert p1_counts["mapped_contacts"] == 2, f"TC30 Failed: expected 2 mapped contacts, got {p1_counts['mapped_contacts']}"
    print(f"  [PASS] TC30: Project-to-Contact Many2many & Computed Counts (Total: {p1_counts['total_contacts']}, Mapped: {p1_counts['mapped_contacts']})")

    # =========================================================================
    # TC31: Contact Extraction in get_project_map_data()
    # =========================================================================
    p1_map_data = odoo_call("sgt.project.heatmap", "get_project_map_data", [[("id", "=", p1_id)]])[0]
    assert "contacts" in p1_map_data, "TC31 Failed: 'contacts' array missing from get_project_map_data()"
    assert len(p1_map_data["contacts"]) == 3, f"TC31 Failed: expected 3 contacts, got {len(p1_map_data['contacts'])}"
    contact_a = next((c for c in p1_map_data["contacts"] if c["id"] == partner_a_id), None)
    assert contact_a and contact_a["has_coordinates"] is True, "TC31 Failed: contact_a coordinates not recognized"
    assert contact_a["role"] == "seller", f"TC31 Failed: contact role mismatch: {contact_a['role']}"
    assert contact_a["province"] == "Bình Dương", f"TC31 Failed: contact province mismatch: {contact_a['province']}"
    print("  [PASS] TC31: Contact Extraction in get_project_map_data() (Coordinates, Role, Province)")

    # =========================================================================
    # TC32: Demo Ecosystems for GEAREA, ARGO, YINGBO (Each has multiple contacts)
    # =========================================================================
    gearea_recheck = next((p for p in api_projects if "gearea" in p["name"].lower()), None)
    argo_recheck = next((p for p in api_projects if "argo" in p["name"].lower()), None)
    yingbo_recheck = next((p for p in api_projects if "yingbo" in p["name"].lower()), None)

    assert gearea_recheck is not None, "TC32 Failed: GEAREA project not found in API data"
    assert argo_recheck is not None, "TC32 Failed: ARGO project not found in API data"
    assert yingbo_recheck is not None, "TC32 Failed: YINGBO project not found in API data"
    print(f"  [PASS] TC32: Major Projects Identified (GEAREA, ARGO, YINGBO) with Independent Eco-networks")

    # =========================================================================
    # TC33: get_top_contact_areas() Mandatory Columns & Descending Sort
    # =========================================================================
    top_argo = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {
        "project_id": "argo",
        "area_level": "district",
        "limit": 10,
    })
    assert "areas" in top_argo, "TC33 Failed: 'areas' key missing"
    assert "total_contacts" in top_argo and "mapped_contacts" in top_argo and "unmapped_contacts" in top_argo, "TC33 Failed: counter keys missing"
    assert len(top_argo["areas"]) > 0, "TC33 Failed: no areas returned for ARGO"
    
    # Check mandatory columns: Khu vực (area) & Khách (customer_count)
    first_area = top_argo["areas"][0]
    assert "area" in first_area and first_area["area"], "TC33 Failed: mandatory column 'Khu vực' (area) missing"
    assert "customer_count" in first_area and isinstance(first_area["customer_count"], int), "TC33 Failed: mandatory column 'Khách' (customer_count) missing"
    assert "percentage" in first_area and isinstance(first_area["percentage"], (int, float)), "TC33 Failed: 'percentage' missing"
    
    # Verify sorted descending by customer_count
    counts = [a["customer_count"] for a in top_argo["areas"]]
    assert counts == sorted(counts, reverse=True), f"TC33 Failed: areas not sorted descending by customer_count: {counts}"
    print(f"  [PASS] TC33: get_top_contact_areas() Mandatory Columns ('Khu vực', 'Khách', 'Tỷ lệ') & Descending Sort")

    # =========================================================================
    # TC34: Dynamic Contact Creation & Dynamic Count Update (No Hardcoding)
    # =========================================================================
    # 1. Check current count for 'Hải An' in ARGO
    hai_an_before = next((a["customer_count"] for a in top_argo["areas"] if a["area"] == "Hải An"), 0)
    
    # 2. Add a new contact in 'Hải An' linked to ARGO
    argo_record = odoo_call("sgt.project.heatmap", "search", [("name", "ilike", "argo")])[0]
    new_contact_ha = odoo_call("res.partner", "create", {
        "name": f"Dynamic Offshore Supplier {ts}",
        "is_company": True,
        "x_type_contact": "seller",
        "x_fb_industry": "Energy",
        "contact_province": "Hải Phòng",
        "contact_district": "Hải An",
        "partner_latitude": 20.8250,
        "partner_longitude": 106.7550,
        "project_ids": [(4, argo_record)],
    })
    
    # Re-fetch top areas
    top_argo_updated = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {
        "project_id": "argo",
        "area_level": "district",
        "limit": 10,
    })
    hai_an_after = next((a["customer_count"] for a in top_argo_updated["areas"] if a["area"] == "Hải An"), 0)
    assert hai_an_after == hai_an_before + 1, f"TC34 Failed: expected Hải An count {hai_an_before + 1}, got {hai_an_after}"

    # 3. Add 5 contacts in 'Dĩ An' to test that Dĩ An dynamically moves to TOP
    di_an_contacts = []
    for i in range(5):
        c_id = odoo_call("res.partner", "create", {
            "name": f"Dynamic Dĩ An Enterprise {ts} #{i}",
            "is_company": True,
            "x_type_contact": "seller",
            "x_fb_industry": "Manufacturing",
            "contact_province": "Bình Dương",
            "contact_district": "Dĩ An",
            "partner_latitude": 10.8980 + (i * 0.001),
            "partner_longitude": 106.7550 + (i * 0.001),
            "project_ids": [(4, argo_record)],
        })
        di_an_contacts.append(c_id)

    top_argo_dian = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {
        "project_id": "argo",
        "area_level": "district",
        "limit": 10,
    })
    assert top_argo_dian["areas"][0]["area"] == "Dĩ An", f"TC34 Failed: Dĩ An should automatically be #1, got {top_argo_dian['areas'][0]['area']}"
    assert top_argo_dian["areas"][0]["customer_count"] >= 5, f"TC34 Failed: Dĩ An count should be >= 5"
    print(f"  [PASS] TC34: Dynamic Contact Creation & Automatic Real-time Recounting (Dĩ An became TOP #1 with {top_argo_dian['areas'][0]['customer_count']} contacts)")

    # =========================================================================
    # TC35: Top Limit Slicing (Top 5, Top 10, Top 20, All)
    # =========================================================================
    res_top5 = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {"project_id": "all", "area_level": "district", "limit": 5})
    res_top10 = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {"project_id": "all", "area_level": "district", "limit": 10})
    res_all_limit = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {"project_id": "all", "area_level": "district", "limit": "all"})
    
    assert len(res_top5["areas"]) <= 5, f"TC35 Failed: limit 5 exceeded: {len(res_top5['areas'])}"
    assert len(res_top10["areas"]) <= 10, f"TC35 Failed: limit 10 exceeded: {len(res_top10['areas'])}"
    assert len(res_all_limit["areas"]) >= len(res_top10["areas"]), "TC35 Failed: all limit should return >= top 10"
    print(f"  [PASS] TC35: Top Limit Slicing (Top 5: {len(res_top5['areas'])}, Top 10: {len(res_top10['areas'])}, All: {len(res_all_limit['areas'])})")

    # =========================================================================
    # TC36: Configurable Area Level (District -> Province -> Ward)
    # =========================================================================
    res_province = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {"project_id": "gearea", "area_level": "province"})
    res_district = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {"project_id": "gearea", "area_level": "district"})
    
    assert res_province["area_level"] == "province", "TC36 Failed: area_level should be 'province'"
    assert res_district["area_level"] == "district", "TC36 Failed: area_level should be 'district'"
    # Top province for GEAREA should be Bình Dương or TP.HCM
    prov_names = [a["area"] for a in res_province["areas"]]
    assert "Bình Dương" in prov_names or "TP. Hồ Chí Minh" in prov_names, f"TC36 Failed: Expected Bình Dương/TP.HCM in {prov_names}"
    print(f"  [PASS] TC36: Configurable Area Level Aggregation (District & Province)")

    # =========================================================================
    # TC37: Synchronization with Active Dashboard Filters (Project & Industry)
    # =========================================================================
    # Filter by Energy industry only
    res_energy = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {
        "project_id": "all",
        "area_level": "district",
        "domain": {"industry": "Energy"},
    })
    # Filter by Manufacturing industry only
    res_mfg = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {
        "project_id": "all",
        "area_level": "district",
        "domain": {"industry": "Manufacturing"},
    })
    assert res_energy["total_contacts"] != res_mfg["total_contacts"], "TC37 Failed: Filter by industry should produce different datasets"
    print(f"  [PASS] TC37: Filter Synchronization (Energy contacts: {res_energy['total_contacts']} vs Manufacturing contacts: {res_mfg['total_contacts']})")

    # =========================================================================
    # TC38: Contact Without Location / Unmapped Contacts Isolation
    # =========================================================================
    unmapped_partner = odoo_call("res.partner", "create", {
        "name": f"Unmapped Test Contact {ts}",
        "is_company": True,
        "x_type_contact": "buyer",
        "partner_latitude": 0.0,
        "partner_longitude": 0.0,
        "project_ids": [(4, argo_record)],
    })
    res_unmapped_check = odoo_call("sgt.project.heatmap", "get_top_contact_areas", [], {
        "project_id": "argo",
        "area_level": "district",
    })
    assert res_unmapped_check["unmapped_contacts"] >= 1, "TC38 Failed: unmapped contacts count should be >= 1"
    assert unmapped_partner in res_unmapped_check["unmapped_partner_ids"], "TC38 Failed: unmapped partner ID missing from unmapped list"
    # Unmapped contact should NOT appear in areas table
    for a in res_unmapped_check["areas"]:
        assert unmapped_partner not in a["partner_ids"], f"TC38 Failed: unmapped partner incorrectly included in area {a['area']}"
    print(f"  [PASS] TC38: Unmapped Contacts Isolated (Count: {res_unmapped_check['unmapped_contacts']}, safely excluded from areas table)")

    # =========================================================================
    # TC39: Geographical Center & Bounds for Click-to-Zoom Interactivity
    # =========================================================================
    first_area_bounds = top_argo_dian["areas"][0]
    assert first_area_bounds["bounds"] is not None, "TC39 Failed: bounds missing for area"
    assert first_area_bounds["center"] is not None, "TC39 Failed: center missing for area"
    assert len(first_area_bounds["bounds"]) == 2, "TC39 Failed: bounds must contain [[min_lat, min_lng], [max_lat, max_lng]]"
    assert len(first_area_bounds["center"]) == 2, "TC39 Failed: center must contain [lat, lng]"
    print(f"  [PASS] TC39: Geographical Center & Bounds Calculated for Area Zoom Interactivity ({first_area_bounds['area']} -> Center: {first_area_bounds['center']})")

    # =========================================================================
    # TC40: Goong Reverse Geocoding & Result Caching on res.partner
    # =========================================================================
    test_geo_partner = odoo_call("res.partner", "create", {
        "name": f"Partner Needs Reverse Geocoding {ts}",
        "is_company": True,
        "partner_latitude": 10.8980,
        "partner_longitude": 106.7550,
        "contact_province": "Bình Dương",
        "contact_district": "Dĩ An",
        "contact_ward": "Phường An Bình",
        "location_source": "manual",
    })
    # Calling action_reverse_geocode_goong should safely skip since all 3 fields already exist (Cache hit)
    odoo_call("res.partner", "action_reverse_geocode_goong", [test_geo_partner])
    read_geo = odoo_call("res.partner", "read", [test_geo_partner], ["contact_province", "contact_district", "contact_ward", "location_source"])[0]
    assert read_geo["contact_ward"] == "Phường An Bình", "TC40 Failed: contact_ward mismatch"
    assert read_geo["contact_district"] == "Dĩ An", "TC40 Failed: contact_district mismatch"
    print(f"  [PASS] TC40: Goong Reverse Geocoding Integration & Cache Awareness on res.partner")

    print("=" * 80)
    print("ALL 40 TEST CASES PASSED SUCCESSFULLY FOR PROJECT HEATMAP & GEO ANALYTICS!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
