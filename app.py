import os
import secrets
import sqlite3
import smtplib
from flask import Flask, render_template, jsonify, request, redirect, session, url_for, Response, abort
from email.message import EmailMessage
from datetime import datetime, timedelta
import database
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io

app = Flask(__name__, template_folder="templates/TT")
APP_NAME = os.environ.get("TRADETRACKER_APP_NAME", "TradeTracker")
app.config.update(
    SECRET_KEY=os.environ.get("TRADETRACKER_SECRET_KEY") or "tradetracker-local-dev-secret",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("TRADETRACKER_SECURE_COOKIE", "0") == "1",
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)


# ================= INIT =================

database.init_db()
if os.environ.get("TRADETRACKER_SEED_DEMO", "1") == "1":
    database.seed_data_if_empty(rows=30)


# ================= HELPERS =================

def is_logged_in():
    return "user_id" in session


def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token, "app_name": APP_NAME}


@app.before_request
def protect_post_routes():
    return


def calc_profit(symbol, trade_type, open_price, close_price, lot):
    multiplier = 10 if symbol == "XAUUSD" else 10000
    profit = (close_price - open_price) * multiplier * lot
    if trade_type == "SELL":
        profit *= -1
    return round(profit, 2)


def generate_verification_expiry():
    return (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")


def verification_is_valid(user):
    expires_at = user[7]
    if not expires_at:
        return False
    try:
        return datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S") >= datetime.now()
    except ValueError:
        return False


def build_public_url(endpoint, **values):
    base_url = (os.environ.get("TRADETRACKER_PUBLIC_BASE_URL") or "http://127.0.0.1:5000").rstrip("/")
    if base_url:
        return f"{base_url}{url_for(endpoint, **values)}"
    return url_for(endpoint, _external=True, **values)


def send_verification_email(email, first_name, verification_url):
    message = EmailMessage()
    message["Subject"] = f"Confirm your {APP_NAME} account"
    message["From"] = os.environ.get("TRADETRACKER_MAIL_FROM") or "no-reply@tradetracker.local"
    message["To"] = email
    message.set_content(
        f"""Hi {first_name},

Welcome to {APP_NAME}.

Confirm your email address using the link below:
{verification_url}

This link expires in 24 hours. After confirming, you will be able to set your password and sign in.
"""
    )

    smtp_host = os.environ.get("TRADETRACKER_SMTP_HOST")
    if not smtp_host:
        print(f"[{APP_NAME}] Verification link for {email}: {verification_url}")
        return "console"

    smtp_port = int(os.environ.get("TRADETRACKER_SMTP_PORT", "587"))
    smtp_user = os.environ.get("TRADETRACKER_SMTP_USERNAME")
    smtp_password = os.environ.get("TRADETRACKER_SMTP_PASSWORD")
    use_tls = os.environ.get("TRADETRACKER_SMTP_USE_TLS", "1") == "1"

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        if use_tls:
            server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(message)
    return "smtp"


# ================= LANDING =================

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/features")
def features():
    return render_template("features.html")


# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first = (request.form.get("first_name") or "").strip()
        last = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not all([first, last, email, password, confirm_password]):
            return render_template("register.html", error="All fields are required")

        try:
            if database.get_user_by_email(email):
                return render_template("register.html", error="This email is already registered. Please log in.")

            if len(password) < 8:
                return render_template("register.html", error="Use at least 8 characters for the password.")

            if password != confirm_password:
                return render_template("register.html", error="Passwords do not match.")

            database.create_user(first, last, email, generate_password_hash(password))
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Email already exists")

    return render_template("register.html")


@app.route("/verify-email/<token>")
def verify_email(token):
    user = database.get_user_by_verification_token(token)
    if not user or not verification_is_valid(user):
        return render_template(
            "verification_status.html",
            status="invalid",
            title="This verification link is no longer valid.",
            message="Request a new sign-up email and we will send you a fresh confirmation link.",
        )

    if user[5] and user[4]:
        return redirect(url_for("login"))

    return render_template("set_password.html", token=token, email=user[3])


@app.route("/set-password/<token>", methods=["POST"])
def set_password(token):
    user = database.get_user_by_verification_token(token)
    if not user or not verification_is_valid(user):
        return render_template(
            "verification_status.html",
            status="invalid",
            title="This password setup link has expired.",
            message="Go back to registration and request a new verification email.",
        )

    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if len(password) < 8:
        return render_template(
            "set_password.html",
            token=token,
            email=user[3],
            error="Use at least 8 characters for the password.",
        )
    if password != confirm_password:
        return render_template(
            "set_password.html",
            token=token,
            email=user[3],
            error="Passwords do not match.",
        )

    database.set_user_password_and_verify(
        user[0],
        generate_password_hash(password),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return render_template(
        "verification_status.html",
        status="success",
        title="Your account is ready.",
        message="Your email is confirmed and your password is set. You can sign in now.",
    )


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            return render_template("login.html", error="Please fill in all fields")

        user = database.get_user_by_email(email)

        if user and user[4] and check_password_hash(user[4], password):
            session.clear()
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")


# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# ================= PROTECTED PAGES =================

@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("index.html")


@app.route("/trades")
def trades():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("trades.html")


@app.route("/analytics")
def analytics():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/market")
def market():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("market.html")


@app.route("/news")
def news():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("news.html")


@app.route("/calculator")
def calculator():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("calculator.html")


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not is_logged_in():
        return redirect(url_for("login"))
    capital_message = None

    if request.method == "POST":
        capital = request.form.get("capital")
        try:
            capital_value = round(float(capital), 2)
            if capital_value < 0:
                raise ValueError
            database.update_user_capital(session["user_id"], capital_value)
            capital_message = "Starting capital updated."
        except (TypeError, ValueError):
            capital_message = "Enter a valid capital amount."

    user = database.get_user_by_id(session["user_id"])
    current_capital = float(user[8]) if user and len(user) > 8 and user[8] is not None else 0.0
    return render_template("settings.html", current_capital=current_capital, capital_message=capital_message)


@app.route("/strategies")
def strategies():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("strategies.html")


@app.route("/journal")
def journal():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("journal.html")


# ================= API =================

@app.route("/api/summary")
def api_summary():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(database.get_summary(session["user_id"]))


@app.route("/api/equity")
def api_equity():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(database.get_equity_series(session["user_id"]))


@app.route("/api/trades")
def api_trades():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    symbol = request.args.get("symbol") or None
    trade_type = request.args.get("type") or None
    risk = request.args.get("risk") or None
    strategy_id = request.args.get("strategy_id") or None
    start = request.args.get("start") or None
    end = request.args.get("end") or None
    search = request.args.get("q") or None
    limit = request.args.get("limit") or 50

    try:
        limit_i = int(limit)
    except ValueError:
        limit_i = 50

    if strategy_id:
        try:
            strategy_id = int(strategy_id)
        except ValueError:
            strategy_id = None

    return jsonify(database.list_trades(
        session["user_id"],
        limit=limit_i,
        symbol=symbol,
        trade_type=trade_type,
        risk=risk,
        strategy_id=strategy_id,
        start=start,
        end=end,
        search=search
    ))


@app.route("/api/symbol_pnl")
def api_symbol_pnl():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(database.symbol_pnl(session["user_id"]))


@app.route("/api/strategies")
def api_strategies():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(database.list_strategies(session["user_id"]))


@app.route("/api/strategy_pnl")
def api_strategy_pnl():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(database.strategy_pnl(session["user_id"]))


@app.route("/api/journal")
def api_journal():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(database.list_journal_entries(session["user_id"]))


@app.route("/export/trades")
def export_trades():
    if not is_logged_in():
        return redirect(url_for("login"))

    rows = database.list_trades(session["user_id"], limit=500)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "created_at", "symbol", "type", "open_price", "close_price",
        "lot", "profit", "risk_level", "strategy", "notes", "screenshot_url"
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["created_at"], r["symbol"], r["trade_type"],
            r["open_price"], r["close_price"], r["lot"], r["profit"],
            r["risk_level"], r.get("strategy_name"), r.get("notes"), r.get("screenshot_url")
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"}
    )


@app.route("/add_trade", methods=["POST"])
def add_trade():
    if not is_logged_in():
        return redirect(url_for("login"))

    symbol = (request.form.get("symbol") or "").strip().upper()
    trade_type = (request.form.get("type") or "").strip().upper()
    open_price = request.form.get("open")
    close_price = request.form.get("close")
    lot = request.form.get("lot")
    risk_level = (request.form.get("risk") or "").strip().title()
    strategy_id = request.form.get("strategy_id") or None
    notes = (request.form.get("notes") or "").strip() or None
    screenshot_url = (request.form.get("screenshot_url") or "").strip() or None

    if not all([symbol, trade_type, open_price, close_price, lot, risk_level]):
        return redirect(url_for("trades"))

    try:
        open_price_f = float(open_price)
        close_price_f = float(close_price)
        lot_f = float(lot)
    except ValueError:
        return redirect(url_for("trades"))

    if trade_type not in {"BUY", "SELL"} or risk_level not in {"Low", "Medium", "High"}:
        return redirect(url_for("trades"))
    if open_price_f <= 0 or close_price_f <= 0 or lot_f <= 0:
        return redirect(url_for("trades"))

    profit = calc_profit(symbol, trade_type, open_price_f, close_price_f, lot_f)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if strategy_id:
        try:
            strategy_id = int(strategy_id)
        except ValueError:
            strategy_id = None

    database.insert_trade(
        session["user_id"],
        symbol,
        trade_type,
        open_price_f,
        close_price_f,
        lot_f,
        profit,
        risk_level,
        created_at,
        strategy_id,
        notes,
        screenshot_url
    )

    return redirect(url_for("trades"))


@app.route("/update_trade", methods=["POST"])
def update_trade():
    if not is_logged_in():
        return redirect(url_for("login"))

    trade_id = request.form.get("trade_id")
    symbol = (request.form.get("symbol") or "").strip().upper()
    trade_type = (request.form.get("type") or "").strip().upper()
    open_price = request.form.get("open")
    close_price = request.form.get("close")
    lot = request.form.get("lot")
    risk_level = (request.form.get("risk") or "").strip().title()
    strategy_id = request.form.get("strategy_id") or None
    notes = (request.form.get("notes") or "").strip() or None
    screenshot_url = (request.form.get("screenshot_url") or "").strip() or None

    if not all([trade_id, symbol, trade_type, open_price, close_price, lot, risk_level]):
        return redirect(url_for("trades"))

    try:
        trade_id_i = int(trade_id)
        open_price_f = float(open_price)
        close_price_f = float(close_price)
        lot_f = float(lot)
    except ValueError:
        return redirect(url_for("trades"))

    if trade_type not in {"BUY", "SELL"} or risk_level not in {"Low", "Medium", "High"}:
        return redirect(url_for("trades"))
    if trade_id_i <= 0 or open_price_f <= 0 or close_price_f <= 0 or lot_f <= 0:
        return redirect(url_for("trades"))

    profit = calc_profit(symbol, trade_type, open_price_f, close_price_f, lot_f)

    if strategy_id:
        try:
            strategy_id = int(strategy_id)
        except ValueError:
            strategy_id = None

    database.update_trade(
        session["user_id"],
        trade_id_i,
        symbol,
        trade_type,
        open_price_f,
        close_price_f,
        lot_f,
        profit,
        risk_level,
        strategy_id,
        notes,
        screenshot_url
    )

    return redirect(url_for("trades"))


@app.route("/delete_trade", methods=["POST"])
def delete_trade():
    if not is_logged_in():
        return redirect(url_for("login"))

    trade_id = request.form.get("trade_id")
    if not trade_id:
        return redirect(url_for("trades"))

    try:
        trade_id_i = int(trade_id)
    except ValueError:
        return redirect(url_for("trades"))

    database.delete_trade(session["user_id"], trade_id_i)
    return redirect(url_for("trades"))


@app.route("/add_strategy", methods=["POST"])
def add_strategy():
    if not is_logged_in():
        return redirect(url_for("login"))

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        return redirect(url_for("strategies"))

    database.create_strategy(session["user_id"], name, description)
    return redirect(url_for("strategies"))


@app.route("/update_strategy", methods=["POST"])
def update_strategy():
    if not is_logged_in():
        return redirect(url_for("login"))

    strategy_id = request.form.get("strategy_id")
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not strategy_id or not name:
        return redirect(url_for("strategies"))

    try:
        strategy_id_i = int(strategy_id)
    except ValueError:
        return redirect(url_for("strategies"))

    database.update_strategy(session["user_id"], strategy_id_i, name, description)
    return redirect(url_for("strategies"))


@app.route("/delete_strategy", methods=["POST"])
def delete_strategy():
    if not is_logged_in():
        return redirect(url_for("login"))

    strategy_id = request.form.get("strategy_id")
    if not strategy_id:
        return redirect(url_for("strategies"))

    try:
        strategy_id_i = int(strategy_id)
    except ValueError:
        return redirect(url_for("strategies"))

    database.delete_strategy(session["user_id"], strategy_id_i)
    return redirect(url_for("strategies"))


@app.route("/add_journal", methods=["POST"])
def add_journal():
    if not is_logged_in():
        return redirect(url_for("login"))

    entry_date = (request.form.get("entry_date") or "").strip()
    mood = (request.form.get("mood") or "").strip().title()
    notes = (request.form.get("notes") or "").strip()

    if not entry_date or not notes:
        return redirect(url_for("journal"))

    if mood and mood not in {"Focused", "Calm", "Confident", "Stressed", "Overtrading"}:
        return redirect(url_for("journal"))

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    database.insert_journal_entry(session["user_id"], entry_date, mood, notes, created_at)

    return redirect(url_for("journal"))


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=os.environ.get("TRADETRACKER_DEBUG", "0") == "1")
