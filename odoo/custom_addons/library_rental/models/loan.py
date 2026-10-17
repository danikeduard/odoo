from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LibraryLoan(models.Model):
    _name = "library.loan"
    _description = "Library Loan"
    _order = "loan_date desc, id desc"

    copy_id = fields.Many2one("library.copy", string="Примірник", required=True, ondelete="restrict")
    member_id = fields.Many2one("library.member", string="Читач", required=True, ondelete="restrict")
    loan_date = fields.Date(string="Дата видачі", required=True, default=fields.Date.today)
    due_date = fields.Date(string="Планова дата повернення", required=True)
    return_date = fields.Date(string="Фактична дата повернення")
    state = fields.Selection(
        [
            ("active", "Активна"),
            ("returned", "Повернена"),
            ("overdue", "Прострочена"),
        ],
        string="Стан",
        required=True,
        default="active",
        readonly=True,
    )

    def init(self):
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS library_loan_open_copy_uniq
            ON library_loan (copy_id)
            WHERE state IN ('active', 'overdue')
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        loans = self.env[self._name]
        for incoming_vals in vals_list:
            vals = dict(incoming_vals)
            vals["state"] = "active"
            loan_date = fields.Date.to_date(vals.get("loan_date") or fields.Date.today())
            due_date = fields.Date.to_date(vals.get("due_date"))
            if not due_date:
                raise ValidationError("Потрібно вказати планову дату повернення.")
            if due_date < loan_date:
                raise ValidationError("Планова дата повернення не може бути раніше дати видачі.")
            copy = self.env["library.copy"].browse(vals.get("copy_id")).exists()
            if len(copy) != 1:
                raise ValidationError("Видача має посилатися на один існуючий примірник.")
            self.env.cr.execute(
                "SELECT id FROM library_copy WHERE id = %s FOR UPDATE", (copy.id,)
            )
            if copy.state != "available" or self.search_count(
                [("copy_id", "=", copy.id), ("state", "in", ["active", "overdue"])]
            ):
                raise ValidationError("Цей примірник уже виданий або недоступний для видачі.")
            try:
                with self.env.cr.savepoint():
                    loan = super(LibraryLoan, self).create(vals)
            except IntegrityError as error:
                raise ValidationError("Цей примірник уже має активну видачу.") from error
            copy.with_context(library_rental_sync=True).write({"state": "loaned"})
            loans |= loan
        return loans

    def write(self, vals):
        if "copy_id" in vals and any(vals["copy_id"] != loan.copy_id.id for loan in self):
            raise ValidationError("Не можна змінити примірник в історії видачі.")
        if "state" in vals and not self.env.context.get("library_rental_sync"):
            raise ValidationError("Стан видачі змінюється автоматично датами або поверненням.")
        today = fields.Date.today()
        for loan in self:
            loan_date = fields.Date.to_date(vals.get("loan_date", loan.loan_date))
            due_date = fields.Date.to_date(vals.get("due_date", loan.due_date))
            return_date = fields.Date.to_date(vals.get("return_date", loan.return_date))
            if due_date and loan_date and due_date < loan_date:
                raise ValidationError("Планова дата повернення не може бути раніше дати видачі.")
            if return_date and loan_date and return_date < loan_date:
                raise ValidationError("Фактична дата повернення не може бути раніше дати видачі.")
            if return_date and loan.state in ("active", "overdue") and return_date > today:
                raise ValidationError("Фактична дата повернення не може бути в майбутньому.")
        if "return_date" in vals:
            vals = dict(vals)
            vals["state"] = "returned" if vals["return_date"] else "active"
        elif "due_date" in vals and not self.env.context.get("library_rental_sync"):
            vals = dict(vals)
            vals["state"] = "overdue" if vals["due_date"] < today else "active"
        result = super().write(vals)
        if vals.get("state") == "returned":
            for loan in self:
                loan.copy_id.with_context(library_rental_sync=True).write({"state": "available"})
        return result

    def unlink(self):
        if any(loan.state in ("active", "overdue") for loan in self):
            raise ValidationError("Не можна видалити активну або прострочену видачу.")
        return super().unlink()

    def action_return(self):
        self.ensure_one()
        self.write({"return_date": fields.Date.today()})
        return True

    @api.constrains("loan_date", "due_date", "return_date")
    def _check_dates(self):
        for loan in self:
            if loan.due_date and loan.loan_date and loan.due_date < loan.loan_date:
                raise ValidationError("Планова дата повернення не може бути раніше дати видачі.")
            if loan.return_date and loan.loan_date and loan.return_date < loan.loan_date:
                raise ValidationError("Фактична дата повернення не може бути раніше дати видачі.")

    @api.model
    def _cron_update_overdue_loans(self):
        overdue_loans = self.search(
            [("state", "=", "active"), ("due_date", "<", fields.Date.today())]
        )
        if overdue_loans:
            overdue_loans.with_context(library_rental_sync=True).write({"state": "overdue"})
