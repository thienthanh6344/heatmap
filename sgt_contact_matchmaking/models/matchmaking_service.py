# -*- coding: utf-8 -*-
"""
SGT Matchmaking Service (Task 20)
Provides production backend scoring engine for Contact Matchmaking Recommendation.

Scoring Rules (Maximum: 95 points):
- Product Category overlap: +30
- Industry match:           +20
- Same Event overlap:       +20
- Buyer/Seller complement:  +20
- Same Country match:       +5
Formula: score = category + industry + event + buyer_seller + country
"""

import json
import logging
import re
import unicodedata
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

SCORING_WEIGHTS = {
    "product_category": 30.0,
    "industry": 20.0,
    "event": 20.0,
    "buyer_seller": 20.0,
    "country": 5.0,
}
MAX_TOTAL_SCORE = 95.0


def _normalize_string(val):
    """Normalize text: strip, lowercase, NFC unicode form."""
    if not val:
        return ""
    text = str(val).strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFC", text).strip().lower()


def _split_items(val):
    """Split comma / semicolon / newline / slash separated string into normalized set."""
    if not val:
        return set()
    raw = str(val)
    parts = re.split(r"[,;|\n\r/]+", raw)
    items = set()
    for p in parts:
        clean = _normalize_string(p)
        if clean:
            items.add(clean)
    return items


