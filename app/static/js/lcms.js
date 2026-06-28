// LCMS shared client-side utilities. No frameworks — vanilla JS/fetch,
// per the spec's "Jinja2 + Bootstrap 5 + vanilla JS/AJAX" frontend choice.

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

// Wraps fetch with the JWT CSRF double-submit header required by
// flask-jwt-extended's cookie-CSRF protection on state-changing requests.
async function lcmsFetch(url, options = {}) {
  const opts = Object.assign({ credentials: 'same-origin' }, options);
  opts.headers = Object.assign({}, options.headers);

  const method = (opts.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const csrfToken = getCookie('lcms_csrf_token');
    if (csrfToken) {
      opts.headers['X-CSRF-TOKEN'] = csrfToken;
    }
  }

  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json';
  }

  const resp = await fetch(url, opts);
  return resp;
}

// ---- Logout ----
document.addEventListener('DOMContentLoaded', () => {
  const logoutForm = document.getElementById('logout-form');
  if (logoutForm) {
    logoutForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await lcmsFetch('/api/auth/logout', { method: 'POST' });
      window.location.href = '/login';
    });
  }

  // ---- Notification bell ----
  const bell = document.getElementById('notif-bell');
  if (bell) {
    bell.addEventListener('click', async () => {
      let panel = document.getElementById('notif-panel');
      if (panel) {
        panel.remove();
        return;
      }
      const resp = await lcmsFetch('/api/notifications');
      if (!resp.ok) return;
      const data = await resp.json();

      panel = document.createElement('div');
      panel.id = 'notif-panel';
      panel.style.cssText = 'position:absolute; top:64px; right:36px; width:340px; max-height:420px; overflow-y:auto; background:var(--ivory-50); border:1px solid var(--line); border-radius:8px; box-shadow:0 12px 32px rgba(10,22,40,0.18); z-index:1100;';

      if (data.notifications.length === 0) {
        panel.innerHTML = '<div style="padding:24px; text-align:center; color:var(--ink-400); font-size:13px;">No notifications yet.</div>';
      } else {
        panel.innerHTML = data.notifications.map(n => `
          <div style="padding:14px 16px; border-bottom:1px solid var(--line); ${n.is_read ? 'opacity:0.6;' : ''}">
            <div style="font-size:13px; color:var(--ink-900); margin-bottom:4px;">${escapeHtml(n.message)}</div>
            <div style="font-size:11px; color:var(--ink-400);">${formatRelativeTime(n.created_at)}</div>
          </div>
        `).join('');
      }
      document.body.appendChild(panel);

      if (data.unread_count > 0) {
        await lcmsFetch('/api/notifications/read-all', { method: 'POST' });
        const badge = bell.querySelector('.lcms-bell-badge');
        if (badge) badge.remove();
      }

      setTimeout(() => {
        document.addEventListener('click', function closePanel(ev) {
          if (panel && !panel.contains(ev.target) && ev.target !== bell) {
            panel.remove();
            document.removeEventListener('click', closePanel);
          }
        });
      }, 0);
    });
  }
});

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatRelativeTime(isoString) {
  const date = new Date(isoString);
  const diffMs = Date.now() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}
