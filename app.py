from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests
import time

app = Flask(__name__)
app.secret_key = "secret123"

NEWS_API_KEY = "8fff8f21092b4577b3fda4f72cab4ea7"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "phi3"


# ================= DB =================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        category TEXT,
        type TEXT,
        date TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budget_data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        start_date TEXT,
        end_date TEXT,
        category TEXT,
        budget REAL,
        actual REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        role TEXT,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


# ================= BUDGET AI =================
def generate_budget_ai(rows):
    insights = []

    total_income = 0
    total_expense = 0
    category_map = {}

    income_categories = ["Salary","Freelance","Investments","Business","Gifts","Other"]

    for r in rows:
        cat = r["category"]
        budget = float(r["budget"])
        actual = float(r["actual"])

        category_map[cat] = {"budget": budget, "actual": actual}

        if cat in income_categories:
            total_income += actual
        else:
            total_expense += actual

    savings = total_income - total_expense

    if savings < 0:
        insights.append("⚠️ You are overspending. Your expenses exceed income.")
    else:
        insights.append(f"✅ You are saving ₹{int(savings)} this period.")

    for cat, data in category_map.items():
        if data["actual"] > data["budget"] and data["budget"] > 0:
            insights.append(f"⚠️ {cat} exceeded budget")

    return insights


# ================= HOME =================
@app.route("/")
def home():
    return render_template("welcome.html")


# ================= AUTH =================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (name,email,password) VALUES (?,?,?)",
            (request.form["name"], request.form["email"], request.form["password"])
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (request.form["email"], request.form["password"])
        )

        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["name"] = user[1]
            session["email"] = user[2]
            return redirect("/dashboard")

    return render_template("login.html")


# ================= PROFILE =================
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("profile.html", name=session["name"], email=session["email"])


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("dashboard.html")


# ================= DASHBOARD VIEW =================
@app.route("/dashboard-view")
def dashboard_view():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, SUM(budget), SUM(actual)
        FROM budget_data
        WHERE user_id=?
        GROUP BY category
    """, (session["user_id"],))

    rows = cursor.fetchall()

    saved_data = {}
    income = {}
    expense = {}

    income_categories = ["Salary","Freelance","Investments","Business","Gifts","Other"]

    total_income = 0
    total_expense = 0

    for cat, b, a in rows:
        saved_data[cat] = {"budget": b or 0, "actual": a or 0}

        if cat in income_categories:
            income[cat] = a or 0
            total_income += a or 0
        else:
            expense[cat] = a or 0
            total_expense += a or 0

    savings = total_income - total_expense

    cursor.execute("""
        SELECT category, type, amount, date
        FROM expenses
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))

    transactions = [
        {"category": c, "type": t, "amount": a, "date": d}
        for c, t, a, d in cursor.fetchall()
    ]

    conn.close()

    return render_template(
        "dashboard_view.html",
        income=income,
        expense=expense,
        transactions=transactions,
        total_income=total_income,
        total_expense=total_expense,
        savings=savings,
        saved_data=saved_data,
        start_date="",
        end_date=""
    )


# ================= SAVE BUDGET =================
@app.route("/save-budget", methods=["POST"])
def save_budget():
    if "user_id" not in session:
        return jsonify({"status": "error", "msg": "unauthorized"})

    data = request.json

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM budget_data 
        WHERE user_id=? AND start_date=? AND end_date=?
    """, (session["user_id"], data["start_date"], data["end_date"]))

    for row in data["rows"]:
        cursor.execute("""
            INSERT INTO budget_data 
            (user_id, start_date, end_date, category, budget, actual)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            data["start_date"],
            data["end_date"],
            row["category"],
            float(row["budget"]) if row["budget"] not in ["", None] else 0,
            float(row["actual"]) if row["actual"] not in ["", None] else 0
        ))

    conn.commit()
    conn.close()

    return jsonify({"status": "saved"})


