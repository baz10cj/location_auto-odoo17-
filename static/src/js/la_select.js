(function () {
    'use strict';

    function buildMenu(root) {
        var hidden = root.querySelector('select.la-select-hidden');
        var optionsBox = root.querySelector('.la-select-options');
        if (!hidden || !optionsBox) return;
        optionsBox.textContent = '';
        Array.prototype.slice.call(hidden.options).forEach(function (opt) {
            if (!opt.value) return;
            var item = document.createElement('button');
            item.type = 'button';
            item.className = 'la-select-option';
            item.dataset.value = opt.value;
            item.dataset.label = opt.textContent;
            var name = document.createElement('span');
            name.className = 'la-select-option-name';
            name.textContent = opt.textContent;
            var check = document.createElement('i');
            check.className = 'fa fa-check la-select-check';
            item.appendChild(name);
            item.appendChild(check);
            item.addEventListener('click', function () {
                selectValue(root, opt.value, opt.textContent, item);
            });
            optionsBox.appendChild(item);
        });
    }

    function selectValue(root, value, label, item) {
        var hidden = root.querySelector('select.la-select-hidden');
        var trigger = root.querySelector('.la-select-trigger');
        var triggerLabel = root.querySelector('.la-select-trigger-label');
        if (hidden) hidden.value = value;
        if (triggerLabel) triggerLabel.textContent = label;
        if (trigger && value) trigger.classList.add('la-filled');
        root.querySelectorAll('.la-select-option').forEach(function (it) {
            it.classList.toggle('la-selected', it === item);
        });
        closeMenu(root);
    }

    function preselect(root) {
        var hidden = root.querySelector('select.la-select-hidden');
        if (!hidden || !hidden.value) return;
        var option = hidden.options[hidden.selectedIndex];
        if (!option || !option.value) return;
        var item = root.querySelector('.la-select-option[data-value="' + option.value + '"]');
        if (item) selectValue(root, option.value, option.textContent, item);
    }

    function filterMenu(root, query) {
        var q = query.toLowerCase();
        root.querySelectorAll('.la-select-option').forEach(function (item) {
            item.hidden = q && item.dataset.label.toLowerCase().indexOf(q) === -1;
        });
    }

    function openMenu(root) {
        var search = root.querySelector('.la-select-search');
        var trigger = root.querySelector('.la-select-trigger');
        if (trigger) {
            var rect = trigger.getBoundingClientRect();
            var spaceBelow = window.innerHeight - rect.bottom;
            if (spaceBelow < 280 && rect.top > 320) {
                root.classList.add('la-open-up');
            } else {
                root.classList.remove('la-open-up');
            }
        }
        root.classList.add('la-open');
        root.setAttribute('aria-expanded', 'true');
        if (search) {
            search.value = '';
            filterMenu(root, '');
            search.focus();
        }
    }

    function closeMenu(root) {
        root.classList.remove('la-open');
        root.setAttribute('aria-expanded', 'false');
    }

    function bind(root) {
        var trigger = root.querySelector('.la-select-trigger');
        var search = root.querySelector('.la-select-search');
        if (trigger) {
            trigger.addEventListener('click', function (e) {
                e.stopPropagation();
                if (root.classList.contains('la-open')) {
                    closeMenu(root);
                } else {
                    openMenu(root);
                }
            });
        }
        if (search) {
            search.addEventListener('input', function () { filterMenu(root, search.value); });
        }
        document.addEventListener('click', function (e) {
            if (!root.contains(e.target)) closeMenu(root);
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeMenu(root);
        });
        buildMenu(root);
        preselect(root);
    }

    function initAll(context) {
        var els = (context || document).querySelectorAll('.la-select');
        for (var i = 0; i < els.length; i++) {
            if (!els[i].dataset.laBound) {
                els[i].dataset.laBound = '1';
                bind(els[i]);
            }
        }
    }

    initAll(document);
    if (typeof MutationObserver !== 'undefined') {
        new MutationObserver(function () {
            initAll(document);
        }).observe(document.documentElement, { childList: true, subtree: true });
    }
})();