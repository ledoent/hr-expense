import {ExpenseListController} from "@hr_expense/views/list";
import {patch} from "@web/core/utils/patch";

patch(ExpenseListController.prototype, {
    // Whether the "Create Trip" button is shown: a team approver with a
    // selection of expenses that are all unlinked and in a pre-posting state.
    displayCreateTrip() {
        const records = this.model.root.selection;
        return (
            this.userIsExpenseTeamApprover &&
            records.length &&
            records.every(
                (record) =>
                    ["draft", "submitted", "approved"].includes(record.data.state) &&
                    !record.data.trip_id
            )
        );
    },
});
