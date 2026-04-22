import os
import sqlite3
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Best default: keep a single writable DB path.
DEFAULT_DB = os.path.join(BASE_DIR, "templates", "database.db")

# Allow override for deployments or future use.
DB_NAME = os.environ.get("TRADETRACKER_DB_PATH", DEFAULT_DB)


# ================= CONNECTION =================

_db_ready = False


def _raw_conn():
    return sqlite3.connect(DB_NAME)


def ensure_db():
    global _db_ready
    if _db_ready:
        return
    init_db()
    _db_ready = True


def get_conn():
    ensure_db()
    return _raw_conn()


# ================= INIT DB =================

def init_db():
    conn = _raw_conn()
    cur = conn.cursor()

    # ---------- USERS TABLE ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # ---------- TRADES TABLE ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            strategy_id INTEGER,
            symbol TEXT NOT NULL,
            trade_type TEXT NOT NULL,
            open_price REAL NOT NULL,
            close_price REAL NOT NULL,
            lot REAL NOT NULL,
            profit REAL NOT NULL,
            risk_level TEXT NOT NULL,
            notes TEXT,
            screenshot_url TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # ---------- STRATEGIES TABLE ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT
        )
    """)

    # ---------- JOURNAL ENTRIES TABLE ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            mood TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Add user_id column to existing trades table if missing
    cur.execute("PRAGMA table_info(trades)")
    columns = [row[1] for row in cur.fetchall()]
    if "user_id" not in columns:
        cur.execute("ALTER TABLE trades ADD COLUMN user_id INTEGER")
        # Default existing trades to the first user (admin)
        cur.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
        default_user_id = row[0] if row else 1
        cur.execute("UPDATE trades SET user_id = ? WHERE user_id IS NULL", (default_user_id,))
    if "strategy_id" not in columns:
        cur.execute("ALTER TABLE trades ADD COLUMN strategy_id INTEGER")
    if "notes" not in columns:
        cur.execute("ALTER TABLE trades ADD COLUMN notes TEXT")
    if "screenshot_url" not in columns:
        cur.execute("ALTER TABLE trades ADD COLUMN screenshot_url TEXT")

    cur.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cur.fetchall()]
    if "is_verified" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 1")
    if "verification_token" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
    if "verification_expires_at" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN verification_expires_at TEXT")
    if "password_set_at" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN password_set_at TEXT")
    if "capital" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN capital REAL NOT NULL DEFAULT 0")

    cur.execute("""
        UPDATE users
        SET is_verified = CASE
            WHEN COALESCE(password, '') = '' THEN 0
            ELSE 1
        END
        WHERE is_verified IS NULL OR is_verified NOT IN (0, 1)
    """)
    cur.execute("""
        UPDATE users
        SET is_verified = 1
        WHERE COALESCE(password, '') != '' AND is_verified = 0
    """)
    cur.execute("""
        UPDATE users
        SET capital = 25000
        WHERE (capital IS NULL OR capital = 0) AND id = 1
    """)

    conn.commit()
    conn.close()


# ================= USERS FUNCTIONS =================

def create_user(first_name, last_name, email, password):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (first_name, last_name, email, password)
        VALUES (?, ?, ?, ?)
    """, (first_name, last_name, email, password))

    conn.commit()
    conn.close()


def create_pending_user(first_name, last_name, email, verification_token, verification_expires_at):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (
            first_name, last_name, email, password, is_verified,
            verification_token, verification_expires_at, password_set_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (first_name, last_name, email, "", 0, verification_token, verification_expires_at, None))

    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()

    conn.close()
    return user


def get_user_by_verification_token(token):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE verification_token = ?", (token,))
    user = cur.fetchone()

    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    conn.close()
    return user


def refresh_verification(user_id, verification_token, verification_expires_at):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET verification_token = ?, verification_expires_at = ?, is_verified = 0
        WHERE id = ?
    """, (verification_token, verification_expires_at, user_id))

    conn.commit()
    conn.close()


def set_user_password_and_verify(user_id, password_hash, password_set_at):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET password = ?,
            is_verified = 1,
            verification_token = NULL,
            verification_expires_at = NULL,
            password_set_at = ?
        WHERE id = ?
    """, (password_hash, password_set_at, user_id))

    conn.commit()
    conn.close()


def update_user_capital(user_id, capital):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("UPDATE users SET capital = ? WHERE id = ?", (capital, user_id))

    conn.commit()
    conn.close()


# ================= SEED DATA =================

