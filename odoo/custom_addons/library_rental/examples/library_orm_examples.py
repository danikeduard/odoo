"""Чотири практичні приклади ORM для library_rental.

Код потрібно виконувати всередині Odoo shell, де змінна ``env`` вже існує.
Файл не створює власний ``env`` і не запускається як звичайний Python-скрипт.
"""

from odoo import fields


def find_books_by_author(env, author="Тарас Шевченко"):
    """Знаходить книги автора через точний домен ``author = author``."""
    books = env["library.book"].search([("author", "=", author)])
    for book in books:
        print(book.id, book.name, book.author, book.isbn)
    return books


def count_available_copies(env, book_name="Кобзар"):
    """Рахує примірники книги без відкритої видачі."""
    book = env["library.book"].search([("name", "=", book_name)], limit=1)
    if not book:
        print("Книгу не знайдено")
        return env["library.copy"]

    copies = env["library.copy"].search([("book_id", "=", book.id)])
    available_copies = copies.filtered(
        lambda copy: copy.state == "available"
        and not copy.loan_ids.filtered(
            lambda loan: loan.state in ("active", "overdue")
        )
    )
    print("Книга:", book.name)
    print("Усього примірників:", len(copies))
    print("Вільних примірників:", len(available_copies))
    return available_copies


def find_overdue_loans(env):
    """Знаходить активні видачі, дата повернення яких уже минула."""
    today = fields.Date.today()
    overdue_loans = env["library.loan"].search(
        [
            ("state", "=", "active"),
            ("due_date", "<", today),
        ]
    )
    for loan in overdue_loans:
        print(
            loan.id,
            loan.copy_id.display_name,
            loan.member_id.display_name,
            loan.due_date,
        )
    return overdue_loans


def create_and_close_loan(env):
    """Створює видачу для доступного примірника і закриває її через write()."""
    copies = env["library.copy"].search([("state", "=", "available")])
    copy = copies.filtered(
        lambda item: not item.loan_ids.filtered(
            lambda loan: loan.state in ("active", "overdue")
        )
    )[:1]
    member = env["library.member"].search([], limit=1)
    if not copy or not member:
        print("Створіть читача та доступний примірник перед запуском")
        return env["library.loan"]

    today = fields.Date.today()
    loan = env["library.loan"].create(
        {
            "copy_id": copy.id,
            "member_id": member.id,
            "loan_date": today,
            "due_date": fields.Date.add(today, days=14),
        }
    )
    print("Створена видача:", loan.id, loan.state, loan.copy_id.state)

    # Модель сама встановлює state=returned і повертає примірник у available.
    loan.write({"return_date": today})
    print("Закрита видача:", loan.id, loan.state, loan.copy_id.state)
    return loan


def run_all_examples(env):
    """Послідовно запускає всі чотири приклади та повертає їх recordset-и."""
    return {
        "books_by_author": find_books_by_author(env),
        "available_copies": count_available_copies(env),
        "overdue_loans": find_overdue_loans(env),
        "closed_loan": create_and_close_loan(env),
    }
