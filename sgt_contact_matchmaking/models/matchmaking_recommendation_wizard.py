# -*- coding: utf-8 -*-
"""
SGT Matchmaking Recommendation Wizard (Task 20)
Presents the Top 10 matching companies in a modern CRM card dashboard layout.
"""

import html
import json
import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SgtMatchmakingRecommendationWizard(models.TransientModel):
    _name = "sgt.matchmaking.recommendation.wizard"
    _description = "Matchmaking Recommendation Wizard (Top 10)"

    source_partner_id = fields.Many2one(
        "res.partner",
        string="Source Contact / Company",
        required=True,
        readonly=True,
    )
    limit = fields.Integer(
        string="Limit",
        default=10,
        required=True,
    )
    min_score = fields.Float(
        string="Minimum Score",
        default=0.0,
    )
    total_candidates = fields.Integer(
        string="Total Candidates Analyzed",
        readonly=True,
    )
    total_matches = fields.Integer(
        string="Total Matches Found",
        readonly=True,
    )
    max_score = fields.Float(
        string="Highest Match Score",
        digits=(4, 1),
        readonly=True,
    )
    line_ids = fields.One2many(
        "sgt.matchmaking.recommendation.wizard.line",
        "wizard_id",
        string="Top Matches",
        readonly=True,
    )
    html_dashboard = fields.Html(
        string="Matchmaking Recommendation Dashboard",
        sanitize=False,
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if active_id and "source_partner_id" in fields_list and not res.get("source_partner_id"):
            res["source_partner_id"] = active_id
        return res

    def action_calculate_recommendations(self):
        """Analyze candidates, rank them, build lines, and render HTML dashboard."""
        self.ensure_one()
        source = self.source_partner_id
        service = self.env["sgt.matchmaking.service"]

        # Run recommendation engine
        matches = service.find_matching_contacts(
            source_contact=source,
            limit=self.limit or 10,
            min_score=self.min_score or 0.0,
        )

        all_candidates_count = self.env["res.partner"].search_count([
            ("id", "!=", source.id),
            ("active", "=", True),
        ])

        # Clear existing lines
        self.line_ids.unlink()

        # Build lines
        lines_data = []
        highest = 0.0
        for m in matches:
            sc = m["score"]
            if sc > highest:
                highest = sc
            bd = m["breakdown"]
            reasons_text = "\n".join(
                [f"✓ {r['label']} (+{r['points']}): {r.get('matched_value', '')}" for r in m["reasons"]]
            )
            lines_data.append((0, 0, {
                "rank": m["rank"],
                "partner_id": m["candidate_id"],
                "score": sc,
                "category_score": bd.get("product_category", 0.0),
                "industry_score": bd.get("industry", 0.0),
                "event_score": bd.get("event", 0.0),
                "buyer_seller_score": bd.get("buyer_seller", 0.0),
                "country_score": bd.get("country", 0.0),
                "reasons_json": json.dumps(m["reasons"], ensure_ascii=False),
                "reasons_display": reasons_text,
            }))

        html_dash = self._render_dashboard_html(source, matches, all_candidates_count)

        self.write({
            "total_candidates": all_candidates_count,
            "total_matches": len(matches),
            "max_score": highest,
            "line_ids": lines_data,
            "html_dashboard": html_dash,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _render_dashboard_html(self, source, matches, total_analyzed):
        """Generate Modern Business CRM Dashboard HTML for Top 10 recommendations."""
        src_name = html.escape(source.name or "Unnamed Contact")
        src_type = (getattr(source, "x_type_contact", "") or "").capitalize() or "Unspecified"
        src_cat = html.escape(getattr(source, "x_product_category", "") or "None")
        src_ind = html.escape(
            (source.industry_id.name if source.industry_id else getattr(source, "x_fb_industry", "")) or "None"
        )
        src_event = html.escape(getattr(source, "x_event", "") or "None")
        src_country = html.escape((source.country_id.name if source.country_id else "") or "None")
        src_details = html.escape(getattr(source, "x_product_details", "") or "")

        top_count = len(matches)
        highest_score = matches[0]["score"] if matches else 0.0

        out = []
        out.append(f"""
<div class="sgt-match-recom-container" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px; border-radius: 12px;">
    <!-- HEADER SOURCE BANNER -->
    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 15px;">
            <div>
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                    <span style="background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 3px 8px; border-radius: 6px; letter-spacing: 0.5px;">SOURCE CONTACT</span>
                    <span style="background: #e0f2fe; color: #0369a1; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 6px;">Role: {src_type}</span>
                </div>
                <h2 style="margin: 0 0 8px 0; font-size: 22px; font-weight: 700; color: #0f172a;">{src_name}</h2>
                <div style="display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; color: #475569;">
                    <span><strong>Category:</strong> {src_cat}</span>
                    <span>•</span>
                    <span><strong>Industry:</strong> {src_ind}</span>
                    <span>•</span>
                    <span><strong>Event:</strong> {src_event}</span>
                    <span>•</span>
                    <span><strong>Country:</strong> {src_country}</span>
                </div>
                {f'<div style="margin-top: 8px; font-size: 12px; color: #64748b; font-style: italic;">Product Details: {src_details}</div>' if src_details else ''}
            </div>
            <!-- STATS CHIPS -->
            <div style="display: flex; gap: 12px;">
                <div style="background: #f1f5f9; padding: 10px 16px; border-radius: 8px; text-align: center; min-width: 90px;">
                    <div style="font-size: 20px; font-weight: 800; color: #0f172a;">{top_count}</div>
                    <div style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;">Top Matches</div>
                </div>
                <div style="background: #eff6ff; padding: 10px 16px; border-radius: 8px; text-align: center; min-width: 90px;">
                    <div style="font-size: 20px; font-weight: 800; color: #2563eb;">{highest_score:.0f}<span style="font-size: 13px; color: #64748b;">/95</span></div>
                    <div style="font-size: 11px; font-weight: 600; color: #2563eb; text-transform: uppercase;">Best Score</div>
                </div>
            </div>
        </div>
    </div>
        """)

        # NO MATCHES CASE
        if not matches:
            out.append("""
    <div style="background: #ffffff; border: 1px dashed #cbd5e1; border-radius: 12px; padding: 48px; text-align: center;">
        <div style="font-size: 40px; margin-bottom: 12px;">🔍</div>
        <h3 style="margin: 0 0 6px 0; font-size: 18px; font-weight: 700; color: #334155;">No matching companies found</h3>
        <p style="margin: 0; font-size: 14px; color: #64748b;">None of the candidates matched the criteria (Product Category, Industry, Event, Buyer/Seller, or Country).</p>
    </div>
</div>
            """)
            return "".join(out)

        # MATCHES LIST
        out.append("""
    <div style="margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;">
        <h3 style="margin: 0; font-size: 16px; font-weight: 700; color: #334155;">
            TOP 10 RECOMMENDED COMPANIES / PARTNERS
        </h3>
        <span style="font-size: 12px; color: #64748b;">Ranked strictly by Matchmaking Formula (Max 95 pts)</span>
    </div>
    <div style="display: flex; flex-direction: column; gap: 14px;">
        """)

        for m in matches:
            rank = m["rank"]
            cand_id = m["candidate_id"]
            cand_name = html.escape(m["name"])
            cand_email = html.escape(m["email"])
            cand_phone = html.escape(m["phone"])
            cand_country = html.escape(m["country"] or "N/A")
            cand_type = (m["type_contact"] or "").capitalize() or "Unspecified"
            cand_score = m["score"]
            score_pct = (cand_score / 95.0) * 100.0
            breakdown = m["breakdown"]
            reasons = m["reasons"]
            supp = m.get("details", {})
            target_pdetails = html.escape(supp.get("target_product_details", ""))

            # Score color theme
            if cand_score >= 80:
                badge_bg = "#dcfce7"
                badge_fg = "#15803d"
                bar_color = "#16a34a"
                rank_bg = "#15803d"
                level_text = "EXCELLENT MATCH"
            elif cand_score >= 60:
                badge_bg = "#e0f2fe"
                badge_fg = "#0369a1"
                bar_color = "#0284c7"
                rank_bg = "#0284c7"
                level_text = "HIGH MATCH"
            elif cand_score >= 40:
                badge_bg = "#fef3c7"
                badge_fg = "#b45309"
                bar_color = "#d97706"
                rank_bg = "#b45309"
                level_text = "MODERATE MATCH"
            else:
                badge_bg = "#f1f5f9"
                badge_fg = "#475569"
                bar_color = "#64748b"
                rank_bg = "#64748b"
                level_text = "LOW MATCH"

            out.append(f"""
        <!-- CANDIDATE CARD #{rank} -->
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); transition: all 0.2s ease;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 14px; margin-bottom: 12px;">
                <!-- LEFT INFO -->
                <div style="display: flex; gap: 14px; align-items: flex-start;">
                    <div style="background: {rank_bg}; color: #ffffff; font-size: 14px; font-weight: 800; border-radius: 8px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        #{rank}
                    </div>
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <h4 style="margin: 0; font-size: 17px; font-weight: 700; color: #0f172a;">{cand_name}</h4>
                            <span style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 5px;">Role: {cand_type}</span>
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: #64748b;">
                            {f'<span>📧 {cand_email}</span>' if cand_email else ''}
                            {f'<span>📞 {cand_phone}</span>' if cand_phone else ''}
                            <span>🌍 {cand_country}</span>
                        </div>
                    </div>
                </div>

                <!-- RIGHT SCORE -->
                <div style="text-align: right; min-width: 160px;">
                    <div style="display: inline-block; background: {badge_bg}; color: {badge_fg}; font-size: 12px; font-weight: 800; padding: 4px 10px; border-radius: 20px; margin-bottom: 4px;">
                        {cand_score:.0f} / 95 PTS ({level_text})
                    </div>
                    <!-- PROGRESS BAR -->
                    <div style="background: #e2e8f0; border-radius: 6px; height: 7px; width: 100%; overflow: hidden; margin-top: 4px;">
                        <div style="background: {bar_color}; width: {score_pct:.1f}%; height: 100%; border-radius: 6px;"></div>
                    </div>
                </div>
            </div>

            <!-- BREAKDOWN & REASONS CHECKLIST -->
            <div style="background: #f8fafc; border-radius: 8px; padding: 12px 14px; margin-top: 8px;">
                <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">MATCH BREAKDOWN & REASONS:</div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; font-size: 13px;">
            """)

            # 5 criteria items
            rules_config = [
                ("product_category", "Same Product Category", 30),
                ("industry", "Same Industry", 20),
                ("event", "Same Event", 20),
                ("buyer_seller", "Buyer/Seller Match", 20),
                ("country", "Same Country", 5),
            ]

            reasons_map = {r["rule"]: r for r in reasons}

            for rule_key, rule_name, rule_max in rules_config:
                if rule_key in reasons_map:
                    item = reasons_map[rule_key]
                    val_str = html.escape(str(item.get("matched_value", "")))
                    out.append(f"""
                    <div style="display: flex; align-items: center; gap: 6px; color: #166534; font-weight: 600;">
                        <span style="color: #16a34a; font-weight: 800; font-size: 14px;">✓</span>
                        <span>{rule_name}</span>
                        <span style="background: #dcfce7; color: #15803d; font-size: 11px; padding: 1px 6px; border-radius: 4px; font-weight: 700;">+{item['points']}</span>
                        {f'<span style="color: #64748b; font-size: 11px; font-weight: 450;">({val_str})</span>' if val_str else ''}
                    </div>
                    """)
                else:
                    out.append(f"""
                    <div style="display: flex; align-items: center; gap: 6px; color: #94a3b8;">
                        <span>✕</span>
                        <span>{rule_name}</span>
                        <span style="font-size: 11px;">(0)</span>
                    </div>
                    """)

            out.append(f"""
                </div>
                {f'<div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #475569;"><strong>Catalog / Product Details:</strong> {target_pdetails}</div>' if target_pdetails else ''}
            </div>

            <!-- ACTION FOOTER -->
            <div style="display: flex; justify-content: flex-end; margin-top: 10px;">
                <a href="/odoo/contacts/{cand_id}" target="_blank"
                   style="display: inline-flex; align-items: center; gap: 5px; background: #ffffff; border: 1px solid #cbd5e1; color: #2563eb; font-size: 12px; font-weight: 600; padding: 5px 12px; border-radius: 6px; text-decoration: none;">
                    View Contact #{cand_id} ↗
                </a>
            </div>
        </div>
            """)

        out.append("""
    </div>
</div>
        """)
        return "".join(out)


class SgtMatchmakingRecommendationWizardLine(models.TransientModel):
    _name = "sgt.matchmaking.recommendation.wizard.line"
    _description = "Matchmaking Recommendation Candidate Line"
    _order = "rank asc, score desc"

    wizard_id = fields.Many2one(
        "sgt.matchmaking.recommendation.wizard",
        string="Wizard",
        ondelete="cascade",
    )
    rank = fields.Integer(string="Rank", default=1)
    partner_id = fields.Many2one("res.partner", string="Company / Contact", required=True)
    score = fields.Float(string="Match Score", digits=(4, 1))
    category_score = fields.Float(string="Category (+30)")
    industry_score = fields.Float(string="Industry (+20)")
    event_score = fields.Float(string="Event (+20)")
    buyer_seller_score = fields.Float(string="Buyer/Seller (+20)")
    country_score = fields.Float(string="Country (+5)")
    reasons_json = fields.Text(string="Reasons JSON")
    reasons_display = fields.Text(string="Match Reasons")

    def action_open_candidate(self):
        """Open the candidate contact form in Odoo."""
        self.ensure_one()
        return {
            "name": self.partner_id.name,
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }
