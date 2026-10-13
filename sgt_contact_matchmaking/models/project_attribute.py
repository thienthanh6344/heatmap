# -*- coding: utf-8 -*-
"""
SGT Project Dynamic Attribute Engine
Allows arbitrary, extensible custom attributes (EAV pattern) for projects
without modifying the database schema or code.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SgtProjectAttribute(models.Model):
    _name = "sgt.project.attribute"
    _description = "Project Custom Attribute Definition"
    _order = "sequence asc, name asc"

    name = fields.Char(
        string="Attribute Name",
        required=True,
        translate=True,
        help="Display name for this attribute (e.g. Capacity, Investment, Technology, Factory Type)",
    )
    code = fields.Char(
        string="Attribute Code",
        required=True,
        index=True,
        help="Unique technical code (e.g. capacity, investment, technology, factory_type)",
    )
    field_type = fields.Selection(
        [
            ("text", "Text / String"),
            ("number", "Number / Quantity / Value"),
            ("boolean", "Boolean (Yes/No)"),
            ("date", "Date"),
            ("selection", "Selection Dropdown"),
        ],
        string="Data Type",
        default="text",
        required=True,
    )
    selection_options = fields.Text(
        string="Selection Options",
        help="Options separated by comma or new line for Selection type (e.g. Solar, Wind, Hydro)",
    )
    unit = fields.Char(
        string="Unit of Measurement",
        help="Unit displayed after the value (e.g. MW, USD, m², VND, Employees)",
    )
    required = fields.Boolean(
        string="Required",
        default=False,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    description = fields.Text(
        string="Description / Help Notes",
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Attribute code must be unique!"),
    ]

    @api.depends("name", "unit")
    def _compute_display_name(self):
        for rec in self:
            if rec.unit:
                rec.display_name = f"{rec.name} ({rec.unit})"
            else:
                rec.display_name = rec.name or ""


class SgtProjectAttributeValue(models.Model):
    _name = "sgt.project.attribute.value"
    _description = "Project Custom Attribute Value"
    _order = "attribute_sequence asc, id asc"

    project_id = fields.Many2one(
        "sgt.project.heatmap",
        string="Project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    attribute_id = fields.Many2one(
        "sgt.project.attribute",
        string="Attribute",
        required=True,
        ondelete="cascade",
        index=True,
    )
    attribute_name = fields.Char(
        related="attribute_id.name",
        string="Attribute Name",
        readonly=True,
    )
    attribute_code = fields.Char(
        related="attribute_id.code",
        string="Code",
        readonly=True,
    )
    field_type = fields.Selection(
        related="attribute_id.field_type",
        string="Type",
        readonly=True,
    )
    unit = fields.Char(
        related="attribute_id.unit",
        string="Unit",
        readonly=True,
    )
    attribute_sequence = fields.Integer(
        related="attribute_id.sequence",
        string="Seq",
        store=True,
    )

    # Generic Typed Storage
    value_text = fields.Char(string="Text Value")
    value_number = fields.Float(string="Numeric Value", digits=(16, 2))
    value_boolean = fields.Boolean(string="Boolean Value")
    value_date = fields.Date(string="Date Value")
    value_selection = fields.Char(string="Selection Value")

    display_value = fields.Char(
        string="Formatted Value",
        compute="_compute_display_value",
        store=True,
    )

    _sql_constraints = [
        ("project_attr_uniq", "unique(project_id, attribute_id)", "This attribute is already configured for this project!"),
    ]

    @api.depends(
        "field_type",
        "value_text",
        "value_number",
        "value_boolean",
        "value_date",
        "value_selection",
        "unit",
    )
    def _compute_display_value(self):
        for rec in self:
            ftype = rec.field_type or "text"
            val_str = ""
            if ftype == "number":
                if rec.value_number:
                    # Clean integer display if no fraction
                    val_str = f"{rec.value_number:g}"
                else:
                    val_str = "0"
            elif ftype == "boolean":
                val_str = _("Yes") if rec.value_boolean else _("No")
            elif ftype == "date":
                val_str = str(rec.value_date) if rec.value_date else ""
            elif ftype == "selection":
                val_str = rec.value_selection or ""
            else:
                val_str = rec.value_text or ""

            if val_str and rec.unit:
                rec.display_value = f"{val_str} {rec.unit}"
            else:
                rec.display_value = val_str
