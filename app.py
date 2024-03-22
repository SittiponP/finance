import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


currentTime = datetime.datetime.now()


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_cash = db.execute(
        "SELECT cash FROM users WHERE id =?", session["user_id"])
    stocks = db.execute(
        "SELECT symbol, SUM(shares) as shares, operation FROM stocks WHERE user_ID = ? GROUP BY symbol HAVING (SUM(shares)) > 0;", session["user_id"])

    total_cash_stocks = 0
    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["total"] = stock["price"] * stock["shares"]
        total_cash_stocks = total_cash_stocks + stock["total"]

    total_cash = total_cash_stocks + user_cash[0]["cash"]
    return render_template(
        "index.html", stocks=stocks, user_cash=user_cash[0], total_cash=total_cash
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        price = lookup(symbol)
        shares = request.form.get("shares")

        user_cash = db.execute(
            "SELECT cash FROM users WHERE id=?", session["user_id"])[0]["cash"]

    # check if valid symbol
        if not symbol:
            return apology("Invalid symbol", 400)
        elif price is None:
            return apology("Invalid symbol", 400)

        try:
            shares = int(shares)
            if shares < 1:
                return apology("share must be positive integer", 400)
        except ValueError:
            return apology("share must be positive integer", 400)

        shares_price = shares * price["price"]
        if user_cash < (shares_price):
            return apology("Cash is not enough", 400)

        else:
            db.execute("UPDATE users SET cash = cash-? WHERE id = ?",
                       shares_price,
                       session["user_id"])

            db.execute("INSERT INTO stocks (user_ID, symbol,shares, prices, operation, date) VALUES(?,?,?,?,?,?);",
                       session["user_id"],
                       symbol.upper(),
                       shares,
                       price["price"],
                       "buy",
                       currentTime)

            flash("Transaction sucessfully")
            return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute(
        "SELECT * FROM stocks WHERE user_ID = ?", session["user_id"])
    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # Check if quote is in lookup
        if quote is None:
            return apology("Invalid symbol", 400)
        else:
            return render_template("quoted.html", name=quote["name"], symbol=quote["symbol"], price=quote["price"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirmation")

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # check if usernamefield has been fill
        if not username:
            return apology("Must have a username", 400)

        # check if username exit
        elif len(rows) != 0:
            return apology("Username already exit", 400)

        # check if password fullfill
        elif not password:
            return apology("Must provide password", 400)

        # check if confirmation passowrd was fullfill
        elif not confirm:
            return apology("Must provide Confirmation Password", 400)

        # check if confirmation and password are match
        elif not password == confirm:
            return apology("password doesn't match")

        else:
            # Generate password
            hash = generate_password_hash(
                password, method="pbkdf2:sha256", salt_length=8
            )

            # Insert into database
            db.execute(
                "INSERT INTO users (username,hash) VALUES(?,?)", username, hash)

            return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

    # chack if shares valid
        try:
            shares = int(shares)
            if shares < 1:
                return apology("Invalie shares", 400)
        except ValueError:
            return apology("Invalid shares", 400)

    # check if user input symbol
        if not symbol:
            return apology("Missing symbol")

        stocks = db.execute(
            "SELECT SUM(shares) as shares FROM stocks WHERE user_ID = ? AND symbol = ?;", session["user_id"], symbol)[0]

        if shares > stocks["shares"]:
            return apology("You don't have this number of shares", 400)

        price = lookup(symbol)["price"]
        shares_value = price * shares

        # Insert history
        db.execute("INSERT INTO stocks (user_ID,symbol,shares,prices,operation,date) VALUES(?,?,?,?,?,?)",
                   session["user_id"], symbol.upper(), -shares, price, "sell", currentTime)

        # Update chas in account
        db.execute("UPDATE users SET cash = cash+? WHERE id=?",
                   shares_value, session["user_id"])

        flash("sold")
        return redirect("/")
    else:
        stocks = db.execute(
            "SELECT symbol FROM stocks WHERE user_ID =? GROUP BY symbol",
            session["user_id"]
        )
        return render_template("sell.html", stocks=stocks)
