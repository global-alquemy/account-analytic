# -*- coding: utf-8 -*-
# 2018 Alquemy - Javier de las Heras <jheras@alquemy.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Account Analytic Distribution',
    'version': '12.0.0.0',
    'category': 'Custom',
    'license': 'AGPL-3',
    'summary': 'Account Analytic Distribution',
    'author': "Alquemy",
    'website': 'https://www.alquemy.es',
    'depends': ['alq_analytic_base', 'account_analytic_parent', 'alq_analytic_reverse', 'queue_job_batch'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/mail_template.xml',
        'views/analytic_line_view.xml',
        'views/analytic_view.xml',
        'views/period_view.xml',
    ],
    'installable': True,
}
