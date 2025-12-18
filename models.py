from . import db, login_manager
from flask_login import UserMixin
from datetime import datetime

# -------------------------------------------
# Admin Model
# -------------------------------------------
class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def get_id(self):
        """Unique ID for Flask-Login"""
        return f"Admin-{self.id}"


# -------------------------------------------
# Staff Model
# -------------------------------------------
class Staff(UserMixin, db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    approved = db.Column(db.Boolean, default=False)
    registered_on = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        """Unique ID for Flask-Login"""
        return f"Staff-{self.id}"


# -------------------------------------------
# Payment Model
# -------------------------------------------
class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.String(20), db.ForeignKey('staff.staff_id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.String(20), nullable=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)


# -------------------------------------------
# Loan Model (Enhanced)
# -------------------------------------------
class Loan(db.Model):
    __tablename__ = 'loans'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.String(20), db.ForeignKey('staff.staff_id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)  # Principal amount
    interest_rate = db.Column(db.Float, default=0.0)  # Interest rate (%)
    tenure_months = db.Column(db.Integer, default=10)  # Loan duration
    total_amount = db.Column(db.Float, default=0.0)  # Principal + interest
    paid_amount = db.Column(db.Float, default=0.0)  # Total paid till date
    balance_amount = db.Column(db.Float, default=0.0)  # Remaining balance
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    requested_on = db.Column(db.DateTime, default=datetime.utcnow)
    deleted = db.Column(db.Boolean, default=False)

    def calculate_total_with_interest(self):
        """Compute total payable (principal + interest)"""
        interest = (self.amount * self.interest_rate) / 100
        self.total_amount = self.amount + interest
        self.balance_amount = self.total_amount

    def apply_payment(self, payment_amount):
        """Reduce balance when admin updates payment"""
        self.paid_amount += payment_amount
        self.balance_amount = max(0.0, self.total_amount - self.paid_amount)
        if self.balance_amount <= 0:
            self.status = 'paid'


# -------------------------------------------
# Flask-Login Loader (supports Admin & Staff)
# -------------------------------------------
@login_manager.user_loader
def load_user(compound_id):
    """Load user by prefixed ID (Admin-1 / Staff-2)"""
    if not compound_id:
        return None

    try:
        role, user_id = compound_id.split('-', 1)
        user_id = int(user_id)
    except ValueError:
        return None

    if role == 'Admin':
        return Admin.query.get(user_id)
    elif role == 'Staff':
        return Staff.query.get(user_id)
    return None
