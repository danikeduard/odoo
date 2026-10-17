{
    'name': 'Library Rental',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Manage library books, copies, members, and loans',
    'depends': [
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/library_book_views.xml',
        'views/library_copy_views.xml',
        'views/library_member_views.xml',
        'views/library_loan_views.xml',
        'views/library_menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
