# HR Expense — Trip suite demo (SMB sales-rep walk)

This branch stacks the optional **Trip** layer over the base hr-expense flow so it
can be installed + evaluated as one unit:

- `hr_expense_trip` — the optional Trip container (groups expense lines; approval
  workflow draft → request → approve → collect receipts → done; trip PDF).
- `hr_expense_advance_clearing` + `hr_expense_advance_clearing_trip` — a **trip
  advance = the budget** (cash issued for the trip, cleared against actual spend).
- `hr_expense_payment` + `hr_expense_payment_trip` — **reimburse the whole trip
  in one payment**.

The Trip is **opt-in**: nothing changes about the plain per-expense flow unless a
trip is used.

## Scenario — a sales rep on the road

**Without a trip (base flow):** the rep files each expense individually (flight,
hotel, dinner). Each is approved and reimbursed on its own; there is no budget and
no grouping — fine for the occasional expense, noisy for a multi-day trip.

**With a trip:** the rep's manager opens a **Trip** ("Q1 East Coast Sales Tour"),
issues a **$2,000 advance** as the trip budget, and approves the trip. The rep
collects receipts against the trip; **Apply Advance** clears them against the
budget (Advance Remaining tracks what's left), and **Pay Trip** reimburses any
balance in one payment. One approval, one budget, one settlement.

| Need | Base | Trip |
|---|---|---|
| Group a multi-day trip's expenses | — | trip.expense_ids |
| Budget | — | advance ( $ issued up front ) |
| Approval | per expense | one trip approval workflow |
| Reimburse | per expense | one payment (Pay Trip) |
| Document | per expense | trip PDF report |

## Screenshots
- Trip with advance budget + Apply Advance ([advance demo](https://storage.googleapis.com/ledo-pr-assets/hr-expense/pr-3/advance-clearing-trip.png)).
- Trip form + batched expenses + state machine ([trip foundation](https://storage.googleapis.com/ledo-pr-assets/hr-expense/pr-1/01-buffer-form-flow-index.png) — see hr-expense#1 for the trip walk).

## Eval
Open this branch's runboat build (admin/admin) and follow the scenario above.
Note: in 19.0, expense posting routes through `hr.expense.post.wizard`, so for the
**Pay Trip** step do *Create Bill* → confirm the post wizard → **Pay Trip**.
