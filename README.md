# Odoo

[![Build Status](https://runbot.odoo.com/runbot/badge/flat/1/master.svg)](https://runbot.odoo.com/runbot)
[![Tech Doc](https://img.shields.io/badge/master-docs-875A7B.svg?style=flat&colorA=8F8F8F)](https://www.odoo.com/documentation/master)
[![Help](https://img.shields.io/badge/master-help-875A7B.svg?style=flat&colorA=8F8F8F)](https://www.odoo.com/forum/help-1)
[![Nightly Builds](https://img.shields.io/badge/master-nightly-875A7B.svg?style=flat&colorA=8F8F8F)](https://nightly.odoo.com/)

Odoo is a suite of web based open source business apps.

The main Odoo Apps include an [Open Source CRM](https://www.odoo.com/page/crm),
[Website Builder](https://www.odoo.com/app/website),
[eCommerce](https://www.odoo.com/app/ecommerce),
[Warehouse Management](https://www.odoo.com/app/inventory),
[Project Management](https://www.odoo.com/app/project),
[Billing &amp; Accounting](https://www.odoo.com/app/accounting),
[Point of Sale](https://www.odoo.com/app/point-of-sale-shop),
[Human Resources](https://www.odoo.com/app/employees),
[Marketing](https://www.odoo.com/app/social-marketing),
[Manufacturing](https://www.odoo.com/app/manufacturing),
[...](https://www.odoo.com/)

Odoo Apps can be used as stand-alone applications, but they also integrate seamlessly so you get
a full-featured [Open Source ERP](https://www.odoo.com) when you install several Apps.

## Getting started with Odoo

For a standard installation please follow the [Setup instructions](https://www.odoo.com/documentation/master/administration/install/install.html)
from the documentation.

To learn the software, we recommend the [Odoo eLearning](https://www.odoo.com/slides),
or [Scale-up, the business game](https://www.odoo.com/page/scale-up-business-game).
Developers can start with [the developer tutorials](https://www.odoo.com/documentation/master/developer/howtos.html).

## Практичне заняття №2: моделі бібліотеки та ORM

Нижче описано наявний модуль `library_rental`, розташований у
`odoo/custom_addons/library_rental`.

### Структура моделей

- `library.book` — книга: `name`, `author`, `isbn`, `publish_year`.
- `library.copy` — фізичний примірник книги: `name`, `book_id`, `state`.
- `library.member` — читач бібліотеки: `name`, `card_number`, `email`, `phone`.
- `library.loan` — видача примірника читачу: `copy_id`, `member_id`,
  `loan_date`, `due_date`, `return_date`, `state`.

Зв'язки:

- `Book.copy_ids` — `One2many` до `library.copy`.
- `Copy.book_id` — `Many2one` до `library.book`.
- `Copy.loan_ids` — `One2many` до `library.loan`.
- `Loan.copy_id` — `Many2one` до `library.copy`.
- `Member.loan_ids` — `One2many` до `library.loan`.
- `Loan.member_id` — `Many2one` до `library.member`.

`One2many` використовує зворотне поле `Many2one`: другий аргумент
`One2many` вказує поле зв'язку на дочірньому записі. Поле `id` кожного
запису Odoo створює автоматично.

Стан примірника: `available`, `loaned`, `lost`, `damaged`. Стан видачі:
`active`, `returned`, `overdue`.

### Обґрунтування `ondelete`

Усі зв'язки `Many2one` мають `ondelete="restrict"`:

- `Copy.book_id` не дозволяє видалити книгу з примірниками.
- `Loan.copy_id` не дозволяє видалити примірник і втратити історію.
- `Loan.member_id` не дозволяє видалити читача і втратити його історію.

Це свідомо зберігає історичні дані; `cascade` для цих зв'язків був би
небезпечним через каскадне видалення книги, примірників або історії.

### Обов'язковість полів

`name` та `author` обов'язкові для книги. `name` і `book_id` обов'язкові
для примірника, бо примірник без книги неможливо ідентифікувати.
`name` і унікальний `card_number` обов'язкові для читача. Для видачі
обов'язкові `copy_id`, `member_id`, `loan_date` і `due_date`: без примірника
або читача видача не має змісту, а дати потрібні для контролю строків.

### AI-generated

За доступною історією цієї сесії видно, що початковий каркас модуля був
доповнений AI-асистентом: створено моделі, views, меню, права, cron та
ORM-приклади. Точне розмежування кожного рядка як згенерованого або
написаного вручну неможливе без повної зовнішньої історії змін.

### Вручну виправлено та перевірено

Перевірено й зафіксовано `ondelete="restrict"`, `required=True`, технічні
назви моделей і полів, значення станів, ORM-домени, частковий унікальний
індекс для не більш ніж однієї відкритої видачі та синхронізацію станів
примірника і видачі. Перевірку виконано статично для Python/AST, XML, CSV
і manifest. ORM у підключеній базі даних у цій сесії не запускався.

### Результати ORM

Приклади знаходяться у
`odoo/custom_addons/library_rental/examples/library_orm_examples.py`.
Фактичні результати залежать від даних конкретної бази, тому їх не вигадано.

#### 1. Книги автора

**Результат:** `[заповнити після виконання find_books_by_author(env)]`.

Домен `[("author", "=", "Тарас Шевченко")]` означає точний збіг поля
`author`. `search()` повертає recordset `library.book`, який може бути
порожнім або містити багато записів.

#### 2. Вільні примірники книги

**Результат:** `[заповнити після виконання count_available_copies(env)]`.

Вільним вважається примірник зі станом `available`, який не має видачі
зі станом `active` або `overdue`. Тому `lost` і `damaged` не вважаються
доступними.

#### 3. Прострочені видачі

**Результат:** `[заповнити після виконання find_overdue_loans(env)]`.

Домен `state = active` і `due_date < today` знаходить активні видачі,
планова дата яких минула. Після роботи щоденного cron такі записи можуть
мати `state = overdue`; для всіх відкритих прострочених записів можна
додатково використовувати `state in ('active', 'overdue')`.

#### 4. Створення та закриття видачі

**Результат:** `[заповнити після виконання create_and_close_loan(env)]`.

`create()` перевіряє доступність примірника, автоматично ставить видачу
в `active` і примірник у `loaned`. `write({"return_date": today})`
закриває видачу: модель сама ставить `returned` і повертає примірник у
`available`. Фактична дата зберігається в `return_date`, а планова — в
`due_date`.

## Інструкція запуску в Windows

У цьому checkout фактичні шляхи такі:

- сервер: `C:\Program Files\Odoo 19\server`;
- запускний файл: `C:\Program Files\Odoo 19\server\odoo-bin`;
- конфігурація: `C:\Program Files\Odoo 19\server\odoo.conf`;
- `addons_path` уже містить `C:\Program Files\Odoo 19\server\odoo\custom_addons`.

У `odoo.conf` поле `db_name` порожнє, тому назву бази не можна визначити
з цього файла. Її потрібно підставити зі свого PostgreSQL/Odoo середовища.

```powershell
Set-Location "C:\Program Files\Odoo 19\server"
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}
$Database = "ВКАЖІТЬ_РЕАЛЬНУ_НАЗВУ_БАЗИ"
$Config = "C:\Program Files\Odoo 19\server\odoo.conf"
python .\odoo-bin -c $Config -d $Database shell
```

У Odoo shell виконайте:

```python
exec(open(
    r"C:\Program Files\Odoo 19\server\odoo\custom_addons\library_rental\examples\library_orm_examples.py",
    encoding="utf-8",
).read())
results = run_all_examples(env)
```

Для збереження виводу в текстовий лог:

```powershell
python .\odoo-bin -c $Config -d $Database shell `
    *> .\library_orm_results.txt
```

Після запуску shell виконайте наведений вище `exec(...)` і
`run_all_examples(env)`. Файл `library_orm_results.txt` з'явиться в
папці сервера.

Оновлення вже встановленого модуля:

```powershell
python .\odoo-bin -c $Config -d $Database `
    -u library_rental --stop-after-init
```

Для першого встановлення використайте `-i library_rental` замість `-u`.

## Security

If you believe you have found a security issue, check our [Responsible Disclosure page](https://www.odoo.com/security-report)
for details and get in touch with us via email.
