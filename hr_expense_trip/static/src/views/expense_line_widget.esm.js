import {X2ManyField, x2ManyField} from "@web/views/fields/x2many/x2many_field";
import {registry} from "@web/core/registry";

// Render expense_ids (One2many, inverse trip_id) Many2many-style so the "Add"
// dialog links *existing* expenses (a plain One2many only creates new ones).
// The link/unlink (4/3) commands resolve to the inverse trip_id, not an m2m.
export class ExpenseLinesWidget extends X2ManyField {
    setup() {
        super.setup();
        // Let a row click open the hr.expense form.
        this.canOpenRecord = true;
    }

    get isMany2Many() {
        return true;
    }
}

export const expenseLinesWidget = {
    ...x2ManyField,
    component: ExpenseLinesWidget,
    additionalClasses: ["o_field_many2many"],
};

registry.category("fields").add("expense_lines_widget", expenseLinesWidget);
