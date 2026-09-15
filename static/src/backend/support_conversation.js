/** @odoo-module **/
import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class LaSupportConversation extends Component {
    static template = "location_auto.LaSupportConversation";
    static props = { ...standardFieldProps };

    setup() {
        this.busService = this.env.services.bus_service;
        this.ticketId = this.props.record.resId;
        this.channel = "la_support_" + this.ticketId;
        this.messages = [];
        this.loading = true;
        this.sending = false;
        this.inputRef = useRef("input");
        this.onNotification = this.onNotification.bind(this);
        this.loadMessages();
        this.busService.addChannel(this.channel);
        this.busService.subscribe("la.support.message", this.onNotification);
    }

    async loadMessages() {
        this.loading = true;
        const messages = await this.env.services.orm.call(
            "la.support.ticket",
            "conversation",
            [this.ticketId]
        );
        this.messages = messages || [];
        this.loading = false;
        this.render();
        this.scrollToBottom();
    }

    onNotification(notif) {
        if (!notif || notif.ticket_id !== this.ticketId) return;
        if (this.messages.some((msg) => msg.id === notif.message_id)) return;
        this.messages.push({
            id: notif.message_id,
            body: notif.body,
            author_type: notif.author_type,
            author_name: notif.author_name,
            create_date: notif.create_date,
        });
        this.render();
        this.scrollToBottom();
    }

    scrollToBottom() {
        const box = this.el && this.el.querySelector(".la-backend-chat-messages");
        if (box) box.scrollTop = box.scrollHeight;
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.onSend();
        }
    }

    async onSend() {
        if (this.sending) return;
        const input = this.inputRef.el;
        const body = input.value.trim();
        if (!body) return;
        this.sending = true;
        input.value = "";
        this.render();
        try {
            const message = await this.env.services.orm.call(
                "la.support.ticket",
                "message_reply",
                [this.ticketId, body]
            );
            if (!this.messages.some((msg) => msg.id === message.id)) {
                this.messages.push(message);
            }
        } catch (e) {
            const current = this.inputRef.el;
            if (current) current.value = body;
        } finally {
            this.sending = false;
            this.render();
            this.scrollToBottom();
        }
    }
}

registry.category("fields").add("la_support_conversation", {
    component: LaSupportConversation,
    supportedTypes: ["char"],
});
