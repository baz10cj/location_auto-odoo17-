import base64
import io
import logging

from PIL import Image, ImageOps

try:
    import pillow_avif.AvifImagePlugin  # noqa: F401  register AVIF decoder with Pillow
except ImportError:
    pass

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LocationVehicle(models.Model):
    _name = 'location.vehicle'
    _description = 'Véhicule'

    def _normalize_image(self, value):
        try:
            if isinstance(value, (str, bytes)):
                raw = base64.b64decode(value)
                for _ in range(3):
                    try:
                        image = Image.open(io.BytesIO(raw))
                        break
                    except Exception:
                        raw = base64.b64decode(raw)
                else:
                    raise ValueError('unable to decode image payload')
            else:
                image = Image.open(io.BytesIO(value))
            image = ImageOps.exif_transpose(image)
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            buffer = io.BytesIO()
            image.save(buffer, 'JPEG', quality=85, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception:
            _logger.warning('Could not normalize vehicle image, keeping original value.', exc_info=True)
            return value

    @api.model_create_multi
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('image_1920'):
                vals['image_1920'] = self._normalize_image(vals['image_1920'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('image_1920'):
            vals['image_1920'] = self._normalize_image(vals['image_1920'])
        return super().write(vals)

    name = fields.Char(string='Nom', required=True)
    license_plate = fields.Char(string='Plaque')
    brand = fields.Char(string='Marque')
    model = fields.Char(string='Modèle')
    image_1920 = fields.Binary(string='Image', attachment=True)
    daily_rate = fields.Float(string='Prix journalier (Dhs)')
    seats = fields.Integer(string='Places')
    gearbox = fields.Selection([
        ('manual', 'Manuelle'),
        ('automatic', 'Automatique'),
    ], string='Boîte de vitesse')
    fuel_type = fields.Selection([
        ('diesel', 'Diesel'),
        ('petrol', 'Essence'),
        ('electric', 'Électrique'),
        ('hybrid', 'Hybride'),
    ], string='Carburant')
    description = fields.Text(string='Description')
    status = fields.Selection([
        ('available', 'Disponible'),
        ('rented', 'Loué'),
        ('maintenance', 'Maintenance'),
    ], string='Statut', default='available')
    inspection_ids = fields.One2many('location.etat.lieux', 'vehicle_id', string='États des lieux')
    inspection_count = fields.Integer(string='Nombre d’inspections', compute='_compute_inspection_count')
    documents_count = fields.Integer(string='Nombre de documents', compute='_compute_documents_count')

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for record in self:
            record.inspection_count = len(record.inspection_ids)

    def _compute_documents_count(self):
        for record in self:
            partners = self.env['location.contract'].search([('vehicle_id', '=', record.id)]).mapped('customer_id')
            record.documents_count = self.env['location.client.document'].search_count([('partner_id', 'in', partners.ids)])

    def action_view_inspections(self):
        return {
            'name': 'États des lieux',
            'type': 'ir.actions.act_window',
            'res_model': 'location.etat.lieux',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    def action_view_documents(self):
        partners = self.env['location.contract'].search([('vehicle_id', '=', self.id)]).mapped('customer_id')
        return {
            'name': 'Documents client',
            'type': 'ir.actions.act_window',
            'res_model': 'location.client.document',
            'view_mode': 'tree,form',
            'domain': [('partner_id', 'in', partners.ids)],
        }
