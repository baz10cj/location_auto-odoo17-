(function () {
    'use strict';

    var root = document.getElementById('la-chat');
    if (!root) return;

    var ticketId = root.dataset.ticketId;
    var wsVersion = root.dataset.wsVersion || '17.0-3';
    var token = root.dataset.token || '';
    var lastId = Number(root.dataset.lastId) || 0;
    var channel = 'la_support_' + ticketId;
    var wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/websocket?version=' + encodeURIComponent(wsVersion);

    var list = document.getElementById('la-chat-messages');
    var input = document.getElementById('la-chat-input');
    var sendBtn = document.getElementById('la-chat-send');
    var statusEl = document.getElementById('la-chat-status');
    var seen = {};
    var ws = null;
    var closed = false;

    document.querySelectorAll('.la-chat-bubble').forEach(function (bubble) {
        var id = Number(bubble.dataset.msgId);
        if (id) seen[id] = true;
    });
    list.scrollTop = list.scrollHeight;

    function setStatus(state) {
        if (statusEl) statusEl.textContent = state;
    }

    function addBubble(msg, forceScroll) {
        if (seen[msg.id]) return;
        seen[msg.id] = true;
        lastId = Math.max(lastId, msg.id || 0);
        var nearBottom = forceScroll || list.scrollHeight - list.scrollTop - list.clientHeight < 80;
        var bubble = document.createElement('div');
        bubble.className = 'la-chat-bubble ' + (msg.author_type === 'agent' ? 'la-chat-agent' : 'la-chat-customer');
        if (msg.author_type === 'agent') {
            var avatar = document.createElement('span');
            avatar.className = 'la-chat-avatar';
            var img = document.createElement('img');
            img.src = '/location_auto/static/img/LOGO.png';
            img.alt = '';
            avatar.appendChild(img);
            bubble.appendChild(avatar);
        }
        var content = document.createElement('div');
        content.className = 'la-chat-bubble-content';
        var meta = document.createElement('span');
        meta.className = 'la-chat-meta';
        meta.textContent = msg.author_type === 'agent' ? 'SUPPORT' : 'Vous';
        var p = document.createElement('p');
        p.textContent = msg.body;
        content.appendChild(meta);
        content.appendChild(p);
        bubble.appendChild(content);
        list.appendChild(bubble);
        if (nearBottom) list.scrollTop = list.scrollHeight;
    }

    function connect() {
        if (closed) return;
        ws = new WebSocket(wsUrl);
        ws.onopen = function () {
            ws.send(JSON.stringify({
                event_name: 'subscribe',
                data: { channels: [channel], last: lastId }
            }));
            setStatus('Connecté');
        };
        ws.onmessage = function (ev) {
            var notifications;
            try {
                notifications = JSON.parse(ev.data);
            } catch (e) {
                return;
            }
            if (!Array.isArray(notifications)) return;
            notifications.forEach(function (n) {
                if (n && n.id) lastId = Math.max(lastId, n.id);
                if (!n || !n.message || n.message.type !== 'la.support.message') return;
                var payload = n.message.payload || {};
                if (String(payload.ticket_id) !== String(ticketId)) return;
                addBubble({
                    id: payload.message_id,
                    body: payload.body,
                    author_type: payload.author_type,
                    author_name: payload.author_name,
                    create_date: payload.create_date
                });
            });
        };
        ws.onclose = function () {
            setStatus('Connexion...');
            setTimeout(connect, 4000);
        };
        ws.onerror = function () {
            try { ws.close(); } catch (e) {}
        };
    }

    function send() {
        var body = input.value.trim();
        if (!body) return;
        input.value = '';
        fetch('/support/ticket/' + ticketId + '/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ body: body, t: token })
        }).then(function (r) {
            return r.json();
        }).then(function (data) {
            if (data.success) {
                addBubble(data.message, true);
            } else if (data.error) {
                alert(data.error);
            }
        }).catch(function () {});
    }

    var polling = false;
    var pollOk = false;

    function poll() {
        if (polling || closed) return;
        polling = true;
        fetch('/support/ticket/' + ticketId + '/messages?after=' + lastId + '&t=' + encodeURIComponent(token))
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (!data.success) return;
                if (!pollOk) {
                    pollOk = true;
                    if (!ws || ws.readyState !== WebSocket.OPEN) setStatus('En ligne');
                }
                (data.messages || []).forEach(function (msg) {
                    addBubble(msg);
                });
            })
            .catch(function () {})
            .then(function () {
                polling = false;
                schedulePoll(ws && ws.readyState === WebSocket.OPEN ? 12000 : 4000);
            });
    }

    function schedulePoll(ms) {
        setTimeout(poll, ms);
    }

    sendBtn.addEventListener('click', send);
    input.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) {
            ev.preventDefault();
            send();
        }
    });

    connect();
    schedulePoll(4000);
})();