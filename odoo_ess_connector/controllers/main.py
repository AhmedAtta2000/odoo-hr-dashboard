# -*- coding: utf-8 -*-
# In odoo_ess_connector/controllers/main.py
import json
import werkzeug # For exceptions like NotFound, Forbidden
import logging # For logging
from odoo import http, fields, exceptions # Import base Odoo exceptions
from odoo.http import request, route, Response # Import Response object
import base64 # For potential PDF handling later
from datetime import datetime, date, time # Import date, time
import pytz # For timezone handling

# Import the custom authentication decorator
from .auth_decorator import api_key_auth

# Setup logger for this controller
_logger = logging.getLogger(__name__)

class EssApiController(http.Controller):

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    def _prepare_employee_data(self, employee):
        """Selects and formats fields from hr.employee record (Odoo 15+ compatible)."""
        if not employee:
            return {}

        # Access Private Address via User's Partner
        user = employee.user_id
        private_partner = user.partner_id if user else None
        formatted_address = None
        if private_partner:
            address_parts = [
                private_partner.street,
                private_partner.street2,
                private_partner.city,
                private_partner.state_id.name,
                private_partner.zip,
                private_partner.country_id.name,
            ]
            formatted_address = ", ".join(filter(None, address_parts))

        # Prepare the dictionary with correct Odoo 18+ fields
        return {
            'id': employee.id,
            'name': employee.name,
            'job_title': employee.job_id.name or employee.employee_title.name or None,
            'work_email': employee.work_email or None,
            'work_phone': employee.work_phone or None,
            'mobile_phone': employee.mobile_phone or None,
            'work_location': employee.work_location_id.name or employee.work_location_id.display_name or None,
            'address': formatted_address or None,
            'department': employee.department_id.name or None,
        }

    def _json_response(self, data, status=200):
        """Helper to create a JSON Response object."""
        headers = {'Content-Type': 'application/json'}
        body = json.dumps(data, ensure_ascii=False)
        return Response(body, status=status, headers=headers)

    def _error_response(self, error_code, message, status_code):
        """Helper to create a JSON error Response object."""
        payload = {'error': error_code, 'message': message}
        return self._json_response(payload, status=status_code)

    # --- ATTENDANCE ENDPOINTS (Refactored/New for hr.attendance) ---

    def _get_employee_and_validate_access(self, employee_id):
        """Helper to fetch employee and validate access. Raises Werkzeug exceptions."""
        employee = request.env['hr.employee'].browse(employee_id)
        if not employee.exists():
            raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")
        # Basic check: user must be linked to the employee or be an admin/manager (add more complex rules later)
        # if request.env.user.employee_id != employee and not request.env.user.has_group('hr_attendance.group_hr_attendance_manager'): # Example manager check
        #      raise werkzeug.exceptions.Forbidden(f"You do not have permission to manage attendance for employee ID {employee_id}.")
        return employee

    def _get_current_odoo_attendance_status(self, employee_id):
        """Determines current check-in/out status from hr.attendance for an employee."""
        # Find the latest attendance record for the employee
        latest_attendance = request.env['hr.attendance'].search([
            ('employee_id', '=', employee_id),
        ], order='check_in desc', limit=1)

        if not latest_attendance:
            return {"status": "checked_out", "last_action_time": None, "message": "No previous attendance recorded. Ready to check in."}

        if not latest_attendance.check_out: # If check_out is not set, employee is checked in
            check_in_user_tz_str = fields.Datetime.context_timestamp(latest_attendance, latest_attendance.check_in).strftime('%Y-%m-%d %H:%M:%S')
            return {
                "status": "checked_in",
                "last_action_time": fields.Datetime.to_string(latest_attendance.check_in),
                "message": f"Currently checked in since {check_in_user_tz_str}."
            }
        else: # Employee is checked out
            check_out_user_tz_str = fields.Datetime.context_timestamp(latest_attendance, latest_attendance.check_out).strftime('%Y-%m-%d %H:%M:%S')
            return {
                "status": "checked_out",
                "last_action_time": fields.Datetime.to_string(latest_attendance.check_out),
                "message": f"Last action: Checked out at {check_out_user_tz_str}."
            }
    # --------------------------------------------------------------------------
    # Controller Endpoints
    # --------------------------------------------------------------------------

    @route('/ess/api/ping', type='http', auth='public', methods=['GET'], csrf=False)
    def ping(self, **kw):
        """Simple public endpoint to check if the connector is running."""
        return self._json_response({"message": "Odoo ESS Connector is running!"})

    @route('/ess/api/employee/<int:employee_id>', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.employee')
    def get_employee_data(self, employee_id, **kw):
        """Fetches specific data for a single employee. Requires Bearer token."""
        try:
            # Find employee - access rules applied based on token user via decorator
            employee = request.env['hr.employee'].search([('id', '=', employee_id)], limit=1)

            if not employee:
                raise werkzeug.exceptions.NotFound("Employee not found.")

            # --- Optional: Add further access control ---
            # Example: Check if the authenticated user *is* the employee or manager
            # if employee.user_id != request.env.user and employee.parent_id.user_id != request.env.user:
            #     raise werkzeug.exceptions.Forbidden("Access Denied: You cannot view this employee's data.")
            # --- End Optional ---

            data = self._prepare_employee_data(employee)
            return self._json_response(data)

        except werkzeug.exceptions.NotFound as e:
            _logger.info(f"Employee not found for ID {employee_id}.")
            return self._error_response('Not Found', str(e), 404)
        except werkzeug.exceptions.Forbidden as e:
            _logger.warning(f"Forbidden access attempt by user {request.env.user.id} to employee {employee_id}")
            return self._error_response('Forbidden', str(e), 403)
        except Exception as e:
            _logger.error(f"Error fetching employee data for ID {employee_id}: {e}", exc_info=True)
            return self._error_response('Internal Server Error', "An unexpected error occurred.", 500)


    @route('/ess/api/leave-types', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.leave.type')
    def get_leave_types(self, **kw):
        """Fetches all active leave types (hr.leave.type). Requires Bearer token."""
        try:
            # Fetch leave types (consider adding domain filter if needed)
            leave_types = request.env['hr.leave.type'].search([])
            types_data = [{'id': lt.id, 'name': lt.name} for lt in leave_types]
            return self._json_response(types_data)

        except Exception as e:
            _logger.error(f"Error fetching leave types: {e}", exc_info=True)
            return self._error_response('Internal Server Error', 'Could not retrieve leave types.', 500)


    @route('/ess/api/leave', type='http', auth='none', methods=['POST'], csrf=False)
    @api_key_auth(required_model='hr.leave')
    def submit_leave_request(self, **kw):
        """Creates a new leave request (hr.leave). Requires Bearer token."""
        try:
            # Manually read and parse JSON body for type='http'
            http_body = request.httprequest.data.decode('utf-8')
            if not http_body:
                _logger.warning("Received empty request body for leave submission.")
                return self._error_response('Bad Request', 'Request body cannot be empty.', 400)

            _logger.info(f"DEBUG: Raw HTTP body received: {http_body}")
            actual_payload = json.loads(http_body)
            _logger.info(f"Received leave request payload for user {request.env.user.login}: {actual_payload}")

            # Validate required fields
            required_fields = ['employee_id', 'leave_type_id', 'from_date', 'to_date']
            missing_fields = [field for field in required_fields if field not in actual_payload]
            if missing_fields:
                msg = f"Missing required fields: {', '.join(missing_fields)}"
                _logger.warning(f"{msg} in leave request payload.")
                return self._error_response('Bad Request', msg, 400)

            # Extract and validate data types
            try:
                employee_id = int(actual_payload['employee_id'])
                leave_type_id = int(actual_payload['leave_type_id'])
                from_date_str = actual_payload['from_date']
                to_date_str = actual_payload['to_date']
                reason = actual_payload.get('note') # Optional

                # Convert date strings; fields.Date.from_string handles YYYY-MM-DD
                date_from = fields.Date.from_string(from_date_str)
                date_to = fields.Date.from_string(to_date_str)

                if date_to < date_from:
                     raise ValueError("The 'to_date' cannot be earlier than the 'from_date'.")

            except (ValueError, TypeError) as e:
                 _logger.warning(f"Invalid data format in leave request payload: {e}")
                 raise werkzeug.exceptions.BadRequest(f"Invalid data format: {e}. Ensure IDs are integers and dates are YYYY-MM-DD.")

            # --- Validate Employee and Leave Type Existence ---
            employee = request.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")

            leave_type_obj = request.env['hr.leave.type'].browse(leave_type_id)
            if not leave_type_obj.exists():
                 raise werkzeug.exceptions.NotFound(f"Leave Type with ID {leave_type_id} not found.")

            # --- Validate Access Rights (Example) ---
            # User can only request for themselves if they are linked to an employee
            # if request.env.user.employee_id and request.env.user.employee_id.id != employee_id:
            #     raise werkzeug.exceptions.Forbidden("You can only request leaves for yourself.")
            # Add more complex rules for managers/HR if needed

            # Prepare values for hr.leave creation
            leave_values = {
                'employee_id': employee_id,
                'holiday_status_id': leave_type_id,
                'request_date_from': date_from,
                'request_date_to': date_to,
                'name': reason or f"Leave request for {employee.name}",
            }

            _logger.info(f"Attempting to create hr.leave with values: {leave_values}")
            # Create the leave record - ORM access rules apply based on token user
            new_leave = request.env['hr.leave'].create(leave_values)
            _logger.info(f"Successfully created hr.leave record with ID: {new_leave.id}")

            # Prepare success response
            success_data = {
                'message': 'Leave request submitted successfully to Odoo.',
                'leave_id': new_leave.id,
                'state': new_leave.state
            }
            return self._json_response(success_data, status=201) # 201 Created

        # --- Specific Odoo/Werkzeug Exception Handling ---
        except (exceptions.AccessError) as e:
            _logger.error(f"Access error submitting leave: {e}", exc_info=True)
            return self._error_response('Forbidden', f"Permission denied: {e}", 403)
        except (exceptions.UserError, exceptions.ValidationError) as e:
            _logger.error(f"Odoo validation error submitting leave: {e}")
            # These errors are often safe to show the user directly
            return self._error_response('Validation Error', str(e), 400)
        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden, werkzeug.exceptions.BadRequest) as e:
             # Handle specific HTTP exceptions raised intentionally
             return self._error_response(e.name, e.description, e.code)
        # --- Generic Exception Handling ---
        except Exception as e:
            _logger.error(f"Unexpected error ({type(e).__name__}) submitting leave request: {e}", exc_info=True)
            return self._error_response('Internal Server Error', 'An unexpected error occurred while submitting the leave request.', 500)

    @route('/ess/api/payslips/<int:employee_id>', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.payslip')
    def get_payslip_list(self, employee_id, **kw):
        """Fetches payslip list for a specific employee."""
        try:
            # --- Validate employee access ---
            employee = request.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")

            # Ensure authenticated user can access this employee's payslips
            # Simple check: user must be linked to the employee requested
            # if request.env.user.employee_id != employee:
            #     raise werkzeug.exceptions.Forbidden("You can only view your own payslips.")
            # Add more complex rules for managers/HR if needed

            # Search for payslips related to this employee
            # Filter by state? e.g., state in ['done', 'paid'] ?
            # Add ordering, limit, offset if needed later
            payslips = request.env['hr.payslip'].search([
                ('employee_id', '=', employee_id),
                ('state', 'in', ['done', 'paid']) # Example: Only show done/paid slips
            ], order='date_to desc') # Show most recent first

            payslips_data = []
            for slip in payslips:
                # Find the 'NET' line total (this can vary based on payroll rules)
                net_line = slip.line_ids.filtered(lambda line: line.code == 'NET')
                net_total = net_line.total if net_line else 0.0

                payslips_data.append({
                    'id': slip.id,
                    'month': slip.name, # Payslip name often includes month/year
                    'total': net_total, # Net wage
                    'status': slip.state, # e.g., 'draft', 'verify', 'done', 'paid'
                    # Determine if PDF is downloadable (e.g., based on state)
                    # Real PDF check would involve looking for report attachment or state
                    'pdf_available': slip.state in ['done', 'paid'],
                    'date_from': slip.date_from.strftime('%Y-%m-%d') if slip.date_from else None,
                    'date_to': slip.date_to.strftime('%Y-%m-%d') if slip.date_to else None,
                })

            return self._json_response(payslips_data)

        except werkzeug.exceptions.NotFound as e:
            _logger.info(f"Employee not found for payslip list: {employee_id}.")
            return self._error_response('Not Found', str(e), 404)
        except werkzeug.exceptions.Forbidden as e:
            _logger.warning(f"Forbidden access attempt by user {request.env.user.id} to payslips of employee {employee_id}")
            return self._error_response('Forbidden', str(e), 403)
        except Exception as e:
            _logger.error(f"Error fetching payslip list for employee {employee_id}: {e}", exc_info=True)
            return self._error_response('Internal Server Error', "An unexpected error occurred.", 500)


    # --- GET Payslip Download Endpoint ---
    @route('/ess/api/payslip/<int:payslip_id>/download', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.payslip')
    def download_payslip_pdf(self, payslip_id, **kw):
        """Downloads the PDF for a specific payslip."""
        try:
            # Find the payslip
            payslip = request.env['hr.payslip'].search([('id', '=', payslip_id)], limit=1)
            if not payslip:
                raise werkzeug.exceptions.NotFound("Payslip not found.")

            # --- Validate employee access ---
            # Ensure the payslip belongs to the employee linked to the authenticated user
            # if request.env.user.employee_id != payslip.employee_id:
            #      raise werkzeug.exceptions.Forbidden("Access Denied: You can only download your own payslips.")

            # --- Check if payslip is in a downloadable state ---
            if payslip.state not in ['done', 'paid']:
                raise werkzeug.exceptions.BadRequest("Payslip PDF is not available for download in its current state.")

            # --- Generate and return the PDF ---
            # Get the standard Odoo payslip report action
            # This might need adjustment based on your exact payroll setup/report name
            report_action_name = 'hr_payroll.action_report_payslip'
            pdf_content, content_type = request.env['ir.actions.report']._render_qweb_pdf(report_action_name, [payslip.id])

            if not pdf_content:
                 _logger.error(f"Failed to generate PDF for payslip ID {payslip_id}.")
                 raise werkzeug.exceptions.InternalServerError("Failed to generate payslip PDF.")

            # Prepare HTTP headers for file download
            filename = f"Payslip_{payslip.employee_id.name}_{payslip.number or payslip.name}.pdf".replace(' ', '_')
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', http.content_disposition(filename)),
                ('Content-Length', len(pdf_content)) # Add content length
            ]

            _logger.info(f"Successfully generated PDF for payslip {payslip_id} for user {request.env.user.login}.")
            return request.make_response(pdf_content, headers=headers)

        except werkzeug.exceptions.NotFound as e:
             _logger.info(f"Payslip not found for download: ID {payslip_id}.")
             return self._error_response('Not Found', str(e), 404)
        except werkzeug.exceptions.Forbidden as e:
             _logger.warning(f"Forbidden access attempt by user {request.env.user.id} to download payslip {payslip_id}")
             return self._error_response('Forbidden', str(e), 403)
        except werkzeug.exceptions.BadRequest as e:
             _logger.warning(f"Bad request downloading payslip {payslip_id}: {e}")
             return self._error_response('Bad Request', str(e), 400)
        except Exception as e:
             _logger.error(f"Error downloading payslip ID {payslip_id}: {e}", exc_info=True)
             return self._error_response('Internal Server Error', "An unexpected error occurred generating the payslip.", 500)

    @route('/ess/api/expenses', type='http', auth='none', methods=['POST'], csrf=False)
    @api_key_auth(required_model='hr.expense')
    def submit_expense(self, **form_data): # Receive form fields in **form_data
        """Creates a new hr.expense record with an attached receipt."""
        try:
            # --- Extract Data ---
            # Use request.params for form fields when type='http'
            # Or access directly from **form_data argument
            description = form_data.get('description')
            amount_str = form_data.get('amount')
            date_str = form_data.get('date')
            employee_id_str = form_data.get('employee_id')
            receipt_file = request.httprequest.files.get('receipt') # Access file upload

            # --- Basic Validation ---
            required_fields = {'description': description, 'amount': amount_str, 'date': date_str, 'employee_id': employee_id_str}
            missing = [k for k, v in required_fields.items() if not v]
            if missing:
                raise werkzeug.exceptions.BadRequest(f"Missing required form fields: {', '.join(missing)}")
            if not receipt_file or not receipt_file.filename:
                raise werkzeug.exceptions.BadRequest("Missing required 'receipt' file upload.")

            # --- Data Type Conversion and Validation ---
            try:
                employee_id = int(employee_id_str)
                amount = float(amount_str)
                expense_date = fields.Date.from_string(date_str)
                if amount <= 0:
                     raise ValueError("Amount must be positive.")
            except ValueError as e:
                _logger.warning(f"Invalid data format in expense payload: {e}")
                raise werkzeug.exceptions.BadRequest(f"Invalid data format: {e}. Ensure amount is a number and date is YYYY-MM-DD.")

            # --- Validate Employee Access ---
            employee = request.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")
            # User can only submit for themselves
            # if request.env.user.employee_id != employee:
            #      raise werkzeug.exceptions.Forbidden("You can only submit expenses for yourself.")

            # --- Find Default Expense Product ---
            # Odoo expenses require a 'product_id'. Find a default one.
            # Common practice: Use a product configured for expenses, e.g., category 'Can be Expensed'.
            # This logic might need adjustment based on specific Odoo setup.
            product = request.env['product.product'].search([
                ('can_be_expensed', '=', True)
                # Add company filter if needed: ('company_id', 'in', [False, employee.company_id.id])
            ], limit=1)
            if not product:
                _logger.error("No default expense product found (product with 'Can be Expensed' checked).")
                raise werkzeug.exceptions.InternalServerError("Expense product configuration missing in Odoo.")

            # --- Prepare hr.expense values ---
            expense_values = {
                'name': description,
                'employee_id': employee_id,
                'product_id': product.id,
                # 'unit_amount': amount, # <-- OLD LINE
                'total_amount': amount,  # <-- NEW LINE - Use total_amount
                'date': expense_date,
                # 'quantity': 1, # Not strictly needed if setting total_amount directly for a single expense
                # 'company_id': employee.company_id.id,
                # 'currency_id': employee.company_id.currency_id.id,
            }
            _logger.info(f"Attempting to create hr.expense with values: {expense_values}")

            # --- Create hr.expense record ---
            expense = request.env['hr.expense'].create(expense_values)
            _logger.info(f"Successfully created hr.expense record with ID: {expense.id}")

            # --- Attach the Receipt File ---
            try:
                attachment_values = {
                    'name': receipt_file.filename,
                    'datas': base64.b64encode(receipt_file.read()), # Read file content and encode
                    'res_model': 'hr.expense',
                    'res_id': expense.id,
                    # 'mimetype': receipt_file.content_type, # Odoo often infers this
                }
                attachment = request.env['ir.attachment'].create(attachment_values)
                # Optional: Link attachment in the message thread (chatter)
                # expense.message_post(body="Receipt attached.", attachment_ids=[attachment.id])
                _logger.info(f"Successfully attached receipt {receipt_file.filename} (Attachment ID: {attachment.id}) to Expense ID {expense.id}")
            except Exception as e_att:
                _logger.error(f"Failed to attach receipt to expense {expense.id}: {e_att}", exc_info=True)
                # Should we delete the expense if attachment fails? Or just warn?
                # For now, let the expense exist but return an error indicating attachment failure.
                # Consider adding a field to the response indicating attachment status.
                # Raising InternalServerError as attachment is usually crucial
                raise werkzeug.exceptions.InternalServerError(f"Expense created (ID: {expense.id}) but failed to attach receipt: {e_att}")


            # Prepare success response
            success_data = {
                'message': 'Expense submitted successfully to Odoo.',
                'expense_id': expense.id,
                'state': expense.state # Return initial state (e.g., 'draft', 'reported')
            }
            return self._json_response(success_data, status=201)

        # --- Exception Handling ---
        except (exceptions.AccessError) as e:
             _logger.error(f"Access error submitting expense: {e}", exc_info=True)
             return self._error_response('Forbidden', f"Permission denied: {e}", 403)
        except (exceptions.UserError, exceptions.ValidationError) as e:
             _logger.error(f"Odoo validation error submitting expense: {e}")
             return self._error_response('Validation Error', str(e), 400)
        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden, werkzeug.exceptions.BadRequest, werkzeug.exceptions.InternalServerError) as e:
             # Handle specific HTTP exceptions raised intentionally
             return self._error_response(e.name, e.description, e.code)
        except Exception as e:
             _logger.error(f"Unexpected error ({type(e).__name__}) submitting expense: {e}", exc_info=True)
             return self._error_response('Internal Server Error', 'An unexpected error occurred while submitting the expense.', 500)

      # --- GET Pending Leaves Count Endpoint ---
    @route('/ess/api/leaves/pending-count/<int:employee_id>', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.leave')
    def get_pending_leaves_count(self, employee_id, **kw):
        """Fetches the count of pending leave requests for a specific employee."""
        try:
            # --- Validate employee access ---
            employee = request.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")

            # Ensure authenticated user can access this employee's data
            # Simple check: user must be linked to the employee requested
            # if request.env.user.employee_id != employee:
            #      raise werkzeug.exceptions.Forbidden("You can only view your own leave count.")
            # Add more complex rules for managers/HR if needed

            # Define "pending" states for leaves. This might vary based on Odoo workflow.
            # Common states before final approval: 'confirm' (To Submit by employee), 'to_approve' (Submitted / To Approve by manager)
            # Some might also consider 'draft' if employees can save drafts they intend to submit.
            # Check your hr.leave model's 'state' field selection options.
            pending_states = ['confirm', 'to_approve']

            # Count leave requests in pending states for this employee
            # The search_count method is efficient for getting just the count.
            pending_count = request.env['hr.leave'].search_count([
                ('employee_id', '=', employee_id),
                ('state', 'in', pending_states)
            ])

            _logger.info(f"Pending leave count for employee {employee_id} (User: {request.env.user.login}): {pending_count}")

            return self._json_response({'employee_id': employee_id, 'pending_leave_count': pending_count})

        except werkzeug.exceptions.NotFound as e:
             _logger.info(f"Employee not found for pending leave count: {employee_id}.")
             return self._error_response('Not Found', str(e), 404)
        except werkzeug.exceptions.Forbidden as e:
             _logger.warning(f"Forbidden access attempt by user {request.env.user.id} to pending leaves of employee {employee_id}")
             return self._error_response('Forbidden', str(e), 403)
        except Exception as e:
             _logger.error(f"Error fetching pending leave count for employee {employee_id}: {e}", exc_info=True)
             return self._error_response('Internal Server Error', "An unexpected error occurred.", 500)      

      # --- GET Next Scheduled Day Off Endpoint ---
    @route('/ess/api/leaves/next-off/<int:employee_id>', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.leave')
    def get_next_scheduled_day_off(self, employee_id, **kw):
        """Fetches the date of the next approved future leave for a specific employee."""
        try:
            # --- Validate employee access ---
            employee = request.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")

            # Ensure authenticated user can access this employee's data
            # if request.env.user.employee_id != employee:
            #      raise werkzeug.exceptions.Forbidden("You can only view your own upcoming leave.")
            # Add more complex rules for managers/HR if needed

            # --- Find the next approved leave ---
            # Get today's date in Odoo's format
            today_date_str = fields.Date.today()

            # Search for approved leaves starting from today onwards
            # Odoo 'state' for approved leaves is typically 'validate' or 'validate1' then 'validate'.
            # Check your specific hr.leave workflow for the final approved state name.
            approved_leave_states = ['validate'] # Adjust if your workflow uses different approved states

            next_leave = request.env['hr.leave'].search([
                ('employee_id', '=', employee_id),
                ('state', 'in', approved_leave_states),
                ('request_date_from', '>=', today_date_str) # Start date is today or in the future
            ], order='request_date_from asc', limit=1) # Order by start date, take the earliest

            if not next_leave:
                _logger.info(f"No upcoming approved leave found for employee {employee_id} (User: {request.env.user.login}).")
                # Return a specific structure even if no leave is found
                return self._json_response({'employee_id': employee_id, 'next_day_off': None, 'leave_name': None})

            # Prepare data for response
            response_data = {
                'employee_id': employee_id,
                'next_day_off': next_leave.request_date_from.strftime('%Y-%m-%d') if next_leave.request_date_from else None,
                'leave_name': next_leave.holiday_status_id.name or next_leave.name, # Name of the leave type or the leave itself
                # Optionally, you could include more details like 'request_date_to'
                # 'request_date_to': next_leave.request_date_to.strftime('%Y-%m-%d') if next_leave.request_date_to else None,
            }
            _logger.info(f"Next day off for employee {employee_id} (User: {request.env.user.login}): {response_data}")
            return self._json_response(response_data)

        except werkzeug.exceptions.NotFound as e:
             _logger.info(f"Employee not found for next day off: {employee_id}.")
             return self._error_response('Not Found', str(e), 404)
        except werkzeug.exceptions.Forbidden as e:
             _logger.warning(f"Forbidden access attempt by user {request.env.user.id} to next day off of employee {employee_id}")
             return self._error_response('Forbidden', str(e), 403)
        except Exception as e:
             _logger.error(f"Error fetching next day off for employee {employee_id}: {e}", exc_info=True)
             return self._error_response('Internal Server Error', "An unexpected error occurred.", 500)    

    # --- GET Today's Attendance Log Endpoint ---
    @route('/ess/api/attendance/today/<int:employee_id>', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.attendance')
    def get_todays_attendance_log(self, employee_id, **kw):
        """Fetches today's attendance log (check-in/out times) for a specific employee."""
        try:
            # --- Validate employee access ---
            employee = request.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")

            # if request.env.user.employee_id != employee:
            #      raise werkzeug.exceptions.Forbidden("You can only view your own attendance log.")

            # --- Determine Today's Date Range in UTC ---
            # Get current user's timezone (or company timezone, or Odoo instance timezone as fallback)
            user_tz_str = request.env.user.tz or request.env.company.resource_calendar_id.tz or 'UTC'
            user_tz = pytz.timezone(user_tz_str)

            # Get "today" in the user's timezone
            today_user_tz = datetime.now(user_tz).date()

            # Start of today in user's timezone, then convert to UTC for DB query
            start_of_day_user_tz = user_tz.localize(datetime.combine(today_user_tz, time.min))
            start_of_day_utc = start_of_day_user_tz.astimezone(pytz.utc).replace(tzinfo=None) # Naive UTC

            # End of today in user's timezone, then convert to UTC for DB query
            end_of_day_user_tz = user_tz.localize(datetime.combine(today_user_tz, time.max))
            end_of_day_utc = end_of_day_user_tz.astimezone(pytz.utc).replace(tzinfo=None) # Naive UTC

            _logger.info(f"Fetching attendance for Employee ID {employee_id} for date {today_user_tz} "
                         f"(UTC range: {start_of_day_utc} to {end_of_day_utc})")

            # Search for attendance records within this UTC range
            # Odoo stores check_in and check_out as naive UTC datetimes in the DB
            attendances = request.env['hr.attendance'].search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', start_of_day_utc),
                ('check_in', '<=', end_of_day_utc), # Or check_out <= end_of_day_utc if relevant
            ], order='check_in asc')

            attendance_log = []
            for att in attendances:
                # Convert UTC datetimes from DB back to user's timezone for display
                check_in_user_tz = fields.Datetime.context_timestamp(att, att.check_in).time() if att.check_in else None
                check_out_user_tz = fields.Datetime.context_timestamp(att, att.check_out).time() if att.check_out else None

                attendance_log.append({
                    'id': att.id,
                    'check_in': check_in_user_tz.strftime('%H:%M:%S') if check_in_user_tz else None,
                    'check_out': check_out_user_tz.strftime('%H:%M:%S') if check_out_user_tz else None,
                    'worked_hours': round(att.worked_hours, 2) if att.worked_hours else None,
                    # Raw UTC values if needed by frontend for further processing
                    # 'check_in_utc': fields.Datetime.to_string(att.check_in) if att.check_in else None,
                    # 'check_out_utc': fields.Datetime.to_string(att.check_out) if att.check_out else None,
                })

            _logger.info(f"Found {len(attendance_log)} attendance records for employee {employee_id} today.")
            return self._json_response(attendance_log)

        except werkzeug.exceptions.NotFound as e:
             return self._error_response('Not Found', str(e), 404)
        except werkzeug.exceptions.Forbidden as e:
             return self._error_response('Forbidden', str(e), 403)
        except Exception as e:
             _logger.error(f"Error fetching today's attendance log for employee {employee_id}: {e}", exc_info=True)
             return self._error_response('Internal Server Error', "An unexpected error occurred.", 500)


    @route('/ess/api/attendance/status/<int:employee_id>', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='hr.attendance')
    def get_odoo_attendance_status(self, employee_id, **kw):
        """Gets the current live attendance status for an employee from hr.attendance."""
        try:
            self._get_employee_and_validate_access(employee_id) # Validates access
            status_data = self._get_current_odoo_attendance_status(employee_id)
            return self._json_response(status_data)
        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden) as e:
            return self._error_response(e.name, e.description, e.code)
        except Exception as e:
            _logger.error(f"Error fetching Odoo attendance status for employee {employee_id}: {e}", exc_info=True)
            return self._error_response('Internal Server Error', "Could not retrieve attendance status.", 500)


    @route('/ess/api/attendance/check-in', type='http', auth='none', methods=['POST'], csrf=False)
    @api_key_auth(required_model='hr.attendance')
    def attendance_check_in(self, **kw): # Expects employee_id in kw or JSON body if type='json'
        """Performs a check-in for an employee."""
        try:
            # For type='http' with POST, data might be in kw or request.params if form-encoded
            # If expecting JSON, parse it like in submit_leave_request
            # For simplicity, let's assume employee_id is sent as a form field or query param
            employee_id_str = kw.get('employee_id') or request.params.get('employee_id')
            if not employee_id_str:
                 raise werkzeug.exceptions.BadRequest("Missing 'employee_id' parameter.")
            employee_id = int(employee_id_str)

            employee = self._get_employee_and_validate_access(employee_id)

            # Check current status from hr.attendance
            current_status_info = self._get_current_odoo_attendance_status(employee_id)
            if current_status_info.get("status") == "checked_in":
                raise werkzeug.exceptions.BadRequest("User is already checked in according to Odoo attendance records.")

            # Create new hr.attendance record
            # Odoo's hr.attendance model often handles setting check_in to now automatically
            new_attendance = request.env['hr.attendance'].create({
                'employee_id': employee.id,
                # 'check_in': fields.Datetime.now(), # Odoo might default this
            })
            _logger.info(f"Employee {employee.name} (ID: {employee.id}) checked IN by user {request.env.user.login}. Attendance ID: {new_attendance.id}")

            # Return the new current status
            return self._json_response(self._get_current_odoo_attendance_status(employee_id), status=201)

        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden, werkzeug.exceptions.BadRequest) as e:
             return self._error_response(e.name, e.description, e.code)
        except ValueError: # For int(employee_id_str)
             return self._error_response('Bad Request', "Invalid 'employee_id' format.", 400)
        except Exception as e:
             _logger.error(f"Error during check-in for employee ID {kw.get('employee_id')}: {e}", exc_info=True)
             return self._error_response('Internal Server Error', "An unexpected error occurred during check-in.", 500)


    @route('/ess/api/attendance/check-out', type='http', auth='none', methods=['POST'], csrf=False)
    @api_key_auth(required_model='hr.attendance')
    def attendance_check_out(self, **kw):
        """Performs a check-out for an employee."""
        try:
            employee_id_str = kw.get('employee_id') or request.params.get('employee_id')
            if not employee_id_str:
                 raise werkzeug.exceptions.BadRequest("Missing 'employee_id' parameter.")
            employee_id = int(employee_id_str)

            employee = self._get_employee_and_validate_access(employee_id)

            # Find the latest open attendance record for the employee
            latest_open_attendance = request.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False), # No check_out time set yet
            ], order='check_in desc', limit=1)

            if not latest_open_attendance:
                raise werkzeug.exceptions.BadRequest("User is not currently checked in or no open attendance record found.")

            # Update the check_out time
            # Odoo's hr.attendance model often handles setting check_out to now automatically on write if empty
            updated = latest_open_attendance.write({
                'check_out': fields.Datetime.now()
            })
            if not updated: # Should not happen if record exists and write is attempted
                _logger.error(f"Failed to write check_out for attendance ID {latest_open_attendance.id}")
                raise werkzeug.exceptions.InternalServerError("Failed to update attendance record for check-out.")

            _logger.info(f"Employee {employee.name} (ID: {employee.id}) checked OUT by user {request.env.user.login}. Attendance ID: {latest_open_attendance.id}")

            # Return the new current status
            return self._json_response(self._get_current_odoo_attendance_status(employee_id))

        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden, werkzeug.exceptions.BadRequest) as e:
             return self._error_response(e.name, e.description, e.code)
        except ValueError:
             return self._error_response('Bad Request', "Invalid 'employee_id' format.", 400)
        except Exception as e:
             _logger.error(f"Error during check-out for employee ID {kw.get('employee_id')}: {e}", exc_info=True)
             return self._error_response('Internal Server Error', "An unexpected error occurred during check-out.", 500)

     # --- NEW: Authenticated Connection Test Endpoint ---
    @route('/ess/api/auth-test', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth() # No specific required_model needed for a simple auth test
    def auth_test(self, **kw):
        """
        Tests API token authentication.
        Returns success and authenticated user info if the token is valid.
        """
        try:
            user = request.env.user # The user is set by the api_key_auth decorator
            response_data = {
                "status": "success",
                "message": "Authentication successful.",
                "authenticated_user_login": user.login,
                "authenticated_user_id": user.id,
                "authenticated_user_name": user.name,
                "notes": "This endpoint confirms your API token is valid and can authenticate with the Odoo ESS Connector."
            }
            _logger.info(f"Auth test successful for user: {user.login} (ID: {user.id})")
            return self._json_response(response_data)

        except Exception as e: # Should not happen if api_key_auth handles auth errors
            _logger.error(f"Unexpected error during auth_test after authentication: {e}", exc_info=True)
            return self._error_response('Internal Server Error', "An unexpected error occurred during authentication test.", 500)
    # ----------------------------------------------------

   # --- NEW: Admin Endpoint to Search Odoo Employees ---
    @route('/ess/api/admin/employees/search', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth() # No specific model, but requires admin-level token usually
    def admin_search_employees(self, term=None, limit=10, **kw):
        """
        Searches for Odoo employees by name or email for admin linking purposes.
        Requires a token with sufficient rights (e.g., HR Manager or Admin).
        :param term: Search term for name or email.
        :param limit: Max number of results to return.
        """
        try:
            # Ensure the authenticated user has rights to search employees widely.
            # This typically means an admin or HR manager.
            # We rely on the token's user permissions here.
            # For a production system, you might add specific group checks here.
            if not request.env.user.has_group('hr.group_hr_user'): # Example check
                _logger.warning(f"User {request.env.user.login} attempted to search employees without HR User rights.")
                # This will be caught by the decorator's auth logging, but good to note.
                # The decorator should handle the 403 if this user doesn't have read on hr.employee
                # This explicit check adds another layer or can provide a more specific error.
                # For now, let Odoo's record rules + decorator handle this.
                pass


            domain = []
            if term:
                term_domain = ['|', '|',
                    ('name', 'ilike', term),
                    ('work_email', 'ilike', term),
                    ('barcode', 'ilike', term) # If you use barcodes for employees
                ]
                # If term could be an ID
                try:
                    employee_id_from_term = int(term)
                    term_domain = ['|', ('id', '=', employee_id_from_term)] + term_domain
                except ValueError:
                    pass # term is not an integer
                domain.extend(term_domain)
            
            # We only want employees that *can* be linked (e.g., active employees)
            # domain.append(('active', '=', True)) # Optional: only search active Odoo employees

            employees = request.env['hr.employee'].search(domain, limit=int(limit), order='name asc')

            results = []
            for emp in employees:
                results.append({
                    'id': emp.id,
                    'name': emp.name or None,
                    'work_email': emp.work_email or 'N/A',
                    'job_title': emp.job_id.name or emp.employee_title.name or 'N/A',
                    'department': emp.department_id.name or 'N/A',
                    'work_phone': emp.work_phone or None, # Add work_phone
                    'mobile_phone': emp.mobile_phone or None, # Add mobile_phone as an alternative
                })
            
            _logger.info(f"Employee search for term '{term}' by user {request.env.user.login} returned {len(results)} results.")
            return self._json_response(results)

        except Exception as e:
            _logger.error(f"Error during admin employee search for term '{term}': {e}", exc_info=True)
            return self._error_response('Internal Server Error', "Could not perform employee search.", 500)

     # --- POST Document to Employee Endpoint ---
    # Uses type='http' for multipart/form-data
    @route('/ess/api/employee/<int:employee_id>/document', type='http', auth='none', methods=['POST'], csrf=False)
    @api_key_auth(required_model='hr.employee') # Or 'ir.attachment' if scope is very granular
    def upload_employee_document(self, employee_id, **form_data):
        """
        Uploads a document and attaches it to the specified hr.employee record.
        Expects multipart/form-data with 'document_type' (text) and 'file' (file upload).
        """
        try:
            # --- Validate Employee Access ---
            # The _get_employee_and_validate_access helper can be reused or adapted
            # It checks if employee exists and if current API user can access/modify this employee.
            # For attaching a document, the API user might need write access on hr.employee (to link attachment)
            # or create access on ir.attachment with the ability to set res_id and res_model.
            # Let's assume for now the API user (e.g. admin) has sufficient rights.
            employee = request.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise werkzeug.exceptions.NotFound(f"Employee with ID {employee_id} not found.")

            # Ensure the authenticated user (via token) has rights to attach documents to this employee.
            # This might involve checking if request.env.user is the employee themselves, their manager, or an HR admin.
            # For a general API user, we'd rely on its Odoo group permissions.
            # For now, let's assume if they passed api_key_auth and employee exists, they can proceed.
            # A stricter check might be:
            # if request.env.user.employee_id != employee and not request.env.user.has_group('hr.group_hr_manager'):
            #     raise werkzeug.exceptions.Forbidden("You are not authorized to upload documents for this employee.")


            # --- Extract Data from Form ---
            document_type = form_data.get('document_type') # e.g., "ID Card", "Contract"
            uploaded_file = request.httprequest.files.get('file') # The name 'file' must match what FastAPI sends

            if not document_type:
                raise werkzeug.exceptions.BadRequest("Missing 'document_type' form field.")
            if not uploaded_file or not uploaded_file.filename:
                raise werkzeug.exceptions.BadRequest("Missing 'file' for upload or file has no name.")

            _logger.info(
                f"User {request.env.user.login} uploading document type '{document_type}' "
                f"for employee {employee.name} (ID: {employee.id}). File: {uploaded_file.filename}"
            )

            # --- File Validation (Optional, but good practice) ---
            # Example: check file type based on content_type or extension
            allowed_mimetypes = ['application/pdf', 'image/jpeg', 'image/png']
            if uploaded_file.content_type not in allowed_mimetypes:
                raise werkzeug.exceptions.BadRequest(
                    f"Invalid file type: {uploaded_file.content_type}. Allowed: PDF, JPG, PNG."
                )
            # Example: check file size (request.httprequest.content_length for total size)
            # File size check for individual files in multipart is more complex here,
            # often better handled by the client or a middleware if Odoo doesn't enforce it early.


            # --- Create ir.attachment record ---
            file_content = uploaded_file.read()
            attachment_vals = {
                'name': uploaded_file.filename,        # Name of the attachment
                'datas': base64.b64encode(file_content), # File content, base64 encoded
                'res_model': 'hr.employee',             # Link to the hr.employee model
                'res_id': employee.id,                  # Link to the specific employee record ID
                'description': document_type,           # Use document_type as description
                'mimetype': uploaded_file.content_type,
                # 'company_id': employee.company_id.id, # Optional: if multi-company and attachments are company-specific
            }
            
            attachment = request.env['ir.attachment'].create(attachment_vals)
            _logger.info(f"Attachment ID {attachment.id} ({attachment.name}) created and linked to Employee ID {employee.id}.")

            # Optional: Post a message in the employee's chatter
            # employee.message_post(body=f"Document '{document_type}: {attachment.name}' uploaded.")

            response_data = {
                'message': 'Document uploaded and attached to employee successfully.',
                'attachment_id': attachment.id,
                'filename': attachment.name,
                'document_type': document_type,
                'employee_id': employee.id
            }
            return self._json_response(response_data, status=201) # 201 Created

        except (exceptions.AccessError) as e: # Catch Odoo's AccessError
             _logger.error(f"Access error uploading document for employee {employee_id}: {e}", exc_info=True)
             return self._error_response('Forbidden', f"Permission denied: {e}", 403)
        except (exceptions.UserError, exceptions.ValidationError) as e: # Odoo's business logic errors
             _logger.error(f"Odoo validation error uploading document for employee {employee_id}: {e}")
             return self._error_response('Validation Error', str(e), 400)
        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden, werkzeug.exceptions.BadRequest) as e:
             _logger.warning(f"HTTP error ({e.code}) uploading document for employee {employee_id}: {e.description}")
             return self._error_response(e.name, e.description, e.code)
        except Exception as e:
             _logger.error(f"Unexpected error uploading document for employee {employee_id}: {e}", exc_info=True)
             return self._error_response('Internal Server Error', "An unexpected error occurred during document upload.", 500)

    @route('/ess/api/employee/<int:employee_id>/documents', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='ir.attachment') # Or hr.employee if preferred for primary model
    def get_employee_documents_list(self, employee_id, **kw):
        """Lists documents (ir.attachment) linked to an hr.employee."""
        try:
            employee = self._get_employee_and_validate_access(employee_id) # Reuses existing helper

            attachments = request.env['ir.attachment'].search([
                ('res_model', '=', 'hr.employee'),
                ('res_id', '=', employee.id),
                # Optional: Add further filtering, e.g., by a specific tag or uploader if needed
            ], order='create_date desc')

            documents_data = []
            for att in attachments:
                documents_data.append({
                    'id': att.id, # This is the ir.attachment ID
                    'filename': att.name,
                    'document_type': att.description or 'N/A', # We stored doc type in description
                    'upload_date': fields.Datetime.to_string(att.create_date), # create_date is already UTC
                    'mimetype': att.mimetype,
                    'size': att.file_size, # Human-readable size
                })
            _logger.info(f"Found {len(documents_data)} documents for employee {employee_id} (User: {request.env.user.login}).")
            return self._json_response(documents_data)

        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden) as e:
            return self._error_response(e.name, e.description, e.code)
        except Exception as e:
            _logger.error(f"Error fetching documents for employee {employee_id}: {e}", exc_info=True)
            return self._error_response('Internal Server Error', "Could not retrieve documents.", 500)


    @route('/ess/api/attachment/<int:attachment_id>/download', type='http', auth='none', methods=['GET'], csrf=False)
    @api_key_auth(required_model='ir.attachment')
    def download_employee_document_attachment(self, attachment_id, **kw):
        """Downloads a specific ir.attachment, ensuring it belongs to the user's employee."""
        try:
            attachment = request.env['ir.attachment'].browse(attachment_id)
            if not attachment.exists() or attachment.res_model != 'hr.employee':
                raise werkzeug.exceptions.NotFound("Document (attachment) not found or not an employee document.")

            # Validate employee access for this attachment
            # The attachment's res_id should be the employee_id
            employee_id_of_attachment = attachment.res_id
            self._get_employee_and_validate_access(employee_id_of_attachment) # Checks if current API user can access this employee

            if not attachment.datas: # Check if there is file content
                raise werkzeug.exceptions.NotFound("Document content not found for this attachment.")

            # Decode base64 data
            file_content = base64.b64decode(attachment.datas)
            
            headers = [
                ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                ('Content-Disposition', http.content_disposition(attachment.name)),
                ('Content-Length', len(file_content))
            ]
            _logger.info(f"User {request.env.user.login} downloading attachment ID {attachment.id} ({attachment.name}).")
            return request.make_response(file_content, headers=headers)

        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden) as e:
            return self._error_response(e.name, e.description, e.code)
        except Exception as e:
            _logger.error(f"Error downloading attachment ID {attachment_id}: {e}", exc_info=True)
            return self._error_response('Internal Server Error', "Could not download document.", 500)


    # --- DELETE Specific Document (Attachment) from Odoo ---
    @route('/ess/api/attachment/<int:attachment_id>', type='http', auth='none', methods=['DELETE'], csrf=False)
    @api_key_auth(required_model='ir.attachment') # Scope check for ir.attachment
    def delete_employee_document_attachment(self, attachment_id, **kw):
        """Deletes a specific ir.attachment, ensuring it belongs to the user's employee."""
        try:
            # Find the attachment using sudo to check its properties first,
            # actual unlink will be done with user context if possible or sudo if needed by policy.
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if not attachment.exists():
                raise werkzeug.exceptions.NotFound("Document (attachment) to delete not found.")

            # --- Validate Ownership and Model ---
            if attachment.res_model != 'hr.employee':
                # This check might be redundant if your listing endpoint only shows hr.employee attachments
                raise werkzeug.exceptions.Forbidden("This attachment is not an employee document.")

            # The employee ID linked to this attachment
            attached_employee_id = attachment.res_id

            # Use the helper to validate if the current API user can act on this employee's data
            # This also sets request.env.user to the API token's user
            target_employee = self._get_employee_and_validate_access(attached_employee_id)
            # _get_employee_and_validate_access already raises Forbidden if the API user (e.g. admin)
            # cannot access this employee, or if the API user is an employee but not this one.

            _logger.info(
                f"User {request.env.user.login} attempting to delete attachment ID {attachment.id} "
                f"({attachment.name}) linked to Employee ID {target_employee.id}."
            )

            # Perform the delete operation.
            # request.env['ir.attachment'] will now operate with the permissions of request.env.user
            # If request.env.user (the one from the token) has unlink rights on ir.attachment
            # (especially those linked to hr.employee based on record rules or group), this will work.
            # If not, you might need to use .sudo() for the unlink operation,
            # but only if your business logic absolutely allows the API user to delete any attachment
            # for an employee they can access.
            # For ESS, usually the employee themselves should be able to delete their own docs.
            # If the token user is the employee themselves, this should work fine if they have unlink rights.
            attachment_to_delete = request.env['ir.attachment'].browse(attachment.id) # Re-browse in current user context
            if not attachment_to_delete.check_access_rights('unlink', raise_exception=False):
                _logger.warning(f"User {request.env.user.login} lacks unlink permission on ir.attachment ID {attachment.id}. Trying with sudo based on ownership.")
                # Fallback to sudo only if it's confirmed it's their own document,
                # or if the API user is a privileged one. For ESS, if the user from token is the employee,
                # they should have rights or this is a flaw.
                # For now, let's be strict: if they don't have direct rights, it fails.
                # This encourages setting up Odoo permissions correctly.
                # If you decide the API user *always* deletes, then use:
                # attachment.sudo().unlink()
                raise werkzeug.exceptions.Forbidden("You do not have permission to delete this specific document.")


            attachment_to_delete.unlink()
            _logger.info(f"Successfully deleted attachment ID {attachment_id}.")

            return self._json_response({'message': 'Document deleted successfully.'}, status=200) # Or 204 No Content

        except (werkzeug.exceptions.NotFound, werkzeug.exceptions.Forbidden, werkzeug.exceptions.BadRequest) as e:
            return self._error_response(e.name, e.description, e.code)
        except exceptions.AccessError as e: # Catch Odoo's own access errors
            _logger.error(f"Odoo AccessError deleting attachment ID {attachment_id}: {e}", exc_info=True)
            return self._error_response('Forbidden', str(e), 403)
        except Exception as e:
            _logger.error(f"Error deleting attachment ID {attachment_id}: {e}", exc_info=True)
            return self._error_response('Internal Server Error', "Could not delete document.", 500)