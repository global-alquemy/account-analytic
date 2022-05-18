# -*- coding: utf-8 -*-
# 2018 Alquemy - Javier de las Heras <jheras@alquemy.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError
from datetime import date


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    reverse_analytic_line_id = fields.Many2one(
        string='Reverse Analytic Line',
        comodel_name='account.analytic.line',
        ondelete='set null',
        index=True,
    )

    src_reverse_analytic_line_id = fields.Many2one(
        string='Src Reverse Analytic Line',
        comodel_name='account.analytic.line',
        ondelete='cascade',
        index=True,
    )

    is_contrasiento = fields.Boolean()

    contrasiento_id = fields.Many2one(
        'account.analytic.line', sting="Contrasiento")

    def action_reverse_analytic_line_view(self):
        self.action_reverse_analytic_line()

    def action_reverse_analytic_line(self, date=fields.Date.today(), move=False, amount=0):
        if amount == 0:
            amount_dict = self.amount
        else:
            amount_dict = amount
        vals = {
            'unit_amount': (-1) * self.unit_amount,
            'amount': (-1) * amount_dict,
            'date': date,
            'time_start': False,
            'time_stop': False,
            'sheet_id': False,
            'src_reverse_analytic_line_id': self.id,
        }
        if move:
            vals['move_id'] = move
        reverse_id = self.copy(vals)
        self.reverse_analytic_line_id = reverse_id
