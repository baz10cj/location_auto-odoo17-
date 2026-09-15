from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class InspectionPhoto(models.Model):
    _name = 'location.inspection.photo'
    _description = 'Photo d’inspection'

    name = fields.Char(string='Nom')
    inspection_id = fields.Many2one('location.etat.lieux', string='Inspection', required=True, ondelete='cascade')
    image = fields.Binary(string='Image', attachment=True)
    mimetype = fields.Char(string='Type MIME')


class EtatLieux(models.Model):
    _name = 'location.etat.lieux'
    _description = 'État des lieux'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Référence', required=True, copy=False)
    type = fields.Selection([
        ('departure', 'Départ'),
        ('return', 'Retour'),
    ], string='Type', required=True, tracking=True)
    reservation_id = fields.Many2one('location.reservation', string='Réservation', tracking=True)
    contract_id = fields.Many2one('location.contract', string='Contrat', tracking=True)
    vehicle_id = fields.Many2one('location.vehicle', string='Véhicule', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', tracking=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, tracking=True)
    mileage_start = fields.Float(string='Kilométrage départ')
    fuel_start = fields.Float(string='Carburant départ (%)')
    mileage_return = fields.Float(string='Kilométrage retour')
    fuel_return = fields.Float(string='Carburant retour (%)')
    existing_damage = fields.Text(string='Dommages existants')
    new_damage = fields.Text(string='Nouveaux dommages')
    observations = fields.Text(string='Observations')
    photo_ids = fields.Many2many('ir.attachment', string='Photos')
    customer_signature = fields.Binary(string='Signature client', attachment=True)
    agent_signature = fields.Binary(string='Signature agent', attachment=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('validated', 'Validé'),
    ], string='État', default='draft', tracking=True)
    active = fields.Boolean(string='Actif', default=True, tracking=True)
    customer_confirmation = fields.Boolean(string='Confirmation client', default=False)
    confirmation_date = fields.Date(string='Date confirmation')
    needs_reconfirmation = fields.Boolean(string='Reconfirmation requise', default=False, copy=False, tracking=True)

    _CONFIRMATION_SENSITIVE_FIELDS = (
        'type', 'reservation_id', 'contract_id', 'vehicle_id', 'partner_id', 'date',
        'mileage_start', 'fuel_start', 'mileage_return', 'fuel_return',
        'existing_damage', 'new_damage', 'observations', 'photo_ids',
        'customer_signature', 'agent_signature',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('location.etat.lieux') or 'NEW'
        return super().create(vals_list)

    @api.onchange('reservation_id')
    def _onchange_reservation_id(self):
        if self.reservation_id:
            self.contract_id = self.reservation_id.contract_id
            self.vehicle_id = self.reservation_id.vehicle_id
            self.partner_id = self.reservation_id.customer_id

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in self._CONFIRMATION_SENSITIVE_FIELDS):
            for inspection in self:
                if inspection.customer_confirmation:
                    inspection.write({
                        'customer_confirmation': False,
                        'confirmation_date': False,
                        'needs_reconfirmation': True,
                    })
                    inspection.message_post(
                        body=_('L\'état des lieux a été modifié : la confirmation du client a été réinitialisée. Le client doit confirmer à nouveau.')
                    )
        return res

    def action_confirm_customer(self):
        self.write({
            'customer_confirmation': True,
            'confirmation_date': fields.Date.today(),
            'needs_reconfirmation': False,
        })

    def action_reset_customer_confirmation(self):
        self.write({
            'customer_confirmation': False,
            'confirmation_date': False,
            'needs_reconfirmation': False,
        })

    def portal_photo_urls(self):
        self.ensure_one()
        urls = []
        for attachment in self.photo_ids:
            token = attachment.generate_access_token()[0]
            urls.append('/web/image/%s?access_token=%s' % (attachment.id, token))
        return urls

    def action_validate(self):
        self.write({'state': 'validated'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_archive(self):
        self.write({'active': False, 'state': 'validated'})

    def action_unarchive(self):
        self.write({'active': True})

    def unlink(self):
        raise ValidationError(_('Inspection history cannot be deleted.'))
