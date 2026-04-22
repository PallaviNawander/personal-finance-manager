from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = "secret123"

NEWS_API_KEY = "8fff8f21092b4577b3fda4f72cab4ea7"

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "tinyllama"


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
    

    conn.commit()
    conn.close()


# ================= HOME =================
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
            diff = data["actual"] - data["budget"]
            insights.append(f"⚠️ {cat} exceeded budget by ₹{int(diff)}")

    if total_income > 0:
        food = category_map.get("Food", {}).get("actual", 0)
        if food > 0.3 * total_income:
            insights.append("🍔 Food spending is high (>30% of income). Try reducing it.")

    return insights
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

    return render_template(
        "profile.html",
        name=session.get("name"),
        email=session.get("email")
    )


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

    # 🔹 Budget-based data for charts
    cursor.execute("""
        SELECT category, SUM(budget), SUM(actual)
        FROM budget_data
        WHERE user_id=?
        GROUP BY category
    """, (session["user_id"],))

    rows = cursor.fetchall()

    income = {}
    expense = {}

    total_income = 0
    total_expense = 0

    income_categories = ["Salary","Freelance","Investments","Business","Gifts","Other"]

    for cat, b, a in rows:
        if cat in income_categories:
            income[cat] = a or 0
            total_income += a or 0
        else:
            expense[cat] = a or 0
            total_expense += a or 0

    savings = total_income - total_expense

    # 🔹 Transactions (for table display)
    cursor.execute("""
        SELECT category, type, amount, date
        FROM expenses
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))

    txn_rows = cursor.fetchall()

    transactions = []
    for cat, t, amt, date in txn_rows:
        transactions.append({
            "category": cat,
            "type": t,
            "amount": amt,
            "date": date
        })

    conn.close()

    return render_template(
        "dashboard_view.html",
        income=income or {},
        expense=expense or {},
        transactions=transactions or [],
        total_income=total_income or 0,
        total_expense=total_expense or 0,
        savings=savings or 0
    )


# ================= SAVE BUDGET =================
@app.route("/save-budget", methods=["POST"])
def save_budget():
    if "user_id" not in session:
        return jsonify({"status": "error"})

    data = request.json

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # delete old entries for same date range
    cursor.execute("""
        DELETE FROM budget_data 
        WHERE user_id=? AND start_date=? AND end_date=?
    """, (session["user_id"], data["start_date"], data["end_date"]))

    for row in data["rows"]:
        cursor.execute("""
            INSERT INTO budget_data (user_id, start_date, end_date, category, budget, actual)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            data["start_date"],
            data["end_date"],
            row["category"],
            float(row["budget"]) if row["budget"] not in [None, ""] else None,
            float(row["actual"]) if row["actual"] not in [None, ""] else None
        ))

    conn.commit()
    conn.close()

    return jsonify({"status": "saved"})
# ================= LOAD BUDGET =================
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

    data = cursor.fetchall()
    conn.close()

    budget_map = {}
    start_date = ""
    end_date = ""

    for s, e, cat, b, a in data:

        if cat not in budget_map:
            budget_map[cat] = {
                "budget": b if b is not None else "",
                "actual": a if a is not None else ""
            }
        else:
            # update safely
            if b is not None:
                budget_map[cat]["budget"] = b
            if a is not None:
                budget_map[cat]["actual"] = a

        # keep latest dates
        start_date = s
        end_date = e

    return render_template(
        "budget.html",
        saved_data=budget_map,
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
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
    except:
        articles = []

    return render_template("news.html", articles=articles)


# ================= CHAT =================
@app.route("/chat", methods=["POST"])
def chat():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"reply": "Login required"})

    msg = request.json.get("message", "")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Save user message
    cursor.execute(
        "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, "user", msg)
    )

    # Get chat history (context)
    cursor.execute(
        "SELECT role, message FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT 6",
        (user_id,)
    )

    history = cursor.fetchall()[::-1]
    chat_memory = "\n".join([f"{r}: {m}" for r, m in history])

    prompt = f"""
You are FinanceGPT.

Rules:
- Keep replies very short (2–3 lines max)
- Be fast and direct
- No unnecessary explanation

{chat_memory}

User: {msg}
"""

    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 60,
                    "temperature": 0.5
                }
            },
            timeout=30
        )

        data = res.json()

        # SAFE RESPONSE HANDLING (IMPORTANT)
        if "response" in data:
            reply = data["response"]
        elif "message" in data and isinstance(data["message"], dict):
            reply = data["message"].get("content", "")
        else:
            reply = "⚠️ No response from model"

        if not reply:
            reply = "⚠️ Empty response from model"

    except Exception as e:
        reply = f"⚠️ Error: {str(e)}"

    # Save assistant reply
    cursor.execute(
        "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, "assistant", reply)
    )

    conn.commit()
    conn.close()

    return jsonify({"reply": reply})
@app.route("/ai-insights", methods=["POST"])
def ai_insights():
    rows = request.json.get("rows", [])
    insights = generate_budget_ai(rows)
    return jsonify({"insights": insights})
@app.route("/get-chat")
def get_chat():
    if "user_id" not in session:
        return jsonify({"history": []})

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, message 
        FROM chat_history 
        WHERE user_id=? 
        ORDER BY id ASC
    """, (session["user_id"],))

    rows = cursor.fetchall()
    conn.close()

    history = [{"role": r, "message": m} for r, m in rows]

    return jsonify({"history": history})

@app.route("/ai-autoplan", methods=["POST"])
def ai_autoplan():
    rows = request.json.get("rows", [])

    total_income = sum(
    float(r["actual"]) if r["actual"] not in [None, ""] else 0
    for r in rows
    if r["category"] in ["Salary","Freelance","Investments","Business","Gifts","Other"]
)

    plan = {}

    for r in rows:
        cat = r["category"]

        if cat in ["Food","Groceries"]:
            plan[cat] = round(0.2 * total_income / 2, 2)

        elif cat in ["Shopping","Entertainment"]:
            plan[cat] = round(0.15 * total_income / 2, 2)

        else:
            plan[cat] = r["budget"]

    return jsonify({"plan": plan})
@app.route("/load-chat")
def load_chat():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"history": []})

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, message
        FROM chat_history
        WHERE user_id=?
        ORDER BY id ASC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    history = []
    for role, message in rows:
        history.append({
            "role": role,
            "message": message
        })

    return jsonify({"history": history})
# ================= RUN =================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)