# ================= LOAD BUDGET =================
@app.route("/budget")
def budget():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT start_date, end_date, category, budget, actual
        FROM budget_data
        WHERE user_id=?
    """, (session["user_id"],))

    rows = cursor.fetchall()
    conn.close()

    saved_data = {}
    start_date = ""
    end_date = ""

    for s, e, cat, b, a in rows:
        saved_data[cat] = {
            "budget": b or 0,
            "actual": a or 0
        }
        start_date = s
        end_date = e

    return render_template(
        "budget.html",
        saved_data=saved_data,
        start_date=start_date,
        end_date=end_date
    )


# ================= NEWS =================
@app.route("/news")
def news():
    if "user_id" not in session:
        return redirect("/login")

    try:
        url = f"https://newsapi.org/v2/top-headlines?category=business&country=in&apiKey={NEWS_API_KEY}"
        data = requests.get(url).json()
        articles = data.get("articles", [])
    except:
        articles = []

    return render_template("news.html", articles=articles)


# ================= CHAT (OLLAMA AI) =================
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    msg = data.get("message", "")
    chat_id = data.get("chat_id")

    if not msg or not chat_id:
        return jsonify({"reply": "Invalid request ❌"})

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Save user message
    cursor.execute("""
        INSERT INTO chat_messages (chat_id, role, message)
        VALUES (?, ?, ?)
    """, (chat_id, "user", msg))

    conn.commit()

    reply = "⚠️ AI failed to respond"

    try:
        # 🧠 Clean system instruction (IMPORTANT for llama3)
        SYSTEM_PROMPT = (
            "You are FinanceGPT, a helpful personal finance assistant. "
            "Respond clearly, directly, and only in natural English. "
            "Do NOT use roles like User:, Assistant:, Me:, or simulate conversations. "
            "Do NOT generate unrelated text or religious greetings. "
            "Stay strictly focused on budgeting, expenses, savings, and financial advice."
        )

        res = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,  # llama3
                "prompt": SYSTEM_PROMPT + "\n\nUser question: " + msg + "\nAnswer:",
                "stream": False,
                "options": {
                    "num_predict": 180,
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            },
            timeout=60
        )

        if res.status_code == 200:
            reply = res.json().get("response", "").strip()

            if not reply:
                reply = "⚠️ Empty response from AI"
        else:
            reply = f"Ollama error: {res.status_code}"

    except requests.exceptions.ConnectionError:
        reply = "❌ Cannot connect to Ollama (run: ollama serve)"

    except requests.exceptions.Timeout:
        reply = "⏳ AI took too long. Try again."

    except Exception as e:
        reply = f"Error: {str(e)}"

    # Save assistant reply
    cursor.execute("""
        INSERT INTO chat_messages (chat_id, role, message)
        VALUES (?, ?, ?)
    """, (chat_id, "assistant", reply))

    conn.commit()
    conn.close()

    return jsonify({"reply": reply})
# ================= CHAT HISTORY =================
@app.route("/get-chat")
def get_chat():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role,message FROM chat_history
        WHERE user_id=?
    """, (session.get("user_id"),))

    rows = cursor.fetchall()
    conn.close()

    return jsonify({"history": rows})


# ================= NEW CHAT =================
@app.route("/new-chat", methods=["POST"])
def new_chat():
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO chats (user_id, title)
        VALUES (?, ?)
    """, (user_id, "New Chat"))

    chat_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({"chat_id": chat_id})


# ================= GET CHATS =================
@app.route("/get-chats")
def get_chats():
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title FROM chats
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,))

    chats = [{"id": r[0], "title": r[1]} for r in cursor.fetchall()]

    conn.close()

    return jsonify({"chats": chats})


# ================= LOAD CHAT =================
@app.route("/load-chat/<int:chat_id>")
def load_chat_by_id(chat_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, message
        FROM chat_messages
        WHERE chat_id=?
        ORDER BY id ASC
    """, (chat_id,))

    history = [{"role": r, "message": m} for r, m in cursor.fetchall()]

    conn.close()

    return jsonify({"history": history})
@app.route("/ai-fill-budget", methods=["POST"])
def ai_fill_budget():
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, actual FROM budget_data
        WHERE user_id=?
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    total_income = sum(
        a or 0 for c, a in rows
        if c in ["Salary","Freelance","Business","Investments"]
    )

    plan = {}

    for c, a in rows:
        if c in ["Food","Groceries"]:
            plan[c] = round(total_income * 0.2 / 2, 2)
        elif c in ["Shopping","Entertainment"]:
            plan[c] = round(total_income * 0.15 / 2, 2)
        else:
            plan[c] = a or 0

    return jsonify(plan)


# ================= RUN =================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)