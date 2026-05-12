# Flask LMS

A simple Learning Management System built with Python, Flask, MySQL, HTML, and CSS.

## Features

- Register and login on separate pages
- Password hashing with Werkzeug
- Login with username or email
- Forgot password reset by username or email
- Student and instructor account types
- Students can select courses
- Add courses
- Instructors can add module notes
- Students can view notes for selected courses
- Upload assignments
- Add marks
- Check marks and results

## Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create the MySQL database and tables.

```powershell
mysql -u root -p < schema.sql
```

If you already created the earlier version of the database, run this update once instead:

```powershell
mysql -u root -p < migration_update.sql
```

4. Set database environment variables if your MySQL credentials are not the defaults.

```powershell
$env:MYSQL_HOST="localhost"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="your_mysql_password"
$env:MYSQL_DATABASE="lms_db"
$env:SECRET_KEY="replace-with-a-random-secret"
```

5. Run the app.

```powershell
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Notes

- Assignment uploads are stored in the `uploads` folder.
- Instructors can add courses and marks.
- Instructors can add module notes for their courses.
- Students can select courses, upload assignments, read notes, and view their own results.
