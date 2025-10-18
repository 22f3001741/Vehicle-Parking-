from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from config import Config
import os
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login' # Route name for the login page
login_manager.login_message_category = 'info' # Flash message category for login required
bcrypt = Bcrypt()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
      # Add datetime related functions to the template context
    from datetime import datetime, timedelta
    @app.context_processor
    def utility_processor():
        return {
            'now': datetime.now,
            'timedelta': timedelta,
            'IST_OFFSET': 5.5  # IST is UTC+5:30 (5.5 hours)
        }

    # Ensure the instance folder exists for SQLite DB
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    # Import and register blueprints
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        # Import models here to avoid circular imports
        from app import models
        db.create_all() # Create database tables if they don't exist

        # Create admin user if it doesn't exist
        admin_username = 'admin' # Standard admin username
        admin_password = 'password' # Change this in a real app!
        if not models.User.query.filter_by(username=admin_username).first():
            admin_user = models.User(username=admin_username, is_admin=True)
            # Use the set_password method which handles hashing
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            db.session.commit()
            print(f"Admin user '{admin_username}' created.")

    return app

# User loader function required by Flask-Login
@login_manager.user_loader
def load_user(user_id):
    # Import models here as well, or move the import to the top
    # if you refactor to avoid circular dependencies differently.
    from app.models import User
    return User.query.get(int(user_id))