class SgtMatchmakingService(models.AbstractModel):
    _name = "sgt.matchmaking.service"
    _description = "SGT Contact Matchmaking Recommendation Service"

    # -------------------------------------------------------------------------
    # FIELD EXTRACTORS & NORMALIZERS
    # -------------------------------------------------------------------------
    @api.model
    def _extract_categories(self, partner):
        """Extract set of normalized product category strings from partner."""
        categories = set()
        # 1. Dedicated field x_product_category
        if hasattr(partner, "x_product_category") and partner.x_product_category:
            categories.update(_split_items(partner.x_product_category))

        # 2. Partner tags (category_id) fallback / supplement
        if partner.category_id:
            for tag in partner.category_id:
                clean_tag = _normalize_string(tag.name)
                if clean_tag:
                    categories.add(clean_tag)
        return categories

    @api.model
    def _extract_industry(self, partner):
        """Extract normalized industry identifier or text."""
        # 1. Standard Odoo Many2one industry_id
        if getattr(partner, "industry_id", None) and partner.industry_id:
            return _normalize_string(partner.industry_id.name)

        # 2. Custom x_fb_industry Char
        if hasattr(partner, "x_fb_industry") and partner.x_fb_industry:
            return _normalize_string(partner.x_fb_industry)

        return ""

    @api.model
    def _extract_events(self, partner):
        """Extract set of normalized participating events."""
        events = set()
        if hasattr(partner, "x_event") and partner.x_event:
            events.update(_split_items(partner.x_event))
        return events

    @api.model
    def _extract_contact_type(self, partner):
        """
        Extract normalized role: 'buyer', 'seller', or 'both'.
        Returns empty string if unknown.
        """
        val = ""
        if hasattr(partner, "x_type_contact") and partner.x_type_contact:
            val = str(partner.x_type_contact).strip().lower()

        if "buyer" in val and "seller" in val:
            return "both"
        elif "buyer" in val:
            return "buyer"
        elif "seller" in val:
            return "seller"
        elif val in ("both", "flexible"):
            return "both"
        return ""

    @api.model
    def _extract_country(self, partner):
        """Extract normalized country key (ID or code or name)."""
        if partner.country_id:
            return partner.country_id.code or _normalize_string(partner.country_id.name)
        if hasattr(partner, "x_country") and partner.x_country:
            return _normalize_string(partner.x_country)
        return ""

    # -------------------------------------------------------------------------
    # CORE SCORING LOGIC (SPECIFICATION RULES)
    # -------------------------------------------------------------------------
    @api.model
    def calculate_match_score(self, source_contact, target_contact):
        """
        Calculates matchmaking score between source_contact and target_contact.
        Formula:
          score = category_score (+30)
                + industry_score (+20)
                + event_score (+20)
                + buyer_seller_score (+20)
                + country_score (+5)
          Total Max: 95.0

        Self-match is strictly 0.0 (and excluded).
        Missing fields do not crash and simply receive 0 points.
        Returns:
          {
             'score': float (0.0 - 95.0),
             'breakdown': {
                 'product_category': float,
                 'industry': float,
                 'event': float,
                 'buyer_seller': float,
                 'country': float
             },
             'reasons': list of dicts,
             'details': dict of supplementary info (e.g. product details)
          }
        """
        if isinstance(source_contact, (int, str)):
            source_contact = self.env["res.partner"].browse(int(source_contact))
        if isinstance(target_contact, (int, str)):
            target_contact = self.env["res.partner"].browse(int(target_contact))

        if not source_contact or not target_contact:
            return {
                "score": 0.0,
                "breakdown": {"category": 0.0, "industry": 0.0, "event": 0.0, "buyer_seller": 0.0, "country": 0.0},
                "reasons": [],
                "details": {},
            }

        # Self-match prevention: Score is 0
        if source_contact.id == target_contact.id:
            return {
                "score": 0.0,
                "breakdown": {"category": 0.0, "industry": 0.0, "event": 0.0, "buyer_seller": 0.0, "country": 0.0},
                "reasons": ["Cannot match a contact with itself."],
                "details": {},
            }

        breakdown = {
            "product_category": 0.0,
            "industry": 0.0,
            "event": 0.0,
            "buyer_seller": 0.0,
            "country": 0.0,
        }
        reasons = []

        # ---------------------------------------------------------------------
        # 1. PRODUCT CATEGORY (+30)
        # ---------------------------------------------------------------------
        src_cats = self._extract_categories(source_contact)
        tgt_cats = self._extract_categories(target_contact)
        common_cats = src_cats.intersection(tgt_cats) if (src_cats and tgt_cats) else set()

        if common_cats:
            breakdown["product_category"] = SCORING_WEIGHTS["product_category"]
            reasons.append({
                "rule": "product_category",
                "label": _("Same Product Category"),
                "points": int(SCORING_WEIGHTS["product_category"]),
                "matched_value": ", ".join(sorted(c.title() for c in common_cats)),
            })

        # ---------------------------------------------------------------------
        # 2. INDUSTRY (+20)
        # ---------------------------------------------------------------------
        src_ind = self._extract_industry(source_contact)
        tgt_ind = self._extract_industry(target_contact)

        if src_ind and tgt_ind and src_ind == tgt_ind:
            breakdown["industry"] = SCORING_WEIGHTS["industry"]
            display_ind = target_contact.industry_id.name if target_contact.industry_id else src_ind.title()
            reasons.append({
                "rule": "industry",
                "label": _("Same Industry"),
                "points": int(SCORING_WEIGHTS["industry"]),
                "matched_value": display_ind,
            })

        # ---------------------------------------------------------------------
        # 3. SAME EVENT (+20)
        # ---------------------------------------------------------------------
        src_events = self._extract_events(source_contact)
        tgt_events = self._extract_events(target_contact)
        common_events = src_events.intersection(tgt_events) if (src_events and tgt_events) else set()

        if common_events:
            breakdown["event"] = SCORING_WEIGHTS["event"]
            reasons.append({
                "rule": "event",
                "label": _("Same Event"),
                "points": int(SCORING_WEIGHTS["event"]),
                "matched_value": ", ".join(sorted(e.title() for e in common_events)),
            })

        # ---------------------------------------------------------------------
        # 4. BUYER / SELLER COMPLEMENTARY (+20)
        # ---------------------------------------------------------------------
        src_type = self._extract_contact_type(source_contact)
        tgt_type = self._extract_contact_type(target_contact)
        is_complementary = False
        comp_label = ""

        if src_type and tgt_type:
            if (src_type == "buyer" and tgt_type == "seller") or (src_type == "seller" and tgt_type == "buyer"):
                is_complementary = True
                comp_label = f"{src_type.capitalize()} ↔ {tgt_type.capitalize()}"
            elif src_type == "both" and tgt_type in ("buyer", "seller", "both"):
                is_complementary = True
                comp_label = f"Both / Flexible ↔ {tgt_type.capitalize()}"
            elif tgt_type == "both" and src_type in ("buyer", "seller"):
                is_complementary = True
                comp_label = f"{src_type.capitalize()} ↔ Both / Flexible"

        if is_complementary:
            breakdown["buyer_seller"] = SCORING_WEIGHTS["buyer_seller"]
            reasons.append({
                "rule": "buyer_seller",
                "label": _("Buyer/Seller Complementary"),
                "points": int(SCORING_WEIGHTS["buyer_seller"]),
                "matched_value": comp_label,
            })

        # ---------------------------------------------------------------------
        # 5. SAME COUNTRY (+5)
        # ---------------------------------------------------------------------
        src_country = self._extract_country(source_contact)
        tgt_country = self._extract_country(target_contact)

        if src_country and tgt_country and src_country == tgt_country:
            breakdown["country"] = SCORING_WEIGHTS["country"]
            country_display = target_contact.country_id.name if target_contact.country_id else src_country.upper()
            reasons.append({
                "rule": "country",
                "label": _("Same Country"),
                "points": int(SCORING_WEIGHTS["country"]),
                "matched_value": country_display,
            })

        # Total Calculation
        total_score = sum(breakdown.values())
        # Enforce max 95.0
        total_score = min(total_score, MAX_TOTAL_SCORE)

        # Ensure both 'category' and 'product_category' exist for convenience
        breakdown["category"] = breakdown["product_category"]

        # Supplementary Product Details (if present on target or source)
        supp_details = {}
        if hasattr(target_contact, "x_product_details") and target_contact.x_product_details:
            supp_details["target_product_details"] = target_contact.x_product_details.strip()
        if hasattr(source_contact, "x_product_details") and source_contact.x_product_details:
            supp_details["source_product_details"] = source_contact.x_product_details.strip()

        return {
            "score": total_score,
            "breakdown": breakdown,
            "reasons": reasons,
            "details": supp_details,
        }

    # -------------------------------------------------------------------------
    # TOP 10 RECOMMENDATION RETRIEVER
    # -------------------------------------------------------------------------
    @api.model
    def find_matching_contacts(self, source_contact, limit=10, min_score=0.0):
        """
        Analyzes all valid candidates in Odoo against source_contact,
        calculates scoring, sorts descending, and returns TOP matches.

        Sort order:
          1. score DESC
          2. name ASC (deterministic)
          3. id ASC (deterministic)

        :param source_contact: res.partner record
        :param limit: Maximum number of matches to return (default 10)
        :param min_score: Minimum score filter threshold (default 0.0)
        :return: List of dicts representing top matching candidates
        """
        if not source_contact:
            return []

        if isinstance(source_contact, (int, str)):
            source_contact = self.env["res.partner"].browse(int(source_contact))
        if not source_contact.exists():
            return []

        # Candidate selection domain: Exclude self, exclude archived
        domain = [
            ("id", "!=", source_contact.id),
            ("active", "=", True),
        ]

        # Prefetch candidates using ORM
        candidates = self.env["res.partner"].search(domain)
        _logger.info("[Matchmaking Service] Evaluating %d candidates for Contact #%d ('%s')...",
                     len(candidates), source_contact.id, source_contact.name)

        scored_candidates = []
        for cand in candidates:
            res = self.calculate_match_score(source_contact, cand)
            score = res["score"]
            if score >= min_score:
                scored_candidates.append({
                    "partner_id": cand.id,
                    "candidate_id": cand.id,
                    "name": cand.name or _("Unnamed Contact"),
                    "email": cand.email or "",
                    "phone": cand.phone or getattr(cand, "mobile", "") or "",
                    "country": cand.country_id.name if cand.country_id else getattr(cand, "x_country", "") or "",
                    "type_contact": getattr(cand, "x_type_contact", "") or "",
                    "score": score,
                    "breakdown": res["breakdown"],
                    "reasons": res["reasons"],
                    "details": res["details"],
                })

        # Deterministic sorting: score DESC, name ASC, candidate_id ASC
        scored_candidates.sort(
            key=lambda x: (-x["score"], (x["name"] or "").strip().lower(), x["candidate_id"])
        )

        # Slice Top N
        top_matches = scored_candidates[:limit]
        for idx, item in enumerate(top_matches, start=1):
            item["rank"] = idx

        _logger.info("[Matchmaking Service] Found %d matching candidates (Top %d selected) for #%d.",
                     len(scored_candidates), len(top_matches), source_contact.id)
        return top_matches
