import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd
from datetime import datetime

"""Feito por Bruno Davis. Exercício do CS50 módulo 9: Flask"""

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #getting all shares of the user
    user_shares = db.execute("SELECT * FROM purchases WHERE user_id = ?",session["user_id"])

    #getting the cash of the user
    in_cash_ = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])

    #in this list will be stored the symbol, name, amount of share, price and the the price of share multiplied for the amount of share
    #all this in a dictionary, for each share
    data_shares = []

    #the cash of total of shares plus the cash atual of user
    cash_total_ = 0

    #for each share, will be done the dictionary
    for share in user_shares:
        data_share = lookup(share['symbol'])
        data_shares.append({
        'symbol' : data_share['symbol'],
        'name' : data_share['name'],
        'shares' : share['amount'],
        'price' : data_share['price'],
        'total' : int(share['amount']) * data_share['price']
        })
        cash_total_ += int(share['amount']) * data_share['price']
    cash_total_ += in_cash_[0]['cash']

    return render_template("index.html", shares = data_shares, in_cash = in_cash_[0], cash_total = cash_total_)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    #if the user are submitted the form
    if request.method == "POST":
        #getting the symbol
        symbol = request.form.get("symbol")
        #getting the amount of shares
        amount_shares = request.form.get("shares")
        #query the share
        result = lookup(symbol)
        #if the user did not fill the symbol or the amount of shares
        if not symbol or not amount_shares:
            return apology("must provide symbol and number of shares correctly", 403)
        #if the query return none
        elif not result:
            return apology("symbol not found", 403)

        #if the amount of shares is not a integer or not positive
        elif float(amount_shares) < 1 or float(amount_shares) - int(amount_shares) != 0:
            return apology("must provide a valid number of shares", 403)

        #calculating the total to pay for the shares
        value_shares = result['price'] * int(amount_shares)
        #getting how cash the user have
        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        #calculating the new cash of the user after the purchase
        new_cash = current_cash[0]['cash'] - value_shares

        #if the new cash is a negative value
        if new_cash < 0:
            return apology("total value of shares is greater atual cash", 403)

        #if the new cash is not a negative value, so we can update the cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])
        #only getting the date of today
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        #inserting the purchase in history
        db.execute("INSERT INTO history (user_id, symbol, shares, price, date) VALUES (?,?,?,?,?)", session["user_id"], symbol, amount_shares, result['price'], dt_string)
        #here we can see if the user has been buy the share before
        share_equal_current = db.execute("SELECT symbol, amount FROM purchases WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
        #if he not already buy before
        if(not share_equal_current):
            db.execute("INSERT INTO purchases (user_id, symbol, amount) VALUES (?,?,?)", session["user_id"], symbol, amount_shares)

        #if he already buy before
        else:
            current_amount = share_equal_current[0]['amount']
            #only update the amount
            db.execute("UPDATE purchases SET amount = ? WHERE user_id = ? AND symbol = ?", current_amount + int(amount_shares), session["user_id"], symbol)

        return redirect("/")
    else:
        in_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        return render_template("buy.html", cash = in_cash[0]['cash'])


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    #getting all buy and sell of user
    all_history = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])
    return render_template("history.html", history = all_history)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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

    #if the user are submitted the form
    if request.method == "POST":
        #getting the symbol of the share
        symbol = request.form.get("symbol")
        #getting the data of the share
        result = lookup(symbol)
        #if the share exists
        if(result):
            message = "Price of " + result['symbol'] + " (" + result['name'] + "): " + usd(result['price'])
        else:
            message = "Not Found"
        #returning the result of search
        return render_template("quote.html",quote_result = message)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    #if the user are submitted the form
    if request.method == "POST":
        #if the user did not fill the username
        if not request.form.get("username"):
            return apology("must provide username", 403)

        #if the user did not fill the username
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        #if the user not fill the password confirmation
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 403)

        #if the password and password confirmation are not same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and password confirmation are not same", 403)

        #searching if the user already exists
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        #if the user not already exists
        if not rows:
            #generating the hash of the password
            hash_ = generate_password_hash(request.form.get("password"))
            #inserting the user in database
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",request.form.get("username"), hash_)
            return redirect("/login")
        else:
            return apology("Username already exists", 403)

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    #getting all symbols of shares of user
    symbol_shares_ = db.execute("SELECT symbol FROM purchases WHERE user_id = ?", session["user_id"])

    #transforming in a simple list of string
    symbol_shares = []
    for symbol in symbol_shares_:
        symbol_shares.append(symbol['symbol'])

    #if the user are submitted the form
    if request.method == "POST":
        #getting the symbol and amount of shares
        symbol_selected = request.form.get("symbol")
        amount_shares = request.form.get("shares")

        #if the user not fill any input
        if not symbol_selected or not amount_shares:
            return apology("must provide a symbol and number of shares", 403)

        #if the user not have the symbol selected(he try "hacked" the website)
        elif symbol_selected not in symbol_shares:
            return apology("you don't have this share", 403)

        #if the amount of shares selected are not a positive and integer number
        elif float(amount_shares) < 1 or float(amount_shares) - int(amount_shares) != 0:
            return apology("must provide a valid number of shares", 403)

        #getting the amount that the user have of the symbol selected
        amount_symbol_selected = db.execute("SELECT amount FROM purchases WHERE user_id = ? AND symbol = ?", session["user_id"], symbol_selected)

        #if the user want sell more shares than he have
        if int(amount_shares) > amount_symbol_selected[0]['amount']:
            return apology("amount of shares selected greater than amount you have", 403)

        #getting the price atualized of the symbol
        data_share = lookup(symbol_selected)
        gain_of_sell = int(amount_shares) * data_share['price']

        #if the user will be sell all shares of the symbol selected, so delete the share of database
        if amount_symbol_selected[0]['amount'] - int(amount_shares) == 0:
            db.execute("DELETE FROM purchases WHERE user_id = ? AND symbol = ?", session["user_id"], symbol_selected)

        else:
            #only update the amount
            db.execute("UPDATE purchases SET amount = ? WHERE user_id = ? AND symbol = ?", amount_symbol_selected[0]['amount'] - int(amount_shares), session["user_id"], symbol_selected)

        #getting the atual cash of the user and update for the new cash
        atual_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        new_cash = atual_cash[0]['cash'] + gain_of_sell
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

        #only getting the date
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        #inserting the sell in history
        db.execute("INSERT INTO history (user_id, symbol, shares, price, date) VALUES (?,?,?,?,?)", session["user_id"], symbol_selected, -1 * int(amount_shares), data_share['price'], dt_string)

        return redirect("/")

    else:
        return render_template("sell.html", symbols = symbol_shares)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)