# Blood Bank Reagent Quality & Inventory Management System

Flask, SQLite, HTML, CSS, and Bootstrap web application for blood bank reagent and inventory management.

## Quick Open

When the app is running locally, open it here:

[Open the web app](http://127.0.0.1:5000/)

If you are sharing it with someone else on the same network, replace `127.0.0.1` with your computer's local IP address.

## Public Web Link

This project is now ready to deploy to a hosting service that gives you a public URL.

For Replit, use:

- `main.py`
- `.replit`

Use the production entry point:

- `wsgi.py`
- `Procfile`

Typical deployment command:

- `gunicorn wsgi:application`

Good next steps for a public link:

1. Push this repository to GitHub.
2. Connect it to a hosting service such as Render, Railway, or Heroku-style hosting.
3. Set the start command to `gunicorn wsgi:application`.
4. Copy the public URL the host gives you and share that link with anyone.

## Included Structure

- `templates/`
- `static/`
- `app.py`
- `schema.sql`
- `database.db`
- `requirements.txt`
- `README.md`

## Notes

- The app is built as a Flask web application.
- `app.py` starts the site.
- The app listens on `0.0.0.0` and uses the `PORT` environment variable when available.
