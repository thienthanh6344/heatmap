# -*- coding: utf-8 -*-
"""
SGT Contact Match Making Model
Provides pairwise contact comparison, explainable scoring, difference analysis, and history tracking.
"""

import html
import json
import logging
import re
import unicodedata
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Configurable weights for scoring calculation (Sum of max = 100.0)
MATCH_WEIGHTS = {
    "name_max": 10.0,
    "name_exact": 10.0,
    "name_similar": 8.0,
    "name_partial": 5.0,
    "email_max": 25.0,
    "email_exact": 25.0,
    "email_domain": 10.0,
    "phone_max": 20.0,
    "phone_exact": 20.0,
    "phone_partial": 10.0,
    "company_max": 15.0,
    "company_exact": 15.0,
    "company_similar": 8.0,
    "position_max": 10.0,
    "position_exact": 10.0,
    "position_similar": 6.0,
    "industry_max": 10.0,
    "industry_exact": 10.0,
    "location_max": 5.0,
    "location_exact": 5.0,
    "location_partial": 3.0,
    "tag_max": 5.0,
    "tag_exact": 5.0,
}

GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "mail.com",
    "zoho.com",
    "protonmail.com",
    "aol.com",
}

COMPANY_NOISE_WORDS = [
    r"\bcông ty\b",
    r"\btnhh\b",
    r"\bjsc\b",
    r"\bcp\b",
    r"\bco\.",
    r"\bltd\b",
    r"\bcorp\b",
    r"\bcorporation\b",
    r"\binc\b",
    r"\btrading\b",
    r"\bgroup\b",
    r"\bholding\b",
    r"\benterprise\b",
    r"\bvietnam\b",
    r"\bviệt nam\b",
]


def remove_vietnamese_diacritics(text):
    """Normalize and strip Vietnamese diacritics for phonetic/loose comparison."""
    if not text:
        return ""
    text = str(text).strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFC", text).strip().lower()


def normalize_phone_number(phone):
    """Normalize phone number: remove non-digits and standardize country code prefix."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("84") and len(digits) >= 10:
        digits = "0" + digits[2:]
    return digits


def extract_email_domain(email):
    """Extract domain part of email address."""
    if not email or "@" not in email:
        return ""
    return email.strip().split("@")[-1].lower()


def tokenize_text(text):
    """Tokenize normalized words."""
    norm = remove_vietnamese_diacritics(text)
    return set(re.findall(r"\w+", norm))


def compute_jaccard_similarity(set_a, set_b):
    """Compute Jaccard similarity index between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return float(intersection) / float(union) if union > 0 else 0.0


