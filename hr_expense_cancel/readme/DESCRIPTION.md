This module lets you reset a posted employee expense back to draft, which
core refuses while a posted journal entry is attached. It draft-cancels the
payments still reconciled with that entry, unreconciles their journal lines
and deletes the entry. Reconciliations created by related modules (such as
bills from `hr_expense_invoice`) are cancelled in step.

A payment that was already unreconciled from the expense before the reset is
left untouched, because nothing links it to the expense any more.
