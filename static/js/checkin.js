/* Student check-in. Same backend contract as before:
   POST <data-url> with session_id + code (+ CSRF) -> JSON { success, course_id } or { error }. */
(function () {
    'use strict';
    var sheet = document.getElementById('checkinSheet');
    if (!sheet) return;
    var form = document.getElementById('checkinForm');
    var input = document.getElementById('ciCode');
    var errorEl = document.getElementById('ciError');
    var submitBtn = document.getElementById('ciSubmit');
    var current = null;   // { session, course }

    function csrf() {
        var m = document.querySelector('meta[name="csrf-token"]');
        return (m && m.content) || ((document.cookie.match(/csrftoken=([^;]+)/) || [])[1]);
    }
    function showError(msg) {
        errorEl.textContent = msg;
        errorEl.hidden = false;
        input.classList.add('ds-input-invalid');
        input.setAttribute('aria-invalid', 'true');
    }
    function clearError() {
        errorEl.hidden = true;
        errorEl.textContent = '';
        input.classList.remove('ds-input-invalid');
        input.removeAttribute('aria-invalid');
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-checkin]');
        if (!btn) return;
        current = { session: btn.getAttribute('data-session'), course: btn.getAttribute('data-course') };
        document.getElementById('ciSub').textContent = btn.getAttribute('data-title') || '';
        input.value = '';
        clearError();
        window.swasaOpenSheet('checkinSheet');
        setTimeout(function () { input.focus(); }, 60);
    });

    input.addEventListener('input', function () {
        // digits only, tolerate pasted spaces/dashes
        input.value = input.value.replace(/[^0-9]/g, '').slice(0, 6);
        if (!errorEl.hidden) clearError();
    });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!current) return;
        var code = input.value.trim();
        if (code.length !== 6) { showError('Enter the full 6-digit code.'); input.focus(); return; }
        clearError();
        window.swasaSetLoading(submitBtn, true, 'Checking in…');

        fetch(sheet.getAttribute('data-url'), {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'session_id=' + encodeURIComponent(current.session) + '&code=' + encodeURIComponent(code)
        }).then(function (res) {
            return res.json().then(function (data) { return { ok: res.ok, data: data }; });
        }).then(function (r) {
            window.swasaSetLoading(submitBtn, false);
            if (r.ok) {
                var tpl = document.getElementById('tplRecorded');
                document.querySelectorAll('.js-state[data-session="' + current.session + '"]').forEach(function (zone) {
                    zone.innerHTML = '';
                    zone.appendChild(tpl.content.cloneNode(true));
                });
                var cid = r.data.course_id || current.course;
                document.querySelectorAll('[data-attended-for="' + cid + '"]').forEach(function (n) {
                    n.textContent = String((parseInt(n.textContent, 10) || 0) + 1);
                });
                window.swasaCloseSheet(sheet);
                window.swasaToast('Attendance recorded.');
            } else {
                showError(r.data.error || 'We could not record your attendance. Please try again.');
                input.focus();
            }
        }).catch(function () {
            window.swasaSetLoading(submitBtn, false);
            showError('No connection. Check your network and try again.');
        });
    });
})();
