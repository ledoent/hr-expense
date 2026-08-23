`hr_expense_advance_clearing` links a clearing expense to the advance expense it
clears, one record to one record. That is the whole relation, and it is the same
relation the module carried before Odoo 19 removed `hr.expense.sheet`.

What the sheet used to add on top was *grouping*: one advance request covering
several purposes — say 3,000 general, 5,000 hotel and 2,000 fuel out of a single
10,000 advance — approved and paid as one document, then cleared line by line.

This bridge restores that grouping for installations that also run
`hr_expense_sheet`. It does not introduce a second link: the sheet-level
advance/clearing relation is **derived** from the per-expense links, so the two
levels cannot drift apart.

It also restores the report-level workflow buttons the sheet carried before
19.0: **Clear Advance** prefills a draft clearing report from the advance's
open lines, and **Return Advance** registers the refund of what was not spent.
