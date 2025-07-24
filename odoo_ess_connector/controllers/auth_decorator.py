# In odoo_ess_connector/controllers/auth_decorator.py
import functools
import werkzeug # Not strictly used here now, but good to keep if controllers use it
from odoo import http, fields, api # api is needed for Environment.manage
from odoo.http import request, Response
import json
import logging
import time

_logger = logging.getLogger(__name__)

def _create_log_entry(log_data):
    """
    Helper function to create an API log entry in a new cursor.
    Ensures log creation is attempted independently of the main request transaction.
    """
    try:
        log_record = request.env['ess.api.log'].sudo().create(log_data) # Use sudo for robustness
        _logger.info(
            f"API Log created (ID: {log_record.id}) for endpoint: {log_data.get('endpoint')} "
            f"by user ID: {log_data.get('user_id', 'N/A')}"
        )
    except Exception as log_e:
        _logger.error(f"CRITICAL: Failed to create API log entry (within main transaction) for {log_data.get('endpoint')}: {log_e}", exc_info=True)

def api_key_auth(required_model=None):
    """
    Decorator to validate API token, check settings, log call,
    and optionally enforce model-based scope.
    If token scope is empty/None, access is allowed (subject to user permissions).
    If token scope is defined, it restricts to only those models.
    :param required_model: str, the technical name of the Odoo model this endpoint primarily interacts with.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            request_ip = request.httprequest.remote_addr
            endpoint_path = request.httprequest.path
            http_method = request.httprequest.method

            log_vals = {
                'endpoint': endpoint_path, 'method': http_method, 'request_ip': request_ip,
                'user_id': None, 'api_token_id': None,
                'response_status_code': 500, 'message': 'Processing...', 'duration_ms': 0
            }

            # --- 1. Check System Settings ---
            try:
                IrConfigParameter = request.env['ir.config_parameter'].sudo()
                integration_enabled_str = IrConfigParameter.get_param('odoo_ess_connector.ess_integration_enabled', 'True')
                if integration_enabled_str.lower() != 'true':
                    _logger.warning(f"ESS API call to {endpoint_path} denied: Integration disabled.")
                    log_vals.update({'response_status_code': 503, 'message': 'Service Unavailable: ESS API disabled.'})
                    _create_log_entry(log_vals)
                    return Response(json.dumps({'error': 'Service Unavailable', 'message': 'ESS API disabled.'}),
                                    status=503, headers={'Content-Type': 'application/json'})

                allowed_ips_str = IrConfigParameter.get_param('odoo_ess_connector.ess_allowed_ips', '').strip()
                if allowed_ips_str:
                    allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()] # Ensure no empty strings
                    if request_ip not in allowed_ips:
                        _logger.warning(f"ESS API call to {endpoint_path} denied: IP {request_ip} not in allowed list.")
                        log_vals.update({'response_status_code': 403, 'message': f"Forbidden: IP {request_ip} not allowed."})
                        _create_log_entry(log_vals)
                        return Response(json.dumps({'error': 'Forbidden', 'message': f"IP {request_ip} not allowed."}),
                                        status=403, headers={'Content-Type': 'application/json'})
            except Exception as settings_e:
                _logger.error(f"Error reading ESS settings for {endpoint_path}: {settings_e}", exc_info=True)
                log_vals.update({'response_status_code': 500, 'message': "Internal Error: Settings check failed."})
                _create_log_entry(log_vals) # Log this critical failure
                return Response(json.dumps({'error': 'Internal Server Error', 'message': 'Error processing integration settings.'}),
                                status=500, headers={'Content-Type': 'application/json'})

            # --- 2. Token Authentication ---
            auth_header = request.httprequest.headers.get('Authorization')
            token_str = None
            if auth_header and auth_header.startswith('Bearer '):
                token_str = auth_header.split(' ')[1]

            if not token_str:
                _logger.warning(f"API call to {endpoint_path} denied: Missing Bearer token.")
                log_vals.update({'response_status_code': 401, 'message': 'Unauthorized: Missing Bearer token.'})
                _create_log_entry(log_vals)
                return Response(json.dumps({'error': 'Unauthorized', 'message': 'Missing Bearer token.'}),
                                status=401, headers={'Content-Type': 'application/json'})

            authenticated_user_recordset = request.env['ess.api.token'].sudo()._validate_token(token_str)
            if not authenticated_user_recordset:
                _logger.warning(f"API call to {endpoint_path} denied: Invalid or inactive token: {token_str[:6]}...")
                log_vals.update({'response_status_code': 401, 'message': 'Unauthorized: Invalid or inactive API token.'})
                _create_log_entry(log_vals)
                return Response(json.dumps({'error': 'Unauthorized', 'message': 'Invalid or inactive API token.'}),
                                status=401, headers={'Content-Type': 'application/json'})

            log_vals['user_id'] = authenticated_user_recordset.id
            token_record = request.env['ess.api.token'].sudo().search([('token', '=', token_str)], limit=1)
            if token_record:
                log_vals['api_token_id'] = token_record.id
            else: # Should not happen if _validate_token returned a user
                _logger.error(f"Consistency issue: Token validated for user {authenticated_user_recordset.login} but token record not found by string '{token_str[:6]}...'.")


            # --- 3. Scope Check (Revised Logic) ---
            if required_model and token_record: # Only check scope if endpoint requires it and we have token details
                current_scope_str = token_record.scope.strip() if token_record.scope else ''

                if current_scope_str: # If scope IS defined on the token, then enforce it
                    allowed_models = [s.strip() for s in current_scope_str.split(',') if s.strip()]
                    if required_model not in allowed_models:
                        _logger.warning(
                            f"API call to {endpoint_path} by user {authenticated_user_recordset.login} denied. "
                            f"Token scope '{current_scope_str}' does not include required model '{required_model}'."
                        )
                        log_vals.update({
                            'response_status_code': 403,
                            'message': f"Forbidden: Token scope does not grant access to '{required_model}'."
                        })
                        _create_log_entry(log_vals)
                        return Response(json.dumps({'error': 'Forbidden', 'message': f"Token does not have scope for '{required_model}'."}),
                                        status=403, headers={'Content-Type': 'application/json'})
                    else:
                        _logger.info(f"Scope check passed (specific scope): user {authenticated_user_recordset.login}, required '{required_model}', token has '{current_scope_str}'")
                else:
                    # Scope is NOT defined (empty string) on the token. This means "allow access to any required_model",
                    # subject to the user's underlying Odoo permissions.
                    _logger.info(f"Scope check passed (empty/None token scope implies all allowed): user {authenticated_user_recordset.login}, required '{required_model}'.")
            elif required_model and not token_record:
                # This should ideally not be reached if token_str was valid and _validate_token returned a user
                _logger.error(f"Internal inconsistency during scope check: Validated user but no token_record found. Token string: {token_str[:6]}...")
                log_vals.update({'response_status_code': 500, 'message': 'Internal Server Error: Scope check inconsistency.'})
                _create_log_entry(log_vals)
                return Response(json.dumps({'error': 'Internal Server Error', 'message': 'Scope check inconsistency.'}),
                                status=500, headers={'Content-Type': 'application/json'})
            # If required_model is None for the decorator, scope check is bypassed.
            # --- End Scope Check ---

            request.update_env(user=authenticated_user_recordset.id)
            _logger.info(
                f"API call to {endpoint_path} granted for user '{authenticated_user_recordset.login}' "
                f"(ID: {authenticated_user_recordset.id}) via token ID: {log_vals.get('api_token_id', 'N/A')}."
            )

            # --- 4. Execute Decorated Controller Method ---
            response_obj = None # Initialize to ensure it's defined for finally block
            try:
                response_obj = func(*args, **kwargs)

                if not isinstance(response_obj, Response):
                    _logger.error(
                        f"Controller {func.__name__} for {endpoint_path} did not return an odoo.http.Response object. "
                        f"Got: {type(response_obj)}. Attempting to convert if dict."
                    )
                    if isinstance(response_obj, dict):
                        response_obj = Response(json.dumps(response_obj), status=200, headers={'Content-Type': 'application/json'})
                    else:
                        # This indicates a programming error in the controller
                        raise TypeError(f"Controller {func.__name__} for {endpoint_path} must return an odoo.http.Response object.")

                log_vals['response_status_code'] = response_obj.status_code
                try:
                    response_data_str = response_obj.data.decode('utf-8')
                    response_data_json = json.loads(response_data_str)
                    msg_detail = response_data_json.get('message', response_data_json.get('error_description', response_data_json.get('error', ''))) # Check more error keys
                    log_vals['message'] = f"{'Success' if response_obj.status_code < 400 else 'Error'}: {msg_detail or response_data_str[:100]}"
                except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                    log_vals['message'] = f"{'Success' if response_obj.status_code < 400 else 'Error'} (Status: {response_obj.status_code}, Content-Type: {response_obj.mimetype})"

            except Exception as controller_e:
                _logger.error(f"Error executing API endpoint {endpoint_path} for user {authenticated_user_recordset.id}: {controller_e}", exc_info=True)
                log_vals['response_status_code'] = 500 # Default to 500 for unhandled controller exceptions
                log_vals['message'] = f"Internal Server Error in controller: {str(controller_e)}"
                # Ensure response_obj is a valid Response object for the finally block and return
                error_body_json = json.dumps({'error': 'Internal Server Error', 'message': 'An error occurred processing your request.'})
                response_obj = Response(error_body_json, status=500, headers={'Content-Type': 'application/json'})
            finally:
                log_vals['duration_ms'] = round((time.time() - start_time) * 1000, 2)
                _create_log_entry(log_vals)

            return response_obj
        return wrapper
    return decorator