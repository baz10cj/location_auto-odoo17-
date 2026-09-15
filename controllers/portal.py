import base64

from odoo import http, _, fields
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.web import Home as PortalHome
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.addons.payment.controllers.portal import PaymentPortal
from odoo.addons.payment import utils as payment_utils


class LocationAutoHome(PortalHome):

    @http.route()
    def index(self, *args, **kw):
        if request.session.uid and not is_user_internal(request.session.uid):
            return request.redirect_query('/my/profile', query=request.params)
        return super().index(*args, **kw)

    @http.route()
    def web_client(self, s_action=None, **kw):
        if request.session.uid and not is_user_internal(request.session.uid):
            return request.redirect_query('/my/profile', query=request.params)
        return super().web_client(s_action, **kw)

    def _login_redirect(self, uid, redirect=None):
        if not redirect and not is_user_internal(uid):
            redirect = '/my/profile'
        return super()._login_redirect(uid, redirect=redirect)


class LocationAutoPortal(http.Controller):

    @http.route(['/my/register'], type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def register(self, **post):
        values = {
            'name': post.get('name') or '',
            'email': post.get('email') or '',
            'phone': post.get('phone') or '',
            'license_number': post.get('license_number') or '',
            'street': post.get('street') or '',
            'city': post.get('city') or '',
        }
        if request.httprequest.method == 'POST':
            try:
                if not values['name'] or not values['email'] or not post.get('password'):
                    raise ValidationError(_('Please fill in your name, email and password.'))
                if post.get('password') and ' ' in post.get('password'):
                    raise ValidationError(_('The password must not contain spaces.'))
                existing_user = request.env['res.users'].sudo().search([('login', '=', values['email'])], limit=1)
                if existing_user:
                    raise ValidationError(_('A user with this email already exists.'))

                partner = request.env['res.partner'].sudo().create({
                    'name': values['name'],
                    'email': values['email'],
                    'phone': values['phone'],
                    'license_number': values['license_number'],
                    'street': values['street'],
                    'city': values['city'],
                })
                user = request.env['res.users'].sudo().create({
                    'name': values['name'],
                    'login': values['email'],
                    'email': values['email'],
                    'password': post.get('password'),
                    'partner_id': partner.id,
                    'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])],
                })
                user.partner_id.write({'user_ids': [(4, user.id)]})

                for field_name, document_type in [('driving_license', 'license'), ('identity_card', 'id'), ('insurance', 'insurance'), ('other_documents', 'other')]:
                    file_storage = request.httprequest.files.get(field_name)
                    if file_storage and file_storage.filename:
                        data = file_storage.read()
                        attachment = request.env['ir.attachment'].sudo().create({
                            'name': file_storage.filename,
                            'datas': base64.b64encode(data).decode('utf-8'),
                            'res_model': 'res.partner',
                            'res_id': partner.id,
                            'type': 'binary',
                        })
                        request.env['location.client.document'].sudo().create({
                            'name': file_storage.filename,
                            'partner_id': partner.id,
                            'document_type': document_type,
                            'attachment_id': attachment.id,
                        })
                return request.redirect('/web/login?redirect=/my/profile')
            except ValidationError as error:
                return request.render('location_auto.portal_register_page', {
                    'error': error.args[0],
                    'values': values,
                })

        return request.render('location_auto.portal_register_page', {'values': values})

    @http.route(['/'], type='http', auth='public', website=True, sitemap=True)
    def website_root(self, **kw):
        return request.redirect('/location-auto')

    @http.route(['/location-auto', '/location-auto/'], type='http', auth='public', website=True, sitemap=True)
    def website_home(self, **kw):
        vehicles = request.env['location.vehicle'].sudo().search([])
        return request.render('location_auto.website_location_auto_homepage', {'vehicles': vehicles})

    @http.route(['/vehicles'], type='http', auth='public', website=True, sitemap=True)
    def vehicles(self, **kw):
        vehicles = request.env['location.vehicle'].sudo().search([])
        return request.render('location_auto.website_vehicles', {'vehicles': vehicles})

    @http.route(['/vehicle/<int:vehicle_id>'], type='http', auth='public', website=True, sitemap=True)
    def vehicle_detail(self, vehicle_id, **kw):
        vehicle = request.env['location.vehicle'].sudo().browse(vehicle_id)
        if not vehicle.exists():
            return request.redirect('/location-auto')
        return request.render('location_auto.website_vehicle_detail', {'vehicle': vehicle})

    @http.route(['/my/reservations/new'], type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=False)
    def new_reservation(self, **post):
        partner = request.env.user.partner_id
        vehicles = request.env['location.vehicle'].sudo().search([])
        default_vehicle_id = int(post.get('vehicle_id') or 0)
        error = ''
        if request.httprequest.method == 'POST':
            try:
                vehicle_id = int(post.get('vehicle_id') or 0)
                start_date = post.get('start_date')
                end_date = post.get('end_date')
                if not vehicle_id or not start_date or not end_date:
                    raise ValidationError(_('Please select a vehicle and your rental dates.'))
                if end_date < start_date:
                    raise ValidationError(_('The end date must be after or equal to the start date.'))
                overlap = request.env['location.reservation'].sudo().search([
                    ('vehicle_id', '=', vehicle_id),
                    ('state', '!=', 'cancelled'),
                    ('start_date', '<=', end_date),
                    ('end_date', '>=', start_date),
                ], limit=1)
                if overlap:
                    raise ValidationError(_(
                        'This vehicle is already booked from %s to %s for this period.',
                        overlap.start_date, overlap.end_date,
                    ))
                request.env['location.reservation'].sudo().create({
                    'customer_id': partner.id,
                    'vehicle_id': vehicle_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'comments': post.get('comments'),
                    'state': 'draft',
                })
                return request.redirect('/my/reservations')
            except ValidationError as exc:
                error = exc.args[0]
        selected_vehicle = request.env['location.vehicle'].sudo().browse(default_vehicle_id) if default_vehicle_id else False
        return request.render('location_auto.portal_new_reservation_page', {
            'vehicles': vehicles,
            'default_vehicle_id': default_vehicle_id,
            'selected_vehicle': selected_vehicle,
            'error': error,
            'values': post,
        })

    @http.route(['/my/reservations'], type='http', auth='user', website=True)
    def reservations(self, **kw):
        partner = request.env.user.partner_id
        reservations = request.env['location.reservation'].sudo().search([('customer_id', '=', partner.id)])
        return request.render('location_auto.portal_reservations_page', {
            'reservations': reservations,
            'today': fields.Date.today(),
        })

    @http.route(['/my/reservations/<int:reservation_id>/cancel'], type='http', auth='user', website=True)
    def cancel_reservation(self, reservation_id, **kw):
        partner = request.env.user.partner_id
        reservation = request.env['location.reservation'].sudo().browse(reservation_id)
        if not reservation.exists() or reservation.customer_id.id != partner.id:
            raise ValidationError(_('You are not allowed to access this reservation.'))
        if reservation.start_date <= fields.Date.today():
            raise ValidationError(_(
                'You can no longer cancel this reservation: the rental has already started.'))
        self = reservation.with_context(lang=partner.lang or 'fr_FR')
        self.message_post(body=_('The reservation was cancelled by the customer.'))
        reservation.action_cancel()
        return request.redirect('/my/reservations')

    @http.route(['/my/contracts'], type='http', auth='user', website=True)
    def contracts(self, **kw):
        partner = request.env.user.partner_id
        contracts = request.env['location.contract'].sudo().search([('customer_id', '=', partner.id)])
        return request.render('location_auto.portal_contracts_page', {'contracts': contracts})

    @http.route(['/my/contracts/<int:contract_id>/download'], type='http', auth='user', website=True)
    def contract_pdf(self, contract_id, **kw):
        contract = request.env['location.contract'].sudo().browse(contract_id)
        if contract.customer_id.id != request.env.user.partner_id.id:
            raise ValidationError(_('You are not allowed to access this contract.'))
        pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf('location_auto.report_contract', [contract.id])
        filename = f'{contract.name or "contract"}.pdf'
        return request.make_response(pdf_content, headers=[('Content-Type', 'application/pdf'), ('Content-Disposition', f'attachment; filename={filename}')])

    @http.route(['/my/contracts/<int:contract_id>/sign'], type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=False)
    def sign_contract(self, contract_id, **post):
        contract = request.env['location.contract'].sudo().browse(contract_id)
        if contract.customer_id.id != request.env.user.partner_id.id:
            raise ValidationError(_('You are not allowed to access this contract.'))
        if request.httprequest.method == 'POST':
            signature = post.get('signature') or ''
            if signature.startswith('data:image'):
                signature = signature.split(',', 1)[1]
            if not signature:
                raise ValidationError(_('Please sign the contract before submitting.'))
            contract.sign(signature)
            return request.redirect('/my/contracts')
        return request.render('location_auto.portal_contract_sign_page', {'contract': contract})

    @http.route(['/my/invoices'], type='http', auth='user', website=True)
    def invoices(self, **kw):
        partner = request.env.user.partner_id
        invoices = request.env['account.move'].sudo().search([
            ('partner_id', '=', partner.id),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
        ])
        return request.render('location_auto.portal_invoices_page', {'invoices': invoices})

    @http.route(['/my/invoices/<int:invoice_id>/pay'], type='http', auth='user', website=True)
    def invoice_pay(self, invoice_id, **kw):
        partner = request.env.user.partner_id
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        if (
            not invoice.exists()
            or invoice.move_type not in ('out_invoice', 'out_refund')
            or invoice.partner_id.id != partner.id
        ):
            raise ValidationError(_('You are not allowed to access this invoice.'))

        # Build the online payment context for the invoice.
        payment_context = {}
        if invoice._has_to_be_paid():
            invoice_company = invoice.company_id or request.env.company
            providers_sudo = request.env['payment.provider'].sudo()._get_compatible_providers(
                invoice_company.id,
                partner.id,
                invoice.amount_total,
                currency_id=invoice.currency_id.id,
            )
            payment_methods_sudo = request.env['payment.method'].sudo()._get_compatible_payment_methods(
                providers_sudo.ids, partner.id, currency_id=invoice.currency_id.id,
            )
            tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
                providers_sudo.ids, partner.id
            )
            payment_context = {
                'amount': invoice.amount_residual,
                'currency': invoice.currency_id,
                'partner_id': partner.id,
                'providers_sudo': providers_sudo,
                'payment_methods_sudo': payment_methods_sudo,
                'tokens_sudo': tokens_sudo,
                'show_tokenize_input_mapping': PaymentPortal._compute_show_tokenize_input_mapping(
                    providers_sudo
                ),
                'transaction_route': f'/invoice/transaction/{invoice.id}/',
                'landing_route': f'/my/invoices/{invoice.id}/pay',
                'access_token': invoice.access_token or invoice._portal_ensure_token(),
                'company_mismatch': not PaymentPortal._can_partner_pay_in_company(
                    partner, invoice_company
                ),
            }

        # Display the payment status if the client just came back from the payment provider.
        landing_tx = False
        raw_tx_id = kw.get('tx_id')
        try:
            tx_id = int(raw_tx_id) if raw_tx_id else 0
        except (TypeError, ValueError):
            tx_id = 0
        if tx_id:
            tx_sudo = request.env['payment.transaction'].sudo().browse(tx_id).exists()
            if tx_sudo and payment_utils.check_access_token(
                kw.get('access_token'), tx_sudo.partner_id.id, tx_sudo.amount,
                tx_sudo.currency_id.id,
            ):
                landing_tx = tx_sudo

        return request.render('location_auto.portal_invoice_pay_page', {
            'invoice': invoice,
            'last_tx': invoice.get_portal_last_transaction(),
            'landing_tx': landing_tx,
            **payment_context,
        })

    @http.route(['/my/invoices/<int:invoice_id>/pdf'], type='http', auth='user', website=True)
    def invoice_pdf(self, invoice_id, **kw):
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        if invoice.move_type not in ('out_invoice', 'out_refund') or invoice.partner_id.id != request.env.user.partner_id.id:
            raise ValidationError(_('You are not allowed to access this invoice.'))
        pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf('account.account_invoices', [invoice.id])
        filename = f'{invoice.name or "invoice"}.pdf'
        return request.make_response(pdf_content, headers=[('Content-Type', 'application/pdf'), ('Content-Disposition', f'attachment; filename={filename}')])

    @http.route(['/my/inspections'], type='http', auth='user', website=True)
    def inspections(self, **kw):
        partner = request.env.user.partner_id
        inspections = request.env['location.etat.lieux'].sudo().search([('partner_id', '=', partner.id)])
        return request.render('location_auto.portal_inspections_page', {'inspections': inspections})

    @http.route(['/my/inspections/<int:inspection_id>/confirm'], type='http', auth='user', website=True)
    def confirm_inspection(self, inspection_id, **kw):
        inspection = request.env['location.etat.lieux'].sudo().browse(inspection_id)
        if inspection.partner_id.id != request.env.user.partner_id.id:
            raise ValidationError(_('You are not allowed to access this inspection.'))
        inspection.action_confirm_customer()
        return request.redirect('/my/inspections')

    @http.route(['/my/profile'], type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=False)
    def profile(self, **post):
        partner = request.env.user.partner_id

        def _own_document(document_id):
            document = request.env['location.client.document'].sudo().browse(int(document_id))
            if not document.exists() or document.partner_id.id != partner.id:
                raise ValidationError(_('You are not allowed to manage this document.'))
            return document

        def _create_attachment(filename, data):
            return request.env['ir.attachment'].sudo().create({
                'name': filename,
                'datas': base64.b64encode(data).decode('utf-8'),
                'res_model': 'res.partner',
                'res_id': partner.id,
                'type': 'binary',
            })

        if request.httprequest.method == 'POST':
            if post.get('doc_id'):
                document = _own_document(post['doc_id'])
                if post.get('delete_doc'):
                    attachment = document.attachment_id
                    document.unlink()
                    if attachment:
                        attachment.unlink()
                    return request.redirect('/my/profile')
                file_storage = request.httprequest.files.get('replace_doc')
                if file_storage and file_storage.filename:
                    attachment = _create_attachment(file_storage.filename, file_storage.read())
                    if document.attachment_id:
                        document.attachment_id.unlink()
                    document.write({'attachment_id': attachment.id, 'name': file_storage.filename})
                    return request.redirect('/my/profile')

            if post.get('new_doc_type'):
                file_storage = request.httprequest.files.get('new_doc_file')
                if not (file_storage and file_storage.filename):
                    raise ValidationError(_('Please choose a file to upload.'))
                attachment = _create_attachment(file_storage.filename, file_storage.read())
                request.env['location.client.document'].sudo().create({
                    'name': file_storage.filename,
                    'partner_id': partner.id,
                    'document_type': post['new_doc_type'],
                    'attachment_id': attachment.id,
                })
                return request.redirect('/my/profile')

            partner.write({
                'name': post.get('name') or partner.name,
                'phone': post.get('phone') or partner.phone,
                'street': post.get('street') or partner.street,
                'city': post.get('city') or partner.city,
                'email': post.get('email') or partner.email,
                'license_number': post.get('license_number') or partner.license_number,
            })
            request.env.user.write({'email': post.get('email') or partner.email})
            avatar_file = request.httprequest.files.get('avatar')
            if avatar_file and avatar_file.filename:
                data = avatar_file.read()
                if data:
                    partner.image_1920 = base64.b64encode(data).decode('utf-8')
            return request.redirect('/my/profile')
        documents = request.env['location.client.document'].sudo().search([('partner_id', '=', partner.id)])
        return request.render('location_auto.portal_profile_page', {'partner': partner, 'documents': documents})


class LocationAutoCustomerPortal(CustomerPortal):

    @http.route()
    def home(self, **kw):
        return request.redirect('/my/reservations')