def seed_data_if_empty(rows: int = 25):
    conn = get_conn()
    cur = conn.cursor()

    # ---------- SEED ADMIN USER ----------
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]

    if users_count == 0:
        admin_password = generate_password_hash("123")
        cur.execute("""
            INSERT INTO users (
                first_name, last_name, email, password, is_verified,
                verification_token, verification_expires_at, password_set_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Admin", "User", "admin", admin_password, 1, None, None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # ---------- SEED STRATEGIES ----------
    cur.execute("SELECT COUNT(*) FROM strategies")
    strategies_count = cur.fetchone()[0]
    if strategies_count == 0:
        default_user_id = 1
        strategies = [
            ("Scalp Momentum", "Fast moves, short holds"),
            ("Breakout", "Key level break confirmations"),
            ("Swing Trend", "Higher timeframe trend trades"),
        ]
        for name, desc in strategies:
            cur.execute("""
                INSERT INTO strategies (user_id, name, description)
                VALUES (?, ?, ?)
            """, (default_user_id, name, desc))

    # ---------- SEED TRADES ----------
    cur.execute("SELECT COUNT(*) FROM trades")
    trades_count = cur.fetchone()[0]

    if trades_count > 0:
        conn.commit()
        conn.close()
        return

    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
    risk_levels = ["Low", "Medium", "High"]
    now = datetime.now()

    for i in range(rows):
        symbol = random.choice(symbols)
        trade_type = random.choice(["BUY", "SELL"])
        lot = random.choice([0.1, 0.2, 0.5, 1.0])

        open_price = (
            round(random.uniform(1.0, 2.0), 5)
            if "USD" in symbol and symbol != "XAUUSD"
            else round(random.uniform(1900, 2600), 2)
        )

        move = (
            random.uniform(-0.02, 0.02)
            if symbol != "XAUUSD"
            else random.uniform(-25, 25)
        )

        close_price = (
            round(open_price + move, 5)
            if symbol != "XAUUSD"
            else round(open_price + move, 2)
        )

        profit = (close_price - open_price) * (10000 if symbol != "XAUUSD" else 10) * lot

        if trade_type == "SELL":
            profit *= -1

        profit = round(profit, 2)

        risk_level = random.choice(risk_levels)
        created_at = (now - timedelta(days=(rows - i))).strftime("%Y-%m-%d %H:%M:%S")

        # randomly assign a strategy
        cur.execute("SELECT id FROM strategies WHERE user_id = ? ORDER BY id", (1,))
        strategy_rows = cur.fetchall()
        strategy_id = random.choice(strategy_rows)[0] if strategy_rows else None

        cur.execute("""
            INSERT INTO trades (
                user_id, strategy_id, symbol, trade_type, open_price, close_price,
                lot, profit, risk_level, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            strategy_id,
            symbol,
            trade_type,
            open_price,
            close_price,
            lot,
            profit,
            risk_level,
            created_at
        ))

    conn.commit()
    conn.close()


# ================= JOURNAL =================

def insert_journal_entry(user_id, entry_date, mood, notes, created_at):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO journal_entries (user_id, entry_date, mood, notes, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, entry_date, mood, notes, created_at))

    conn.commit()
    conn.close()


def list_journal_entries(user_id, limit: int = 30):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, entry_date, mood, notes, created_at
        FROM journal_entries
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC
        LIMIT ?
    """, (user_id, limit))

    rows = cur.fetchall()
    conn.close()

    return [{
        "id": r[0],
        "entry_date": r[1],
        "mood": r[2],
        "notes": r[3],
        "created_at": r[4],
    } for r in rows]


# ================= SUMMARY =================

def get_summary(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COALESCE(capital, 0) FROM users WHERE id = ?", (user_id,))
    capital_row = cur.fetchone()
    starting_balance = float(capital_row[0]) if capital_row else 0.0

    cur.execute("SELECT COUNT(*) FROM trades WHERE user_id = ?", (user_id,))
    trades = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(profit), 0) FROM trades WHERE user_id = ?", (user_id,))
    net_profit = float(cur.fetchone()[0])

    cur.execute("SELECT COUNT(*) FROM trades WHERE profit > 0 AND user_id = ?", (user_id,))
    wins = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM trades WHERE profit < 0 AND user_id = ?", (user_id,))
    losses = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(profit), 0) FROM trades WHERE profit > 0 AND user_id = ?", (user_id,))
    gross_profit = float(cur.fetchone()[0])

    cur.execute("SELECT COALESCE(SUM(profit), 0) FROM trades WHERE profit < 0 AND user_id = ?", (user_id,))
    gross_loss = float(cur.fetchone()[0])

    avg_win = round(gross_profit / wins, 2) if wins else 0.0
    avg_loss = round(gross_loss / losses, 2) if losses else 0.0
    profit_factor = round((gross_profit / abs(gross_loss)) if gross_loss != 0 else 0.0, 2)

    win_rate = (wins / trades * 100) if trades else 0.0

    equity = round(starting_balance + net_profit, 2)

    # max drawdown from equity curve
    cur.execute("""
        SELECT profit
        FROM trades
        WHERE user_id = ?
        ORDER BY datetime(created_at) ASC
    """, (user_id,))
    profits = [float(r[0]) for r in cur.fetchall()]
    running = starting_balance
    peak = starting_balance
    max_dd = 0.0
    for p in profits:
        running += p
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    conn.close()

    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "net_profit": round(net_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": round(max_dd, 2),
        "equity": equity,
        "starting_balance": starting_balance
    }


# ================= EQUITY SERIES =================

def get_equity_series(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COALESCE(capital, 0) FROM users WHERE id = ?", (user_id,))
    capital_row = cur.fetchone()
    starting_balance = float(capital_row[0]) if capital_row else 0.0

    cur.execute("""
        SELECT created_at, profit
        FROM trades
        WHERE user_id = ?
        ORDER BY datetime(created_at) ASC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    running = starting_balance

    labels = []
    values = []

    for created_at, profit in rows:
        running += float(profit)
        labels.append(created_at.split(" ")[0])
        values.append(round(running, 2))

    return {"labels": labels, "values": values}


