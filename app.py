from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = "secret123"
NEWS_API_KEY = "8fff8f21092b4577b3fda4f72cab4ea7"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "mistral"

# ------------------ DB INIT ------------------
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


# ------------------ ROUTES ------------------
@app.route("/")
def home():
    return render_template("welcome.html")


@app.route("/signup", methods=["GET","POST"])
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


@app.route("/login", methods=["GET","POST"])
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
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("dashboard.html")


# ------------------ DASHBOARD VIEW ------------------
@app.route("/dashboard-view")
def dashboard_view():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount, category, type, date FROM expenses WHERE user_id=?",
        (session["user_id"],)
    )

    rows = cursor.fetchall()

    transactions = []
    income_data = {}
    expense_data = {}

    total_income = 0
    total_expense = 0

    for amount, category, t, date in rows:
        transactions.append({
            "amount": amount,
            "category": category,
            "type": t,
            "date": date
        })

        if t == "income":
            total_income += amount
            income_data[category] = income_data.get(category, 0) + amount
        else:
            total_expense += amount
            expense_data[category] = expense_data.get(category, 0) + amount

    savings = total_income - total_expense

    conn.close()

    return render_template(
        "dashboard_view.html",
        transactions=transactions,
        income=income_data,
        expense=expense_data,
        total_income=total_income,
        total_expense=total_expense,
        savings=savings
    )


# ------------------ ADD EXPENSE ------------------
@app.route("/add-expense", methods=["POST"])
def add_expense():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO expenses (user_id, amount, category, type, date) VALUES (?, ?, ?, ?, ?)",
        (
            session["user_id"],
            request.form["amount"],
            request.form["category"],
            request.form["type"],
            request.form["date"]
        )
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard-view")


# ------------------ CHAT ------------------
@app.route("/chat", methods=["POST"])
def chat():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"reply": "Please login first"})

    user_msg = request.json.get("message", "")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, "user", user_msg)
    )

    cursor.execute(
        "SELECT role, message FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT 6",
        (user_id,)
    )

    history = cursor.fetchall()[::-1]

    conn.close()

    chat_memory = "\n".join([f"{r}: {m}" for r, m in history])

    prompt = f"""
You are a finance assistant.

Keep answers short and useful.

Chat history:
{chat_memory}

User:
{user_msg}
"""

    try:
        res = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=120  # ⬅️ important increase
        )

        data = res.json()
        reply = data.get("response", "No response from model")

    except Exception as e:
        reply = f"Ollama connection failed: {str(e)}"

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, "assistant", reply)
    )

    conn.commit()
    conn.close()

    return jsonify({"reply": reply})
# ------------------ OTHER ROUTES ------------------
@app.route("/news")
def finance_news():
    import requests

    query = request.args.get("q")

    # If user searches → show search results
    if query:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "apiKey": NEWS_API_KEY,
            "pageSize": 10
        }

    # Otherwise → show random finance/business news
    else:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": "business",
            "language": "en",
            "apiKey": NEWS_API_KEY,
            "pageSize": 10
        }

    try:
        res = requests.get(url, params=params, timeout=10)
        articles = res.json().get("articles", [])
    except:
        articles = []

    return render_template(
        "news.html",
        articles=articles,
        query=query
    )
@app.route("/budget")
def budget():
    return render_template("budget.html")

@app.route("/tax")
def tax():
    return render_template("tax.html")


# ------------------ RUN ------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)