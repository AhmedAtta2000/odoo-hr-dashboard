# -*- coding: utf-8 -*-
import secrets
import logging # Import logging for _logger
from odoo import models, fields, api, exceptions, _

_logger = logging.getLogger(__name__) # Initialize logger for this model

class EssApiToken(models.Model):
    _name = 'ess.api.token'
    _description = 'ESS API Access Token'
    _order = 'create_date desc' # Show newest first, good default

    # --- Fields Definition ---
    name = fields.Char(
        string='Label',
        required=True,
        help="A user-friendly label for the token (e.g., 'ESS Portal Backend Integration')"
    )
    user_id = fields.Many2one(
        'res.users',
        string='Associated User', # Changed string for clarity
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade', # Good practice: delete tokens if the user is deleted
        help="The Odoo user this token will act on behalf of for API calls."
    )
    token = fields.Char(
        string='API Token', # Changed string for clarity
        readonly=True, # Token should not be manually editable after creation
        copy=False,    # Prevent copying the token value to new records
        help="The unique API access token. Generated automatically on creation."
    )
    scope = fields.Char(
        string='Scope (Optional)',
        help="Future use: Comma-separated list of allowed models or permissions (e.g., 'hr.employee.read, hr.leave.create'). Not currently enforced."
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, this token will be disabled and cannot be used for authentication."
    )
    last_used = fields.Datetime(
        string='Last Used On', # Changed string for clarity
        readonly=True,
        help="Timestamp of the last successful API call using this token."
    )
    note = fields.Text(
        string="Internal Notes",
        help="Optional notes about this token's purpose or usage."
    )

    # --- SQL Constraints ---
    _sql_constraints = [
        ('token_uniq', 'unique (token)', 'Each API Token must be unique!'),
    ]

    # --- CRUD Method Overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        """
        Overrides the create method to automatically generate a secure token
        for each new record.
        """
        for vals in vals_list:
            if 'token' not in vals or not vals['token']: # Generate token if not provided or empty
                vals['token'] = secrets.token_urlsafe(32) # Generates a 43-character URL-safe token
            # Note: Group check for 'odoo_ess_connector.group_ess_api_access' was removed as per previous discussion.
            # If re-introducing, ensure the user being assigned (vals.get('user_id')) has the group.
        return super(EssApiToken, self).create(vals_list)

    def write(self, vals):
        """
        Overrides the write method to prevent modification of the 'token' field
        after it has been generated.
        """
        if 'token' in vals:
            for record in self:
                # Allow setting token if it's currently False (e.g. during import)
                # but prevent changing an existing token.
                if record.token and vals['token'] != record.token:
                    raise exceptions.UserError(
                        _("The API Token value cannot be changed after it has been generated.")
                    )
        return super(EssApiToken, self).write(vals)

    # --- Action Methods (for buttons in UI) ---
    def action_toggle_active(self):
        """Toggles the 'active' status of the selected token(s)."""
        # self is a recordset, so iterate if multiple records are selected
        for record in self:
            record.active = not record.active
        return True # Necessary for Odoo client action to refresh view

    def action_regenerate_token(self):
        """Generates a new token for the selected record(s), effectively revoking the old one."""
        if not self.env.user.has_group('base.group_system'): # Example: only allow admins to regenerate
            raise exceptions.AccessError(_("Only administrators can regenerate tokens directly."))
        for record in self:
            record.write({'token': secrets.token_urlsafe(32)})
        return True


    # --- Business Logic / Helper Methods ---
    @api.model
    def _validate_token(self, token_str: str):
        """
        Validates an API token string.
        - Checks if the token exists and is active.
        - Checks if the associated user is active.
        - Updates the 'last_used' timestamp on successful validation.
        Returns the res.users recordset if valid, otherwise None.
        """
        if not token_str:
            _logger.debug("Token validation: No token string provided.")
            return None

        # Search for an active token matching the provided string
        token_record = self.search([
            ('token', '=', token_str),
            ('active', '=', True)
        ], limit=1)

        if not token_record:
            _logger.warning(f"Token validation: Token '{token_str[:6]}...' not found or inactive.")
            return None

        # Check if the user associated with the token is active
        user = token_record.user_id
        if not user or not user.active:
            _logger.warning(f"Token validation: User '{user.login if user else 'N/A'}' for token '{token_str[:6]}...' is inactive or missing.")
            return None

        # Update 'last_used' timestamp.
        # This is a write operation. To avoid potential deadlocks or performance issues on
        # high-frequency reads, it's done in a new cursor.
        # It uses sudo() to ensure the write happens regardless of the current API user's
        # direct write permissions on ess.api.token, as this is an internal tracking mechanism.
        try:
            with self.pool.cursor() as cr_new:
                # Create a new environment with the new cursor and SUPERUSER_ID for this specific operation
                env_new = api.Environment(cr_new, self.env.uid, self.env.context) # uid is current user, but operation is sudo
                token_to_update = self.browse(token_record.id).with_env(env_new)
                token_to_update.sudo().write({'last_used': fields.Datetime.now()})
                # cr_new.commit() # Committing here might be too soon if main transaction fails
                # Odoo usually handles commit at the end of the HTTP request.
                # If this write absolutely must happen even if later code fails, a separate commit is needed.
                # For now, let it be part of the main transaction.
        except Exception as e:
            _logger.error(f"Token validation: Failed to update 'last_used' for token ID {token_record.id}: {e}", exc_info=True)
            # Do not fail the entire token validation just because 'last_used' couldn't be updated.
            # This is an auxiliary piece of information.

        _logger.info(f"Token validation: Token '{token_str[:6]}...' successfully validated for user '{user.login}'.")
        return user # Return the res.users record