from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

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
            return redirect("/dashboard")   # 👈 goes to explore page

    return render_template("login.html")


# ------------------ EXPLORE PAGE ------------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("dashboard.html")


# ------------------ PERSONAL DASHBOARD ------------------
@app.route("/dashboard-view")
def dashboard_view():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount, category, type FROM expenses WHERE user_id=?",
        (session["user_id"],)
    )
    rows = cursor.fetchall()

    income_data = {}
    expense_data = {}

    total_income = 0
    total_expense = 0

    for amount, category, t in rows:
        t = t if t else "expense"

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
        income=income_data,
        expense=expense_data,
        total_income=total_income,
        total_expense=total_expense,
        savings=savings
    )


# ------------------ ADD ENTRY ------------------
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
@app.route("/news")
def news():
    return render_template("news.html")

@app.route("/budget")
def budget():
    return render_template("budget.html")

@app.route("/tax")
def tax():
    return render_template("tax.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)