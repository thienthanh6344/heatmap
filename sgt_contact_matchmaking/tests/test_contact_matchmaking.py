# -*- coding: utf-8 -*-
"""
Comprehensive Automated Test Suite for Task 19: SGT Contact Match Making.
Verifies:
CASE 1: Near identical contacts -> Very High Match (>=80%)
CASE 2: Same company + domain + similar position, different person -> Medium / High Match
CASE 3: Completely different contacts -> Low / Very Low Match (<40%)
CASE 4: Missing email handling (Zero crash, graceful scoring)
CASE 5: Missing phone handling (Zero crash, graceful scoring)
CASE 6: Contact A == Contact B validation (Warning / ValidationError)
CASE 7: Symmetric pair key normalization (A-B and B-A share same pair_key, no duplicate)
CASE 8: res.partner smart button 'match_count' and action_view_matches()
CASE 9: res.partner action_start_match_making() wizard launcher
CASE 10: Interactive Wizard action_compare_and_match() and persistent saving to sgt.contact.match
CASE 11: Difference View & Badges (MATCH, SIMILAR, DIFFERENT, MISSING)
CASE 12: Recalculate match action on sgt.contact.match
"""

import json
import logging
import sys
import time
import xmlrpc.client

_logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_tests():
    print("=" * 70)
    print("STARTING TEST SUITE: TASK 19 - SGT CONTACT MATCH MAKING")
    print("=" * 70)

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
    print(f"[*] Connected to Odoo 1 (UID: {uid})")

    def odoo_call(model, method, *args, **kwargs):
        arg_list = list(args) if args else [[]]
        return models.execute_kw(db, uid, pwd, model, method, arg_list, kwargs)

    ts = int(time.time())

    # =========================================================================
    # SETUP TEST DATA
    # =========================================================================
    print("\n--- SETUP: Creating Distinct Test Partners ---")
    company_test_id = odoo_call("res.partner", "create", {
        "name": f"Saigon Enterprise Test Co {ts}",
        "is_company": True,
        "city": "Ho Chi Minh City",
    })

    tag_test_id = odoo_call("res.partner.category", "create", {
        "name": f"Enterprise VIP {ts}",
    })

    # Partner 1: Nguyen Van An (Vietnamese diacritics)
    p1_id = odoo_call("res.partner", "create", {
        "name": "Nguyễn Văn An",
        "parent_id": company_test_id,
        "function": "Sales Director",
        "email": f"an.nguyen.{ts}@saigon-enterprise.vn",
        "phone": "+84 901 234 567",
        "city": "Ho Chi Minh City",
        "category_id": [(6, 0, [tag_test_id])],
    })

    # Partner 2: Nguyen Van An (No diacritics, identical phone/email/company)
    p2_id = odoo_call("res.partner", "create", {
        "name": "Nguyen Van An",
        "parent_id": company_test_id,
        "function": "Sales Director",
        "email": f"an.nguyen.{ts}@saigon-enterprise.vn",
        "phone": "0901234567",
        "city": "Ho Chi Minh City",
        "category_id": [(6, 0, [tag_test_id])],
    })

    # Partner 3: Colleague at same company (Different name, same domain, different phone)
    p3_id = odoo_call("res.partner", "create", {
        "name": "Trần Tuấn Kiệt",
        "parent_id": company_test_id,
        "function": "Sales Executive",
        "email": f"kiet.tran.{ts}@saigon-enterprise.vn",
        "phone": "0988777666",
        "city": "Ho Chi Minh City",
        "category_id": [(6, 0, [tag_test_id])],
    })

    # Partner 4: Completely different person from another company
    p4_id = odoo_call("res.partner", "create", {
        "name": "Lê Hoàng Yến",
        "function": "HR Specialist",
        "email": f"yen.le.{ts}@otherdomain.com",
        "phone": "0933111222",
        "city": "Hanoi",
    })

    # Partner 5: Missing email
    p5_id = odoo_call("res.partner", "create", {
        "name": "Vũ Văn Thiếu Email",
        "phone": "0911222333",
        "city": "Da Nang",
    })

    # Partner 6: Missing phone
    p6_id = odoo_call("res.partner", "create", {
        "name": "Đặng Thị Thiếu Phone",
        "email": f"thieu.phone.{ts}@gmail.com",
        "city": "Can Tho",
    })

    print(f"[PASS] Created test partners: P1={p1_id}, P2={p2_id}, P3={p3_id}, P4={p4_id}, P5={p5_id}, P6={p6_id}")

    # =========================================================================
    # CASE 1: Near Identical Contacts -> Very High Match (>=80%)
    # =========================================================================
    print("\n--- CASE 1: Near Identical Contacts Evaluation ---")
    eval_res_1 = odoo_call("sgt.contact.match", "evaluate_contacts", p1_id, p2_id)
    score_1 = eval_res_1["score"]
    level_1 = eval_res_1["match_level"]
    print(f"[*] Evaluated P1 vs P2: Score = {score_1}%, Level = {level_1}")

    assert score_1 >= 80.0, f"Expected Very High Match (>=80%), got {score_1}%"
    assert level_1 == "very_high", f"Expected level 'very_high', got {level_1}"
    assert eval_res_1["breakdown"]["email"] == 25.0, "Expected exact email score = 25"
    assert eval_res_1["breakdown"]["phone"] == 20.0, "Expected exact phone score = 20"
    assert eval_res_1["breakdown"]["company"] == 15.0, "Expected company score = 15"
    assert eval_res_1["breakdown"]["position"] == 10.0, "Expected position score = 10"
    assert eval_res_1["breakdown"]["name"] >= 8.0, "Expected name score >= 8 (diacritic match)"
    assert "html_report" in eval_res_1 and len(eval_res_1["html_report"]) > 200
    print(f"[PASS] CASE 1: P1 and P2 evaluated as {score_1}% ({level_1}) with full explainable breakdown!")

    # =========================================================================
    # CASE 2: Same Company + Email Domain -> Medium / High Match (40% - 79%)
    # =========================================================================
    print("\n--- CASE 2: Same Company & Corporate Domain ---")
    eval_res_2 = odoo_call("sgt.contact.match", "evaluate_contacts", p1_id, p3_id)
    score_2 = eval_res_2["score"]
    level_2 = eval_res_2["match_level"]
    print(f"[*] Evaluated P1 vs P3: Score = {score_2}%, Level = {level_2}")

    assert 40.0 <= score_2 < 80.0, f"Expected Medium/High Match (40-79%), got {score_2}%"
    assert level_2 in ("medium", "high"), f"Expected medium/high, got {level_2}"
    assert eval_res_2["breakdown"]["company"] == 15.0, "Expected same company score = 15"
    assert eval_res_2["breakdown"]["email"] == 10.0, "Expected domain email score = 10"
    print(f"[PASS] CASE 2: P1 and P3 evaluated as {score_2}% ({level_2}) with corporate domain & company similarity!")

    # =========================================================================
    # CASE 3: Completely Different Contacts -> Low / Very Low Match (<40%)
    # =========================================================================
    print("\n--- CASE 3: Completely Different Contacts ---")
    eval_res_3 = odoo_call("sgt.contact.match", "evaluate_contacts", p1_id, p4_id)
    score_3 = eval_res_3["score"]
    level_3 = eval_res_3["match_level"]
    print(f"[*] Evaluated P1 vs P4: Score = {score_3}%, Level = {level_3}")

    assert score_3 < 40.0, f"Expected Low/Very Low Match (<40%), got {score_3}%"
    assert level_3 in ("low", "very_low"), f"Expected low/very_low, got {level_3}"
    print(f"[PASS] CASE 3: P1 and P4 evaluated as {score_3}% ({level_3})!")

    # =========================================================================
    # CASE 4: Missing Email (Zero Crash, Graceful Handling)
    # =========================================================================
    print("\n--- CASE 4: Missing Email Handling ---")
    eval_res_4 = odoo_call("sgt.contact.match", "evaluate_contacts", p1_id, p5_id)
    assert "score" in eval_res_4
    assert eval_res_4["breakdown"]["email"] == 0.0
    email_row = next(r for r in eval_res_4["comparison"] if r["field"] == "Email Address")
    assert email_row["status"] == "MISSING"
    print(f"[PASS] CASE 4: Missing email handled gracefully (status='MISSING', zero crash)!")

    # =========================================================================
    # CASE 5: Missing Phone (Zero Crash, Graceful Handling)
    # =========================================================================
    print("\n--- CASE 5: Missing Phone Handling ---")
    eval_res_5 = odoo_call("sgt.contact.match", "evaluate_contacts", p1_id, p6_id)
    assert "score" in eval_res_5
    assert eval_res_5["breakdown"]["phone"] == 0.0
    phone_row = next(r for r in eval_res_5["comparison"] if r["field"] == "Phone / Mobile")
    assert phone_row["status"] == "MISSING"
    print(f"[PASS] CASE 5: Missing phone handled gracefully (status='MISSING', zero crash)!")

    # =========================================================================
    # CASE 6: Contact A == Contact B (Self Match Validation)
    # =========================================================================
    print("\n--- CASE 6: Contact A == Contact B Validation ---")
    try:
        odoo_call("sgt.contact.match", "evaluate_contacts", p1_id, p1_id)
        assert False, "Should have raised exception when Contact A == Contact B"
    except Exception as e:
        assert "different contacts" in str(e).lower() or "validation" in str(e).lower()
        print(f"[PASS] CASE 6: Correctly rejected self-match: {e}")

    # =========================================================================
    # CASE 7: Symmetric Pair Key & Duplicate History Prevention
    # =========================================================================
    print("\n--- CASE 7: Symmetric Pair Key & Duplicate History Prevention ---")
    # Wizard 1: Compare P1 and P2
    wiz1_id = odoo_call("sgt.contact.match.wizard", "create", {
        "contact_a_id": p1_id,
        "contact_b_id": p2_id,
    })
    odoo_call("sgt.contact.match.wizard", "action_compare_and_match", [wiz1_id])

    wiz1 = odoo_call("sgt.contact.match.wizard", "read", [wiz1_id], ["score", "saved_match_id"])[0]
    match_rec_1_id = wiz1["saved_match_id"][0]
    m1 = odoo_call("sgt.contact.match", "read", [match_rec_1_id], ["name", "pair_key", "score"])[0]
    expected_pair_key = f"{min(p1_id, p2_id)}_{max(p1_id, p2_id)}"
    assert m1["pair_key"] == expected_pair_key, f"Mismatch pair_key: {m1['pair_key']}"

    # Wizard 2: Compare reversed P2 and P1
    wiz2_id = odoo_call("sgt.contact.match.wizard", "create", {
        "contact_a_id": p2_id,
        "contact_b_id": p1_id,
    })
    odoo_call("sgt.contact.match.wizard", "action_compare_and_match", [wiz2_id])
    wiz2 = odoo_call("sgt.contact.match.wizard", "read", [wiz2_id], ["score", "saved_match_id"])[0]
    match_rec_2_id = wiz2["saved_match_id"][0]

    # Must reuse the same match record instead of duplicating
    assert match_rec_1_id == match_rec_2_id, f"Expected same match record, got {match_rec_1_id} vs {match_rec_2_id}"

    total_pairs = odoo_call("sgt.contact.match", "search_count", [("pair_key", "=", expected_pair_key)])
    assert total_pairs == 1, f"Expected exactly 1 record for pair_key {expected_pair_key}, found {total_pairs}"
    print(f"[PASS] CASE 7: Reused match record #{match_rec_1_id} for pair {expected_pair_key}. Duplicate prevented!")

    # =========================================================================
    # CASE 8: res.partner Smart Button 'match_count' & action_view_matches()
    # =========================================================================
    print("\n--- CASE 8: res.partner Smart Button & Action ---")
    p1_data = odoo_call("res.partner", "read", [p1_id], ["match_count"])[0]
    assert p1_data["match_count"] >= 1, f"Expected match_count >= 1 on P1, got {p1_data['match_count']}"

    p2_data = odoo_call("res.partner", "read", [p2_id], ["match_count"])[0]
    assert p2_data["match_count"] >= 1, f"Expected match_count >= 1 on P2, got {p2_data['match_count']}"

    action_view = odoo_call("res.partner", "action_view_matches", [p1_id])
    assert action_view.get("res_model") == "sgt.contact.match"
    assert "list" in action_view.get("view_mode")
    print(f"[PASS] CASE 8: Smart button match_count verified on partners (P1={p1_data['match_count']}, P2={p2_data['match_count']})!")

    # =========================================================================
    # CASE 9: res.partner action_start_match_making() Launcher
    # =========================================================================
    print("\n--- CASE 9: res.partner action_start_match_making() Launcher ---")
    launcher_res = odoo_call("res.partner", "action_start_match_making", [p1_id])
    assert launcher_res.get("res_model") == "sgt.contact.match.wizard"
    wiz_launched_id = launcher_res.get("res_id")
    wiz_launched = odoo_call("sgt.contact.match.wizard", "read", [wiz_launched_id], ["contact_a_id"])[0]
    assert wiz_launched["contact_a_id"][0] == p1_id, "Contact A should be pre-filled with partner ID"
    print(f"[PASS] CASE 9: 1-click launcher opened wizard with Contact A pre-filled as #{p1_id}!")

    # =========================================================================
    # CASE 10: Interactive Wizard action_compare_and_match() Output
    # =========================================================================
    print("\n--- CASE 10: Wizard Interactive Output Verification ---")
    wiz_test_id = odoo_call("sgt.contact.match.wizard", "create", {
        "contact_a_id": p1_id,
        "contact_b_id": p3_id,
    })
    odoo_call("sgt.contact.match.wizard", "action_compare_and_match", [wiz_test_id])
    wiz_test = odoo_call("sgt.contact.match.wizard", "read", [wiz_test_id], [
        "has_result", "score", "match_level", "result_html", "saved_match_id"
    ])[0]

    assert wiz_test["has_result"] is True
    assert wiz_test["score"] == score_2
    assert "sgt-match-dashboard" in wiz_test["result_html"]
    assert "Why are these contacts matched?" in wiz_test["result_html"]
    assert "Comparison Details" in wiz_test["result_html"]
    print(f"[PASS] CASE 10: Wizard generated full rich HTML dashboard with score, reasons, and table!")

    # =========================================================================
    # CASE 11: Difference View & Badges Verification
    # =========================================================================
    print("\n--- CASE 11: Difference View & Badges Verification ---")
    comp_json_str = odoo_call("sgt.contact.match", "read", [match_rec_1_id], ["comparison_json"])[0]["comparison_json"]
    comp_list = json.loads(comp_json_str)
    statuses = {item["field"]: item["status"] for item in comp_list}

    assert statuses.get("Email Address") == "MATCH"
    assert statuses.get("Phone / Mobile") == "MATCH"
    assert statuses.get("Company") == "MATCH"
    assert statuses.get("Full Name") in ("MATCH", "SIMILAR")
    print(f"[PASS] CASE 11: Badges validated: {statuses}")

    # =========================================================================
    # CASE 12: Recalculate Action on sgt.contact.match
    # =========================================================================
    print("\n--- CASE 12: Recalculate Match Action ---")
    recalc_res = odoo_call("sgt.contact.match", "action_recalculate", [match_rec_1_id])
    assert recalc_res.get("type") == "ir.actions.client"
    assert recalc_res.get("params", {}).get("type") == "success"
    print(f"[PASS] CASE 12: action_recalculate executed successfully and updated record #{match_rec_1_id}!")

    print("\n" + "=" * 70)
    print("ALL 12 TEST CASES PASSED 100%!")
    print("TASK 19 SGT CONTACT MATCH MAKING IS FULLY VERIFIED!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
