# app.py

from flask import Flask, g
from db import get_db_connection
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from config import Config

jwt = JWTManager()
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    jwt.init_app(app)
    mail.init_app(app)

    @app.before_request
    def before_request():
        """Establish a database connection before each request."""
        g.db = get_db_connection()

    @app.teardown_request
    def teardown_request(exception):
        """Close the database connection after each request."""
        db = getattr(g, 'db', None)
        if db is not None and db.is_connected():
            db.close()

    from routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
