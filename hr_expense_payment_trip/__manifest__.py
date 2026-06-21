# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "HR Expense Payment Trip",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Pay all of a trip's expenses in a single payment",
    "author": "Ledo, Odoo Community Association (OCA)",
    "maintainers": ["dnplkndll"],
    "license": "AGPL-3",
    "development_status": "Alpha",
    "website": "https://github.com/OCA/hr-expense",
    "depends": ["hr_expense_payment", "hr_expense_trip"],
    "data": ["views/hr_trip_views.xml"],
    "installable": True,
    "auto_install": True,
}
