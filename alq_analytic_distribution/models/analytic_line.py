# -*- coding: utf-8 -*-
# 2018 Alquemy - Javier de las Heras <jheras@alquemy.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
import logging
from datetime import datetime
from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import (
    RetryableJobError,
)
import time

_logger = logging.getLogger(__name__)


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    period_start_id = fields.Many2one(
        string='Periodo fin de imputación',
        comodel_name='account.analytic.period',
        ondelete='restrict',
        related='account_id.period_start_id',
        readonly=True,
        store=True
    )

    period_end_id = fields.Many2one(
        string='Periodo fin de imputación',
        comodel_name='account.analytic.period',
        ondelete='restrict',
        related='account_id.period_end_id',
        readonly=True,
        store=True
    )

    distribution_type = fields.Selection(
        string='Distribution Type',
        selection=[('brother', 'Brother Account'),
                   ('specific', 'Specific Account')],
        index=True,
    )

    distribute_acc_analytic_line_ids = fields.One2many(
        string='Distribute Account Analytic Line',
        comodel_name='account.analytic.line',
        inverse_name='src_distribute_acc_analytic_line_id',
    )

    src_distribute_acc_analytic_line_id = fields.Many2one(
        string='Src Distribute Account Analytic Line',
        comodel_name='account.analytic.line',
        ondelete='cascade',
        index=True,
    )

    src_distribute_acc_analytic_id = fields.Many2one(
        string='Src Distribute Account Analytic',
        comodel_name='account.analytic.account',
        related='src_distribute_acc_analytic_line_id.account_id',
        readonly=True,
        store=True,
    )

    is_reverse_distribution = fields.Boolean(
        string='Is Reverse by Distribution',
        index=True,
    )

    @api.model
    def check_analytical_cast(self, emails):
        row_count = self.env['account.analytic.line'].search_count([])
        last_log_id = self.env['analytical.cast.log'].search([])[-1]

        body_html = "<p>El proceso de reparto ha finalizado. Se han generado " + str(row_count) + \
            " apuntes analíticos.</p>"

        email_to = emails
        subject = "Verificación de reparto analítico"

        self.send_check_analytic_by_mail(
            last_log_id.id, email_to, subject, body_html)

        last_log_id.start_delete_date = datetime.now()
        last_log_id.row_count_start_delete = row_count
        _logger.info('[RA] - ROW COUNT END - %s',
                     str(row_count))
        self.delete_analytical_cast()
        row_count = self.env['account.analytic.line'].search_count([])
        last_log_id = self.env['analytical.cast.log'].search([])[-1]
        last_log_id.end_date = datetime.now()
        last_log_id.row_count_end = row_count

    def send_check_analytic_by_mail(self, id, email_to, subject, body_html):
        template = self.env.ref(
            'alq_analytic_distribution.alq_check_analytic_notification')
        template.write({
            'email_from': self.env.user.partner_id.email,
            'email_to': email_to,
            'subject': subject,
            'body_html': body_html})
        template.send_mail(id, force_send=True)

    @api.model
    def delete_analytical_cast(self):
        self._delete_analytical_cast_process()

    def _delete_analytical_cast_process(self):
        _logger.info('[RA] - REMOVE OLD ANALYTIC LINES DISTRIBUTION')
        query = "CALL delete_analytic_distribution()"
        self.env.cr.execute(query)
        self.env.cr.commit()

    @api.model
    def generate_analytical_cast(self, detail_log=False):
        # Comprobamos que no sea sabado o domingo
        '''
        if datetime.today().weekday() == 5 or datetime.today().weekday() == 6:
            _logger.info('[RA] - NOT DISTRIBUTION DAY')
            return
        '''
        row_count = self.env['account.analytic.line'].search_count([])
        log_vals = {
            'row_count_start_distribution': row_count,
            'start_distribution_date': datetime.now(),
        }
        self.env['analytical.cast.log'].create(log_vals)
        # La BBDD debería de estar sin repartos, pero asegurarnos, la volvemos a borrar
        self.delete_analytical_cast()

        # Generamos el reparto entre cuentas especificas
        _logger.info('[RA] - START SPECIFIC DISTRIBUTION')
        analytic_account_ids = self.env['account.analytic.account'].with_context(active_test=False).search(
            [('account_distribution_type', '=', 'src_dist')])
        batch_specific = self.env['queue.job.batch'].get_new_batch('Specific')
        for analytic_account_id in analytic_account_ids:
            name_job = analytic_account_id.complete_name
            self.with_context(job_batch=batch_specific).with_delay(
                priority=15, max_retries=500, description=name_job).account_analytical_specific_cast(detail_log, analytic_account_id)
        batch_specific.enqueue()
        _logger.info('[RA] - FINISH SPECIFIC DISTRIBUTION')

        # Generamos el reparto entre cuentas hermanas
        _logger.info('[RA] - START BROTHER DISTRIBUTION')
        analytic_account_ids = self.env['account.analytic.account'].with_context(active_test=False).search(
            [('brother_distribution', '=', True)])
        period_ids = self.env['account.analytic.period'].search([])
        batch_brother = self.env['queue.job.batch'].get_new_batch('Brother')
        for period_id in period_ids:
            for analytic_account_id in analytic_account_ids:
                name_job = period_id.name + ' - ' + analytic_account_id.complete_name
                self.with_context(job_batch=batch_brother).with_delay(
                    priority=20, max_retries=500, description=name_job).account_analytical_cast(detail_log, period_id, analytic_account_id, batch_specific)

        batch_brother.enqueue()
        _logger.info('[RA] - FINISH BROTHER DISTRIBUTION')

        # Generamos reversiones
        batch_revert = self.env['queue.job.batch'].get_new_batch('Revert')
        analytic_account_ids = self.env['account.analytic.account'].with_context(active_test=False).search(
            [('brother_distribution', '=', True)])
        for analytic_account_id in analytic_account_ids:
            name_job = ' REVERTIR - ' + analytic_account_id.complete_name
            self.with_context(job_batch=batch_revert).with_delay(
                priority=25, max_retries=500, description=name_job).account_analytical_reverse(detail_log, analytic_account_id, batch_brother)

        batch_revert.enqueue()
        # Duplicamos, mandamos correo y borramos reparto de la base de datos de producción
        self.with_delay(priority=30, max_retries=500,
                        description='EMAIL - BORRAR REPARTO').check_distribution(batch_revert)

    @api.multi
    @job
    def account_analytical_specific_cast(self, detail_log, analytic_account_id):
        _logger.info('[RA] - START DISTRIBUTION TO %s',
                     analytic_account_id.name)
        analytical_cast = analytic_account_id._get_specific_analytical_cast()
        for line in analytic_account_id.line_ids.filtered(lambda x: not x.src_reverse_analytic_line_id and not x.reverse_analytic_line_id and x.amount != 0):
            line._create_specific_analytical_cast(
                analytical_cast, detail_log)
        self.env.cr.commit()
        _logger.info('[RA] - FINISH DISTRIBUTION TO %s',
                     analytic_account_id.complete_name)

    @api.multi
    @job
    def account_analytical_cast(self, detail_log, period_id, analytic_account_id, batch):
        batch.check_state()
        if batch.state != 'finished':
            time.sleep(300)
            raise RetryableJobError(
                ('Todavía hay jobs de reparto pendientes'))
        _logger.info('[RA] - START DISTRIBUTION TO %s',
                     analytic_account_id.complete_name)
        analytical_cast = analytic_account_id._get_analytical_cast(period_id)
        for line in analytic_account_id.line_ids.filtered(lambda x: not x.src_reverse_analytic_line_id and not x.reverse_analytic_line_id and x.amount != 0
                                                          and x.date >= period_id.date_start and x.date <= period_id.date_end):
            line._create_analytical_cast(analytical_cast, detail_log)
        self.env.cr.commit()
        _logger.info('[RA] - FINISH DISTRIBUTION TO %s',
                     analytic_account_id.complete_name)

    @api.multi
    @job
    def account_analytical_reverse(self, detail_log, analytic_account_id, batch):
        batch.check_state()
        if batch.state != 'finished':
            time.sleep(300)
            raise RetryableJobError(
                ('Todavía hay jobs de reparto pendientes'))

        for line in analytic_account_id.line_ids.filtered(lambda x: not x.src_reverse_analytic_line_id and not x.reverse_analytic_line_id and x.amount != 0):
            if not line.reverse_analytic_line_id:
                if detail_log:
                    _logger.info('[RA] - CREATE REVERSION %s - %f',
                                 self.name, self.amount)
                aline_ids = self.env['account.analytic.line'].search(
                    [('src_distribute_acc_analytic_line_id', '=', line.id)])
                amounts = aline_ids.mapped('amount')
                amount = round(sum(amounts), 2)
                if amount != 0:
                    line.action_reverse_analytic_line(
                        date=line.date, amount=amount)
                    line.reverse_analytic_line_id.is_reverse_distribution = True

    def _create_analytical_cast(self, analytical_cast, detail_log=False):
        self.ensure_one()
        values = []
        for acc, coef in analytical_cast:
            if coef != 0:
                vals = {
                    'unit_amount': self.unit_amount * coef,
                    'amount': self.amount * coef,
                    'date': self.date,
                    'src_distribute_acc_analytic_line_id': self.id,
                    'distribution_type': 'brother',
                    'account_id': acc,
                    'name': self.name,
                    'company_id': self.company_id.id,
                    'move_id': self.move_id.id
                }
                values.append(vals)
                if detail_log:
                    _logger.info(
                        '[RA] - CREATE ANALYTIC LINE %s - %s - %f',
                        vals['name'], str(vals['account_id']), vals['amount'])
        if values:
            self.create(values)

    def _create_specific_analytical_cast(self, analytical_cast, detail_log=False):
        self.ensure_one()
        for acc, coef in analytical_cast:
            if coef != 0:
                vals = {
                    'unit_amount': self.unit_amount * coef,
                    'amount': self.amount * coef,
                    'date': self.date,
                    'src_distribute_acc_analytic_line_id': self.id,
                    'distribution_type': 'specific',
                    'account_id': acc,
                    'name': self.name,
                    'company_id': self.company_id.id,
                    'move_id': self.move_id.id
                }
                analytic_line = self.create(vals)
                if detail_log:
                    _logger.info(
                        '[RA] - CREATE ANALYTIC LINE %s - %s - %f',
                        analytic_line.name, analytic_line.account_id.name, analytic_line.amount)
                # Si no tiene reversion, la hacemos
                if not self.reverse_analytic_line_id:
                    if detail_log:
                        _logger.info('[RA] - CREATE REVERSION %s - %f',
                                     self.name, self.amount)
                    self.action_reverse_analytic_line(date=self.date)
                    self.reverse_analytic_line_id.is_reverse_distribution = True

    def drop_conn(self, cr, db_name):
        # Try to terminate all other connections that might prevent
        # dropping the database
        try:
            # PostgreSQL 9.2 renamed pg_stat_activity.procpid to pid:
            # http://www.postgresql.org/docs/9.2/static/release-9-2.html#AEN110389
            pid_col = 'pid' if cr._cnx.server_version >= 90200 else 'procpid'

            cr.execute("""SELECT pg_terminate_backend(%(pid_col)s)
                        FROM pg_stat_activity
                        WHERE datname = %%s AND
                                %(pid_col)s != pg_backend_pid()""" % {'pid_col': pid_col},
                       (db_name,))
        except Exception:
            pass

    @api.multi
    @job
    def check_distribution(self, batch):
        batch.check_state()
        if batch.state != 'finished':
            time.sleep(300)
            raise RetryableJobError(
                ('Todavía hay jobs de reparto pendientes'))
        config = self.env['ir.config_parameter'].sudo()
        mails = config.get_param('check_analytical_mails', '')
        if not mails:
            _logger.info(
                '[RA] - NOT FOUND check_analytical_mails PARAMETER')
            return
        self.env['account.analytic.line'].check_analytical_cast(mails)
