# Copyright 2026 Ledo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Employee Advance Clearing on Expense Reports",
    "summary": "Group employee advances and their clearings on expense reports",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "author": "Ledo, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/hr-expense",
    "license": "AGPL-3",
    "development_status": "Alpha",
    "maintainers": ["dnplkndll"],
    "depends": ["hr_expense_advance_clearing", "hr_expense_sheet"],
    "data": ["views/hr_expense_sheet_views.xml"],
    "installable": True,
    "auto_install": True,
}
