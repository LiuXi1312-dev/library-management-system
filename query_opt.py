"""借阅查询 SQL 优化对比脚本

复现简历中的优化结论：借阅查询响应时间 0.8s → 0.3s。
用法：python query_opt.py --rows 20000
"""
import argparse
import os
import random
import sqlite3
import time

DB_PATH = "query_opt_demo.db"


def build_demo_db(rows: int) -> sqlite3.Connection:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT)")
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    cur.execute("""CREATE TABLE borrows (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        book_id INTEGER,
        due_date TEXT,
        status TEXT
    )""")
    cur.executemany("INSERT INTO books VALUES (?,?)",
                    [(i, f"图书-{i}") for i in range(1, 501)])
    cur.executemany("INSERT INTO users VALUES (?,?)",
                    [(i, f"用户-{i}") for i in range(1, 301)])
    random.seed(42)
    data = [(i, random.randint(1, 300), random.randint(1, 500),
             f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
             random.choice(["borrowed", "borrowed", "borrowed", "returned"]))
            for i in range(1, rows + 1)]
    cur.executemany("INSERT INTO borrows VALUES (?,?,?,?,?)", data)

    # ===== 优化点 2：建立复合索引 =====
    cur.execute("CREATE INDEX idx_borrow_user_status ON borrows(user_id, status)")
    cur.execute("CREATE INDEX idx_borrow_due_status ON borrows(due_date, status)")
    conn.commit()
    return conn


def naive_query(conn: sqlite3.Connection):
    """优化前：SELECT * + 逐条再查关联表（N+1 查询）"""
    cur = conn.cursor()
    cur.execute("SELECT * FROM borrows WHERE status='borrowed'")
    records = cur.fetchall()
    result = []
    for r in records:                                   # 每条记录再查两次 → N+1
        cur.execute("SELECT title FROM books WHERE id=?", (r[2],))
        title = cur.fetchone()[0]
        cur.execute("SELECT name FROM users WHERE id=?", (r[1],))
        name = cur.fetchone()[0]
        result.append((r[0], name, title, r[3]))
    return result


def optimized_query(conn: sqlite3.Connection):
    """优化后：一次 JOIN 取齐字段 + 只取需要的列 + 走索引"""
    cur = conn.cursor()
    cur.execute("""
        SELECT b.id, u.name, bk.title, b.due_date
        FROM borrows b
        JOIN users u ON u.id = b.user_id
        JOIN books bk ON bk.id = b.book_id
        WHERE b.status = 'borrowed'
        ORDER BY b.due_date
    """)
    return cur.fetchall()


def explain(conn: sqlite3.Connection, sql: str) -> None:
    cur = conn.cursor()
    cur.execute(f"EXPLAIN QUERY PLAN {sql}")
    for row in cur.fetchall():
        print("   ", row[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20000, help="模拟借阅记录条数")
    args = ap.parse_args()

    print(f"构造 {args.rows} 条借阅记录 ...")
    conn = build_demo_db(args.rows)

    t0 = time.perf_counter()
    n1 = naive_query(conn)
    t1 = time.perf_counter()
    n2 = optimized_query(conn)
    t2 = time.perf_counter()

    print(f"\n优化前（SELECT * + N+1 关联查询）: {t1 - t0:.3f}s，返回 {len(n1)} 条")
    print(f"优化后（JOIN + 覆盖索引 + 按需取列）: {t2 - t1:.3f}s，返回 {len(n2)} 条")
    print(f"提升: {(t1 - t0) / max(t2 - t1, 1e-6):.1f}x\n")

    print("优化后查询的执行计划（出现 USING INDEX 即命中索引）：")
    explain(conn, """
        SELECT b.id, u.name, bk.title, b.due_date
        FROM borrows b JOIN users u ON u.id=b.user_id JOIN books bk ON bk.id=b.book_id
        WHERE b.status='borrowed' ORDER BY b.due_date
    """)

    conn.close()
    os.remove(DB_PATH)
    print("\n说明：0.8s→0.3s 是当时环境(2 万条记录)的实测值，本机结果会随数据量与机器性能变化。")


if __name__ == "__main__":
    main()
