from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountAnalyticPeriod(models.Model):
    _name = 'account.analytic.period'
    _description = 'Account Analytic Period'
    _order = 'date_start'

    name = fields.Char(
        string='Name',
        required=True,
    )

    date_start = fields.Date(
        string='Date Start',
        required=True,
    )

    date_end = fields.Date(
        string='Date End',
        required=True,
    )

    @api.constrains('date_start', 'date_end')
    def _validate_range(self):
        for this in self:
            if this.date_start > this.date_end:
                raise ValidationError(
                    _("%s is not a valid range (%s > %s)") % (
                        this.name, this.date_start, this.date_end))
