from odoo import fields, models


class ClientDocument(models.Model):
    _name = 'location.client.document'
    _description = 'Document client'

    name = fields.Char(string='Nom', required=True)
    partner_id = fields.Many2one('res.partner', string='Client')
    document_type = fields.Selection([
        ('id', 'Pièce d’identité'),
        ('license', 'Permis de conduire'),
        ('insurance', 'Assurance'),
        ('other', 'Autre'),
    ], string='Type de document')
    attachment_id = fields.Many2one('ir.attachment', string='Pièce jointe')
