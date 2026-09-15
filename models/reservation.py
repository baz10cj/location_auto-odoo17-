from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LocationReservation(models.Model):
    _name = 'location.reservation'
    _description = 'Réservation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Référence', required=True, copy=False, tracking=True)
    customer_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    vehicle_id = fields.Many2one('location.vehicle', string='Véhicule', required=True, tracking=True)
    contract_id = fields.Many2one('location.contract', string='Contrat', tracking=True)
    invoice_id = fields.Many2one('account.move', string='Facture', tracking=True)
    start_date = fields.Date(string='Date de début', required=True, tracking=True)
    end_date = fields.Date(string='Date de fin', required=True, tracking=True)
    comments = fields.Text(string='Commentaires')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('cancelled', 'Annulée'),
    ], string='État', default='draft', tracking=True)
    inspection_ids = fields.One2many('location.etat.lieux', 'reservation_id', string='États des lieux')
    inspection_count = fields.Integer(string='Nombre d’inspections', compute='_compute_inspection_count')

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for record in self:
            record.inspection_count = len(record.inspection_ids)

    def get_state_label(self):
        self.ensure_one()
        return _(dict(self._fields['state'].selection).get(self.state, self.state))

    @api.constrains('vehicle_id', 'start_date', 'end_date', 'state')
    def _check_vehicle_availability(self):
        for record in self:
            if record.end_date < record.start_date:
                raise ValidationError(_('The end date must be after or equal to the start date.'))
            if record.state != 'confirmed':
                continue
            domain = [
                ('id', '!=', record.id),
                ('vehicle_id', '=', record.vehicle_id.id),
                ('state', '=', 'confirmed'),
                ('start_date', '<=', record.end_date),
                ('end_date', '>=', record.start_date),
            ]
            conflict = self.search(domain) | self.filtered(
                lambda other: other.id != record.id
                and other.state == 'confirmed'
                and other.vehicle_id.id == record.vehicle_id.id
                and other.start_date <= record.end_date
                and other.end_date >= record.start_date
            )
            if conflict:
                raise ValidationError(_(
                    'This vehicle is already booked from %s to %s for this period.',
                    conflict[0].start_date, conflict[0].end_date,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('location.reservation') or 'RES-0001'
        return super().create(vals_list)

    def action_confirm(self):
        for record in self:
            if not record.contract_id:
                contract = self.env['location.contract'].create({
                    'reservation_id': record.id,
                    'customer_id': record.customer_id.id,
                    'vehicle_id': record.vehicle_id.id,
                    'state': 'confirmed',
                })
                record.contract_id = contract.id
            if not record.invoice_id:
                days = max(1, (record.end_date - record.start_date).days)
                income_account = self.env['account.account'].search([
                    ('account_type', '=', 'income'),
                    ('company_id', '=', self.env.company.id),
                ], limit=1)
                invoice = self.env['account.move'].create({
                    'move_type': 'out_invoice',
                    'partner_id': record.customer_id.id,
                    'invoice_date': fields.Date.today(),
                    'invoice_line_ids': [(0, 0, {
                        'name': 'Location {} du {} au {}'.format(
                            record.vehicle_id.name, record.start_date, record.end_date),
                        'quantity': days,
                        'price_unit': record.vehicle_id.daily_rate,
                        'account_id': income_account.id,
                    })],
                })
                invoice.action_post()
                record.invoice_id = invoice.id
        self.write({'state': 'confirmed'})
        for record in self:
            conflicting = self.search([
                ('id', '!=', record.id),
                ('vehicle_id', '=', record.vehicle_id.id),
                ('state', '=', 'draft'),
                ('start_date', '<=', record.end_date),
                ('end_date', '>=', record.start_date),
            ])
            for other in conflicting:
                other.action_cancel()
                other._notify_cancelled(record.vehicle_id.name, other.start_date, other.end_date)

    def _notify_cancelled(self, vehicle_name, start_date, end_date):
        self.ensure_one()
        self = self.with_context(lang=self.customer_id.lang or 'fr_FR')
        subject = _('Your reservation %s has been cancelled') % self.name
        body_html = _(
            'Hello %s,<br/>Your reservation <b>%s</b> has been automatically cancelled because the vehicle <b>%s</b> has been booked by another customer for the same period (from %s to %s).'
        ) % (self.customer_id.name, self.name, vehicle_name, start_date, end_date)
        self.message_post(body=_(
            'This reservation was automatically cancelled: the vehicle %s has been booked by another customer from %s to %s.'
        ) % (vehicle_name, start_date, end_date))
        if self.customer_id.email:
            self.env['mail.mail'].create({
                'subject': subject,
                'body_html': body_html,
                'email_to': self.customer_id.email,
            }).send()

    def action_cancel(self):
        for record in self:
            if record.contract_id and record.contract_id.state in ('draft', 'confirmed'):
                record.contract_id.write({'state': 'cancelled'})
            if record.invoice_id:
                record.invoice_id.with_context(force_delete=True).unlink()
        self.write({'state': 'cancelled'})

    def action_view_inspections(self):
        return {
            'name': 'États des lieux',
            'type': 'ir.actions.act_window',
            'res_model': 'location.etat.lieux',
            'view_mode': 'tree,form',
            'domain': [('reservation_id', '=', self.id)],
            'context': {'default_reservation_id': self.id},
        }
