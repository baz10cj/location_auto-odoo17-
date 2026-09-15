from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    license_number = fields.Char(string='Numéro de permis')
    documents_count = fields.Integer(string='Documents', compute='_compute_documents_count')

   
    def _compute_documents_count(self):
        for record in self:
            record.documents_count = self.env['location.client.document'].search_count([('partner_id', '=', record.id)])

    def action_view_documents(self):
        return {
            'name': 'Documents client',
            'type': 'ir.actions.act_window',
            'res_model': 'location.client.document',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
