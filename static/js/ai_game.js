/**
 * Chinese Chess Game - AI Battle Entry Point
 *
 * Requires login; redirects to /login if not authenticated.
 */
import { initAuth } from './modules/auth_ui.js';
import { initAiBattle } from './modules/ai_battle.js';

(async function main() {
    const user = await initAuth();
    if (user) {
        initAiBattle();
    }
})();
