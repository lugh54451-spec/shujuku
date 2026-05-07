PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS sold_item_view;
DROP VIEW IF EXISTS unsold_item_view;
DROP TRIGGER IF EXISTS orders_item_must_be_unsold;
DROP TRIGGER IF EXISTS orders_item_status_to_sold;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS item;
DROP TABLE IF EXISTS user;

CREATE TABLE user (
    user_id TEXT PRIMARY KEY,
    user_name TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE TABLE item (
    item_id TEXT PRIMARY KEY,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    status INTEGER NOT NULL CHECK (status IN (0, 1)),
    seller_id TEXT NOT NULL,
    FOREIGN KEY (seller_id) REFERENCES user(user_id)
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL UNIQUE,
    buyer_id TEXT NOT NULL,
    order_date TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES item(item_id),
    FOREIGN KEY (buyer_id) REFERENCES user(user_id)
);

CREATE TRIGGER orders_item_must_be_unsold
BEFORE INSERT ON orders
FOR EACH ROW
WHEN (SELECT status FROM item WHERE item_id = NEW.item_id) <> 0
BEGIN
    SELECT RAISE(ABORT, 'This item has already been sold.');
END;

CREATE TRIGGER orders_item_status_to_sold
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    UPDATE item SET status = 1 WHERE item_id = NEW.item_id;
END;

CREATE VIEW sold_item_view AS
SELECT i.item_name, o.buyer_id
FROM item i
JOIN orders o ON i.item_id = o.item_id
WHERE i.status = 1;

CREATE VIEW unsold_item_view AS
SELECT item_id, item_name, category, price, seller_id
FROM item
WHERE status = 0;

INSERT INTO user (user_id, user_name, phone) VALUES
('u001', 'ZhangSan', '13800000001'),
('u002', 'LiSi', '13800000002'),
('u003', 'WangWu', '13800000003'),
('u004', 'ZhaoLiu', '13800000004');

INSERT INTO item (item_id, item_name, category, price, status, seller_id) VALUES
('i001', 'CalculusBook', 'Book', 20, 0, 'u001'),
('i002', 'DeskLamp', 'DailyGoods', 35, 0, 'u002'),
('i003', 'Microcontroller', 'Electronics', 80, 0, 'u001'),
('i004', 'Chair', 'Furniture', 50, 0, 'u003'),
('i005', 'WaterBottle', 'DailyGoods', 15, 0, 'u004');

INSERT INTO orders (order_id, item_id, buyer_id, order_date) VALUES
('o001', 'i002', 'u001', '2024-05-01'),
('o002', 'i004', 'u002', '2024-05-03');
