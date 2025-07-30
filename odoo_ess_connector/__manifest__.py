# -*- coding: utf-8 -*-
{
    'name': "Odoo ESS Connector",
    'summary': """Provides secure API access for external ESS SaaS portal.""",
    'description': """
        Exposes specific HR data (Employee, Attendance, Leave, Payslip, Expense)
        via REST API endpoints for integration with an external Employee Self-Service portal.
        Includes API token management and security features.
    """,
    'author': "ahmed atta / one iteration", # Change this
    
    'category': 'Human Resources/API',
    'version': '1.0.0', # Match spec
    # Specify Odoo version compatibility (adjust if needed)
    'depends': [
        'base',
        'web', # Needed for controllers
        'hr',
        'hr_attendance',
        'hr_holidays',
        'hr_payroll',
        'base_setup',
        'hr_expense',
        'documents',   # For the documents app integration if you use its features
        'account',     ],
    'data': [
        #'security/ess_security.xml', # Define security group
        'security/ir.model.access.csv', # Define model access rights
        'views/ess_api_token_views.xml', 
        'views/settings_views.xml',
        # Add views later if needed (e.g., for API Token management)
        # 'views/ess_api_token_views.xml',
        # 'views/settings_views.xml',
    ],
    'installable': True,
    'application': False, # It's not a standalone application
    'auto_install': False,
    'license': 'LGPL-3', # Or your preferred license
}