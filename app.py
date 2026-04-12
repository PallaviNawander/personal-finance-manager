from flask import Flask, render_template, request, redirect, url_for
import requests
import sqlite3

app = Flask(__name__)


def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER,
        category TEXT,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("welcome.html")


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        return redirect(url_for('dashboard'))
    return render_template("login.html")


@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        return redirect(url_for('dashboard'))
    return render_template("signup.html")

@app.route("/dashboard")
def dashboard():
    url = "https://newsapi.org/v2/everything?q=finance&sortBy=publishedAt&apiKey=8fff8f21092b4577b3fda4f72cab4ea7"

    response = requests.get(url)
    data = response.json()
    articles = data.get("articles", [])

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM expenses")
    rows = cursor.fetchall()

    conn.close()
    expenses = []
    for row in rows:
        expenses.append({
            "id": row[0],
            "amount": row[1],
            "category": row[2],
            "date": row[3]
        })

    return render_template("dashboard.html", expenses=expenses, articles=articles)

@app.route("/add-expense", methods=["POST"])
def add_expense():
    amount = request.form["amount"]
    category = request.form["category"]
    date = request.form["date"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO expenses (amount, category, date) VALUES (?, ?, ?)",
        (amount, category, date)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route("/delete/<int:id>")
def delete(id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM expenses WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    amount = request.form["amount"]
    category = request.form["category"]
    date = request.form["date"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE expenses
        SET amount=?, category=?, date=?
        WHERE id=?
    """, (amount, category, date, id))

    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    init_db()   # VERY IMPORTANT
    app.run(debug=True)