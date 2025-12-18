from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, abort, session
from . import db, bcrypt
from .models import Admin, Staff, Payment, Loan
from flask_login import login_user, logout_user, login_required, current_user
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pandas as pd, datetime

bp = Blueprint('routes', __name__)

# -------------------------------------------------
# Ensure Default Admin Exists
# -------------------------------------------------
@bp.before_app_request
def ensure_admin():
    admin = Admin.query.filter_by(email='admin@example.com').first()
    if not admin:
        pw = bcrypt.generate_password_hash('adminpass').decode('utf-8')
        admin = Admin(email='admin@example.com', password=pw)
        db.session.add(admin)
        db.session.commit()

# -------------------------------------------------
# Session Protection
# -------------------------------------------------
@bp.before_app_request
def protect_routes():
    if current_user.is_authenticated and not current_user.is_active:
        logout_user()
        session.clear()
        flash("Session expired, please login again.", "warning")
        return redirect(url_for('routes.index'))

# -------------------------------------------------
# Role Guards
# -------------------------------------------------
def admin_required(f):
    @login_required
    def wrapper(*args, **kwargs):
        if isinstance(current_user, Staff):
            flash("Access denied: Staff cannot view admin pages.", "danger")
            return redirect(url_for("routes.staff_dashboard"))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def staff_required(f):
    @login_required
    def wrapper(*args, **kwargs):
        if isinstance(current_user, Admin):
            flash("Access denied: Admin cannot view staff pages.", "danger")
            return redirect(url_for("routes.admin_dashboard"))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# -------------------------------------------------
# Home Page
# -------------------------------------------------
@bp.route('/')
def index():
    return render_template('index.html')

