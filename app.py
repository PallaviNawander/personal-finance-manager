from flask import Flask, render_template, request, redirect, url_for
import requests
app = Flask(__name__)

expenses = []

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

    print(data)

    articles = data.get("articles", [])

    return render_template("dashboard.html", expenses=expenses, articles=articles)

@app.route("/add-expense", methods=["POST"])
def add_expense():
    expense = {
        "amount": request.form["amount"],
        "category": request.form["category"],
        "date": request.form["date"]
    }
    expenses.append(expense)
    return redirect(url_for('dashboard'))

@app.route("/delete/<int:index>")
def delete(index):
    if index < len(expenses):
        expenses.pop(index)
    return redirect(url_for('dashboard'))

@app.route("/update/<int:index>", methods=["POST"])
def update(index):
    if index < len(expenses):
        expenses[index]["amount"] = request.form["amount"]
        expenses[index]["category"] = request.form["category"]
        expenses[index]["date"] = request.form["date"]
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    app.run(debug=True)