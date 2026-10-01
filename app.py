"""图书管理系统 · Flask 入口

运行：python app.py  →  http://127.0.0.1:5000
"""
from datetime import date, timedelta
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_, select
from werkzeug.security import check_password_hash

from models import Book, Borrow, User, create_session_factory, seed_if_empty

app = Flask(__name__)
app.secret_key = "library-demo-secret-key"

engine, SessionLocal = create_session_factory()
seed_if_empty(SessionLocal)

REMIND_DAYS = 3   # 到期前 3 天开始提醒


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("当前角色没有该操作权限", "warn")
                return redirect(url_for("index"))
            return func(*args, **kwargs)
        return wrapper
    return deco


def current_user():
    with SessionLocal() as s:
        return s.get(User, session["user_id"])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with SessionLocal() as s:
            user = s.query(User).filter_by(username=username).one_or_none()
            if user and check_password_hash(user.password_hash, password):
                session.update({"user_id": user.id, "role": user.role, "name": user.name})
                return redirect(url_for("index"))
        flash("账号或密码错误", "warn")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    keyword = request.args.get("q", "").strip()
    with SessionLocal() as s:
        stmt = select(Book)
        if keyword:
            stmt = stmt.where(or_(Book.title.like(f"%{keyword}%"),
                                  Book.author.like(f"%{keyword}%")))
        books = s.execute(stmt.order_by(Book.id)).scalars().all()

        # 优化点 1+2：一次性 JOIN 取齐用户与图书信息，走 idx_borrow_user_status 索引
        stmt = (select(Borrow, Book.title, User.name)
                .join(Book, Borrow.book_id == Book.id)
                .join(User, Borrow.user_id == User.id)
                .where(Borrow.status == "borrowed")
                .order_by(Borrow.due_date))
        if session["role"] != "admin":
            stmt = stmt.where(Borrow.user_id == session["user_id"])
        rows = s.execute(stmt).all()

        today = date.today()
        due_soon = [r for r in rows if today <= r[0].due_date <= today + timedelta(days=REMIND_DAYS)]
        overdue = [r for r in rows if r[0].due_date < today]
        for b in overdue:                      # 更新逾期状态
            b[0].status = "overdue"
        s.commit()

    return render_template("index.html", books=books, rows=rows,
                           due_soon=due_soon, overdue=overdue, keyword=keyword)


@app.route("/borrow/<int:book_id>", methods=["POST"])
@login_required
def borrow(book_id):
    with SessionLocal() as s:
        book = s.get(Book, book_id)
        if not book or book.available <= 0:
            flash("该书暂无可借库存", "warn")
            return redirect(url_for("index"))
        exist = s.query(Borrow).filter_by(user_id=session["user_id"], book_id=book_id,
                                          status="borrowed").first()
        if exist:
            flash("你已经借了这本书", "warn")
            return redirect(url_for("index"))
        today = date.today()
        s.add(Borrow(user_id=session["user_id"], book_id=book_id, borrow_date=today,
                     due_date=today + timedelta(days=30), status="borrowed"))
        book.available -= 1
        s.commit()
        flash(f"借阅成功：{book.title}", "ok")
    return redirect(url_for("index"))


@app.route("/return/<int:borrow_id>", methods=["POST"])
@login_required
def return_book(borrow_id):
    with SessionLocal() as s:
        record = s.get(Borrow, borrow_id)
        if not record:
            flash("记录不存在", "warn")
            return redirect(url_for("index"))
        if session["role"] != "admin" and record.user_id != session["user_id"]:
            flash("不能归还他人的借阅记录", "warn")
            return redirect(url_for("index"))
        record.status = "returned"
        record.return_date = date.today()
        book = s.get(Book, record.book_id)
        book.available += 1
        s.commit()
        flash("归还成功", "ok")
    return redirect(url_for("index"))


@app.route("/books/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def new_book():
    if request.method == "POST":
        with SessionLocal() as s:
            total = int(request.form.get("total", 1))
            s.add(Book(isbn=request.form.get("isbn", ""),
                       title=request.form["title"],
                       author=request.form.get("author", ""),
                       publisher=request.form.get("publisher", ""),
                       total=total, available=total))
            s.commit()
        flash("图书录入成功", "ok")
        return redirect(url_for("index"))
    return render_template("book_form.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