# -------------------------------------------------
# Admin Authentication
# -------------------------------------------------
@bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.admin_dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        pw = request.form['password']
        admin = Admin.query.filter_by(email=email).first()
        if admin and bcrypt.check_password_hash(admin.password, pw):
            login_user(admin)
            flash('Logged in as admin', 'success')
            return redirect(url_for('routes.admin_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('admin/login.html')


@bp.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    session.clear()
    flash('Admin logged out', 'info')
    return render_template('logout.html', user_type="Admin", login_url=url_for('routes.admin_login'))

# -------------------------------------------------
# Staff Authentication
# -------------------------------------------------
@bp.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.staff_dashboard'))

    if request.method == 'POST':
        staff_id = request.form['staff_id']
        pw = request.form['password']

        staff = Staff.query.filter_by(staff_id=staff_id).first()
        if staff and bcrypt.check_password_hash(staff.password, pw):
            if not staff.approved:
                flash("Your account is not yet approved by the admin.", "warning")
                return redirect(url_for('routes.staff_login'))
            login_user(staff)
            flash(f"Welcome, {staff.name}!", "success")
            return redirect(url_for('routes.staff_dashboard'))
        else:
            flash("Invalid Staff ID or Password", "danger")

    return render_template('staff/login.html')


@bp.route('/staff/register', methods=['GET', 'POST'])
def staff_register():
    if request.method == 'POST':
        staff_id = request.form['staff_id']
        name = request.form['name']
        password = request.form['password']

        existing = Staff.query.filter_by(staff_id=staff_id).first()
        if existing:
            flash("Staff ID already registered. Please log in instead.", "warning")
            return redirect(url_for('routes.staff_login'))

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        staff = Staff(staff_id=staff_id, name=name, password=pw_hash, approved=False)
        db.session.add(staff)
        db.session.commit()

        flash("Registration successful. Please wait for admin approval.", "info")
        return redirect(url_for('routes.staff_login'))

    return render_template('staff/register.html')


@bp.route('/staff/logout')
@login_required
def staff_logout():
    logout_user()
    session.clear()
    flash('Logged out successfully.', 'info')
    return render_template('logout.html', user_type="Staff", login_url=url_for('routes.staff_login'))

# -------------------------------------------------
# Admin Dashboard
# -------------------------------------------------
@bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    staff_count = Staff.query.count()
    payments_count = Payment.query.count()
    loans_count = Loan.query.count()
    pending_staff = Staff.query.filter_by(approved=False).all()
    return render_template('admin/dashboard.html',
                           staff_count=staff_count,
                           payments_count=payments_count,
                           loans_count=loans_count,
                           pending_staff=pending_staff)

# -------------------------------------------------
# Manage Staff
# -------------------------------------------------
@bp.route('/admin/manage-staff')
@admin_required
def admin_manage_staff():
    staff_members = Staff.query.order_by(Staff.id.desc()).all()
    return render_template('admin/manage_staff.html', staff_members=staff_members)

# -------------------------------------------------
# ✅ Admin: Approve / Reject Staff
# -------------------------------------------------
@bp.route('/admin/approve/<int:id>')
@admin_required
def approve_staff(id):
    staff = Staff.query.get_or_404(id)
    staff.approved = True
    db.session.commit()
    flash(f"{staff.name} has been approved successfully!", "success")
    return redirect(url_for('routes.admin_manage_staff'))


@bp.route('/admin/reject/<int:id>')
@admin_required
def reject_staff(id):
    staff = Staff.query.get_or_404(id)
    db.session.delete(staff)
    db.session.commit()
    flash(f"{staff.name} has been removed successfully.", "info")
    return redirect(url_for('routes.admin_manage_staff'))

# -------------------------------------------------
# Upload Payments
# -------------------------------------------------
@bp.route('/admin/upload-payments', methods=['GET', 'POST'])
@admin_required
def upload_payments():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('Please choose a CSV file.', 'warning')
            return redirect(url_for('routes.upload_payments'))

        try:
            df = pd.read_csv(file)
            required_cols = {'staff_id', 'amount', 'month'}
            if not required_cols.issubset(df.columns):
                flash('CSV must have columns: staff_id, amount, month', 'danger')
                return redirect(url_for('routes.upload_payments'))

            for _, row in df.iterrows():
                staff = Staff.query.filter_by(staff_id=row['staff_id']).first()
                if staff:
                    payment = Payment(
                        staff_id=staff.staff_id,
                        amount=float(row['amount']),
                        month=row['month']
                    )
                    db.session.add(payment)
            db.session.commit()
            flash('Payments uploaded successfully!', 'success')
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')

        return redirect(url_for('routes.admin_dashboard'))

    return render_template('admin/upload_payments.html')

# -------------------------------------------------
# Upload Loans (✅ FIX: Handle Loan Repayments Properly)
# -------------------------------------------------
@bp.route('/admin/upload-loans', methods=['GET', 'POST'])
@admin_required
def upload_loans():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('Please choose a CSV file.', 'warning')
            return redirect(url_for('routes.upload_loans'))

        try:
            df = pd.read_csv(file)
            required_cols = {'staff_id', 'amount', 'status'}
            if not required_cols.issubset(df.columns):
                flash('CSV must have columns: staff_id, amount, status', 'danger')
                return redirect(url_for('routes.upload_loans'))

            for _, row in df.iterrows():
                staff_id = str(row['staff_id']).strip()
                amount = float(row['amount'])
                status = str(row.get('status', 'pending')).strip().lower()

                staff = Staff.query.filter_by(staff_id=staff_id).first()
                if not staff:
                    flash(f"⚠️ Staff ID {staff_id} not found.", "warning")
                    continue

                if status in ['paid', 'repayment', 'paid_part']:
                    active_loan = (
                        Loan.query.filter_by(staff_id=staff_id, deleted=False)
                        .filter(Loan.status.in_(['approved', 'paid']))
                        .order_by(Loan.id.desc())
                        .first()
                    )

                    if active_loan:
                        active_loan.paid_amount = (active_loan.paid_amount or 0) + amount
                        active_loan.balance_amount = max(0, (active_loan.total_amount or active_loan.amount) - active_loan.paid_amount)

                        if active_loan.balance_amount <= 0:
                            active_loan.status = 'paid'
                            flash(f"✅ Loan for {staff_id} fully repaid and closed.", "success")
                        else:
                            flash(f"💰 {staff_id} repaid ₹{amount}. Remaining: ₹{active_loan.balance_amount:.2f}", "info")

                        db.session.add(active_loan)
                    else:
                        flash(f"⚠️ No active loan found for {staff_id}.", "warning")
                else:
                    loan = Loan(
                        staff_id=staff_id,
                        amount=amount,
                        status=status if status in ['approved', 'pending', 'rejected'] else 'pending'
                    )
                    db.session.add(loan)

            db.session.commit()
            flash('✅ Loan data processed successfully!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error processing file: {str(e)}', 'danger')

        return redirect(url_for('routes.admin_dashboard'))

    return render_template('admin/upload_loans.html')

# -------------------------------------------------
# Admin Payments
# -------------------------------------------------
@bp.route('/admin/payments')
@admin_required
def admin_payments():
    payments = Payment.query.order_by(Payment.id.desc()).all()
    return render_template('admin/payments.html', payments=payments)

# -------------------------------------------------
# Admin Pending Loans
# -------------------------------------------------
@bp.route('/admin/pending-loans')
@admin_required
def admin_pending_loans():
    pending_loans = Loan.query.filter_by(status='pending').order_by(Loan.requested_on.desc()).all()
    return render_template('admin/pending_loans.html', loans=pending_loans)

# -------------------------------------------------
# ✅ Admin: Approve / Reject Loan Requests
# -------------------------------------------------
@bp.route('/admin/loan/approve/<int:id>')
@admin_required
def admin_loan_approve(id):
    loan = Loan.query.get_or_404(id)
    loan.status = 'approved'
    db.session.commit()
    flash(f"Loan ID {loan.id} for Staff {loan.staff_id} approved successfully!", "success")
    return redirect(url_for('routes.admin_pending_loans'))


@bp.route('/admin/loan/reject/<int:id>')
@admin_required
def admin_loan_reject(id):
    loan = Loan.query.get_or_404(id)
    loan.status = 'rejected'
    db.session.commit()
    flash(f"Loan ID {loan.id} for Staff {loan.staff_id} rejected.", "info")
    return redirect(url_for('routes.admin_pending_loans'))

# -------------------------------------------------
# Reports
# -------------------------------------------------
@bp.route('/admin/report-payments')
@admin_required
def report_payments():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(220, 800, "Staff Payments Report")

    payments = Payment.query.order_by(Payment.created_on.desc()).all()
    y = 760
    pdf.setFont("Helvetica", 10)
    for p in payments:
        pdf.drawString(60, y, f"Staff ID: {p.staff_id} | Amount: ₹{p.amount} | Month: {p.month} | Date: {p.created_on.strftime('%Y-%m-%d')}")
        y -= 18
        if y < 80:
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 10)

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="payments_report.pdf", mimetype="application/pdf")


