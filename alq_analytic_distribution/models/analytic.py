# -*- coding: utf-8 -*-
# 2018 Alquemy - Javier de las Heras <jheras@alquemy.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    period_start_id = fields.Many2one(
        string='Periodo de inicio de imputación',
        comodel_name='account.analytic.period',
        ondelete='restrict',
    )

    period_end_id = fields.Many2one(
        string='Periodo fin de imputación',
        comodel_name='account.analytic.period',
        ondelete='restrict',
    )

    account_distribution_type = fields.Selection(
        string='Account Distribution Type',
        selection=[('src_dist', 'Source Distribution'),
                   ('dest_dist', 'Destination Distribution')]
    )

    src_account_distribution_ids = fields.Many2many(
        string='Source Account Distribution',
        comodel_name='account.analytic.account',
        relation='account_analytic_distribution_rel',
        column1='src_account_analytic_id',
        column2='dest_account_analytic_id',
    )

    dest_account_distribution_ids = fields.Many2many(
        string='Destination Account Distribution',
        comodel_name='account.analytic.account',
        relation='account_analytic_distribution_rel',
        column1='dest_account_analytic_id',
        column2='src_account_analytic_id',
        domain=[('account_distribution_type', 'in', ['dest_dist'])],
    )

    brother_distribution = fields.Boolean(
        string='Brother Distribution',
    )

    is_leaf = fields.Boolean(
        string='Is Leaf',
        compute='_compute_is_leaf',
        store=True)

    amount_invoiced = fields.Float(
        string='Amount Invoiced',
        compute='_compute_amount_invoiced')

    @api.onchange('account_distribution_type', 'brother_distribution')
    def _onchange_account_distribution_type(self):
        if self.account_distribution_type == 'dest_dist':
            self.brother_distribution = True
        if self.account_distribution_type == 'src_dist':
            self.brother_distribution = False

    def _get_specific_analytical_cast(self):
        res = []
        # Buscamos las cuentas de destino
        specific_analytic_ids = self.dest_account_distribution_ids
        amount_invoiced_total = 0
        for specific_analytic_id in specific_analytic_ids:
            amount_invoiced_total += specific_analytic_id.amount_invoiced
        if amount_invoiced_total != 0:
            for specific_analytic_id in specific_analytic_ids:
                res.append((specific_analytic_id.id,
                            specific_analytic_id.amount_invoiced / amount_invoiced_total))
        return res

    @api.depends('line_ids')
    def _compute_amount_invoiced(self):
        for record in self:
            amount_invoiced = 0
            if record.is_leaf:
                amount_invoiced = record._get_amount_invoiced()
            else:
                sons = record.search([('parent_id', '=', record.id)])
                for son in sons:
                    amount_invoiced += son.amount_invoiced
            record.amount_invoiced = amount_invoiced

    def _get_amount_invoiced(self):
        self.ensure_one()
        res = 0
        if not self.brother_distribution:
            for line in self.line_ids.filtered(
                    lambda x: x.move_id and x.general_account_id.user_type_id.id == 14):
                res += line.amount
            if res < 0:
                res = 0
        else:
            brother_analytic_ids = self.env['account.analytic.account'].with_context(active_test=False).search(
                [('parent_id', '=', self.parent_id.id),
                 ('brother_distribution', '=', False)])
            for brother_analytic_id in brother_analytic_ids:
                res += brother_analytic_id.amount_invoiced
        return res

    @api.depends('parent_id')
    def _compute_is_leaf(self):
        for record in self:
            record.is_leaf = True
            sons = self.env['account.analytic.account'].with_context(active_test=False).search(
                [('parent_id', '=', record.id)])
            if sons:
                record.is_leaf = False

    def _get_analytical_cast(self, period_id):
        res = []
        # Buscamos las cuentas hermanas
        brother_analytic_ids = self.env['account.analytic.account'].with_context(active_test=False).search(
            ['&', ('parent_id', '=', self.parent_id.id),
             '&', ('id', '!=', self.id),
             '&', ('brother_distribution', '=', False),
             '&', '|', ('period_start_id', '=',
                        False), ('period_start_id.date_start', '<=', period_id.date_start),
             '|', ('period_end_id', '=', False), ('period_end_id.date_end', '>=', period_id.date_end)])
        amount_invoiced_total = 0
        for brother_analytic_id in brother_analytic_ids:
            amount_invoiced_total += brother_analytic_id.amount_invoiced
        if amount_invoiced_total != 0:
            for brother_analytic_id in brother_analytic_ids:
                res.append((brother_analytic_id.id,
                            brother_analytic_id.amount_invoiced / amount_invoiced_total))
        return res


class AccountAnalyticDistributionRel(models.Model):
    _name = 'account.analytic.distribution.rel'

    src_account_analytic_id = fields.Many2one(
        string='Source Account Analytic',
        comodel_name='account.analytic.account',
        ondelete='cascade',
        required=True,
    )

    dest_account_analytic_id = fields.Many2one(
        string='Dest. Account Analytic',
        comodel_name='account.analytic.account',
        ondelete='cascade',
        required=True,
    )


class AnalyticCastLog(models.Model):
    _name = 'analytical.cast.log'

    start_distribution_date = fields.Datetime(
        string='Start Distribution Date',
        default=fields.Datetime.now,
    )

    start_delete_date = fields.Datetime(
        string='Start Delete Date',
        default=fields.Datetime.now,
    )

    end_date = fields.Datetime(
        string='End Date',
        default=fields.Datetime.now,
    )

    row_count_start_distribution = fields.Integer(
        string='Row Count Start Distribution',
    )

    row_count_start_delete = fields.Integer(
        string='Row Count Start',
    )

    row_count_end = fields.Integer(
        string='Row Count End',
    )
