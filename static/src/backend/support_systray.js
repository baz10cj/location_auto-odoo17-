/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class SupportSystray extends Component {
    static template = "location_auto.SupportSystray";

    setup() {
        const services = this.env.services;
        this.orm = services.orm;
        this.actionService = services.action;
        this.notificationService = services.notification;
        this.busService = services.bus_service;
        this.userService = services.user;
        this.hasGroup = this.userService.hasGroup("location_auto.group_support_agent");
        this.unread = 0;
        this.highlight = false;
        this.seenNotifs = new Set();
        this.onNotification = this.onNotification.bind(this);
        this.loadUnread();
        if (this.hasGroup) {
            this.busService.addChannel("la_support_agents");
            this.busService.subscribe("la.support.agent.notif", this.onNotification);
        }
    }

    async loadUnread() {
        const total = await this.orm.call("la.support.ticket", "agent_unread_total", [[]]);
        this.unread = Number(total) || 0;
        this.render();
    }

    onNotification(notif) {
        if (!notif || !notif.ticket_id) return;
        if (notif.author_type !== "customer") return;
        if (notif.message_id && this.seenNotifs.has(notif.message_id)) return;
        if (notif.message_id) this.seenNotifs.add(notif.message_id);
        this.loadUnread();
        this.highlight = true;
        this.render();
        setTimeout(() => {
            this.highlight = false;
            this.render();
        }, 3000);
        this.notificationService.add(
            notif.body,
            {
                title: `Nouveau message client - ${notif.ticket_name || "Support"}`,
                type: "warning",
                sticky: false,
                onClick: () => this.openTicket(notif.ticket_id),
            }
        );
    }

    openTicket(ticketId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "la.support.ticket",
            res_id: ticketId,
            views: [[false, "form"]],
        });
    }

    openInbox() {
        this.actionService.doAction("location_auto.action_la_support_ticket");
    }
}

registry.category("systray").add("location_auto.support_systray", {
    Component: SupportSystray,
    sequence: 5,
});