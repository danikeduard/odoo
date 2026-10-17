from odoo import fields, models


class LibraryBook(models.Model):
    _name = "library.book"
    _description = "Library Book"
    _order = "name"

    name = fields.Char(string="Назва", required=True)
    author = fields.Char(string="Автор", required=True)
    isbn = fields.Char(string="ISBN")
    publish_year = fields.Integer(string="Рік видання")
    copy_ids = fields.One2many("library.copy", "book_id", string="Примірники")

