from flask import Flask, render_template, request
app=Flask(__name__)
@app.route("/")
def home():
    return render_template("welcome.html")
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"]
        password=request.form["password"]
        return "Login successful!"
    return render_template("login.html")
@app.route("/signup")
def signup():
    return render_template("signup.html")
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")
if __name__=="__main__":
    app.run(debug=True)