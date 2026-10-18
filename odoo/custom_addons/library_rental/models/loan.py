from datetime import timedelta

from psycopg2.errors import UniqueViolation

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LibraryLoan(models.Model):
    _name = "library.loan"
    _description = "Library Loan"
    _order = "loan_date desc, id desc"

    LOAN_PERIOD_DAYS = 14
    FINE_RATE_PER_DAY = 5.0

    copy_id = fields.Many2one("library.copy", string="Примірник", required=True, ondelete="restrict")
    member_id = fields.Many2one("library.member", string="Читач", required=True, ondelete="restrict")
    loan_date = fields.Date(
        string="Дата видачі",
        required=True,
        default=fields.Date.context_today,
    )
    due_date = fields.Date(
        string="Планова дата повернення",
        compute="_compute_due_date",
        store=True,
    )
    return_date = fields.Date(string="Фактична дата повернення")
    fine_amount = fields.Float(
        string="Сума штрафу",
        compute="_compute_fine_amount",
        store=True,
    )
    is_overdue = fields.Boolean(
        string="Прострочена",
        compute="_compute_is_overdue",
    )
    state = fields.Selection(
        [
            ("active", "Активна"),
            ("overdue", "Прострочена"),
            ("returned", "Повернена"),
        ],
        string="Стан",
        required=True,
        default="active",
        readonly=True,
    )

    @api.depends("loan_date")
    def _compute_due_date(self):
        for rec in self:
            if rec.loan_date:
                rec.due_date = rec.loan_date + timedelta(
                    days=self.LOAN_PERIOD_DAYS
                )
            else:
                rec.due_date = False

    @api.depends("due_date", "return_date")
    def _compute_fine_amount(self):
        for rec in self:
            rec.fine_amount = (
                (rec.return_date - rec.due_date).days * self.FINE_RATE_PER_DAY
                if rec.return_date and rec.due_date and rec.return_date > rec.due_date
                else 0.0
            )

    @api.depends("state", "due_date")
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = bool(
                rec.state in ("active", "overdue")
                and rec.due_date
                and rec.due_date < today
            )

    @api.onchange("copy_id")
    def _onchange_copy_id(self):
        if not self.copy_id:
            return
        other_active_loan = self.search(
            [
                ("copy_id", "=", self.copy_id.id),
                ("state", "in", ["active", "overdue"]),
                ("id", "!=", self._origin.id),
            ],
            limit=1,
        )
        if other_active_loan:
            return {
                "warning": {
                    "title": _("Попередження"),
                    "message": _(
                        "Для вибраного примірника вже існує інша активна видача."
                    ),
                }
            }

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
            copy = self.env["library.copy"].browse(vals.get("copy_id")).exists()
            if len(copy) != 1:
                raise ValidationError(
                    _("Видача має посилатися на один існуючий примірник.")
                )
            self.env.cr.execute(
                "SELECT id FROM library_copy WHERE id = %s FOR UPDATE", (copy.id,)
            )
            if copy.state != "available" or self.search_count(
                [("copy_id", "=", copy.id), ("state", "in", ["active", "overdue"])]
            ):
                raise ValidationError(
                    _("Цей примірник уже виданий або недоступний для видачі.")
                )
            try:
                with self.env.cr.savepoint():
                    loan = super(LibraryLoan, self).create(vals)
            except UniqueViolation as error:
                if error.diag.constraint_name != "library_loan_open_copy_uniq":
                    raise
                raise ValidationError(
                    _("Цей примірник уже має активну видачу.")
                ) from error
            copy.with_context(library_rental_sync=True).write({"state": "loaned"})
            loans |= loan
        self._update_overdue_state()
        return loans

    def write(self, vals):
        if "copy_id" in vals and any(vals["copy_id"] != loan.copy_id.id for loan in self):
            raise ValidationError(_("Не можна змінити примірник в історії видачі."))
        if "state" in vals and not self.env.context.get("library_rental_sync"):
            raise ValidationError(
                _("Стан видачі змінюється автоматично датами або поверненням.")
            )
        today = fields.Date.today()
        for loan in self:
            loan_date = fields.Date.to_date(vals.get("loan_date", loan.loan_date))
            return_date = fields.Date.to_date(vals.get("return_date", loan.return_date))
            if return_date and loan_date and return_date < loan_date:
                raise ValidationError(
                    _("Фактична дата повернення не може бути раніше дати видачі.")
                )
            if return_date and loan.state in ("active", "overdue") and return_date > today:
                raise ValidationError(
                    _("Фактична дата повернення не може бути в майбутньому.")
                )
        if "return_date" in vals:
            vals = dict(vals)
            vals["state"] = "returned" if vals["return_date"] else "active"
        result = super().write(vals)
        if vals.get("state") == "returned":
            for loan in self:
                loan.copy_id.with_context(library_rental_sync=True).write({"state": "available"})
        if (
            not self.env.context.get("library_rental_sync")
            and {"loan_date", "return_date"} & vals.keys()
        ):
            self._update_overdue_state()
        return result

    def unlink(self):
        if any(loan.state in ("active", "overdue") for loan in self):
            raise ValidationError(_("Не можна видалити активну або прострочену видачу."))
        return super().unlink()

    def action_return(self):
        self.ensure_one()
        self.write({"return_date": fields.Date.today()})
        return True

    def action_restore_active(self):
        self.ensure_one()
        self.write({"return_date": False})
        return True

    @api.model
    def _update_overdue_state(self):
        today = fields.Date.today()
        open_loans = self.search(
            [
                ("state", "in", ["active", "overdue"]),
                ("return_date", "=", False),
            ]
        )
        overdue_loans = open_loans.filtered(
            lambda loan: loan.due_date and loan.due_date < today
        )
        active_loans = open_loans - overdue_loans
        if overdue_loans:
            overdue_loans.with_context(library_rental_sync=True).write(
                {"state": "overdue"}
            )
        if active_loans:
            active_loans.with_context(library_rental_sync=True).write(
                {"state": "active"}
            )

    @api.constrains("copy_id", "state")
    def _check_active_copy_loan(self):
        for rec in self:
            if not rec.copy_id or rec.state not in ("active", "overdue"):
                continue
            if self.search_count(
                [
                    ("copy_id", "=", rec.copy_id.id),
                    ("state", "in", ["active", "overdue"]),
                    ("id", "!=", rec.id),
                ]
            ):
                raise ValidationError(
                    _("Цей примірник уже має активну видачу.")
                )

    @api.constrains("loan_date", "due_date")
    def _check_due_date(self):
        for rec in self:
            if rec.loan_date and rec.due_date and rec.due_date <= rec.loan_date:
                raise ValidationError(
                    _("Планова дата повернення має бути пізніше дати видачі.")
                )

    @api.constrains("loan_date", "return_date")
    def _check_return_date(self):
        for rec in self:
            if rec.loan_date and rec.return_date and rec.return_date < rec.loan_date:
                raise ValidationError(
                    _("Фактична дата повернення не може бути раніше дати видачі.")
                )
