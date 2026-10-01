-- 图书管理系统 · MySQL 建表脚本
-- 用法：mysql -u root -p library < schema.sql
CREATE DATABASE IF NOT EXISTS library DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE library;

CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(64)  NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(16)  NOT NULL COMMENT 'admin/teacher/student',
  name          VARCHAR(64)  NOT NULL,
  phone         VARCHAR(32),
  INDEX idx_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS books (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  isbn      VARCHAR(32),
  title     VARCHAR(200) NOT NULL,
  author    VARCHAR(100),
  publisher VARCHAR(100),
  total     INT DEFAULT 1,
  available INT DEFAULT 1,
  INDEX idx_books_title (title),
  INDEX idx_books_isbn (isbn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS borrows (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT NOT NULL,
  book_id     INT NOT NULL,
  borrow_date DATE NOT NULL,
  due_date    DATE NOT NULL,
  return_date DATE,
  status      VARCHAR(16) DEFAULT 'borrowed' COMMENT 'borrowed/returned/overdue',
  CONSTRAINT fk_borrow_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_borrow_book FOREIGN KEY (book_id) REFERENCES books(id),
  -- 查询优化核心：覆盖「按用户查在借记录」与「按到期日查提醒」两类高频查询
  INDEX idx_borrow_user_status (user_id, status),
  INDEX idx_borrow_due_status (due_date, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 优化后的借阅查询（可直接 EXPLAIN 验证是否走索引）
-- EXPLAIN SELECT b.id, u.name, bk.title, b.due_date
--   FROM borrows b
--   JOIN users u  ON u.id  = b.user_id
--   JOIN books bk ON bk.id = b.book_id
--  WHERE b.status = 'borrowed' AND b.user_id = 1
--  ORDER BY b.due_date;
