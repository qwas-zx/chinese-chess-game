import unittest

from flask import Flask, session

from game.game_session_manager import game_session_manager
from routes.ai_routes import register_ai_routes
from routes.game_routes import register_routes as register_game_routes


class AIRoutesTests(unittest.TestCase):
    def test_ai_review_returns_success_without_name_error(self):
        app = Flask(__name__)
        app.secret_key = 'test-secret'
        register_ai_routes(app)

        with app.test_request_context('/api/ai/review', method='POST'):
            session['user_id'] = 'user-1'
            session['username'] = 'tester'
            response = app.view_functions['ai_review']()

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['reviews'], [])

    def test_review_uses_real_move_history_entries(self):
        app = Flask(__name__)
        app.secret_key = 'test-secret'
        register_game_routes(app)

        game_session_manager.remove('user-2')
        with app.test_request_context('/api/review', method='POST'):
            session['user_id'] = 'user-2'
            session['username'] = 'tester2'
            game = game_session_manager.get_local_game('user-2')
            game.make_move(4, 9, 4, 8)
            response = app.view_functions['review']()

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['reviews']), 1)


if __name__ == '__main__':
    unittest.main()
