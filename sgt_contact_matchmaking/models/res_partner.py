# -*- coding: utf-8 -*-
"""
Extension for res.partner model to support Contact Match Making & Recommendations (Task 19 & 20).
Provides smart buttons, matchmaking profile fields, and Find Matching Companies action.
"""

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Task 19 Pairwise Match Counter
    match_count = fields.Integer(
        string="Matches",
        compute="_compute_match_count",
        help="Number of pairwise comparisons involving this contact",
    )

    # Task 20 Matchmaking Profile Fields
    x_type_contact = fields.Selection(
        [
            ("buyer", "Buyer"),
            ("seller", "Seller"),
            ("both", "Buyer & Seller (Flexible)"),
        ],
        string="Contact Role / Type",
        help="Business matchmaking role: Buyer, Seller, or Both",
        index=True,
    )
    x_product_category = fields.Char(
        string="Product Category",
        help="Comma-separated product categories (e.g. Electronics, Software)",
        index=True,
    )
    x_product_details = fields.Text(
        string="Product Details",
        help="Detailed product specifications, catalogue, or capabilities for matchmaking",
    )
    x_event = fields.Char(
        string="Participating Events",
        help="Trade fairs, expos, conferences (e.g. Vietnam Expo 2026, Saigon Tech Fair)",
        index=True,
    )
    x_fb_industry = fields.Char(
        string="FB Industry",
        help="Industry classification or category tag",
        index=True,
    )

    # Project Association (Each major project includes many contacts)
    project_ids = fields.Many2many(
        "sgt.project.heatmap",
        "sgt_project_partner_rel",
        "partner_id",
        "project_id",
        string="Associated Projects",
        help="Major projects this contact is affiliated with (e.g. Gearea, Argo, YingBo)",
    )
    contact_province = fields.Char(
        string="Province / City",
        index=True,
        help="Vietnamese Province/City for Project Heatmap analytics",
    )
    contact_district = fields.Char(
        string="District / County",
        index=True,
        help="District for Project Heatmap analytics",
    )
    contact_ward = fields.Char(
        string="Ward / Commune",
        index=True,
        help="Ward or Commune for Project Heatmap analytics",
    )
    location_source = fields.Selection(
        [
            ("goong", "Goong Geocoding"),
            ("manual", "Manual Input"),
            ("import", "Imported Data"),
        ],
        string="Location Source",
        default="manual",
        help="Identifies whether location was resolved via Goong API, manual input, or import",
    )
    geocoded_at = fields.Datetime(
        string="Geocoded At",
        help="Timestamp of last geocoding resolution",
    )
    contact_has_coordinates = fields.Boolean(
        string="Has GPS Coordinates",
        compute="_compute_contact_has_coordinates",
        store=True,
        index=True,
    )

    @api.depends("partner_latitude", "partner_longitude")
    def _compute_contact_has_coordinates(self):
        for partner in self:
            lat = partner.partner_latitude
            lng = partner.partner_longitude
            partner.contact_has_coordinates = bool(
                lat and lng and
                -90.0 <= lat <= 90.0 and
                -180.0 <= lng <= 180.0 and
                not (lat == 0.0 and lng == 0.0)
            )

    def _compute_match_count(self):
        MatchModel = self.env["sgt.contact.match"]
        for partner in self:
            if not partner.id:
                partner.match_count = 0
                continue
            partner.match_count = MatchModel.search_count([
                "|",
                ("contact_a_id", "=", partner.id),
                ("contact_b_id", "=", partner.id),
            ])

    def action_view_matches(self):
        """Open pairwise match records involving this contact (Task 19)."""
        self.ensure_one()
        return {
            "name": _("Match Contacts (%s)") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "sgt.contact.match",
            "view_mode": "list,form,graph",
            "domain": [
                "|",
                ("contact_a_id", "=", self.id),
                ("contact_b_id", "=", self.id),
            ],
            "context": {
                "default_contact_a_id": self.id,
            },
        }

    def action_start_match_making(self):
        """Open the Pairwise Match Making wizard pre-filling this contact as Contact A (Task 19)."""
        self.ensure_one()
        wizard = self.env["sgt.contact.match.wizard"].create({
            "contact_a_id": self.id,
        })
        return {
            "name": _("Contact Match Making"),
            "type": "ir.actions.act_window",
            "res_model": "sgt.contact.match.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_find_matching_companies(self):
        """
        Task 20: Matchmaking Recommendation Action.
        Analyzes this contact's profile and proposes TOP 10 matching companies/contacts.
        """
        self.ensure_one()
        wizard = self.env["sgt.matchmaking.recommendation.wizard"].create({
            "source_partner_id": self.id,
            "limit": 10,
            "min_score": 0.0,
        })
        # Calculate recommendations right away
        wizard.action_calculate_recommendations()

        return {
            "name": _("Find Matching Companies for %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "sgt.matchmaking.recommendation.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    def action_reverse_geocode_goong(self):
        """
        Reverse geocodes coordinates to populate missing Ward, District, Province
        using Goong API and caches the result on the partner record.
        """
        for partner in self:
            if not partner.contact_has_coordinates:
                continue
            if partner.contact_province and partner.contact_district and partner.contact_ward:
                continue
            res = self.env["sgt.goong.service"].reverse_geocode(
                partner.partner_latitude, partner.partner_longitude
            )
            if res.get("status") == "success":
                vals = {
                    "location_source": "goong",
                    "geocoded_at": fields.Datetime.now(),
                }
                if not partner.contact_province and res.get("province"):
                    vals["contact_province"] = res["province"]
                if not partner.contact_district and res.get("district"):
                    vals["contact_district"] = res["district"]
                if not partner.contact_ward and res.get("ward"):
                    vals["contact_ward"] = res["ward"]
                partner.write(vals)
        return True
