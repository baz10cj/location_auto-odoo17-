from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LocationContract(models.Model):
    _name = 'location.contract'
    _description = 'Contrat de location'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Référence', required=True, copy=False, tracking=True)
    reservation_id = fields.Many2one('location.reservation', string='Réservation', tracking=True)
    customer_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    vehicle_id = fields.Many2one('location.vehicle', string='Véhicule', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('vehicle_delivered', 'Véhicule livré'),
        ('closed', 'Clôturé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True)
    inspection_ids = fields.One2many('location.etat.lieux', 'contract_id', string='États des lieux')
    inspection_count = fields.Integer(string='Nombre d’inspections', compute='_compute_inspection_count')
    documents_count = fields.Integer(string='Nombre de documents', compute='_compute_documents_count')
    start_date = fields.Date(related='reservation_id.start_date', string='Date de début', store=True, readonly=True)
    end_date = fields.Date(related='reservation_id.end_date', string='Date de fin', store=True, readonly=True)
    rental_duration = fields.Integer(string='Durée de location (jours)', compute='_compute_rental_duration', store=False)
    reservation_comments = fields.Text(related='reservation_id.comments', string='Commentaires de réservation', readonly=True)
    customer_signature = fields.Binary(string='Signature client', attachment=True)
    signature_date = fields.Date(string='Date de signature', readonly=True)

    @api.depends('start_date', 'end_date')
    def _compute_rental_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                record.rental_duration = (record.end_date - record.start_date).days + 1
            else:
                record.rental_duration = 0

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for record in self:
            record.inspection_count = len(record.inspection_ids)

    @api.depends('customer_id')
    def _compute_documents_count(self):
        for record in self:
            record.documents_count = self.env['location.client.document'].search_count([('partner_id', '=', record.customer_id.id)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('location.contract') or 'CT-0001'
        return super().create(vals_list)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_deliver_vehicle(self):
        departure_inspections = self.env['location.etat.lieux'].search_count([
            ('contract_id', '=', self.id),
            ('type', '=', 'departure'),
        ])
        if departure_inspections == 0:
            raise ValidationError(_('You cannot deliver the vehicle without a departure inspection.'))
        self.write({'state': 'vehicle_delivered'})

    def action_close(self):
        return_inspections = self.env['location.etat.lieux'].search_count([
            ('contract_id', '=', self.id),
            ('type', '=', 'return'),
        ])
        if return_inspections == 0:
            raise ValidationError(_('You cannot close the contract without a return inspection.'))
        self.write({'state': 'closed'})

    def action_view_inspections(self):
        return {
            'name': 'États des lieux',
            'type': 'ir.actions.act_window',
            'res_model': 'location.etat.lieux',
            'view_mode': 'tree,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_documents(self):
        return {
            'name': 'Documents client',
            'type': 'ir.actions.act_window',
            'res_model': 'location.client.document',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.customer_id.id)],
            'context': {'default_partner_id': self.customer_id.id},
        }

    def get_customer_signature(self):
        signature = self.customer_signature
        if isinstance(signature, bytes):
            try:
                signature = signature.decode('utf-8')
            except UnicodeDecodeError:
                signature = signature.decode('latin-1')
        return signature

    def sign(self, signature):
        self.write({
            'customer_signature': signature,
            'signature_date': fields.Date.context_today(self),
        })
