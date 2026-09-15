/** @odoo-module */

import { _t } from '@web/core/l10n/translation';
import { StripeOptions } from '@payment_stripe/js/stripe_options';
import paymentForm from '@payment/js/payment_form';

const LA_STRIPE_APPEARANCE = {
    theme: 'flat',
    variables: {
        colorText: '#f4ebdd',
        colorTextSecondary: '#c9c1b2',
        colorBackground: '#1a2224',
        colorBorder: '#3a4346',
        colorPrimary: '#c69d65',
        colorDanger: '#e08a6b',
        fontFamily: 'Karla, "Segoe UI", sans-serif',
        borderRadius: '8px',
        spacingUnit: '4px',
    },
    rules: {
        '.Label': {
            color: '#f4ebdd',
            fontWeight: '600',
            fontSize: '13px',
            marginBottom: '6px',
        },
        '.Input': {
            color: '#f4ebdd',
            backgroundColor: '#1a2224',
            border: '1px solid #3a4346',
            padding: '12px 14px',
            boxShadow: 'none',
        },
        '.Input:focus': {
            borderColor: '#c69d65',
        },
        '.Input::placeholder': {
            color: '#8b857a',
        },
        '.Tab': {
            color: '#f4ebdd',
            backgroundColor: '#1a2224',
            border: '1px solid #3a4346',
        },
        '.Tab--selected': {
            color: '#f4ebdd',
            borderColor: '#c69d65',
            backgroundColor: 'rgba(198,157,101,0.12)',
        },
        '.Error': {
            color: '#e08a6b',
        },
    },
};

paymentForm.include({

    _laWaitStripeSdk() {
        if (typeof Stripe !== 'undefined') {
            return Promise.resolve();
        }
        return new Promise(resolve => {
            const check = () => {
                if (typeof Stripe !== 'undefined') {
                    resolve();
                } else {
                    setTimeout(check, 50);
                }
            };
            check();
        });
    },

    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'stripe') {
            return this._super(...arguments);
        }
        await this._laWaitStripeSdk();

        this.stripeElements ??= {};
        if (flow === 'token') {
            return;
        } else if (this.stripeElements[paymentOptionId]) {
            this.stripeElements[paymentOptionId].update({ appearance: LA_STRIPE_APPEARANCE });
            this._setPaymentFlow('direct');
            return;
        }

        this._setPaymentFlow('direct');

        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        const inlineForm = this._getInlineForm(radio);
        const stripeInlineForm = inlineForm.querySelector('[name="o_stripe_element_container"]');
        this.stripeInlineFormValues = JSON.parse(
            stripeInlineForm.dataset['stripeInlineFormValues']
        );

        this.stripeJS ??= Stripe(
            this.stripeInlineFormValues['publishable_key'],
            new StripeOptions()._prepareStripeOptions(stripeInlineForm.dataset),
        );

        let elementsOptions = {
            appearance: LA_STRIPE_APPEARANCE,
            currency: this.stripeInlineFormValues['currency_name'],
            captureMethod: this.stripeInlineFormValues['capture_method'],
            paymentMethodTypes: [
                this.stripeInlineFormValues['payment_methods_mapping'][paymentMethodCode]
                ?? paymentMethodCode
            ],
        };
        if (this.paymentContext['mode'] === 'payment') {
            elementsOptions.mode = 'payment';
            elementsOptions.amount = parseInt(this.stripeInlineFormValues['minor_amount']);
            if (this.stripeInlineFormValues['is_tokenization_required']) {
                elementsOptions.setupFutureUsage = 'off_session';
            }
        }
        else {
            elementsOptions.mode = 'setup';
            elementsOptions.setupFutureUsage = 'off_session';
        }
        this.stripeElements[paymentOptionId] = this.stripeJS.elements(elementsOptions);

        const paymentElementOptions = {
            defaultValues: {
                billingDetails: this.stripeInlineFormValues['billing_details'],
            },
        };
        const paymentElement = this.stripeElements[paymentOptionId].create(
            'payment', paymentElementOptions
        );
        paymentElement.on('loaderror', response => {
            this._displayErrorDialog(_t("Cannot display the payment form"), response.error.message);
        });
        paymentElement.mount(stripeInlineForm);

        const tokenizationCheckbox = inlineForm.querySelector(
            'input[name="o_payment_tokenize_checkbox"]'
        );
        if (tokenizationCheckbox) {
            this.stripeElements[paymentOptionId].update({
                setupFutureUsage: tokenizationCheckbox.checked ? 'off_session' : null,
            });
            tokenizationCheckbox.addEventListener('input', () => {
                this.stripeElements[paymentOptionId].update({
                    setupFutureUsage: tokenizationCheckbox.checked ? 'off_session' : null,
                });
            });
        }
    },

});