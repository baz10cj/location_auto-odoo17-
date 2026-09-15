import logging
import secrets

from odoo import _, api, fields, models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class LaSupportTicket(models.Model):
    _name = 'la.support.ticket'
    _description = 'Support Ticket'
    _order = 'id desc'

    name = fields.Char(string='Sujet', required=True)
    email = fields.Char(string='Email')
    partner_id = fields.Many2one('res.partner', string='Client', ondelete='set null')
    state = fields.Selection([
        ('new', 'New support ticket'),
        ('in_progress', 'Support ticket in progress'),
        ('waiting_customer', 'Awaiting your reply'),
        ('done', 'Support ticket closed'),
    ], string='État', default='new', required=True)
    priority = fields.Selection([
        ('0', 'Basse'),
        ('1', 'Normale'),
        ('2', 'Haute'),
    ], string='Priorité', default='1', required=True)
    user_id = fields.Many2one('res.users', string='Assigné à', domain="[('share', '=', False)]")
    visitor_token = fields.Char(string='Jeton visiteur', default=lambda self: secrets.token_hex(16), copy=False, required=True)
    message_ids = fields.One2many('la.support.message', 'ticket_id', string='Conversation')
    message_count = fields.Integer(string='Messages', compute='_compute_message_count')
    unread_count = fields.Integer(string='Messages non lus (agents)', default=0, copy=False)
    customer_unread = fields.Boolean(string='Non lu par le client', default=False, copy=False)

    @api.depends('message_ids')
    def _compute_message_count(self):
        for ticket in self:
            ticket.message_count = len(ticket.message_ids)

    def access_link(self):
        self.ensure_one()
        return '/support/ticket/%d?t=%s' % (self.id, self.visitor_token)

    def conversation(self):
        self.ensure_one()
        if self.env.user._is_internal():
            self.sudo().write({'unread_count': 0})
        messages = self.env['la.support.message'].sudo().search(
            [('ticket_id', '=', self.id)], order='id asc')
        return [{
            'id': message.id,
            'body': message.body,
            'author_type': message.author_type,
            'author_name': message.author_id.name or '',
            'create_date': message.create_date.isoformat(),
        } for message in messages]

    def mark_agent_read(self):
        self.write({'unread_count': 0})

    def mark_customer_read(self):
        self.write({'customer_unread': False})

    def agent_unread_total(self):
        tickets = self.search([('unread_count', '>', 0)])
        return sum(ticket.unread_count for ticket in tickets)

    def message_reply(self, body):
        self.ensure_one()
        message = self.send_message(body, author_type='agent')
        return {
            'id': message.id,
            'body': message.body,
            'author_type': message.author_type,
            'author_name': message.author_id.name or '',
            'create_date': message.create_date.isoformat(),
        }

    def toggle_done(self):
        for ticket in self:
            ticket.state = 'done' if ticket.state != 'done' else 'in_progress'

    def assign_to_me(self):
        for ticket in self:
            ticket.user_id = self.env.user.id

    def send_message(self, body, author_type='customer', partner=None):
        self.ensure_one()
        if not body or not body.strip():
            raise ValueError(_('The message content is empty.'))
        partner = partner or self.partner_id
        message = self.env['la.support.message'].sudo().create({
            'ticket_id': self.id,
            'author_id': partner.id if partner else False,
            'author_type': author_type,
            'body': body.strip(),
        })
        self.sudo().write({
            'state': 'waiting_customer' if author_type == 'agent' else 'in_progress',
        })
        payload = {
            'ticket_id': self.id,
            'message_id': message.id,
            'author_type': author_type,
            'author_name': partner.name if partner else '',
            'body': message.body,
            'create_date': message.create_date.isoformat(),
        }
        try:
            self.env['bus.bus'].sudo()._sendone('la_support_%d' % self.id, 'la.support.message', payload)
        except Exception:
            _logger.warning('bus notification failed for ticket %s', self.id, exc_info=True)
        if author_type == 'customer':
            if not self.env.user._is_internal():
                self.sudo().write({'unread_count': (self.unread_count or 0) + 1})
                agent_payload = dict(payload, ticket_name=self.name, unread_total=self.unread_count)
                try:
                    self.env['bus.bus'].sudo()._sendone('la_support_agents', 'la.support.agent.notif', agent_payload)
                except Exception:
                    _logger.warning('bus agent notification failed for ticket %s', self.id, exc_info=True)
        else:
            self.sudo().write({'customer_unread': True})
        if author_type == 'customer':
            self._notify_agents(message)
        else:
            self._notify_customer(message)
        return message

    def _notify_customer(self, message):
        self.ensure_one()
        recipient = self.email
        if not recipient:
            return
        link = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '') + self.access_link()
        try:
            self.env['mail.mail'].sudo().create({
                'subject': '[%s] %s' % (self.name, _('A support agent has replied')),
                'body_html': '<p>%s</p><p>%s</p><p><a href="%s">%s</a></p>' % (
                    _('A support agent replied to your request "%s":') % self.name,
                    html2plaintext(message.body).replace('\n', '<br/>'),
                    link,
                    _('Open the conversation'),
                ),
                'email_to': recipient,
                'auto_delete': True,
            })
        except Exception:
            _logger.warning('customer notification email failed for ticket %s', self.id, exc_info=True)

    def _notify_agents(self, message):
        self.ensure_one()
        agents = self.env['res.users'].sudo().search([('groups_id', 'in', self.env.ref('location_auto.group_support_agent').id)])
        recipients = set()
        if self.user_id:
            recipients.add(self.user_id.email)
        recipients.update(a.email for a in agents if a.email)
        if not recipients:
            return
        link = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '') + '/web#id=%d&model=la.support.ticket&view_type=form' % self.id
        try:
            self.env['mail.mail'].sudo().create({
                'subject': '[%s] %s' % (self.name, _('New customer message')),
                'body_html': '<p>%s</p><p>%s</p><p><a href="%s">%s</a></p>' % (
                    _('The customer wrote a new message on the ticket "%s":') % self.name,
                    html2plaintext(message.body).replace('\n', '<br/>'),
                    link,
                    _('Open the ticket'),
                ),
                'email_to': ','.join(sorted(recipients)),
                'auto_delete': True,
            })
        except Exception:
            _logger.warning('agent notification email failed for ticket %s', self.id, exc_info=True)


class LaSupportMessage(models.Model):
    _name = 'la.support.message'
    _description = 'Support Message'
    _order = 'id asc'

    ticket_id = fields.Many2one('la.support.ticket', string='Demande', ondelete='cascade', required=True)
    author_id = fields.Many2one('res.partner', string='Auteur', ondelete='set null')
    author_type = fields.Selection([
        ('customer', 'Client'),
        ('agent', 'Agent'),
    ], string="Type d'auteur", required=True, default='customer')
    body = fields.Text(string='Message', required=True)