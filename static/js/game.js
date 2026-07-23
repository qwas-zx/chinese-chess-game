/**
 * Chinese Chess Game - Local Two-Player Entry Point
 *
 * Requires login; redirects to /login if not authenticated.
 */
import { initAuth } from './modules/auth_ui.js';
import { init } from './modules/ui.js';

(async function main() {
    const user = await initAuth();
    if (user) {
        init();
    }
})();