# ================= LIST TRADES =================

def list_trades(user_id: int, limit: int = 50, symbol=None, trade_type=None, risk=None, start=None, end=None, search=None, strategy_id=None):
    conn = get_conn()
    cur = conn.cursor()

    query = """
        SELECT t.id, t.created_at, t.symbol, t.trade_type,
               t.open_price, t.close_price, t.lot, t.profit, t.risk_level,
               t.strategy_id, s.name, t.notes, t.screenshot_url
        FROM trades t
        LEFT JOIN strategies s ON s.id = t.strategy_id
        WHERE t.user_id = ?
    """
    params = [user_id]

    if symbol:
        query += " AND symbol = ?"
        params.append(symbol)
    if trade_type:
        query += " AND trade_type = ?"
        params.append(trade_type)
    if risk:
        query += " AND t.risk_level = ?"
        params.append(risk)
    if strategy_id:
        query += " AND t.strategy_id = ?"
        params.append(strategy_id)
    if start:
        query += " AND datetime(t.created_at) >= datetime(?)"
        params.append(start)
    if end:
        query += " AND datetime(t.created_at) <= datetime(?)"
        params.append(end)
    if search:
        query += " AND (t.symbol LIKE ? OR t.trade_type LIKE ? OR t.risk_level LIKE ? OR s.name LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like, like])

    query += " ORDER BY datetime(t.created_at) DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, tuple(params))

    rows = cur.fetchall()
    conn.close()

    return [{
        "id": r[0],
        "created_at": r[1],
        "symbol": r[2],
        "trade_type": r[3],
        "open_price": r[4],
        "close_price": r[5],
        "lot": r[6],
        "profit": r[7],
        "risk_level": r[8],
        "strategy_id": r[9],
        "strategy_name": r[10],
        "notes": r[11],
        "screenshot_url": r[12],
    } for r in rows]


# ================= SYMBOL PNL =================

def symbol_pnl(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT symbol, COALESCE(SUM(profit), 0)
        FROM trades
        WHERE user_id = ?
        GROUP BY symbol
        ORDER BY SUM(profit) DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return {
        "labels": [r[0] for r in rows],
        "values": [round(float(r[1]), 2) for r in rows]
    }


# ================= INSERT TRADE =================

def insert_trade(user_id, symbol, trade_type, open_price, close_price, lot, profit, risk_level, created_at, strategy_id=None, notes=None, screenshot_url=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO trades (
            user_id, strategy_id, symbol, trade_type, open_price, close_price,
            lot, profit, risk_level, notes, screenshot_url, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, strategy_id, symbol, trade_type, open_price, close_price, lot, profit, risk_level, notes, screenshot_url, created_at))

    conn.commit()
    conn.close()


# ================= UPDATE / DELETE =================

def update_trade(user_id, trade_id, symbol, trade_type, open_price, close_price, lot, profit, risk_level, strategy_id=None, notes=None, screenshot_url=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE trades
        SET symbol = ?, trade_type = ?, open_price = ?, close_price = ?,
            lot = ?, profit = ?, risk_level = ?, strategy_id = ?, notes = ?, screenshot_url = ?
        WHERE id = ? AND user_id = ?
    """, (symbol, trade_type, open_price, close_price, lot, profit, risk_level, strategy_id, notes, screenshot_url, trade_id, user_id))

    conn.commit()
    conn.close()


def delete_trade(user_id, trade_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM trades WHERE id = ? AND user_id = ?", (trade_id, user_id))

    conn.commit()
    conn.close()


# ================= STRATEGIES =================

def list_strategies(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, description
        FROM strategies
        WHERE user_id = ?
        ORDER BY name ASC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]


def strategy_pnl(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(s.name, 'Unassigned'), COALESCE(SUM(t.profit), 0)
        FROM trades t
        LEFT JOIN strategies s ON s.id = t.strategy_id
        WHERE t.user_id = ?
        GROUP BY s.name
        ORDER BY SUM(t.profit) DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return {
        "labels": [r[0] for r in rows],
        "values": [round(float(r[1]), 2) for r in rows]
    }


def create_strategy(user_id: int, name: str, description: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO strategies (user_id, name, description)
        VALUES (?, ?, ?)
    """, (user_id, name, description))
    conn.commit()
    conn.close()


def update_strategy(user_id: int, strategy_id: int, name: str, description: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE strategies
        SET name = ?, description = ?
        WHERE id = ? AND user_id = ?
    """, (name, description, strategy_id, user_id))
    conn.commit()
    conn.close()


def delete_strategy(user_id: int, strategy_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM strategies WHERE id = ? AND user_id = ?", (strategy_id, user_id))
    conn.commit()
    conn.close()
