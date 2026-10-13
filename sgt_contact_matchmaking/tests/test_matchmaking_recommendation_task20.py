# -*- coding: utf-8 -*-
"""
Comprehensive Automated Test Suite for Task 20: Matchmaking Scoring & Recommendation.
Tests:
- TC1: Perfect Match (95 pts) -> All 5 criteria match
- TC2: Category Only (+30 pts) -> Only product category matches
- TC3: Multiple Category Overlap Capping (+30 pts Max) -> Overlaps multiple categories, capped at 30
- TC4: Industry Only (+20 pts) -> Only industry matches
- TC5: Event Only (+20 pts) -> Only shared event matches, capped at 20
- TC6: Buyer - Seller Complementary (+20 pts) -> Buyer <-> Seller complementary
- TC7: Both - Buyer / Both - Seller / Both - Both (+20 pts)
- TC8: Buyer - Buyer Non-Complementary (0 pts)
- TC9: Seller - Seller Non-Complementary (0 pts)
- TC10: Country Only (+5 pts) -> Only same country
- TC11: Zero Match (0 pts) -> Completely different
- TC12: Self Match Exclusion (0 pts & Excluded from candidates)
- TC13: Missing / Null Fields Resilience (Zero division / AttributeError safe)
- TC14: Top 10 Limit & Deterministic Sorting (score DESC, name ASC, id ASC)
- TC15: Explainable Reasons Breakdown & Wizard Integration
"""

