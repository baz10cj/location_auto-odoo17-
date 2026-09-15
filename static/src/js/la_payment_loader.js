(function () {
    'use strict';

    var WALLET_HTML = '<span class="la-wallet la-wallet-left"></span>'
        + '<span class="la-wallet la-wallet-right"></span>'
        + '<span class="la-coin">$</span>';

    function inject() {
        document.querySelectorAll('.o_blockUI .o_spinner').forEach(function (sp) {
            if (sp.dataset.laWallet) return;
            sp.dataset.laWallet = '1';
            sp.classList.add('la-wallet-host');
            var img = sp.querySelector('img');
            if (img) img.remove();
            var anim = document.createElement('div');
            anim.className = 'la-wallet-anim';
            anim.innerHTML = WALLET_HTML;
            sp.appendChild(anim);
        });
    }

    inject();
    if (typeof MutationObserver !== 'undefined') {
        new MutationObserver(inject).observe(document.body, { childList: true, subtree: true });
    }
})();