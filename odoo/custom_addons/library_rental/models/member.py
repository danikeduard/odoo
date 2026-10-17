from odoo import fields, models


class LibraryMember(models.Model):
    _name = "library.member"
    _description = "Library Member"
    _order = "name"

    name = fields.Char(string="Ім'я та прізвище", required=True)
    card_number = fields.Char(string="Номер читацького квитка", required=True)
    email = fields.Char(string="Електронна пошта")
    phone = fields.Char(string="Телефон")
    loan_ids = fields.One2many("library.loan", "member_id", string="Видачі")

    _sql_constraints = [
        (
            "library_member_card_number_uniq",
            "unique(card_number)",
            "Номер читацького квитка має бути унікальним.",
        ),
    ]