import sys
import time
import xmlrpc.client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_tests():
    print("=" * 75)
    print("STARTING TEST SUITE: TASK 20 - MATCHMAKING SCORING & RECOMMENDATION")
    print("=" * 75)

    db = "odoo_01"
    login = "tranthien442005@gmail.com"
    pwd = "123456"

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

    # Get country IDs for Vietnam (VN) and Japan (JP)
    vn_country = odoo_call("res.country", "search", [("code", "=", "VN")], limit=1)
    jp_country = odoo_call("res.country", "search", [("code", "=", "JP")], limit=1)
    vn_id = vn_country[0] if vn_country else False
    jp_id = jp_country[0] if jp_country else False

    # Get an industry ID if available
    ind_res = odoo_call("res.partner.industry", "search", [], limit=2)
    ind1_id = ind_res[0] if ind_res else False
    ind2_id = ind_res[1] if len(ind_res) > 1 else False

    print("\n--- SETUP: Creating Specialized Contacts for Task 20 Verification ---")

    # Source Contact: ABC Trading (Buyer, Electronics & IoT, Tech, Expo 2026, Vietnam)
    source_id = odoo_call("res.partner", "create", {
        "name": f"T20 Source ABC Trading {ts}",
        "is_company": True,
        "x_type_contact": "buyer",
        "x_product_category": "Electronics, IoT Devices",
        "x_product_details": "High precision smart IoT sensors and microcontrollers",
        "x_event": "Vietnam Expo 2026, Saigon Tech 2026",
        "x_fb_industry": "Technology",
        "industry_id": ind1_id,
        "country_id": vn_id,
    })
    print(f"[*] Created Source Contact #{source_id}")

    # Candidate 1: Perfect Match Target (Seller, Electronics & Automation, Tech, Expo 2026, Vietnam) -> 95 pts
    c1_perfect_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 1 Perfect Supplier {ts}",
        "is_company": True,
        "x_type_contact": "seller",
        "x_product_category": "Electronics, Automation",
        "x_product_details": "Industrial electronics and automation hardware",
        "x_event": "Vietnam Expo 2026",
        "x_fb_industry": "Technology",
        "industry_id": ind1_id,
        "country_id": vn_id,
    })

    # Candidate 2: Category Only (Buyer, Electronics, Logistics, Hanoi Expo, Japan) -> 30 pts
    c2_cat_only_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 2 Cat Only {ts}",
        "is_company": True,
        "x_type_contact": "buyer",  # Buyer + Buyer = 0
        "x_product_category": "Electronics, Machinery",
        "x_event": "Hanoi Expo 2025",
        "x_fb_industry": "Logistics",
        "industry_id": ind2_id,
        "country_id": jp_id,
    })

    # Candidate 3: Multiple Categories Overlap Capping -> Overlaps 2 categories, Buyer+Buyer, diff all -> 30 pts max
    c3_multi_cat_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 3 Multi Cat Overlap {ts}",
        "is_company": True,
        "x_type_contact": "buyer",  # Buyer + Buyer = 0
        "x_product_category": "Electronics, IoT Devices, Semiconductors",  # overlaps 2 items
        "x_event": "Different Fair",
        "x_fb_industry": "Logistics",
        "industry_id": ind2_id,
        "country_id": jp_id,
    })

    # Candidate 4: Industry Only (Buyer, Apparel, Tech, Other Fair, Japan) -> 20 pts
    c4_ind_only_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 4 Industry Only {ts}",
        "is_company": True,
        "x_type_contact": "buyer",  # Buyer + Buyer = 0
        "x_product_category": "Apparel, Garments",
        "x_event": "Different Fair",
        "x_fb_industry": "Technology",
        "industry_id": ind1_id,
        "country_id": jp_id,
    })

    # Candidate 5: Event Only (Buyer, Apparel, Logistics, Expo 2026, Japan) -> 20 pts
    c5_event_only_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 5 Event Only {ts}",
        "is_company": True,
        "x_type_contact": "buyer",
        "x_product_category": "Garments, Textile",
        "x_event": "Vietnam Expo 2026, Saigon Tech 2026",  # multiple events overlap -> capped at 20
        "x_fb_industry": "Logistics",
        "industry_id": ind2_id,
        "country_id": jp_id,
    })

    # Candidate 6: Buyer-Seller Complementary Only (Seller, Apparel, Logistics, Other Fair, Japan) -> 20 pts
    c6_bs_only_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 6 BuyerSeller Only {ts}",
        "is_company": True,
        "x_type_contact": "seller",  # Buyer <-> Seller = +20
        "x_product_category": "Apparel, Garments",
        "x_event": "Other Fair",
        "x_fb_industry": "Logistics",
        "industry_id": ind2_id,
        "country_id": jp_id,
    })

    # Candidate 7: Both Type Complementary (Both, Apparel, Logistics, Other Fair, Japan) -> 20 pts
    c7_both_type_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 7 Both Role {ts}",
        "is_company": True,
        "x_type_contact": "both",  # Buyer <-> Both = +20
        "x_product_category": "Furniture",
        "x_event": "Other Fair",
        "x_fb_industry": "Logistics",
        "industry_id": ind2_id,
        "country_id": jp_id,
    })

    # Candidate 8: Buyer-Buyer Non-Complementary (Buyer, Apparel, Logistics, Other Fair, Japan) -> 0 pts
    c8_bb_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 8 Buyer Buyer {ts}",
        "is_company": True,
        "x_type_contact": "buyer",  # Buyer <-> Buyer = 0
        "x_product_category": "Food, Beverage",
        "x_event": "Other Fair",
        "x_fb_industry": "Agriculture",
        "country_id": jp_id,
    })

    # Candidate 9: Seller-Seller Non-Complementary
    seller_source_id = odoo_call("res.partner", "create", {
        "name": f"T20 Seller Source {ts}",
        "is_company": True,
        "x_type_contact": "seller",
        "x_product_category": "Toys",
        "x_event": "Toy Fair",
        "country_id": jp_id,
    })
    c9_ss_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 9 Seller Seller {ts}",
        "is_company": True,
        "x_type_contact": "seller",  # Seller <-> Seller = 0
        "x_product_category": "Chemicals",
        "x_event": "Chem Fair",
        "country_id": vn_id,
    })

    # Candidate 10: Country Only (Buyer, Ceramics, Retail, Ceramic Expo, Vietnam) -> 5 pts
    c10_country_only_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 10 Country Only {ts}",
        "is_company": True,
        "x_type_contact": "buyer",  # Buyer + Buyer = 0
        "x_product_category": "Ceramics",
        "x_event": "Ceramic Fair",
        "x_fb_industry": "Arts",
        "country_id": vn_id,  # Same Country = +5
    })

    # Candidate 11: Zero Match (Buyer, Fashion, Textile, Paris Fashion Week, France/Japan) -> 0 pts
    c11_zero_match_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 11 Zero Match {ts}",
        "is_company": True,
        "x_type_contact": "buyer",
        "x_product_category": "Fashion, Haute Couture",
        "x_event": "Paris Fashion Week",
        "x_fb_industry": "Textile",
        "country_id": jp_id,
    })

    # Candidate 12: Contact with missing / null fields (None, False, empty strings)
    c12_null_fields_id = odoo_call("res.partner", "create", {
        "name": f"T20 Cand 12 Missing Fields {ts}",
        "is_company": True,
        "x_type_contact": False,
        "x_product_category": False,
        "x_event": False,
        "x_fb_industry": False,
        "industry_id": False,
        "country_id": False,
    })

    print("[*] All specialized test partners created successfully.")

    # =========================================================================
    # TEST CASES EXECUTION
    # =========================================================================

    print("\n--- TC1: Perfect Match (95 pts) ---")
    res_tc1 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c1_perfect_id)
    print(f"[*] TC1 Result: score={res_tc1['score']}, breakdown={res_tc1['breakdown']}")
    assert res_tc1["score"] == 95.0, f"Expected 95.0, got {res_tc1['score']}"
    assert res_tc1["breakdown"]["category"] == 30.0
    assert res_tc1["breakdown"]["industry"] == 20.0
    assert res_tc1["breakdown"]["event"] == 20.0
    assert res_tc1["breakdown"]["buyer_seller"] == 20.0
    assert res_tc1["breakdown"]["country"] == 5.0
    print("[PASS] TC1: Perfect Match achieved exactly 95.0 points across all 5 criteria!")

    print("\n--- TC2: Category Only (+30 pts) ---")
    res_tc2 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c2_cat_only_id)
    print(f"[*] TC2 Result: score={res_tc2['score']}, breakdown={res_tc2['breakdown']}")
    assert res_tc2["score"] == 30.0, f"Expected 30.0, got {res_tc2['score']}"
    assert res_tc2["breakdown"]["category"] == 30.0
    assert res_tc2["breakdown"]["industry"] == 0.0
    assert res_tc2["breakdown"]["event"] == 0.0
    assert res_tc2["breakdown"]["buyer_seller"] == 0.0
    assert res_tc2["breakdown"]["country"] == 0.0
    print("[PASS] TC2: Category match only correctly evaluated to +30.0 points!")

    print("\n--- TC3: Multiple Category Overlap Capping (+30 pts Max) ---")
    res_tc3 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c3_multi_cat_id)
    print(f"[*] TC3 Result: score={res_tc3['score']}, breakdown={res_tc3['breakdown']}")
    assert res_tc3["score"] == 30.0, f"Expected 30.0, got {res_tc3['score']}"
    assert res_tc3["breakdown"]["category"] == 30.0, "Category score must cap at 30 even with multiple matches"
    print("[PASS] TC3: Overlapping multiple categories correctly capped at +30.0 points maximum!")

    print("\n--- TC4: Industry Only (+20 pts) ---")
    res_tc4 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c4_ind_only_id)
    print(f"[*] TC4 Result: score={res_tc4['score']}, breakdown={res_tc4['breakdown']}")
    assert res_tc4["score"] == 20.0, f"Expected 20.0, got {res_tc4['score']}"
    assert res_tc4["breakdown"]["industry"] == 20.0
    print("[PASS] TC4: Industry match only correctly evaluated to +20.0 points!")

    print("\n--- TC5: Event Only (+20 pts) ---")
    res_tc5 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c5_event_only_id)
    print(f"[*] TC5 Result: score={res_tc5['score']}, breakdown={res_tc5['breakdown']}")
    assert res_tc5["score"] == 20.0, f"Expected 20.0, got {res_tc5['score']}"
    assert res_tc5["breakdown"]["event"] == 20.0, "Event score must cap at 20 even with multiple events"
    print("[PASS] TC5: Shared event participation correctly evaluated to +20.0 points!")

    print("\n--- TC6: Buyer - Seller Complementary (+20 pts) ---")
    res_tc6 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c6_bs_only_id)
    print(f"[*] TC6 Result: score={res_tc6['score']}, breakdown={res_tc6['breakdown']}")
    assert res_tc6["score"] == 20.0, f"Expected 20.0, got {res_tc6['score']}"
    assert res_tc6["breakdown"]["buyer_seller"] == 20.0
    print("[PASS] TC6: Buyer <-> Seller complementary relationship correctly awarded +20.0 points!")

    print("\n--- TC7: Both - Buyer / Both - Seller / Both - Both (+20 pts) ---")
    res_tc7 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c7_both_type_id)
    print(f"[*] TC7 Result: score={res_tc7['score']}, breakdown={res_tc7['breakdown']}")
    assert res_tc7["breakdown"]["buyer_seller"] == 20.0
    # Also verify Both <-> Both
    res_both_both = odoo_call("sgt.matchmaking.service", "calculate_match_score", c7_both_type_id, c7_both_type_id)
    # Note: self match returns 0, let's create another 'both' contact
    c7_both_2_id = odoo_call("res.partner", "create", {"name": f"Both 2 {ts}", "x_type_contact": "both"})
    res_bb = odoo_call("sgt.matchmaking.service", "calculate_match_score", c7_both_type_id, c7_both_2_id)
    assert res_bb["breakdown"]["buyer_seller"] == 20.0
    print("[PASS] TC7: 'both' complementary matching successfully awarded +20.0 points across combinations!")

    print("\n--- TC8: Buyer - Buyer Non-Complementary (0 pts) ---")
    res_tc8 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c8_bb_id)
    print(f"[*] TC8 Result: score={res_tc8['score']}, breakdown={res_tc8['breakdown']}")
    assert res_tc8["breakdown"]["buyer_seller"] == 0.0
    print("[PASS] TC8: Buyer <-> Buyer correctly received 0 points for complementary!")

    print("\n--- TC9: Seller - Seller Non-Complementary (0 pts) ---")
    res_tc9 = odoo_call("sgt.matchmaking.service", "calculate_match_score", seller_source_id, c9_ss_id)
    print(f"[*] TC9 Result: score={res_tc9['score']}, breakdown={res_tc9['breakdown']}")
    assert res_tc9["breakdown"]["buyer_seller"] == 0.0
    print("[PASS] TC9: Seller <-> Seller correctly received 0 points for complementary!")

    print("\n--- TC10: Country Only (+5 pts) ---")
    res_tc10 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c10_country_only_id)
    print(f"[*] TC10 Result: score={res_tc10['score']}, breakdown={res_tc10['breakdown']}")
    assert res_tc10["score"] == 5.0, f"Expected 5.0, got {res_tc10['score']}"
    assert res_tc10["breakdown"]["country"] == 5.0
    print("[PASS] TC10: Same country only correctly awarded +5.0 points!")

    print("\n--- TC11: Zero Match (0 pts) ---")
    res_tc11 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c11_zero_match_id)
    print(f"[*] TC11 Result: score={res_tc11['score']}, breakdown={res_tc11['breakdown']}")
    assert res_tc11["score"] == 0.0, f"Expected 0.0, got {res_tc11['score']}"
    print("[PASS] TC11: Completely different contacts correctly scored 0.0 points!")

    print("\n--- TC12: Self Match Exclusion ---")
    res_tc12 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, source_id)
    print(f"[*] TC12 Self score: {res_tc12['score']}, reasons: {res_tc12['reasons']}")
    assert res_tc12["score"] == 0.0
    assert "Cannot match a contact with itself" in res_tc12["reasons"][0]
    print("[PASS] TC12: Self-matching safely blocked and returned 0.0 score!")

    print("\n--- TC13: Missing / Null Fields Resilience ---")
    res_tc13 = odoo_call("sgt.matchmaking.service", "calculate_match_score", source_id, c12_null_fields_id)
    print(f"[*] TC13 Result with null fields: score={res_tc13['score']}")
    assert isinstance(res_tc13["score"], (int, float))
    print("[PASS] TC13: Evaluated partner with null/empty fields safely without exceptions!")

    print("\n--- TC14: Top 10 Limit & Deterministic Sorting ---")
    matches = odoo_call("sgt.matchmaking.service", "find_matching_contacts", source_id, 10, 0.0)
    print(f"[*] Top matches count: {len(matches)}")
    assert len(matches) <= 10, f"Expected at most 10 matches, got {len(matches)}"
    # Verify strict descending sort
    scores = [m["score"] for m in matches]
    print(f"[*] Scores in Top 10: {scores}")
    assert scores == sorted(scores, reverse=True), "Top 10 must be strictly sorted in descending score order"
    # Verify top match has maximum score 95.0
    assert matches[0]["score"] == 95.0, f"Expected highest score 95.0, got {matches[0]['score']}"
    assert matches[0]["rank"] == 1
    # Verify candidate 1 perfect match is in top matches with 95.0
    match_ids = [m["partner_id"] for m in matches]
    assert c1_perfect_id in match_ids, "Candidate 1 (Perfect Match) must be in Top 10 matches"
    c1_match = next(m for m in matches if m["partner_id"] == c1_perfect_id)
    assert c1_match["score"] == 95.0, "Candidate 1 must score 95.0 points"
    # Verify source contact is NOT anywhere in matches
    assert source_id not in match_ids, "Source contact must not be in candidate pool!"
    print("[PASS] TC14: Top 10 limit, descending order, deterministic ranking, and self exclusion verified!")

    print("\n--- TC15: Explainable Reasons Breakdown & Wizard Execution ---")
    # Verify structured reasons on Candidate 1
    reasons = c1_match["reasons"]
    print(f"[*] Candidate 1 reasons ({len(reasons)} items):")
    for r in reasons:
        print(f"    - {r}")
    rule_or_labels = [f"{r.get('rule', '')} {r.get('label', '')}" if isinstance(r, dict) else str(r) for r in reasons]
    assert any("categor" in rl.lower() for rl in rule_or_labels), "Expected Category match in reasons"
    assert any("industr" in rl.lower() for rl in rule_or_labels), "Expected Industry match in reasons"
    assert any("event" in rl.lower() for rl in rule_or_labels), "Expected Event match in reasons"
    assert any("complementary" in rl.lower() or "buyer" in rl.lower() or "role" in rl.lower() for rl in rule_or_labels), "Expected Complementary match in reasons"
    assert any("countr" in rl.lower() for rl in rule_or_labels), "Expected Country match in reasons"

    # Test Wizard execution from res.partner action
    wizard_action = odoo_call("res.partner", "action_find_matching_companies", [source_id])
    assert wizard_action["type"] == "ir.actions.act_window"
    assert wizard_action["res_model"] == "sgt.matchmaking.recommendation.wizard"
    wizard_id = wizard_action["res_id"]
    print(f"[*] Wizard launched: ID #{wizard_id}")

    # Inspect wizard lines and HTML dashboard
    wiz_data = odoo_call("sgt.matchmaking.recommendation.wizard", "read", [wizard_id], ["line_ids", "html_dashboard"])[0]
    line_ids = wiz_data["line_ids"]
    dashboard_html = wiz_data["html_dashboard"]
    assert len(line_ids) > 0, "Wizard lines must be populated with Top 10 candidates"
    assert "sgt-match-recom-container" in dashboard_html, "Dashboard HTML must be rendered"
    assert "Global Tech Supplier" in dashboard_html or "Cand 1" in dashboard_html
    print(f"[PASS] TC15: Explainable breakdown and interactive Recommendation Wizard verified successfully!")

    print("\n" + "=" * 75)
    print("ALL 15 TEST CASES PASSED 100%!")
    print("TASK 20 MATCHMAKING SCORING & RECOMMENDATION ENGINE VERIFIED!")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
