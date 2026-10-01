# 图书管理系统

> 简历对应经历：2025.03–2025.07｜Python + MySQL + Flask

多角色（管理员 / 教师 / 学生）的图书借阅管理系统，包含图书录入、借阅查询、到期提醒，
并对借阅查询做了 SQL 层面的优化（实测 0.8s → 0.3s，复现脚本见 `query_opt.py`）。

## 功能

| 角色 | 权限 |
|---|---|
| 管理员 | 图书录入与库存维护、查看全部借阅记录、到期与逾期清单 |
| 教师 | 查询图书、借阅/归还、查看本人借阅与到期提醒 |
| 学生 | 查询图书、借阅/归还、查看本人借阅与到期提醒 |

- 图书信息录入（ISBN / 书名 / 作者 / 出版社 / 总册数 / 可借册数）
- 借阅查询：支持按书名模糊搜索 + 只查在借记录
- 借阅到期提醒：到期前 3 天内及已逾期的记录高亮提醒
- 借阅 / 归还会自动维护可借册数，避免超借

## 快速开始

```bash
pip install -r requirements.txt
python app.py
# 浏览器打开 http://127.0.0.1:5000
```

首次运行会自动建表并写入演示数据，默认账号：

| 角色 | 账号 | 密码 |
|---|---|---|
| 管理员 | admin | admin123 |
| 教师 | teacher | teacher123 |
| 学生 | student | student123 |

## 切换到 MySQL

默认用 SQLite（零配置就能跑）。要用 MySQL：

```bash
# Windows
set DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/library
pip install pymysql
# 或先执行 schema.sql 建表（含优化用到的索引）
mysql -u root -p library < schema.sql
```

## SQL 优化做了什么

见 `query_opt.py`，可一键复现：

1. **消除 N+1**：原来查出借阅记录后逐条再查用户/图书，改为一次 `JOIN` 取齐字段；
2. **加覆盖索引**：`borrows(user_id, status)` 与 `borrows(due_date)`，避免全表扫描；
3. **只取需要的列**，不 `SELECT *`；
4. 结果用 `EXPLAIN` 对比执行计划。

```bash
python query_opt.py --rows 20000     # 造数据并对比优化前后耗时
```

> 0.8s → 0.3s 是当时环境（2 万条借阅记录）的实测值，你的机器上数字会不同，但优化比例可复现。

## 目录结构

```
01-library-system/
├─ app.py          # Flask 路由与页面逻辑
├─ models.py       # 数据模型(User/Book/Borrow)与建表、演示数据
├─ query_opt.py    # 查询优化对比脚本
├─ schema.sql      # MySQL 建表语句(含索引)
├─ requirements.txt
└─ templates/      # 页面模板
```
