from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LibraryCopy(models.Model):
    _name = "library.copy"
    _description = "Library Book Copy"
    _order = "name"

    name = fields.Char(string="Інвентарний номер", required=True)
    book_id = fields.Many2one("library.book", string="Книга", required=True, ondelete="restrict")
    state = fields.Selection(
        [
            ("available", "Доступний"),
            ("loaned", "Виданий"),
            ("lost", "Втрачений"),
            ("damaged", "Пошкоджений"),
        ],
        string="Стан",
        required=True,
        default="available",
    )
    loan_ids = fields.One2many("library.loan", "copy_id", string="Історія видач")

    _sql_constraints = [
        (
            "library_copy_name_uniq",
            "unique(name)",
            "Інвентарний номер примірника має бути унікальним.",
        ),
    ]

    def write(self, vals):
        requested_state = vals.get("state")
        if requested_state and not self.env.context.get("library_rental_sync"):
            for copy in self:
                has_open_loan = self.env["library.loan"].search_count(
                    [
                        ("copy_id", "=", copy.id),
                        ("state", "in", ["active", "overdue"]),
                    ]
                )
                if requested_state == "loaned" and not has_open_loan:
                    raise ValidationError(
                        "Примірник можна позначити виданим лише за наявності активної видачі."
                    )
                if requested_state != "loaned" and has_open_loan:
                    raise ValidationError(
                        "Не можна змінити стан примірника з активною видачею."
                    )
        return super().write(vals)

    @api.constrains("book_id")
    def _check_book(self):
        if any(not copy.book_id for copy in self):
            raise ValidationError("Для кожного примірника потрібно вказати книгу.")

