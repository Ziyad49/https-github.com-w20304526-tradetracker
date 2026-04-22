# TradeTracker

TradeTracker is a Flask-based trading journal and performance intelligence platform designed to help traders log trades, review discipline, monitor strategy performance, and reflect on decision-making through analytics and journaling.

This project was developed as a final-year university project and has been shaped to feel more like a complete product than a basic CRUD application. The app combines trade tracking, strategy review, psychology journaling, market analysis, risk planning, and presentation-focused UI improvements in one workspace.

## Project Highlights

- Premium landing, authentication, and dashboard experience
- Trade desk with filtering, review modal, and CSV export
- Analytics page with trader score, monthly PnL trend, streaks, and strategy/symbol insights
- Journal page with reflection scoring, mood signals, and a timeline view
- Strategy playbook with documentation depth and performance context
- Market workspace with TradingView integration
- News and macro briefing page
- Position size and risk calculator
- Session hardening and CSRF protection
- Basic automated tests for key flows

## Core Features

- User registration and login
- Email verification and set-password onboarding flow
- Session-based authentication
- Trade creation, editing, deletion, and export
- Strategy management
- Journal entry creation and review
- Summary metrics including:
  - net profit
  - win rate
  - profit factor
  - average win / loss
  - max drawdown
  - equity curve
- Symbol and strategy profitability breakdowns
- Risk planning calculator
- Embedded chart workspace

## Pages Included

- `/` Landing page
- `/login` Login
- `/register` Register
- `/verify-email/<token>` Email verification
- `/set-password/<token>` Password setup
- `/dashboard` Command dashboard
- `/trades` Trade desk
- `/analytics` Performance analytics
- `/journal` Reflection journal
- `/strategies` Strategy playbook
- `/market` Market workspace
- `/news` News and calendar briefing
- `/calculator` Risk calculator
- `/settings` Workspace settings

## Tech Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Chart.js

## Project Structure

```text
trade_tracker/
├── app.py
├── database.py
├── requirements.txt
├── tests/
│   └── test_app.py
├── static/
│   ├── style.css
│   ├── static.js
│   └── images/
└── templates/
    └── TT/
        ├── base.html
        ├── landing.html
        ├── login.html
        ├── register.html
        ├── index.html
        ├── trades.html
        ├── analytics.html
        ├── journal.html
        ├── strategies.html
        ├── market.html
        ├── news.html
        ├── calculator.html
        └── settings.html
```

## How To Run

The project already includes a local virtual environment in `venv`.

```bash
cd '/Users/ziyadmatroufi/Documents/trade_tracker '
source venv/bin/activate
export TRADETRACKER_SECRET_KEY='replace-with-a-long-random-secret'
export TRADETRACKER_DEBUG=1
export TRADETRACKER_PUBLIC_BASE_URL='http://127.0.0.1:5000'
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Deploying Publicly

The fastest way to publish TradeTracker is with Render.

1. Push this project to GitHub.
2. Sign in to Render and create a new Web Service from the repo.
3. Render can use the included [render.yaml](/Users/ziyadmatroufi/Documents/trade_tracker%20/render.yaml) file automatically.
4. After the first deploy, set these environment variables in Render:
   - `TRADETRACKER_PUBLIC_BASE_URL=https://your-domain.com`
   - `TRADETRACKER_MAIL_FROM=your-email@your-domain.com`
   - `TRADETRACKER_SMTP_HOST=...`
   - `TRADETRACKER_SMTP_PORT=587`
   - `TRADETRACKER_SMTP_USERNAME=...`
   - `TRADETRACKER_SMTP_PASSWORD=...`
   - `TRADETRACKER_SMTP_USE_TLS=1`
5. In Render, open the service `Settings` page and add your custom domain.
6. Update your DNS records at your domain provider using Render’s instructions.

Important:
- This project uses SQLite, so the included Render config mounts a persistent disk at `/var/data`.
- Without a persistent disk, database changes would be lost on redeploy.
- After the domain is connected, use the custom domain value in `TRADETRACKER_PUBLIC_BASE_URL` so email verification links are correct.

## Environment Variables

The app supports the following configuration values:

- `TRADETRACKER_SECRET_KEY`
  - Secret key for Flask sessions. Set this in any non-trivial environment.
- `TRADETRACKER_DEBUG`
  - Set to `1` to run Flask with debug mode enabled.
- `TRADETRACKER_APP_NAME`
  - Public-facing product name shown in auth screens and emails.
- `TRADETRACKER_SEED_DEMO`
  - Set to `1` to seed demo content on startup.
  - Set to `0` to disable demo seeding.
- `TRADETRACKER_SECURE_COOKIE`
  - Set to `1` when running behind HTTPS to mark cookies as secure.
- `TRADETRACKER_PUBLIC_BASE_URL`
  - Public base URL used inside verification emails.
  - Defaults to `http://127.0.0.1:5000` for local development.
- `TRADETRACKER_MAIL_FROM`
  - Sender address used for outgoing verification emails.
- `TRADETRACKER_SMTP_HOST`
  - SMTP server host. If omitted, the app falls back to local console-preview mode and prints the verification link in the Flask terminal.
- `TRADETRACKER_SMTP_PORT`
  - SMTP server port.
- `TRADETRACKER_SMTP_USERNAME`
  - SMTP username for authenticated email delivery.
- `TRADETRACKER_SMTP_PASSWORD`
  - SMTP password or app password.
- `TRADETRACKER_SMTP_USE_TLS`
  - Set to `1` to enable STARTTLS for SMTP delivery.
- `TRADETRACKER_DB_PATH`
  - Override the SQLite database file location.

See [.env.example](/Users/ziyadmatroufi/Documents/trade_tracker%20/.env.example) for a starter template.

## Security Improvements Included

The project now includes several foundational hardening improvements:

- no hardcoded Flask secret key
- session cookie security defaults
- CSRF protection on POST forms
- email verification before password activation
- environment-driven debug mode
- cleaner request validation on key input routes

## Running Tests

The project includes a lightweight `unittest` suite covering core flows.

```bash
cd '/Users/ziyadmatroufi/Documents/trade_tracker '
python3 -m unittest discover -s tests -v
```

Current tested areas:

- profit calculation logic
- register / login / logout flow
- CSRF protection on POST routes
- adding a trade
- adding a strategy
- adding a journal entry

## Suggested Demo Flow

For a final presentation, a strong sequence is:

1. Show the landing page and login/register flow
2. Open the dashboard and explain the project goal
3. Show the trade desk and how trades are logged and reviewed
4. Show the analytics page and trader score
5. Show the journal page for reflection and mood tracking
6. Show the strategies page as the trader playbook
7. End on settings or CSV export to reinforce completeness

## Recommended Screenshots

If you are submitting this project with documentation or slides, take screenshots of:

- landing page
- login page
- dashboard
- trades page
- analytics page
- journal page
- strategies page

## Future Improvements

- stronger server-side validation and stricter database constraints
- more route and API test coverage
- real market/news data integration
- richer account/profile management
- file upload support for trade screenshots
- deployment configuration for production hosting
- deeper analytics such as expectancy, monthly breakdowns, and mood-versus-performance correlation

## Notes

- The project currently uses SQLite for simplicity and easy local execution.
- Demo data can be enabled or disabled using environment variables.
- TradingView chart loading requires internet access in the browser.
