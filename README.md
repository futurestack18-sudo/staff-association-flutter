Staff Payments Portal - Ready to run
==================================

How to run (locally)
1. Create a virtual environment:
   python -m venv venv
   venv\Scripts\activate   (Windows) or source venv/bin/activate (mac/linux)

2. Install requirements:
   pip install -r requirements.txt

3. (Optional) Edit .env to set SECRET_KEY or DATABASE_URL.

4. Run:
   python app.py
   or
   flask run

Default admin:
 - email: admin@example.com
 - password: adminpass

Project structure:
[
  ".env",
  "app.py",
  "app/__init__.py",
  "app/models.py",
  "app/routes.py",
  "app/static/css/style.css",
  "app/templates/admin/dashboard.html",
  "app/templates/admin/loans.html",
  "app/templates/admin/login.html",
  "app/templates/admin/payments.html",
  "app/templates/admin/staff_list.html",
  "app/templates/admin/upload_loans.html",
  "app/templates/admin/upload_payments.html",
  "app/templates/base.html",
  "app/templates/index.html",
  "app/templates/staff/dashboard.html",
  "app/templates/staff/login.html",
  "app/templates/staff/register.html",
  "app/templates/staff/request_loan.html",
  "requirements.txt",
  "run.bat",
  "run.sh"
]

Notes:
 - This is a minimal, functional starter project.
 - CSV uploads use pandas; expected columns are described in upload pages.
 - Reports generate simple PDFs via ReportLab.