@bp.route('/admin/report-loans')
@admin_required
def report_loans():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(220, 800, "Staff Loans Report")

    loans = Loan.query.order_by(Loan.requested_on.desc()).all()
    y = 760
    pdf.setFont("Helvetica", 10)
    for l in loans:
        pdf.drawString(60, y, f"Staff ID: {l.staff_id} | Amount: ₹{l.amount} | Status: {l.status} | Date: {l.requested_on.strftime('%Y-%m-%d')}")
        y -= 18
        if y < 80:
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 10)

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="loans_report.pdf", mimetype="application/pdf")

# -------------------------------------------------
# Staff Dashboard (✅ FIXED Paid Column Sync)
# -------------------------------------------------
@bp.route('/staff/dashboard')
@staff_required
def staff_dashboard():
    payments = Payment.query.filter_by(staff_id=current_user.staff_id).all()
    total_payments = sum(p.amount for p in payments) if payments else 0

    loans = (
        Loan.query.filter(
            Loan.staff_id == current_user.staff_id,
            Loan.deleted == False
        )
        .filter(Loan.status.in_(['approved', 'paid']))
        .order_by(Loan.id.desc())
        .all()
    )

    for loan in loans:
        if loan.total_amount is None:
            loan.total_amount = loan.amount
        if loan.paid_amount is None:
            loan.paid_amount = 0
        if loan.balance_amount is None or loan.balance_amount < 0:
            loan.balance_amount = loan.total_amount - loan.paid_amount
        if loan.balance_amount <= 0:
            loan.status = 'paid'

    db.session.commit()

    total_loans = sum(l.balance_amount for l in loans if l.balance_amount > 0)

    return render_template(
        'staff/dashboard.html',
        payments=payments,
        loans=loans,
        total_payments=total_payments,
        total_loans=total_loans
    )

# -------------------------------------------------
# Staff Loan Request
# -------------------------------------------------
@bp.route('/staff/request-loan', methods=['GET', 'POST'])
@staff_required
def staff_request_loan():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        tenure = int(request.form['tenure'])
        if not current_user.staff_id:
            flash('Your staff ID not assigned yet', 'warning')
            return redirect(url_for('routes.staff_dashboard'))

        interest_rate = 5 if tenure == 10 else 10
        l = Loan(
            staff_id=current_user.staff_id,
            amount=amount,
            interest_rate=interest_rate,
            tenure_months=tenure,
            status='pending'
        )
        l.calculate_total_with_interest()
        db.session.add(l)
        db.session.commit()
        flash(f"Loan request submitted for ₹{amount:.2f} ({tenure} months at {interest_rate}% interest)", "success")
        return redirect(url_for('routes.staff_dashboard'))

    return render_template('staff/request_loan.html')
