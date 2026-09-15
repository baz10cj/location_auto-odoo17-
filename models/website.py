from odoo import api, fields, models
from odoo.http import request


class Website(models.Model):
    _inherit = 'website'

    active = fields.Boolean(default=True)

    @api.model
    def get_current_website(self, fallback=True):
        if request and request.session.get('force_website_id'):
            forced = self.browse(request.session['force_website_id']).exists()
            if forced and not forced.active:
                request.session.pop('force_website_id')
        if self.env.context.get('website_id'):
            context_website = self.browse(self.env.context['website_id']).exists()
            if not context_website.active:
                self = self.with_context(website_id=False)
        return super().get_current_website(fallback=fallback)
