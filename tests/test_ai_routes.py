import unittest

from flask import Flask, session

from routes.ai_routes import register_ai_routes


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


if __name__ == '__main__':
    unittest.main()
