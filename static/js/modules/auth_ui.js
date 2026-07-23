/**
 * Shared Auth UI helpers.
 *
 * - `ensureLogin()`: checks auth status, redirects to /login?redirect=...
 *   if the user is not logged in. Returns the user object when logged in.
 * - `initNavUserInfo()`: fills the navigation bar with the username and a
 *   logout button.
 *
 * Call `initAuth()` at the top of any protected page to do both.
 */
import { authMe, authLogout } from './api.js';

let _currentUser = null;

function _redirectToLogin() {
    const here = window.location.pathname;
    // Don't redirect in an endless loop from the login page itself.
    if (here === '/login') return;
    window.location.href = `/login?redirect=${encodeURIComponent(here)}`;
}

/**
 * Ensure the user is logged in. Returns the user dict or null.
 * If ``redirect`` is true, unauthenticated users are sent to /login.
 */
async function ensureLogin(redirect = true) {
    const data = await authMe();
    if (data.success && data.user) {
        _currentUser = data.user;
        return data.user;
    }
    _currentUser = null;
    if (redirect) {
        _redirectToLogin();
    }
    return null;
}

/**
 * Update the nav bar with username + logout button.
 * Expects these elements exist in the page:
 *   - #navUserInfo (container, starts hidden)
 *   - #navUsername (span where the username goes)
 *   - #navLogoutBtn (logout button)
 *   - #navLoginLink (the "登录" link to hide when logged in)
 */
function initNavUserInfo(user) {
    const infoEl = document.getElementById('navUserInfo');
    const nameEl = document.getElementById('navUsername');
    const loginLink = document.getElementById('navLoginLink');

    if (!infoEl || !nameEl || !loginLink) return;

    if (user) {
        nameEl.textContent = user.username;
        infoEl.style.display = 'flex';
        loginLink.style.display = 'none';
    } else {
        infoEl.style.display = 'none';
        loginLink.style.display = 'inline-block';
    }

    const logoutBtn = document.getElementById('navLogoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await authLogout();
            window.location.href = '/login';
        });
    }
}

/**
 * Combined init: check login (redirect if not), then update the nav.
 * Call this on every protected page.
 */
async function initAuth() {
    const user = await ensureLogin(true);
    initNavUserInfo(user);
    return user;
}

function getCurrentUser() {
    return _currentUser;
}

export { ensureLogin, initNavUserInfo, initAuth, getCurrentUser };
