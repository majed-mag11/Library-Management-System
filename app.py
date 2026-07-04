import os
import numbers
from functools import wraps

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session ,jsonify
from werkzeug.security import check_password_hash, generate_password_hash

#In this code i used the help of Microsoft Copilt

app = Flask(__name__)
app.secret_key = "supersecretkey"   # Change this in production

db = SQL("sqlite:///books.db")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash("You must be logged in.")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    rows = db.execute("""
            SELECT books.id, books.title, books.stock, books.status, books.buy_price , books.borrow_fee,
                authors.name AS author,
                genres.name AS genre
            FROM books
            JOIN authors ON books.author_id = authors.id
            JOIN genres ON books.genre_id = genres.id
            ORDER BY books.title
        """)
    genres = db.execute("SELECT DISTINCT name FROM genres")
    authors = db.execute("SELECT DISTINCT name FROM authors")

    return render_template("index.html", books=rows, genres=genres, authors=authors)


@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = 'cleint'
        if not username or not password:
            flash("All fields are required.")
            return redirect("/register")

        # Check if username exists
        existing = db.execute("SELECT * FROM users WHERE username = ?", username)
        if existing:
            flash("Username already exists.")
            return redirect("/register")

        # Insert new user
        hash_pw = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (username, hash, role) VALUES (?, ?, ?)",
            username, hash_pw, role
        )

        flash("Registered successfully. You may now log in.")
        return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = db.execute("SELECT * FROM users WHERE username = ?", username)

        if not user or not check_password_hash(user[0]["hash"], password):
            flash("Invalid username or password.")
            return redirect("/login")

        # Store user in session
        session["user_id"] = user[0]["id"]
        session["username"] = user[0]["username"]
        session["role"] = user[0]["role"]

        flash("Logged in successfully.")
        return redirect("/")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out.")
    return redirect("/")


