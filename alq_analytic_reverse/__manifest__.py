# -*- coding: utf-8 -*-
# 2018 Alquemy - Javier de las Heras <jheras@alquemy.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Account Analytic Reverse',
    'version': '12.0.0.0',
    'category': 'Custom',
    'license': 'AGPL-3',
    'summary': 'Account Analytic Distribution',
    'author': "Alquemy",
    'website': 'https://www.alquemy.es',
    'depends': ['analytic', 'account', 'hr_timesheet'],
    'data': [
        'views/analytic_view.xml',
    ],
    'installable': True,
}
