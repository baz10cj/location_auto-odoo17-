odoo.define('location_auto.table_search', [], function (require) {
    'use strict';

    function bindSearch(input) {
        var target = document.querySelector(input.dataset.searchTarget);
        if (!target) return;
        var rowSel = input.dataset.searchRow || 'li';
        var rows = Array.prototype.slice.call(target.querySelectorAll(rowSel));
        var empty = target.lastElementChild && target.lastElementChild.classList.contains('la-search-empty')
            ? target.lastElementChild
            : (target.nextElementSibling && target.nextElementSibling.classList.contains('la-search-empty')
                ? target.nextElementSibling
                : null);
        input.addEventListener('input', function () {
            var q = input.value.trim().toLowerCase();
            var any = false;
            rows.forEach(function (li) {
                var hit = !q || (li.textContent || '').toLowerCase().indexOf(q) !== -1;
                li.hidden = !hit;
                if (hit) any = true;
            });
            if (empty) empty.hidden = any;
        });
    }

    function initAll(context) {
        (context || document).querySelectorAll('.la-search-bar:not([data-la-bound])').forEach(function (input) {
            input.dataset.laBound = '1';
            bindSearch(input);
        });
    }

    initAll(document);
    if (typeof MutationObserver !== 'undefined') {
        new MutationObserver(function () { initAll(document); }).observe(document.documentElement, { childList: true, subtree: true });
    }
});