from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request


class LocationAutoSupport(http.Controller):

    def _get_ticket(self, ticket_id, token=None):
        ticket = request.env['la.support.ticket'].sudo().browse(int(ticket_id))
        if not ticket.exists():
            return False
        user = request.env.user
        if user._is_internal():
            return ticket
        if token and ticket.visitor_token and token == ticket.visitor_token:
            return ticket
        if user.partner_id and ticket.partner_id and ticket.partner_id.id == user.partner_id.id:
            return ticket
        return False

    @http.route(['/support'], type='http', auth='public', website=True)
    def support_new(self, **kw):
        values = {
            'name': kw.get('name') or '',
            'email': kw.get('email') or '',
            'message': kw.get('message') or '',
        }
        user = request.env.user
        if values['email'] or not user._is_public():
            values['email'] = values['email'] or request.env.user.email
        return request.render('location_auto.support_new_page', {'values': values})

    @http.route(['/support/submit'], type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def support_submit(self, **post):
        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        message = (post.get('message') or '').strip()
        if not name:
            raise ValidationError(_('Please enter a subject.'))
        if not message:
            raise ValidationError(_('Please write a message.'))
        if not email:
            user = request.env.user
            email = user.email
        if not email:
            raise ValidationError(_('Please enter your email address.'))

        user = request.env.user
        partner = False
        if user.partner_id and not user._is_public():
            partner = user.partner_id
        partner = partner or request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': email.split('@')[0] or email,
                'email': email,
            })

        ticket = request.env['la.support.ticket'].sudo().create({
            'name': name,
            'email': email,
            'partner_id': partner.id,
        })
        ticket.send_message(message, author_type='customer', partner=partner)
        return request.redirect(ticket.access_link())

    @http.route(['/support/ticket/<int:ticket_id>'], type='http', auth='public', website=True)
    def support_ticket(self, ticket_id, t=None, **kw):
        ticket = self._get_ticket(ticket_id, token=t)
        if not ticket:
            return request.redirect('/support')
        ticket.sudo().mark_customer_read()
        session_info = request.env['ir.http'].get_frontend_session_info()
        messages = ticket.message_ids.sudo()
        state_labels = {
            'new': _('New support ticket'),
            'in_progress': _('Support ticket in progress'),
            'waiting_customer': _('Awaiting your reply'),
            'done': _('Support ticket closed'),
        }
        return request.render('location_auto.support_ticket_page', {
            'ticket': ticket,
            'messages': messages,
            'state_label': state_labels.get(ticket.state, ticket.state),
            'last_id': messages[-1].id if messages else 0,
            'ws_version': session_info.get('websocket_worker_version') or '17.0-3',
            'ticket_id': ticket.id,
            'token': ticket.visitor_token if t == ticket.visitor_token else '',
        })

    @http.route(['/support/ticket/<int:ticket_id>/send'], type='http', auth='public', methods=['POST'], csrf=False)
    def support_send(self, ticket_id, **kw):
        payload = request.httprequest.get_json(silent=True) or {}
        t = payload.get('t')
        ticket = self._get_ticket(ticket_id, token=t)
        if not ticket:
            return request.make_json_response({'success': False, 'error': _('This conversation is not accessible.')})
        body = str(payload.get('body') or '').strip()
        if not body:
            return request.make_json_response({'success': False, 'error': _('The message is empty.')})
        user = request.env.user
        partner = user.partner_id if user.partner_id and not user._is_public() else ticket.partner_id
        message = ticket.sudo().send_message(body, author_type='customer', partner=partner)
        return request.make_json_response({
            'success': True,
            'message': {
                'id': message.id,
                'body': message.body,
                'author_type': message.author_type,
                'author_name': message.author_id.name or '',
                'create_date': message.create_date.isoformat(),
            },
        })

    @http.route(['/support/ticket/<int:ticket_id>/messages'], type='http', auth='public', methods=['GET'], csrf=False)
    def support_messages(self, ticket_id, after=0, t=None, **kw):
        ticket = self._get_ticket(ticket_id, token=t)
        if not ticket:
            return request.make_json_response({'success': False, 'error': _('This conversation is not accessible.')})
        after = int(after or 0)
        messages = ticket.message_ids.sudo().filtered(lambda m: m.id > after)
        return request.make_json_response({
            'success': True,
            'messages': [{
                'id': message.id,
                'body': message.body,
                'author_type': message.author_type,
                'author_name': message.author_id.name or '',
                'create_date': message.create_date.isoformat(),
            } for message in messages],
        })

    @http.route(['/my/support/unread'], type='http', auth='user', website=True)
    def support_unread(self, **kw):
        partner = request.env.user.partner_id
        count = request.env['la.support.ticket'].sudo().search_count([
            ('partner_id', '=', partner.id),
            ('customer_unread', '=', True),
        ])
        return request.make_json_response({'count': count})

    @http.route(['/my/support/next'], type='http', auth='user', website=True)
    def my_support_next(self, **kw):
        partner = request.env.user.partner_id
        ticket = request.env['la.support.ticket'].sudo().search([
            ('partner_id', '=', partner.id),
            ('customer_unread', '=', True),
        ], order='id desc', limit=1)
        if not ticket:
            return request.redirect('/my/support')
        return request.redirect(ticket.access_link())

    @http.route(['/my/support'], type='http', auth='user', website=True)
    def my_support(self, **kw):
        partner = request.env.user.partner_id
        tickets = request.env['la.support.ticket'].sudo().search([('partner_id', '=', partner.id)])
        return request.render('location_auto.support_my_page', {'tickets': tickets})