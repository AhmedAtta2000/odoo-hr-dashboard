# -*- coding: utf-8 -*-
from odoo import models, fields, api

class EssApiLog(models.Model):
    _name = 'ess.api.log'
    _description = 'ESS API Call Log'
    _order = 'create_date desc' # Show newest logs first

    # --- Fields Definition ---
    create_date = fields.Datetime(string="Timestamp", readonly=True, default=fields.Datetime.now)
    user_id = fields.Many2one(
        'res.users',
        string='Authenticated User',
        readonly=True,
        ondelete='set null', # Keep log even if user is deleted, just nullify the link
        help="The Odoo user on whose behalf the API call was made."
    )
    api_token_id = fields.Many2one(
        'ess.api.token',
        string='API Token Used',
        readonly=True,
        ondelete='set null',
        help="The specific API token that was used for authentication (if applicable)."
    )
    endpoint = fields.Char(
        string='Endpoint Called',
        readonly=True,
        help="The API endpoint path that was accessed."
    )
    method = fields.Char(
        string='HTTP Method',
        readonly=True,
        help="e.g., GET, POST, PUT, DELETE"
    )
    request_ip = fields.Char(
        string='Request IP Address',
        readonly=True,
        help="The IP address from which the API request originated."
    )
    response_status_code = fields.Integer(
        string='Response Status Code',
        readonly=True,
        help="e.g., 200, 401, 404, 500"
    )
    # Optional: Store a brief message or error details
    message = fields.Text(
        string='Message/Error Detail',
        readonly=True,
        help="Additional information, such as error messages or success details."
    )
    # Optional: Duration of the request processing within Odoo
    duration_ms = fields.Float(
        string='Processing Duration (ms)',
        readonly=True,
        help="Time taken by Odoo to process the request (controller execution)."
    )

    # No methods needed for this model initially, it's primarily for data storage.