@app.route("/admin/books/edit/<int:book_id>", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    # GET → show form
    if request.method == "GET":
        book = db.execute("""
            SELECT books.*, authors.name AS author_name, genres.name AS genre_name
            FROM books
            JOIN authors ON books.author_id = authors.id
            JOIN genres ON books.genre_id = genres.id
            WHERE books.id = ?
        """, book_id)

        if not book:
            flash("Book not found.")
            return redirect("/index")

        return render_template("edit_book.html", book=book[0])

    # POST → update book
    title = request.form.get("title")
    author = request.form.get("author")
    genre = request.form.get("genre")
    stock = request.form.get("stock")
    buy_price = request.form.get("buy_price")
    borrow_fee = request.form.get("borrow_fee")
    status = request.form.get("status")

    # Find or create author
    existing_author = db.execute("SELECT id FROM authors WHERE name = ?", author)
    if existing_author:
        author_id = existing_author[0]["id"]
    else:
        db.execute("INSERT INTO authors (name) VALUES (?)", author)
        author_id = db.execute("SELECT id FROM authors WHERE name = ?", author)[0]["id"]

    # Find or create genre
    existing_genre = db.execute("SELECT id FROM genres WHERE name = ?", genre)
    if existing_genre:
        genre_id = existing_genre[0]["id"]
    else:
        db.execute("INSERT INTO genres (name) VALUES (?)", genre)
        genre_id = db.execute("SELECT id FROM genres WHERE name = ?", genre)[0]["id"]

    # Update book
    db.execute("""
        UPDATE books
        SET title = ?, author_id = ?, genre_id = ?, stock = ?, status = ?, buy_price = ?, borrow_fee = ?
        WHERE id = ?
    """, title, author_id, genre_id, stock, status, buy_price, borrow_fee, book_id)

    flash("Book updated successfully.")
    return redirect("/")

@app.route("/add_books", methods=["GET", "POST"])
@login_required
def add_books():

    # Only allow admin
    if session.get("role") != "admin":
        flash("Access denied! Admins only.")
        return redirect("/")

    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        genre = request.form.get("genre")
        stock = request.form.get("stock")
        buy_price = request.form.get("buy_price")
        borrow_fee = request.form.get("borrow_fee")
        status = request.form.get("status")

        # Convert numbers safely
        try:
            stock = int(stock)
            buy_price = float(buy_price)
            borrow_fee = float(borrow_fee)
        except:
            flash("Invalid number format.")
            return redirect("/add_books")

        # Insert or find author
        existing_author = db.execute("SELECT id FROM authors WHERE name = ?", author)
        if existing_author:
            author_id = existing_author[0]["id"]
        else:
            db.execute("INSERT INTO authors (name) VALUES (?)", author)
            author_id = db.execute("SELECT id FROM authors WHERE name = ?", author)[0]["id"]

        # Insert or find genre
        existing_genre = db.execute("SELECT id FROM genres WHERE name = ?", genre)
        if existing_genre:
            genre_id = existing_genre[0]["id"]
        else:
            db.execute("INSERT INTO genres (name) VALUES (?)", genre)
            genre_id = db.execute("SELECT id FROM genres WHERE name = ?", genre)[0]["id"]

        # Insert book
        db.execute("""
            INSERT INTO books (title, author_id, genre_id, stock, status, buy_price, borrow_fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, title, author_id, genre_id, stock, status, buy_price, borrow_fee)

        flash("Book added successfully!")
        return redirect("/")

    return render_template("add_books.html")

@login_required
@app.route("/search_books")
def search_books():
    q = request.args.get("q", "")
    genre = request.args.get("genre", "")
    author = request.args.get("author", "")
    status = request.args.get("status", "")

    query = """
        SELECT books.id, books.title, books.status,
                authors.name AS author,
                genres.name AS genre
        FROM books
        JOIN authors ON books.author_id = authors.id
        JOIN genres ON books.genre_id = genres.id
        WHERE (books.title LIKE ? OR authors.name LIKE ?)
    """


    params = [f"%{q}%", f"%{q}%"]

    if genre:
        query += " AND genre = ?"
        params.append(genre)

    if author:
        query += " AND author = ?"
        params.append(author)

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " LIMIT 20"

    rows = db.execute(query, *params)
    return jsonify(rows)

@login_required
@app.route("/borrow/<int:book_id>", methods=["GET", "POST"])
def borrow(book_id):

    row = db.execute("SELECT stock FROM books WHERE id = ?", book_id)
    old_stock = row[0]["stock"]

    # Reduce stock
    db.execute("UPDATE books SET stock = ? WHERE id = ?", old_stock - 1, book_id)

    # Insert borrow record
    db.execute("""
        INSERT INTO borrowed_books (user_id, book_id, return_date)
        VALUES (?, ?, NULL)
    """, session["user_id"], book_id)

    flash("Book borrowed successfully!")
    return redirect("/")

@login_required
@app.route("/borrowed_books" , methods=["GET" , "POST"])
def borrowed_books():
    if request.method == "POST" and session.get("role") == "admin":
        borrow_id = request.form.get("return_id")

        if borrow_id:
            record = db.execute("SELECT book_id FROM borrowed_books WHERE id = ?", borrow_id)
            if record:
                book_id = record[0]["book_id"]

                db.execute("""
                    UPDATE borrowed_books
                    SET return_date = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, borrow_id)

                db.execute("""
                    UPDATE books
                    SET stock = stock + 1
                    WHERE id = ?
                """, book_id)

                flash("Book returned successfully!")

        return redirect("/borrowed_books")

    username = session["username"]

    if session.get("role") == "admin":

        rows = db.execute("""
                          SELECT borrowed_books.id, borrowed_books.borrow_date, borrowed_books.return_date,
                                 users.username,
                                 books.title
                          FROM borrowed_books
                          JOIN users ON borrowed_books.user_id = users.id
                          JOIN books ON borrowed_books.book_id = books.id
                          WHERE borrowed_books.return_date IS NULL
                          ORDER BY borrowed_books.borrow_date DESC
                          """)

    else:
        rows = db.execute("""
                          SELECT borrowed_books.id , borrowed_books.borrow_date, borrowed_books.return_date,
                          users.username,
                                 books.title
                          FROM borrowed_books
                          JOIN users ON borrowed_books.user_id = users.id
                          JOIN books ON borrowed_books.book_id = books.id
                          WHERE borrowed_books.return_date IS NULL
                            AND users.username = ?
                          ORDER BY borrowed_books.borrow_date DESC
                          """, username)

    return render_template("borrowed_books.html", rows = rows)

@app.route("/admin/books/suspend/<int:book_id>", methods=["POST", "GET"])
@login_required
def suspend_book(book_id):

    if session["role"] != "admin":
        flash("Access Denied!.")
        return redirect("/")

    db.execute("UPDATE books SET status = 'suspended' WHERE id = ?", book_id)

    flash("Book has been suspended.")
    return redirect("/")

@login_required
@app.route("/history")
def history():

    if session.get("role") != "admin":

        rowrs = rows = db.execute("""
            SELECT borrowed_books.id, borrowed_books.borrow_date, borrowed_books.return_date,
                users.username,
                books.title
            FROM borrowed_books
            JOIN users ON borrowed_books.user_id = users.id
            JOIN books ON borrowed_books.book_id = books.id
            WHERE users.username = ?
            ORDER BY borrowed_books.borrow_date DESC
        """, session["username"])

    else:
        rows = db.execute("""
            SELECT borrowed_books.id, borrowed_books.borrow_date, borrowed_books.return_date,
                users.username,
                books.title
            FROM borrowed_books
            JOIN users ON borrowed_books.user_id = users.id
            JOIN books ON borrowed_books.book_id = books.id
            ORDER BY borrowed_books.borrow_date DESC
        """)

    return render_template("history.html", rows=rows)

@login_required
@app.route("/finance", methods=["GET", "POST"])
def finance():

    if session.get("role") != "admin":
        flash("Access denied! Admins only.")
        return redirect("/")

    # Default filter values
    period = request.args.get("period", "daily")   # daily, monthly, all
    trans_type = request.args.get("type", "all")   # borrow, sell, all
    month = request.args.get("month")              # YYYY-MM format

    query = """
        SELECT borrowed_books.id,
               borrowed_books.borrow_date,
               borrowed_books.return_date,
               users.username,
               books.title,
               books.borrow_fee,
               'borrow' AS transaction_type
        FROM borrowed_books
        JOIN users ON borrowed_books.user_id = users.id
        JOIN books ON borrowed_books.book_id = books.id
    """

    # If you add sales later, UNION them here:
    # UNION ALL SELECT sales.id, sales.date, NULL, users.username, books.title, books.buy_price, 'sell' ...

    conditions = []
    params = []

    # Period filter
    if period == "daily":
        conditions.append("DATE(borrowed_books.borrow_date) = DATE('now')")
    elif period == "monthly" and month:
        conditions.append("strftime('%Y-%m', borrowed_books.borrow_date) = ?")
        params.append(month)

    # Transaction type filter
    if trans_type == "borrow":
        conditions.append("transaction_type = 'borrow'")
    elif trans_type == "sell":
        conditions.append("transaction_type = 'sell'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY borrowed_books.borrow_date DESC"

    rows = db.execute(query, *params)

    # Calculate total money
    total_money = sum(r["borrow_fee"] for r in rows if r["transaction_type"] == "borrow")

    return render_template("finance.html",
                           rows=rows,
                           total_money=total_money,
                           period=period,
                           trans_type=trans_type,
                           month=month)
