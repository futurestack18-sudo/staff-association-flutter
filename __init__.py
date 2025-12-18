from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin
import os

# Initialize core extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'devsecretkey')

    # ✅ Define absolute path for SQLite database
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.abspath(os.path.join(basedir, '..', 'instance'))
    os.makedirs(instance_dir, exist_ok=True)

    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'sqlite:///' + os.path.join(instance_dir, 'atme.db').replace('\\', '/')
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # ✅ Import both models
    from app.models import Admin, Staff

    # ----------------------------------------
    # Enhanced Flask-Login integration
    # ----------------------------------------
    @login_manager.user_loader
    def load_user(compound_id):
        """Load user based on 'Role-ID' format."""
        if not compound_id:
            return None

        role, user_id = compound_id.split('-', 1)
        if role == 'Admin':
            return Admin.query.get(int(user_id))
        elif role == 'Staff':
            return Staff.query.get(int(user_id))
        return None

    # Monkey-patch get_id() for both Admin and Staff to store Role-ID
    def admin_get_id(self):
        return f"Admin-{self.id}"

    def staff_get_id(self):
        return f"Staff-{self.id}"

    Admin.get_id = admin_get_id
    Staff.get_id = staff_get_id

    # ----------------------------------------
    # Login configuration
    # ----------------------------------------
    login_manager.login_view = 'routes.staff_login'
    login_manager.login_message_category = 'warning'

    # Register blueprints
    from . import routes
    app.register_blueprint(routes.bp)

    # Create DB tables
    with app.app_context():
        db.create_all()

    # Prevent caching after logout
    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return app
