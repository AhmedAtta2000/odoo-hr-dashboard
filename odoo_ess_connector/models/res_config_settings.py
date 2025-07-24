# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- ESS Connector Settings ---
    ess_integration_enabled = fields.Boolean(
        string="Enable ESS Integration",
        config_parameter='odoo_ess_connector.ess_integration_enabled',
        default=True, # Default to enabled
        help="Master switch to enable or disable all ESS API Connector functionality."
    )
    ess_allowed_ips = fields.Char(
        string="Allowed IPs for ESS API",
        config_parameter='odoo_ess_connector.ess_allowed_ips',
        help="Comma-separated list of IP addresses allowed to access the ESS API. Leave empty to allow all."
    )
    # We might not need a specific field for the button if it just opens the token view.
    # If it were to perform an action like generating a specific token,
    # then a related field or a method on res.config.settings might be used.

    # Example method that could be called by a button in settings (optional)
    # def action_manage_ess_tokens(self):
    #     """Opens the ESS API Token management view."""
    #     action = self.env['ir.actions.act_window']._for_xml_id('odoo_ess_connector.action_ess_api_token')
    #     return action