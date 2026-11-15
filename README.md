# 📔 Keepsake: your personal digital scrapbook

The project has two folders: **`backend/`** (Flask + MySQL, Python) and **`frontend/`** (HTML templates, CSS, JavaScript). Run every command below from inside `backend/`.

A colourful, private archive for memories, photos, notes, documents and links.
Built with **Flask**, **MySQL** and plain **HTML / CSS / JavaScript**.

## Features

- **Dashboard**: greeting, quick-add buttons, counts, "On this day", recent items, favourites, collections
- **Archive**: create, view, edit, delete and favourite memories, photos, notes, documents and links
- **Details**: title, story/note, date, location, tags, collection
- **Collections and tags**: create, rename, recolour and delete; click a tag to see everything with it
- **Uploads**: JPG, PNG, GIF, WebP images and PDF, Word, Excel, PowerPoint, OpenDocument, TXT, MD, CSV, RTF documents, with live previews, file details, type/size validation and secure storage
- **Search and filters**: search titles, notes, places, tags and file names; filter by type, tag, collection, date range and favourites; five sort orders; pagination
- **Accounts**: register, sign in, sign out, password reset; every query is scoped to the signed-in user
- **Animated design**: a wavy rainbow site name, drifting colour blobs and floating keepsakes, a shifting-gradient dashboard banner with a rotating prompt, pop-in cards, count-up numbers, sparkle cursor trail, confetti on sign-in and a rainbow scroll bar. Animation switches off automatically for people who enable "reduce motion" on their device.
- **Feedback**: success/error messages, friendly empty states, confirmation dialogs before permanent deletes

## Requirements

- Python 3.9+
- MySQL 8.0+ (or MariaDB 10.4+), running and reachable

## Setup

```bash
cd backend

# 1. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Create your settings file
cp .env.example .env               # Windows: copy .env.example .env
```

**3. Edit `.env`** and enter your MySQL details and a secret key:

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=keepsake
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
SECRET_KEY=<paste the output of the command below>
```

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**4. Create the database and tables**

```bash
python init_db.py
```

This creates the database if it doesn't exist (your MySQL user needs permission
to create it) and runs `schema.sql`. It's safe to run again. If your user can't
create databases, create it once as an admin and grant access:

```sql
CREATE DATABASE keepsake CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON keepsake.* TO 'your_mysql_username'@'localhost';
```

Alternatively, run `schema.sql` yourself: `mysql -u USER -p keepsake < schema.sql`.

**5. Run the site**

```bash
python app.py
```

Open <http://127.0.0.1:5000>, click **Create account**, and start pinning things up.

## Look and themes

Keepsake has a light and a dark theme. Use the sun/moon button in the header to switch;
your choice is remembered in the browser, and until you choose it follows your device setting.
Animations (floating background, animated logo, scroll reveals, count-up numbers, hover effects)
are switched off automatically for people who prefer reduced motion.
Styles live in `frontend/static/css/` (`style.css` holds the colour tokens for both themes).

## Password reset

Click **Forgot your password?** on the sign-in page. If you've set `MAIL_SERVER`
(and related `MAIL_*` values) in `.env`, the reset link is emailed. If not, the
link is **printed in the terminal** where the server is running. That's handy for
a personal local install. Links expire after 60 minutes and work once.

## Configuration reference (`.env`)

| Setting | Purpose | Default |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | MySQL connection | `127.0.0.1`, `3306`, `keepsake`, `root`, empty |
| `SECRET_KEY` | Signs sessions. Set it, or you're signed out on every restart | random per start |
| `SESSION_COOKIE_SECURE` | Set `true` when served over HTTPS | `false` |
| `SESSION_DAYS` | Length of "keep me signed in" | `14` |
| `ALLOW_REGISTRATION` | Set `false` after creating your account to close sign-ups | `true` |
| `MAX_UPLOAD_MB` | Largest single upload | `15` |
| `UPLOAD_DIR` | Where uploads are stored (keep outside any public folder) | `instance/uploads` |
| `HOST`, `PORT`, `FLASK_DEBUG` | Server options (debug only on your own computer) | `127.0.0.1`, `5000`, `false` |
| `TRUST_PROXY`, `APP_BASE_URL` | For use behind a reverse proxy | off / auto |
| `MAIL_*` | Optional SMTP for reset emails | not set |

`.env` is git-ignored. Database credentials live only on the server and are
never sent to the browser.

## Project layout

```
README.md
backend/                      Python / Flask / MySQL
  app.py                      entry point
  init_db.py                  creates the database and tables  (--reset drops them, with confirmation)
  schema.sql                  MySQL schema: users, collections, items, tags, item_tags, password_resets
  .env.example                settings template (copy to .env)
  requirements.txt
  keepsake/
    __init__.py               app factory, template helpers, error pages
    config.py                 reads .env
    db.py                     PyMySQL helpers (parameterised queries only)
    security.py               CSRF, security headers, login guard, throttling, safe redirects
    auth.py                   register / login / logout / password reset
    archive.py                item CRUD, favourites, authenticated file serving
    organize.py               collections and tags
    queries.py                search / filter / sort SQL
    uploads.py                upload validation and storage
    main.py                   landing page and dashboard
  instance/uploads/           your uploaded files (git-ignored)
frontend/                     what the browser shows
  templates/                  Jinja HTML templates (base, dashboard, items, collections, tags, auth, errors)
  static/
    css/style.css             the scrapbook styling
    css/animations.css        all animations (delete its <link> in base.html to turn them off)
    js/app.js, boot.js        menus, previews, confirmation dialogs
    js/fx.js                  scroll reveals, count-up, sparkles, confetti (optional)
```

## Security notes

- Passwords hashed with Werkzeug (scrypt); login and reset attempts are throttled; login timing doesn't reveal which emails exist
- CSRF token on every POST; session fixation prevented; `HttpOnly` + `SameSite=Lax` cookies
- All SQL uses bound parameters; sort columns come from a whitelist; Jinja auto-escapes output
- Every item, collection, tag and file lookup includes `user_id`, so one account can never open another's content
- Uploads: extension whitelist **and** file-signature check, random stored names, per-user folders outside `static/`, size limit, served only through a login-protected route with `nosniff` and a sandbox CSP. SVG/HTML are not accepted
- Content-Security-Policy, `X-Frame-Options`, `Referrer-Policy` headers on all pages
- Only `http(s)` links are accepted; redirects after login are restricted to same-site paths

## Running in production

Use a real WSGI server and HTTPS, for example `pip install gunicorn` then
`gunicorn "keepsake:create_app()"` behind nginx. Set `SESSION_COOKIE_SECURE=true`,
`TRUST_PROXY=true`, `FLASK_DEBUG=false`, and a fixed `SECRET_KEY`. The login throttle
is in-memory per process, which is fine for a personal site.

## Troubleshooting

- **"The archive can't reach its database"**: check `DB_*` in `.env`, that MySQL is running, and that you ran `python init_db.py`.
- **`Access denied`**: wrong `DB_USER` / `DB_PASSWORD`.
- **`cryptography` error connecting to MySQL 8**: it's in `requirements.txt` (needed for `caching_sha2_password`); re-run `pip install -r requirements.txt`.
- **Back up** your data with `mysqldump keepsake > backup.sql` **and** copy the `instance/uploads/` folder.
