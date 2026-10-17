/* SWASA UI helpers: toasts, sheets, confirmation dialog, loading buttons.
   No dependencies. Everything is progressive: pages still work without it. */
(function () {
    'use strict';

    // ── Toasts ────────────────────────────────────────────────────────────
    var ICON = {
        success: '<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/></svg>',
        error: '<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>'
    };

    function toast(message, kind, ms) {
        var region = document.getElementById('toastRegion');
        if (!region) return;
        kind = (kind === 'error' || kind === 'warning') ? kind : 'success';
        var el = document.createElement('div');
        el.className = 'ds-toast ds-toast-' + kind;
        el.innerHTML = (kind === 'success' ? ICON.success : ICON.error) + '<span></span>';
        el.lastChild.textContent = message;
        region.appendChild(el);
        setTimeout(function () {
            el.classList.add('is-leaving');
            setTimeout(function () { el.remove(); }, 220);
        }, ms || (kind === 'error' ? 6000 : 3500));
    }
    window.swasaToast = toast;

    // ── Sheets (native <dialog>) ──────────────────────────────────────────
    function openSheet(id) {
        var d = document.getElementById(id);
        if (d && typeof d.showModal === 'function' && !d.open) d.showModal();
        return d;
    }
    function closeSheet(d) { if (d && d.open) d.close(); }
    window.swasaOpenSheet = openSheet;
    window.swasaCloseSheet = closeSheet;

    document.addEventListener('click', function (e) {
        var opener = e.target.closest('[data-sheet-open]');
        if (opener) { openSheet(opener.getAttribute('data-sheet-open')); return; }
        var closer = e.target.closest('[data-sheet-close]');
        if (closer) { closeSheet(closer.closest('dialog')); return; }
        // click on the backdrop (the <dialog> itself) closes it
        if (e.target.tagName === 'DIALOG' && e.target.classList.contains('ds-sheet')) closeSheet(e.target);
    });

    // ── Confirmation dialog (replaces window.confirm) ─────────────────────
    function confirmDialog(opts) {
        return new Promise(function (resolve) {
            var d = document.createElement('dialog');
            d.className = 'ds-sheet';
            d.setAttribute('aria-labelledby', 'cfTitle');
            d.innerHTML =
                '<div class="ds-sheet-grab" aria-hidden="true"></div>' +
                '<div class="ds-sheet-head"><div><h2 class="ds-sheet-title" id="cfTitle"></h2></div></div>' +
                '<div class="ds-sheet-body"><p class="ds-sheet-sub" style="font-size:14px;line-height:1.5"></p></div>' +
                '<div class="ds-sheet-foot">' +
                '<button type="button" class="ds-btn ds-btn-danger ds-btn-lg ds-btn-block" data-yes></button>' +
                '<button type="button" class="ds-btn ds-btn-ghost ds-btn-block" data-no>Cancel</button></div>';
            d.querySelector('#cfTitle').textContent = opts.title || 'Are you sure?';
            d.querySelector('p').textContent = opts.message || '';
            d.querySelector('[data-yes]').textContent = opts.confirmLabel || 'Confirm';
            var done = false;
            function finish(v) { if (done) return; done = true; d.close(); d.remove(); resolve(v); }
            d.querySelector('[data-yes]').addEventListener('click', function () { finish(true); });
            d.querySelector('[data-no]').addEventListener('click', function () { finish(false); });
            d.addEventListener('cancel', function (ev) { ev.preventDefault(); finish(false); });
            d.addEventListener('click', function (ev) { if (ev.target === d) finish(false); });
            document.body.appendChild(d);
            d.showModal();
            d.querySelector('[data-no]').focus();
        });
    }
    window.swasaConfirm = confirmDialog;

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form.hasAttribute || !form.hasAttribute('data-confirm') || form.__confirmed) return;
        e.preventDefault();
        confirmDialog({
            title: form.getAttribute('data-confirm-title') || 'Are you sure?',
            message: form.getAttribute('data-confirm'),
            confirmLabel: form.getAttribute('data-confirm-label') || 'Confirm'
        }).then(function (ok) {
            if (ok) { form.__confirmed = true; form.submit(); }
        });
    });

    // ── Loading button helper ─────────────────────────────────────────────
    window.swasaSetLoading = function (btn, on, text) {
        if (!btn) return;
        var lbl = btn.querySelector('.lbl');
        if (on) {
            btn.__label = lbl ? lbl.textContent : '';
            btn.classList.add('is-loading');
            btn.setAttribute('aria-busy', 'true');
            btn.disabled = true;
            if (lbl) lbl.textContent = text || 'Please wait…';
            if (!btn.querySelector('.ds-spinner-sm')) {
                var sp = document.createElement('span');
                sp.className = 'ds-spinner-sm';
                btn.insertBefore(sp, btn.firstChild);
            }
        } else {
            btn.classList.remove('is-loading');
            btn.removeAttribute('aria-busy');
            btn.disabled = false;
            if (lbl && btn.__label) lbl.textContent = btn.__label;
            var s = btn.querySelector('.ds-spinner-sm');
            if (s) s.remove();
        }
    };

    // ── Server messages → toasts ──────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-toast-message]').forEach(function (n) {
            var tag = n.getAttribute('data-kind') || '';
            toast(n.textContent.trim(), /error|danger/.test(tag) ? 'error' : /warning/.test(tag) ? 'warning' : 'success');
        });
    });
})();
