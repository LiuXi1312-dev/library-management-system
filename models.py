"""数据模型层：User / Book / Borrow

默认 SQLite，便于零配置启动；设置环境变量 DATABASE_URL 即可切换 MySQL，例如：
  mysql+pymysql://root:password@127.0.0.1:3306/library
"""
import os
from datetime import date, timedelta

from sqlalchemy import (
    Column, Date, ForeignKey, Index, Integer, String, Text, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from werkzeug.security import generate_password_hash

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False)          # admin / teacher / student
    name = Column(String(64), nullable=False)
    phone = Column(String(32))

    borrows = relationship("Borrow", back_populates="user")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    isbn = Column(String(32), index=True)
    title = Column(String(200), nullable=False, index=True)
    author = Column(String(100))
    publisher = Column(String(100))
    total = Column(Integer, default=1)                 # 总册数
    available = Column(Integer, default=1)             # 可借册数

    borrows = relationship("Borrow", back_populates="book")


class Borrow(Base):
    __tablename__ = "borrows"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    borrow_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    return_date = Column(Date)
    status = Column(String(16), default="borrowed")    # borrowed / returned / overdue

    user = relationship("User", back_populates="borrows")
    book = relationship("Book", back_populates="borrows")

    # 优化点 2：覆盖高频查询的复合索引
    __table_args__ = (
        Index("idx_borrow_user_status", "user_id", "status"),
        Index("idx_borrow_due_status", "due_date", "status"),
    )


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///library.db")


def create_session_factory(url: str | None = None):
    url = url or get_database_url()
    engine = create_engine(url, future=True, echo=False)
    # SQLite 下每次请求新建连接时的线程限制处理
    if url.startswith("sqlite"):
        engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False, future=True)


DEMO_USERS = [
    ("admin", "admin123", "admin", "系统管理员"),
    ("teacher", "teacher123", "teacher", "张老师"),
    ("student", "student123", "student", "刘曦"),
]

DEMO_BOOKS = [
    ("9787115428028", "Python编程：从入门到实践", "Eric Matthes", "人民邮电出版社", 5),
    ("9787111633811", "OpenCV计算机视觉编程攻略", "安德里安·凯勒", "人民邮电出版社", 3),
    ("9787302510082", "数据库系统概论", "王珊", "清华大学出版社", 8),
    ("9787115375667", "Flask Web开发实战", "李辉", "机械工业出版社", 4),
    ("9787121369497", "深度学习", "Ian Goodfellow", "电子工业出版社", 6),
    ("9787115546131", "计算机视觉：算法与应用", "Richard Szeliski", "科学出版社", 3),
]


def seed_if_empty(session_factory) -> None:
    """建表后写入演示数据，方便 clone 下来就能看到效果。"""
    with session_factory() as s:
        if s.query(User).count() == 0:
            for username, pwd, role, name in DEMO_USERS:
                s.add(User(username=username,
                           password_hash=generate_password_hash(pwd),
                           role=role, name=name))
        if s.query(Book).count() == 0:
            for isbn, title, author, pub, total in DEMO_BOOKS:
                s.add(Book(isbn=isbn, title=title, author=author,
                           publisher=pub, total=total, available=total))
        s.commit()

        # 造几条借阅记录，其中包含一条即将到期和一条已逾期，用于演示提醒
        if s.query(Borrow).count() == 0:
            student = s.query(User).filter_by(username="student").one()
            teacher = s.query(User).filter_by(username="teacher").one()
            books = s.query(Book).limit(3).all()
            today = date.today()
            samples = [
                (student.id, books[0].id, today - timedelta(days=20), today - timedelta(days=2), "borrowed"),
                (student.id, books[1].id, today - timedelta(days=5), today + timedelta(days=2), "borrowed"),
                (teacher.id, books[2].id, today - timedelta(days=1), today + timedelta(days=25), "borrowed"),
            ]
            for uid, bid, bdate, ddate, status in samples:
                s.add(Borrow(user_id=uid, book_id=bid, borrow_date=bdate,
                             due_date=ddate, status=status))
            s.commit()
