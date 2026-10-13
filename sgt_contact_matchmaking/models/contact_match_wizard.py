# -*- coding: utf-8 -*-
"""
Interactive Contact Match Making Wizard
Allows interactive selection of Contact A and Contact B, instant scoring, visual breakdown, and persistent saving.
"""

import json
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SgtContactMatchWizard(models.TransientModel):
    _name = "sgt.contact.match.wizard"
    _description = "Contact Match Making Interactive Tool"

    contact_a_id = fields.Many2one(
        "res.partner",
        string="Contact A",
        required=True,
        help="Primary contact to evaluate",
    )
    contact_b_id = fields.Many2one(
        "res.partner",
        string="Contact B",
        help="Secondary contact to compare against Contact A",
    )
    has_result = fields.Boolean(
        string="Has Match Result",
        default=False,
    )
    score = fields.Float(
        string="Match Score (%)",
        digits=(5, 1),
        readonly=True,
    )
    match_level = fields.Selection(
        [
            ("very_high", "Very High Match"),
            ("high", "High Match"),
            ("medium", "Medium Match"),
            ("low", "Low Match"),
            ("very_low", "Very Low Match"),
        ],
        string="Match Level",
        readonly=True,
    )
    match_level_label = fields.Char(string="Level Label", readonly=True)
    badge_class = fields.Char(string="Badge Class", readonly=True)

    name_score = fields.Float(string="Name Score", readonly=True)
    email_score = fields.Float(string="Email Score", readonly=True)
    phone_score = fields.Float(string="Phone Score", readonly=True)
    company_score = fields.Float(string="Company Score", readonly=True)
    position_score = fields.Float(string="Position Score", readonly=True)
    industry_score = fields.Float(string="Industry Score", readonly=True)
    location_score = fields.Float(string="Location Score", readonly=True)
    tag_score = fields.Float(string="Tag Score", readonly=True)

    result_html = fields.Html(
        string="Interactive Match Dashboard",
        readonly=True,
        sanitize=False,
    )
    saved_match_id = fields.Many2one(
        "sgt.contact.match",
        string="Saved Match Record",
        readonly=True,
    )

    @api.onchange("contact_a_id", "contact_b_id")
    def _onchange_contacts(self):
        if self.contact_a_id and self.contact_b_id and self.contact_a_id == self.contact_b_id:
            self.contact_b_id = False
            return {
                "warning": {
                    "title": _("Invalid Selection"),
                    "message": _("Please select two different contacts to compare."),
                }
            }
        # Reset result if contacts change
        self.has_result = False
        self.result_html = False

    def action_compare_and_match(self):
        """Perform match calculation, generate dashboard, and persist match record in database."""
        self.ensure_one()
        if not self.contact_a_id or not self.contact_b_id:
            raise UserError(_("Please select both Contact A and Contact B before comparing."))

        if self.contact_a_id.id == self.contact_b_id.id:
            raise ValidationError(_("Please select two different contacts to compare."))

        MatchModel = self.env["sgt.contact.match"]
        eval_res = MatchModel.evaluate_contacts(self.contact_a_id, self.contact_b_id)

        # Symmetric pair key: min(a,b)_max(a,b)
        aid = self.contact_a_id.id
        bid = self.contact_b_id.id
        pair_key = f"{min(aid, bid)}_{max(aid, bid)}"

        # Find existing match record to avoid duplicates
        existing_match = MatchModel.search([("pair_key", "=", pair_key)], limit=1)
        match_vals = {
            "contact_a_id": self.contact_a_id.id,
            "contact_b_id": self.contact_b_id.id,
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
            "matched_by": self.env.user.id,
            "matched_at": fields.Datetime.now(),
        }

        if existing_match:
            existing_match.write(match_vals)
            saved_record = existing_match
        else:
            saved_record = MatchModel.create(match_vals)

        self.write({
            "has_result": True,
            "score": eval_res["score"],
            "match_level": eval_res["match_level"],
            "match_level_label": eval_res["match_level_label"],
            "badge_class": eval_res["badge_class"],
            "name_score": eval_res["breakdown"]["name"],
            "email_score": eval_res["breakdown"]["email"],
            "phone_score": eval_res["breakdown"]["phone"],
            "company_score": eval_res["breakdown"]["company"],
            "position_score": eval_res["breakdown"]["position"],
            "industry_score": eval_res["breakdown"]["industry"],
            "location_score": eval_res["breakdown"]["location"],
            "tag_score": eval_res["breakdown"]["tag"],
            "result_html": eval_res["html_report"],
            "saved_match_id": saved_record.id,
        })

        # Reopen wizard view with populated dashboard
        return {
            "type": "ir.actions.act_window",
            "name": _("Contact Match Making"),
            "res_model": "sgt.contact.match.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_history_record(self):
        """Open the saved persistent match record."""
        self.ensure_one()
        if not self.saved_match_id:
            raise UserError(_("No match history record found yet. Please click 'Compare & Match' first."))
        return {
            "name": _("Match History - %s") % self.saved_match_id.name,
            "type": "ir.actions.act_window",
            "res_model": "sgt.contact.match",
            "res_id": self.saved_match_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_reset(self):
        """Reset wizard to compare new contacts."""
        self.ensure_one()
        self.write({
            "contact_b_id": False,
            "has_result": False,
            "score": 0.0,
            "match_level": False,
            "result_html": False,
            "saved_match_id": False,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Contact Match Making"),
            "res_model": "sgt.contact.match.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