class SgtContactMatch(models.Model):
    _name = "sgt.contact.match"
    _description = "SGT Contact Match History & Evaluation"
    _order = "score desc, matched_at desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("sgt.contact.match") or _("New Match"),
    )
    contact_a_id = fields.Many2one(
        "res.partner",
        string="Contact A",
        required=True,
        ondelete="cascade",
        index=True,
    )
    contact_b_id = fields.Many2one(
        "res.partner",
        string="Contact B",
        required=True,
        ondelete="cascade",
        index=True,
    )
    pair_key = fields.Char(
        string="Normalized Pair Key",
        compute="_compute_pair_key",
        store=True,
        index=True,
        help="Symmetric pair key min(a,b)_max(a,b) to prevent duplicated history",
    )
    score = fields.Float(
        string="Match Score (%)",
        digits=(5, 1),
        required=True,
        default=0.0,
        index=True,
    )
    match_level = fields.Selection(
        [
            ("very_high", "Very High Match (80-100%)"),
            ("high", "High Match (60-79%)"),
            ("medium", "Medium Match (40-59%)"),
            ("low", "Low Match (20-39%)"),
            ("very_low", "Very Low Match (0-19%)"),
        ],
        string="Match Level",
        compute="_compute_match_level",
        store=True,
        index=True,
    )
    # Breakdown scores
    name_score = fields.Float(string="Name Score", digits=(4, 1), default=0.0)
    email_score = fields.Float(string="Email Score", digits=(4, 1), default=0.0)
    phone_score = fields.Float(string="Phone Score", digits=(4, 1), default=0.0)
    company_score = fields.Float(string="Company Score", digits=(4, 1), default=0.0)
    position_score = fields.Float(string="Position Score", digits=(4, 1), default=0.0)
    industry_score = fields.Float(string="Industry Score", digits=(4, 1), default=0.0)
    location_score = fields.Float(string="Location Score", digits=(4, 1), default=0.0)
    tag_score = fields.Float(string="Tag Score", digits=(4, 1), default=0.0)

    # Detailed Explanations & HTML Dashboard
    reasons_json = fields.Text(string="Reasons JSON")
    reasons_text = fields.Text(string="Match Reasons (Text)")
    comparison_json = fields.Text(string="Comparison JSON")
    dashboard_html = fields.Html(string="Match Dashboard UI", sanitize=False)

    matched_by = fields.Many2one(
        "res.users",
        string="Matched By",
        default=lambda self: self.env.user,
        index=True,
    )
    matched_at = fields.Datetime(
        string="Matched Date",
        default=fields.Datetime.now,
        index=True,
    )
    notes = fields.Text(string="Notes")

    @api.depends("contact_a_id", "contact_b_id")
    def _compute_pair_key(self):
        for rec in self:
            if rec.contact_a_id and rec.contact_b_id:
                aid = rec.contact_a_id.id
                bid = rec.contact_b_id.id
                rec.pair_key = f"{min(aid, bid)}_{max(aid, bid)}"
            else:
                rec.pair_key = False

    @api.depends("score")
    def _compute_match_level(self):
        for rec in self:
            s = rec.score or 0.0
            if s >= 80.0:
                rec.match_level = "very_high"
            elif s >= 60.0:
                rec.match_level = "high"
            elif s >= 40.0:
                rec.match_level = "medium"
            elif s >= 20.0:
                rec.match_level = "low"
            else:
                rec.match_level = "very_low"

    @api.constrains("contact_a_id", "contact_b_id")
    def _check_different_contacts(self):
        for rec in self:
            if rec.contact_a_id and rec.contact_b_id and rec.contact_a_id == rec.contact_b_id:
                raise ValidationError(_("Please select two different contacts to perform match making."))

    # -------------------------------------------------------------------------
    # MATCHING ALGORITHM ENGINE
    # -------------------------------------------------------------------------
    @api.model
    def evaluate_contacts(self, partner_a, partner_b):
        """
        Calculates explainable matching score, breakdown, reasons, and comparison details.
        Returns a dict containing:
        - score: float (0.0 - 100.0)
        - match_level: selection string
        - breakdown: dict of scores
        - reasons: list of dicts [{'type': 'success'|'warning'|'info'|'danger', 'text': str}]
        - comparison: list of dicts [{'field': str, 'val_a': str, 'val_b': str, 'status': str, 'score': float}]
        - html_report: formatted modern HTML component
        """
        if not partner_a or not partner_b:
            raise UserError(_("Both Contact A and Contact B are required for matching."))
        if isinstance(partner_a, (int, str)):
            partner_a = self.env["res.partner"].browse(int(partner_a))
        if isinstance(partner_b, (int, str)):
            partner_b = self.env["res.partner"].browse(int(partner_b))
        if not partner_a.exists() or not partner_b.exists():
            raise UserError(_("One or both selected contacts do not exist."))
        if partner_a.id == partner_b.id:
            raise ValidationError(_("Please select two different contacts to compare."))

        breakdown = {
            "name": 0.0,
            "email": 0.0,
            "phone": 0.0,
            "company": 0.0,
            "position": 0.0,
            "industry": 0.0,
            "location": 0.0,
            "tag": 0.0,
        }
        reasons = []
        comparison = []

        # 1. NAME EVALUATION
        name_a = (partner_a.name or "").strip()
        name_b = (partner_b.name or "").strip()
        norm_name_a = remove_vietnamese_diacritics(name_a)
        norm_name_b = remove_vietnamese_diacritics(name_b)

        if not name_a or not name_b:
            n_status = "MISSING"
            breakdown["name"] = 0.0
            reasons.append({"type": "warning", "text": _("Contact name is missing on one or both records")})
        elif name_a.lower() == name_b.lower():
            n_status = "MATCH"
            breakdown["name"] = MATCH_WEIGHTS["name_exact"]
            reasons.append({"type": "success", "text": _("Exact matching full name: '%s'") % name_a})
        elif norm_name_a == norm_name_b:
            n_status = "SIMILAR"
            breakdown["name"] = MATCH_WEIGHTS["name_similar"]
            reasons.append({"type": "success", "text": _("Identical name with Vietnamese diacritic variation ('%s' vs '%s')") % (name_a, name_b)})
        else:
            tokens_a = tokenize_text(name_a)
            tokens_b = tokenize_text(name_b)
            jaccard = compute_jaccard_similarity(tokens_a, tokens_b)
            if jaccard >= 0.6:
                n_status = "SIMILAR"
                breakdown["name"] = MATCH_WEIGHTS["name_partial"]
                reasons.append({"type": "info", "text": _("High token similarity in contact names (overlap: %d%%)") % int(jaccard * 100)})
            else:
                n_status = "DIFFERENT"
                breakdown["name"] = 0.0

        comparison.append({
            "field": _("Full Name"),
            "val_a": name_a or "—",
            "val_b": name_b or "—",
            "status": n_status,
            "score": breakdown["name"],
            "max": MATCH_WEIGHTS["name_max"],
        })

        # 2. EMAIL EVALUATION
        email_a = (partner_a.email or "").strip().lower()
        email_b = (partner_b.email or "").strip().lower()

        if not email_a or not email_b:
            e_status = "MISSING"
            breakdown["email"] = 0.0
        elif email_a == email_b:
            e_status = "MATCH"
            breakdown["email"] = MATCH_WEIGHTS["email_exact"]
            reasons.append({"type": "success", "text": _("Identical primary email address: %s") % email_a})
        else:
            domain_a = extract_email_domain(email_a)
            domain_b = extract_email_domain(email_b)
            if domain_a and domain_a == domain_b and domain_a not in GENERIC_EMAIL_DOMAINS:
                e_status = "SIMILAR"
                breakdown["email"] = MATCH_WEIGHTS["email_domain"]
                reasons.append({"type": "success", "text": _("Same corporate email domain: @%s") % domain_a})
            else:
                e_status = "DIFFERENT"
                breakdown["email"] = 0.0
                reasons.append({"type": "warning", "text": _("Different email addresses (%s vs %s)") % (email_a, email_b)})

        comparison.append({
            "field": _("Email Address"),
            "val_a": email_a or "—",
            "val_b": email_b or "—",
            "status": e_status,
            "score": breakdown["email"],
            "max": MATCH_WEIGHTS["email_max"],
        })

        # 3. PHONE EVALUATION
        raw_phone_a = (partner_a.phone or partner_a.mobile or "").strip()
        raw_phone_b = (partner_b.phone or partner_b.mobile or "").strip()
        phone_a = normalize_phone_number(raw_phone_a)
        phone_b = normalize_phone_number(raw_phone_b)

        if not phone_a or not phone_b:
            p_status = "MISSING"
            breakdown["phone"] = 0.0
        elif phone_a == phone_b:
            p_status = "MATCH"
            breakdown["phone"] = MATCH_WEIGHTS["phone_exact"]
            reasons.append({"type": "success", "text": _("Identical normalized phone number: %s") % raw_phone_a})
        elif len(phone_a) >= 8 and len(phone_b) >= 8 and (phone_a[-8:] == phone_b[-8:]):
            p_status = "SIMILAR"
            breakdown["phone"] = MATCH_WEIGHTS["phone_partial"]
            reasons.append({"type": "info", "text": _("Matching telephone suffix digits (%s)") % phone_a[-8:]})
        else:
            p_status = "DIFFERENT"
            breakdown["phone"] = 0.0

        comparison.append({
            "field": _("Phone / Mobile"),
            "val_a": raw_phone_a or "—",
            "val_b": raw_phone_b or "—",
            "status": p_status,
            "score": breakdown["phone"],
            "max": MATCH_WEIGHTS["phone_max"],
        })

        # 4. COMPANY EVALUATION
        comp_a = (partner_a.parent_id.name or partner_a.commercial_company_name or "").strip()
        comp_b = (partner_b.parent_id.name or partner_b.commercial_company_name or "").strip()

        def clean_company_name(name):
            clean = remove_vietnamese_diacritics(name)
            for pattern in COMPANY_NOISE_WORDS:
                clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)
            return re.sub(r"\s+", " ", clean).strip()

        c_clean_a = clean_company_name(comp_a)
        c_clean_b = clean_company_name(comp_b)

        if not comp_a or not comp_b:
            c_status = "MISSING"
            breakdown["company"] = 0.0
        elif comp_a.lower() == comp_b.lower() or (partner_a.parent_id and partner_a.parent_id == partner_b.parent_id):
            c_status = "MATCH"
            breakdown["company"] = MATCH_WEIGHTS["company_exact"]
            reasons.append({"type": "success", "text": _("Associated with the exact same company: '%s'") % comp_a})
        elif c_clean_a and c_clean_b and (c_clean_a == c_clean_b or compute_jaccard_similarity(set(c_clean_a.split()), set(c_clean_b.split())) >= 0.6):
            c_status = "SIMILAR"
            breakdown["company"] = MATCH_WEIGHTS["company_similar"]
            reasons.append({"type": "success", "text": _("Similar organization names: '%s' and '%s'") % (comp_a, comp_b)})
        else:
            c_status = "DIFFERENT"
            breakdown["company"] = 0.0
            reasons.append({"type": "warning", "text": _("Different associated companies")})

        comparison.append({
            "field": _("Company"),
            "val_a": comp_a or "—",
            "val_b": comp_b or "—",
            "status": c_status,
            "score": breakdown["company"],
            "max": MATCH_WEIGHTS["company_max"],
        })

        # 5. JOB POSITION EVALUATION
        pos_a = (partner_a.function or "").strip()
        pos_b = (partner_b.function or "").strip()
        norm_pos_a = remove_vietnamese_diacritics(pos_a)
        norm_pos_b = remove_vietnamese_diacritics(pos_b)

        words_a = [w for w in norm_pos_a.lower().split() if len(w) > 2]
        words_b = [w for w in norm_pos_b.lower().split() if len(w) > 2]
        shared_pos_words = set(words_a).intersection(set(words_b))
        jaccard_pos = compute_jaccard_similarity(set(norm_pos_a.split()), set(norm_pos_b.split())) if norm_pos_a and norm_pos_b else 0.0

        if not pos_a or not pos_b:
            pos_status = "MISSING"
            breakdown["position"] = 0.0
        elif pos_a.lower() == pos_b.lower():
            pos_status = "MATCH"
            breakdown["position"] = MATCH_WEIGHTS["position_exact"]
            reasons.append({"type": "success", "text": _("Identical job position: '%s'") % pos_a})
        elif jaccard_pos >= 0.3 or shared_pos_words:
            pos_status = "SIMILAR"
            breakdown["position"] = MATCH_WEIGHTS["position_similar"]
            reasons.append({"type": "info", "text": _("Similar job title/role: '%s' vs '%s'") % (pos_a, pos_b)})
        else:
            pos_status = "DIFFERENT"
            breakdown["position"] = 0.0

        comparison.append({
            "field": _("Job Position"),
            "val_a": pos_a or "—",
            "val_b": pos_b or "—",
            "status": pos_status,
            "score": breakdown["position"],
            "max": MATCH_WEIGHTS["position_max"],
        })

        # 6. INDUSTRY EVALUATION
        ind_a = partner_a.industry_id.name if partner_a.industry_id else ""
        ind_b = partner_b.industry_id.name if partner_b.industry_id else ""

        if not ind_a or not ind_b:
            ind_status = "MISSING"
            breakdown["industry"] = 0.0
        elif ind_a.lower() == ind_b.lower() or partner_a.industry_id == partner_b.industry_id:
            ind_status = "MATCH"
            breakdown["industry"] = MATCH_WEIGHTS["industry_exact"]
            reasons.append({"type": "success", "text": _("Same business industry: '%s'") % ind_a})
        else:
            ind_status = "DIFFERENT"
            breakdown["industry"] = 0.0

        comparison.append({
            "field": _("Industry"),
            "val_a": ind_a or "—",
            "val_b": ind_b or "—",
            "status": ind_status,
            "score": breakdown["industry"],
            "max": MATCH_WEIGHTS["industry_max"],
        })

        # 7. LOCATION EVALUATION (Country, State, City)
        country_a = partner_a.country_id.name if partner_a.country_id else ""
        country_b = partner_b.country_id.name if partner_b.country_id else ""
        city_a = (partner_a.city or "").strip()
        city_b = (partner_b.city or "").strip()

        loc_desc_a = ", ".join(filter(None, [city_a, country_a]))
        loc_desc_b = ", ".join(filter(None, [city_b, country_b]))

        norm_city_a = remove_vietnamese_diacritics(city_a)
        norm_city_b = remove_vietnamese_diacritics(city_b)
        same_country = bool(country_a and country_b and country_a.lower() == country_b.lower())
        same_city = bool(norm_city_a and norm_city_b and norm_city_a.lower() == norm_city_b.lower())

        if not loc_desc_a or not loc_desc_b:
            loc_status = "MISSING"
            breakdown["location"] = 0.0
        elif (same_country and same_city) or (same_city and (not country_a or not country_b or country_a == country_b)):
            loc_status = "MATCH"
            breakdown["location"] = MATCH_WEIGHTS["location_exact"]
            reasons.append({"type": "success", "text": _("Identical geographic location: %s") % loc_desc_a})
        elif same_country or same_city:
            loc_status = "SIMILAR"
            breakdown["location"] = MATCH_WEIGHTS["location_partial"]
            reasons.append({"type": "info", "text": _("Same region or country: %s") % (country_a or city_a)})
        else:
            loc_status = "DIFFERENT"
            breakdown["location"] = 0.0
            reasons.append({"type": "warning", "text": _("Different locations (%s vs %s)") % (loc_desc_a, loc_desc_b)})

        comparison.append({
            "field": _("Location"),
            "val_a": loc_desc_a or "—",
            "val_b": loc_desc_b or "—",
            "status": loc_status,
            "score": breakdown["location"],
            "max": MATCH_WEIGHTS["location_max"],
        })

        # 8. TAGS / CATEGORIES EVALUATION
        tags_a = set(partner_a.category_id.mapped("name"))
        tags_b = set(partner_b.category_id.mapped("name"))
        common_tags = tags_a.intersection(tags_b)

        tag_str_a = ", ".join(tags_a) if tags_a else ""
        tag_str_b = ", ".join(tags_b) if tags_b else ""

        if not tags_a or not tags_b:
            tag_status = "MISSING"
            breakdown["tag"] = 0.0
        elif tags_a == tags_b:
            tag_status = "MATCH"
            breakdown["tag"] = MATCH_WEIGHTS["tag_exact"]
            reasons.append({"type": "success", "text": _("Identical contact tags: %s") % ", ".join(common_tags)})
        elif common_tags:
            tag_status = "SIMILAR"
            breakdown["tag"] = round(min(MATCH_WEIGHTS["tag_max"], len(common_tags) * 2.5), 1)
            reasons.append({"type": "success", "text": _("Shared contact tags: %s") % ", ".join(common_tags)})
        else:
            tag_status = "DIFFERENT"
            breakdown["tag"] = 0.0

        comparison.append({
            "field": _("Tags / Categories"),
            "val_a": tag_str_a or "—",
            "val_b": tag_str_b or "—",
            "status": tag_status,
            "score": breakdown["tag"],
            "max": MATCH_WEIGHTS["tag_max"],
        })

        # Total Raw Score
        raw_total = sum(breakdown.values())
        final_score = min(100.0, max(0.0, round(raw_total, 1)))

        # Level determination
        if final_score >= 80.0:
            level = "very_high"
            level_label = _("VERY HIGH MATCH")
            level_color = "#10b981"  # Emerald
            badge_class = "success"
        elif final_score >= 60.0:
            level = "high"
            level_label = _("HIGH MATCH")
            level_color = "#2563eb"  # Blue
            badge_class = "info"
        elif final_score >= 40.0:
            level = "medium"
            level_label = _("MEDIUM MATCH")
            level_color = "#f59e0b"  # Amber
            badge_class = "warning"
        elif final_score >= 20.0:
            level = "low"
            level_label = _("LOW MATCH")
            level_color = "#f97316"  # Orange
            badge_class = "danger"
        else:
            level = "very_low"
            level_label = _("VERY LOW MATCH")
            level_color = "#ef4444"  # Red
            badge_class = "danger"

        # Generate Rich Dashboard HTML
        html_report = self._generate_dashboard_html(
            partner_a=partner_a,
            partner_b=partner_b,
            score=final_score,
            level=level,
            level_label=level_label,
            level_color=level_color,
            breakdown=breakdown,
            reasons=reasons,
            comparison=comparison,
        )

        return {
            "score": final_score,
            "match_level": level,
            "match_level_label": level_label,
            "badge_class": badge_class,
            "breakdown": breakdown,
            "reasons": reasons,
            "comparison": comparison,
            "html_report": html_report,
        }

    # -------------------------------------------------------------------------
    # HTML DASHBOARD GENERATOR (Modern Business CRM Dashboard Style)
    # -------------------------------------------------------------------------
    @api.model
    def _generate_dashboard_html(self, partner_a, partner_b, score, level, level_label, level_color, breakdown, reasons, comparison):
        """Generates modern, responsive, and beautiful HTML presentation for Match Results."""
        
        # Initials for avatar
        def get_initials(name):
            parts = (name or "").strip().split()
            if not parts:
                return "C"
            if len(parts) == 1:
                return parts[0][:2].upper()
            return (parts[0][0] + parts[-1][0]).upper()

        init_a = html.escape(get_initials(partner_a.name))
        init_b = html.escape(get_initials(partner_b.name))
        name_a_esc = html.escape(partner_a.name or _("Unknown"))
        name_b_esc = html.escape(partner_b.name or _("Unknown"))
        comp_a_esc = html.escape(partner_a.parent_id.name or partner_a.commercial_company_name or "—")
        comp_b_esc = html.escape(partner_b.parent_id.name or partner_b.commercial_company_name or "—")
        pos_a_esc = html.escape(partner_a.function or "—")
        pos_b_esc = html.escape(partner_b.function or "—")
        email_a_esc = html.escape(partner_a.email or "—")
        email_b_esc = html.escape(partner_b.email or "—")
        phone_a_esc = html.escape(partner_a.phone or partner_a.mobile or "—")
        phone_b_esc = html.escape(partner_b.phone or partner_b.mobile or "—")

        # Circular Gauge SVG Calculation
        radius = 54
        circumference = 2 * 3.14159 * radius
        dashoffset = circumference - (score / 100.0) * circumference

        # Reasons HTML
        reasons_items = ""
        for r in reasons:
            t = r.get("type", "info")
            txt = html.escape(r.get("text", ""))
            if t == "success":
                icon = '<span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#dcfce7;color:#16a34a;margin-right:10px;font-weight:bold;">✓</span>'
                bg_item = "background:#f8fafc;border-left:4px solid #16a34a;"
            elif t == "warning":
                icon = '<span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#fef3c7;color:#d97706;margin-right:10px;font-weight:bold;">⚠</span>'
                bg_item = "background:#f8fafc;border-left:4px solid #f59e0b;"
            else:
                icon = '<span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#e0f2fe;color:#0284c7;margin-right:10px;font-weight:bold;">ℹ</span>'
                bg_item = "background:#f8fafc;border-left:4px solid #0284c7;"
            
            reasons_items += f"""
            <div style="padding:10px 14px;border-radius:6px;margin-bottom:8px;font-size:13.5px;color:#334155;display:flex;align-items:center;{bg_item}">
                {icon}
                <span>{txt}</span>
            </div>
            """

        # Comparison Table Rows
        table_rows = ""
        badge_styles = {
            "MATCH": "background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;",
            "SIMILAR": "background:#dbeafe;color:#1d4ed8;border:1px solid #bfdbfe;",
            "DIFFERENT": "background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;",
            "MISSING": "background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0;",
        }

        for row in comparison:
            f_name = html.escape(row.get("field", ""))
            v_a = html.escape(str(row.get("val_a", "—")))
            v_b = html.escape(str(row.get("val_b", "—")))
            st = row.get("status", "DIFFERENT")
            pts = row.get("score", 0.0)
            max_pts = row.get("max", 0.0)
            b_style = badge_styles.get(st, badge_styles["DIFFERENT"])
            pts_color = level_color if pts > 0 else "#94a3b8"

            table_rows += f"""
            <tr style="border-bottom:1px solid #f1f5f9;transition:background 0.2s;">
                <td style="padding:12px 14px;font-weight:600;color:#1e293b;font-size:13px;">{f_name}</td>
                <td style="padding:12px 14px;color:#475569;font-size:13px;word-break:break-word;">{v_a}</td>
                <td style="padding:12px 14px;color:#475569;font-size:13px;word-break:break-word;">{v_b}</td>
                <td style="padding:12px 14px;text-align:center;">
                    <span style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;letter-spacing:0.5px;{b_style}">
                        {st}
                    </span>
                </td>
                <td style="padding:12px 14px;text-align:right;font-weight:600;font-size:12.5px;color:#334155;">
                    <span style="color:{pts_color};">{pts:.1f}</span>
                    <span style="color:#94a3b8;font-size:11px;">/{max_pts:.0f}</span>
                </td>
            </tr>
            """

        # Breakdown criteria bars
        def render_bar(label, val, max_val, color="#2563eb"):
            pct = min(100.0, (val / max_val * 100.0)) if max_val > 0 else 0.0
            return f"""
            <div style="margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:12.5px;">
                    <span style="color:#475569;font-weight:500;">{label}</span>
                    <span style="font-weight:700;color:#1e293b;">{val:.1f} <span style="color:#94a3b8;font-weight:normal;">/ {max_val:.0f}</span></span>
                </div>
                <div style="height:7px;background:#e2e8f0;border-radius:4px;overflow:hidden;">
                    <div style="height:100%;width:{pct}%;background:{color};border-radius:4px;transition:width 0.6s ease;"></div>
                </div>
            </div>
            """

        bars_html = f"""
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(210px, 1fr));gap:12px 24px;">
            <div>
                {render_bar(_("Email Similarity"), breakdown.get("email", 0), MATCH_WEIGHTS["email_max"], "#2563eb")}
                {render_bar(_("Phone Similarity"), breakdown.get("phone", 0), MATCH_WEIGHTS["phone_max"], "#0284c7")}
                {render_bar(_("Company Entity"), breakdown.get("company", 0), MATCH_WEIGHTS["company_max"], "#0d9488")}
                {render_bar(_("Full Name Similarity"), breakdown.get("name", 0), MATCH_WEIGHTS["name_max"], "#4f46e5")}
            </div>
            <div>
                {render_bar(_("Job Position"), breakdown.get("position", 0), MATCH_WEIGHTS["position_max"], "#7c3aed")}
                {render_bar(_("Industry Classification"), breakdown.get("industry", 0), MATCH_WEIGHTS["industry_max"], "#9333ea")}
                {render_bar(_("Location (Country/City)"), breakdown.get("location", 0), MATCH_WEIGHTS["location_max"], "#db2777")}
                {render_bar(_("Contact Tags Overlap"), breakdown.get("tag", 0), MATCH_WEIGHTS["tag_max"], "#e11d48")}
            </div>
        </div>
        """

        # Full container assembly
        res_html = f"""
        <div class="sgt-match-dashboard" style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background:#f8fafc; padding:20px; border-radius:12px; border:1px solid #e2e8f0; margin-top:16px;">
            
            <!-- SECTION 1: SIDE-BY-SIDE CONTACT CARDS -->
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px;">
                
                <!-- CONTACT A CARD -->
                <div style="background:#ffffff; border-radius:10px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.05); padding:18px; position:relative; overflow:hidden;">
                    <div style="position:absolute;top:0;left:0;right:0;height:4px;background:#2563eb;"></div>
                    <div style="display:flex;align-items:center;margin-bottom:12px;">
                        <div style="width:44px;height:44px;border-radius:10px;background:#eff6ff;color:#2563eb;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;margin-right:12px;border:1px solid #bfdbfe;">
                            {init_a}
                        </div>
                        <div>
                            <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#2563eb;">CONTACT A</span>
                            <h3 style="margin:2px 0 0 0;font-size:17px;font-weight:700;color:#0f172a;">{name_a_esc}</h3>
                        </div>
                    </div>
                    <div style="font-size:13px;color:#475569;line-height:1.6;border-top:1px solid #f1f5f9;padding-top:10px;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <span style="color:#64748b;">{_('Company')}:</span>
                            <strong style="color:#1e293b;">{comp_a_esc}</strong>
                        </div>
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <span style="color:#64748b;">{_('Job Position')}:</span>
                            <span style="color:#334155;">{pos_a_esc}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <span style="color:#64748b;">{_('Email')}:</span>
                            <span style="color:#334155;">{email_a_esc}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#64748b;">{_('Phone')}:</span>
                            <span style="color:#334155;">{phone_a_esc}</span>
                        </div>
                    </div>
                </div>

                <!-- CONTACT B CARD -->
                <div style="background:#ffffff; border-radius:10px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.05); padding:18px; position:relative; overflow:hidden;">
                    <div style="position:absolute;top:0;left:0;right:0;height:4px;background:#0d9488;"></div>
                    <div style="display:flex;align-items:center;margin-bottom:12px;">
                        <div style="width:44px;height:44px;border-radius:10px;background:#f0fdfa;color:#0d9488;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;margin-right:12px;border:1px solid #99f6e4;">
                            {init_b}
                        </div>
                        <div>
                            <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#0d9488;">CONTACT B</span>
                            <h3 style="margin:2px 0 0 0;font-size:17px;font-weight:700;color:#0f172a;">{name_b_esc}</h3>
                        </div>
                    </div>
                    <div style="font-size:13px;color:#475569;line-height:1.6;border-top:1px solid #f1f5f9;padding-top:10px;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <span style="color:#64748b;">{_('Company')}:</span>
                            <strong style="color:#1e293b;">{comp_b_esc}</strong>
                        </div>
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <span style="color:#64748b;">{_('Job Position')}:</span>
                            <span style="color:#334155;">{pos_b_esc}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <span style="color:#64748b;">{_('Email')}:</span>
                            <span style="color:#334155;">{email_b_esc}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#64748b;">{_('Phone')}:</span>
                            <span style="color:#334155;">{phone_b_esc}</span>
                        </div>
                    </div>
                </div>

            </div>

            <!-- SECTION 2: MATCH SCORE & BREAKDOWN HERO CARD -->
            <div style="background:#ffffff; border-radius:10px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.05); padding:24px; margin-bottom:24px;">
                <div style="display:grid; grid-template-columns:auto 1fr; gap:32px; align-items:center;">
                    
                    <!-- Circular Score Gauge -->
                    <div style="text-align:center; min-width:180px;">
                        <div style="position:relative; width:140px; height:140px; margin:0 auto;">
                            <svg width="140" height="140" viewBox="0 0 140 140">
                                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="#e2e8f0" stroke-width="12" />
                                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="{level_color}" stroke-width="12"
                                        stroke-linecap="round" stroke-dasharray="{circumference}" stroke-dashoffset="{dashoffset}"
                                        transform="rotate(-90 70 70)" style="transition:stroke-dashoffset 1s ease;" />
                            </svg>
                            <div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                                <span style="font-size:32px; font-weight:800; color:#0f172a; line-height:1;">{score:.0f}<span style="font-size:18px;font-weight:600;">%</span></span>
                                <span style="font-size:11px; font-weight:700; color:#64748b; margin-top:2px;">{_('MATCH SCORE')}</span>
                            </div>
                        </div>
                        <div style="margin-top:12px;">
                            <span style="display:inline-block; padding:4px 14px; border-radius:20px; font-size:12px; font-weight:700; color:#ffffff; background:{level_color}; letter-spacing:0.5px;">
                                {level_label}
                            </span>
                        </div>
                    </div>

                    <!-- Breakdown Progress Bars -->
                    <div style="border-left:1px solid #f1f5f9; padding-left:24px;">
                        <h4 style="margin:0 0 16px 0; font-size:15px; font-weight:700; color:#1e293b;">
                            {_('Weighted Scoring Criteria Breakdown')}
                        </h4>
                        {bars_html}
                    </div>

                </div>
            </div>

            <!-- SECTION 3: MATCH REASONS (EXPLAINABILITY) -->
            <div style="background:#ffffff; border-radius:10px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.05); padding:20px; margin-bottom:24px;">
                <h4 style="margin:0 0 14px 0; font-size:15px; font-weight:700; color:#1e293b; display:flex; align-items:center;">
                    <i class="fa fa-info-circle" style="color:#2563eb; margin-right:8px;"></i>
                    {_('Why are these contacts matched?')}
                </h4>
                <div style="margin-top:8px;">
                    {reasons_items}
                </div>
            </div>

            <!-- SECTION 4: DIFFERENCE VIEW (COMPARISON DETAILS TABLE) -->
            <div style="background:#ffffff; border-radius:10px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.05); overflow:hidden;">
                <div style="padding:16px 20px; border-bottom:1px solid #e2e8f0; background:#f8fafc;">
                    <h4 style="margin:0; font-size:15px; font-weight:700; color:#1e293b; display:flex; align-items:center;">
                        <i class="fa fa-exchange" style="color:#0284c7; margin-right:8px;"></i>
                        {_('Comparison Details (Difference View)')}
                    </h4>
                </div>
                <div style="overflow-x:auto;">
                    <table style="width:100%; border-collapse:collapse; text-align:left;">
                        <thead>
                            <tr style="background:#f8fafc; border-bottom:2px solid #e2e8f0;">
                                <th style="padding:10px 14px; font-size:12px; font-weight:700; color:#475569; text-transform:uppercase;">{_('Field')}</th>
                                <th style="padding:10px 14px; font-size:12px; font-weight:700; color:#475569; text-transform:uppercase;">{_('Contact A')}</th>
                                <th style="padding:10px 14px; font-size:12px; font-weight:700; color:#475569; text-transform:uppercase;">{_('Contact B')}</th>
                                <th style="padding:10px 14px; font-size:12px; font-weight:700; color:#475569; text-transform:uppercase; text-align:center;">{_('Result')}</th>
                                <th style="padding:10px 14px; font-size:12px; font-weight:700; color:#475569; text-transform:uppercase; text-align:right;">{_('Score')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
        """
        return res_html

    # -------------------------------------------------------------------------
    # RECORD ACTIONS
    # -------------------------------------------------------------------------
    def action_recalculate(self):
        """Recalculate match score based on current partner data."""
        for rec in self:
            eval_res = self.evaluate_contacts(rec.contact_a_id, rec.contact_b_id)
            rec.write({
                "score": eval_res["score"],
                "name_score": eval_res["breakdown"]["name"],
                "email_score": eval_res["breakdown"]["email"],
                "phone_score": eval_res["breakdown"]["phone"],
                "company_score": eval_res["breakdown"]["company"],
                "position_score": eval_res["breakdown"]["position"],
                "industry_score": eval_res["breakdown"]["industry"],
                "location_score": eval_res["breakdown"]["location"],
                "tag_score": eval_res["breakdown"]["tag"],
                "reasons_json": json.dumps(eval_res["reasons"], ensure_ascii=False),
                "reasons_text": "\n".join([r["text"] for r in eval_res["reasons"]]),
                "comparison_json": json.dumps(eval_res["comparison"], ensure_ascii=False),
                "dashboard_html": eval_res["html_report"],
                "matched_at": fields.Datetime.now(),
            })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Match Recalculated"),
                "message": _("Match score and comparison details have been updated successfully."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_contact_a(self):
        self.ensure_one()
        return {
            "name": _("Contact A"),
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.contact_a_id.id,
            "target": "current",
        }

    def action_open_contact_b(self):
        self.ensure_one()
        return {
            "name": _("Contact B"),
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.contact_b_id.id,
            "target": "current",
        }
