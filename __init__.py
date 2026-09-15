from . import models
from . import controllers


def _set_keydrive_layout(env):
    layout = env.ref('location_auto.external_layout_keydrive')
    env['res.company'].search([]).write({'external_report_layout_id': layout.id})
