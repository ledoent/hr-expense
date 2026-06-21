# Copyright 2024 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    """Best-effort stash of the 18.0 *sheet-level* advance/clearing link.

    In 18.0 a clearing expense report (``hr.expense.sheet``) pointed at the
    advance report it cleared via ``advance_sheet_id``. 19.0 core removes the
    ``hr.expense.sheet`` model entirely, so that column disappears with the
    table. Because ``hr_expense_advance_clearing`` depends on ``hr_expense``,
    core's migration (which drops the sheet table and fills
    ``hr.expense.former_sheet_id``) runs *before* this script — so in the
    standard upgrade path the table is already gone here and nothing is
    stashed. The primary clearing link is rebuilt in post-migration from the
    *line-level* ``hr.expense.av_line_id``, which lives on the surviving
    ``hr_expense`` table.

    Some OpenUpgrade orchestrations run addon pre-steps before core drops the
    table; when that happens we preserve the sheet link so post-migration can
    *report* (not silently guess) any clearing that the line-level pass missed.
    """
    cr = env.cr
    if not openupgrade.table_exists(
        cr, "hr_expense_sheet"
    ) or not openupgrade.column_exists(cr, "hr_expense_sheet", "advance_sheet_id"):
        _logger.info(
            "hr_expense_advance_clearing: hr.expense.sheet already removed; "
            "clearing links will be rebuilt from hr_expense.av_line_id."
        )
        return
    openupgrade.logged_query(
        cr,
        """
        CREATE TABLE IF NOT EXISTS _ou_haac_sheet_link AS
            SELECT id AS sheet_id, advance_sheet_id
            FROM hr_expense_sheet
            WHERE advance_sheet_id IS NOT NULL
        """,
    )
