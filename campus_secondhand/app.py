from datetime import date
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
import os
import sqlite3

from init_db import DB_PATH, init_database


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))

BRAND = "\u6821\u56ed\u4e8c\u624b\u4ea4\u6613\u5e73\u53f0"
CATEGORIES = ["Book", "DailyGoods", "Electronics", "Furniture"]

HEADER_LABELS = {
    "user_id": "\u7528\u6237\u7f16\u53f7",
    "user_name": "\u7528\u6237\u540d",
    "phone": "\u624b\u673a\u53f7",
    "item_id": "\u5546\u54c1\u7f16\u53f7",
    "item_name": "\u5546\u54c1\u540d",
    "category": "\u7c7b\u522b",
    "price": "\u4ef7\u683c",
    "status": "\u72b6\u6001",
    "seller_id": "\u5356\u5bb6\u7f16\u53f7",
    "seller_name": "\u5356\u5bb6\u59d3\u540d",
    "buyer_id": "\u4e70\u5bb6\u7f16\u53f7",
    "buyer_name": "\u4e70\u5bb6\u59d3\u540d",
    "order_id": "\u8ba2\u5355\u7f16\u53f7",
    "order_date": "\u8ba2\u5355\u65e5\u671f",
    "purchase_status": "\u8d2d\u4e70\u72b6\u6001",
    "item_count": "\u5546\u54c1\u6570\u91cf",
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql: str, params: tuple = ()) -> int:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount


def scalar(sql: str, params: tuple = ()):
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()[0]


def field(data: dict, name: str, default: str = "") -> str:
    return data.get(name, [default])[0].strip()


def option(value: str, label: str, selected: str = "") -> str:
    mark = " selected" if value == selected else ""
    return f'<option value="{escape(value)}"{mark}>{escape(label)}</option>'


def table(rows: list[sqlite3.Row], empty: str = "\u6682\u65e0\u6570\u636e") -> str:
    if not rows:
        return f'<p class="empty">{escape(empty)}</p>'
    headers = rows[0].keys()
    head = "".join(f"<th>{escape(HEADER_LABELS.get(str(h), str(h)))}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(row[h]))}</td>" for h in headers)
        body.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def card(title: str, value: str, note: str = "") -> str:
    return f"""<section class="card">
      <h3>{escape(title)}</h3>
      <p class="metric">{escape(value)}</p>
      <p>{escape(note)}</p>
    </section>"""


def page(title: str, body: str, message: str = "", active: str = "") -> bytes:
    nav_items = [
        ("/items", "\u5546\u54c1"),
        ("/users", "\u7528\u6237"),
        ("/orders", "\u8ba2\u5355"),
        ("/queries", "\u67e5\u8be2"),
        ("/operations", "\u6570\u636e\u64cd\u4f5c"),
        ("/purchase", "\u8d2d\u4e70"),
        ("/stats", "\u7edf\u8ba1\u4e0e\u89c6\u56fe"),
        ("/report", "\u5b89\u5168\u4e0e\u6062\u590d"),
    ]
    nav = "".join(
        f'<a class="{"active" if href == active else ""}" href="{href}">{label}</a>'
        for href, label in nav_items
    )
    notice = f'<div class="notice">{escape(message)}</div>' if message else ""
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - {BRAND}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">{BRAND}</a>
    <nav>{nav}</nav>
  </header>
  <main>{notice}{body}</main>
</body>
</html>"""
    return html.encode("utf-8")


def next_order_id() -> str:
    current = scalar("SELECT COALESCE(MAX(CAST(SUBSTR(order_id, 2) AS INTEGER)), 0) FROM orders")
    return f"o{current + 1:03d}"


class CampusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        message = field(params, "msg")
        routes = {
            "/": self.home,
            "/items": self.items,
            "/users": self.users,
            "/orders": self.orders,
            "/queries": self.queries,
            "/operations": self.operations,
            "/purchase": self.purchase,
            "/stats": self.stats,
            "/report": self.report,
        }
        if parsed.path == "/static/style.css":
            self.static("style.css")
            return
        view = routes.get(parsed.path)
        if view is None:
            self.respond(page("\u9875\u9762\u4e0d\u5b58\u5728", "<h1>\u9875\u9762\u4e0d\u5b58\u5728</h1>", active=""), HTTPStatus.NOT_FOUND)
            return
        self.respond(view(params, message))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        data = parse_qs(self.rfile.read(length).decode("utf-8"))
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/operations":
                msg = self.handle_operation(data)
                self.redirect(f"/operations?{urlencode({'msg': msg})}")
            elif parsed.path == "/purchase":
                msg = self.handle_purchase(data)
                self.redirect(f"/purchase?{urlencode({'msg': msg})}")
            else:
                self.redirect("/")
        except (sqlite3.Error, ValueError) as exc:
            msg = "\u64cd\u4f5c\u5931\u8d25\uff1a" + str(exc)
            self.redirect(f"{parsed.path}?{urlencode({'msg': msg})}")

    def static(self, filename: str) -> None:
        path = STATIC_DIR / filename
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond(self, data: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def home(self, _params, message: str) -> bytes:
        total = scalar("SELECT COUNT(*) FROM item")
        unsold = scalar("SELECT COUNT(*) FROM item WHERE status = 0")
        orders = scalar("SELECT COUNT(*) FROM orders")
        sold = total - unsold
        recent = query("""SELECT o.order_id, i.item_name, u.user_name AS buyer_name, o.order_date
                         FROM orders o
                         JOIN item i ON o.item_id = i.item_id
                         JOIN user u ON o.buyer_id = u.user_id
                         ORDER BY o.order_date DESC, o.order_id DESC LIMIT 5""")
        body = f"""
        <section class="hero"><h1>{BRAND}\u7ba1\u7406\u540e\u53f0</h1></section>
        <section class="grid three">
          {card("\u5546\u54c1\u603b\u6570", str(total), "\u5f53\u524d\u5e73\u53f0\u6536\u5f55\u5546\u54c1")}
          {card("\u5728\u552e\u5546\u54c1", str(unsold), "\u53ef\u7ee7\u7eed\u4ea4\u6613")}
          {card("\u5df2\u5b8c\u6210\u8ba2\u5355", str(orders), "\u7d2f\u8ba1\u6210\u4ea4\u8bb0\u5f55")}
        </section>
        <section class="panel">
          <h2>\u4ea4\u6613\u6982\u89c8</h2>
          <div class="summary-line">
            <span>\u5728\u552e {unsold} \u4ef6</span>
            <span>\u5df2\u552e {sold} \u4ef6</span>
            <span>\u8ba2\u5355 {orders} \u7b14</span>
          </div>
        </section>
        <section class="panel"><h2>\u6700\u8fd1\u8ba2\u5355</h2>{table(recent)}</section>
        """
        return page("\u9996\u9875", body, message)

    def users(self, _params, message: str) -> bytes:
        rows = query("SELECT user_id, user_name, phone FROM user ORDER BY user_id")
        return page("\u7528\u6237\u5217\u8868", f"<h1>\u7528\u6237\u5217\u8868</h1>{table(rows)}", message, "/users")

    def items(self, _params, message: str) -> bytes:
        rows = query("""SELECT item_id, item_name, category, price,
                              CASE status WHEN 0 THEN '\u672a\u552e\u51fa' ELSE '\u5df2\u552e\u51fa' END AS status,
                              seller_id
                       FROM item ORDER BY item_id""")
        return page("\u5546\u54c1\u5217\u8868", f"<h1>\u5546\u54c1\u5217\u8868</h1>{table(rows)}", message, "/items")

    def orders(self, _params, message: str) -> bytes:
        rows = query("""SELECT o.order_id, o.item_id, i.item_name, o.buyer_id,
                              u.user_name AS buyer_name, o.order_date
                       FROM orders o
                       JOIN item i ON o.item_id = i.item_id
                       JOIN user u ON o.buyer_id = u.user_id
                       ORDER BY o.order_id""")
        return page("\u8ba2\u5355\u5217\u8868", f"<h1>\u8ba2\u5355\u5217\u8868</h1>{table(rows)}", message, "/orders")

    def queries(self, params, message: str) -> bytes:
        selected = field(params, "q", "unsold")
        fixed = {
            "unsold": ("\u672a\u552e\u5546\u54c1", "SELECT item_id, item_name, category, price, seller_id FROM item WHERE status = 0 ORDER BY item_id", ()),
            "price": ("\u4ef7\u683c\u5927\u4e8e 30 \u7684\u5546\u54c1", "SELECT item_id, item_name, category, price, status, seller_id FROM item WHERE price > 30 ORDER BY price DESC", ()),
            "daily": ("\u751f\u6d3b\u7528\u54c1\u7c7b\u5546\u54c1", "SELECT item_id, item_name, category, price, status, seller_id FROM item WHERE category = 'DailyGoods' ORDER BY item_id", ()),
            "u001": ("u001 \u53d1\u5e03\u7684\u5546\u54c1", "SELECT item_id, item_name, category, price, status FROM item WHERE seller_id = 'u001' ORDER BY item_id", ()),
            "sold_buyers": ("\u5df2\u552e\u5546\u54c1\u53ca\u4e70\u5bb6\u59d3\u540d", "SELECT i.item_id, i.item_name, u.user_name AS buyer_name FROM orders o JOIN item i ON o.item_id = i.item_id JOIN user u ON o.buyer_id = u.user_id ORDER BY i.item_id", ()),
            "order_detail": ("\u8ba2\u5355\u660e\u7ec6", "SELECT o.order_id, i.item_name, u.user_name AS buyer_name, o.order_date FROM orders o JOIN item i ON o.item_id = i.item_id JOIN user u ON o.buyer_id = u.user_id ORDER BY o.order_id", ()),
            "u001_sold": ("u001 \u5356\u5bb6\u5546\u54c1\u4ea4\u6613\u72b6\u6001", "SELECT i.item_id, i.item_name, CASE WHEN o.order_id IS NULL THEN '\u672a\u8d2d\u4e70' ELSE '\u5df2\u8d2d\u4e70' END AS purchase_status, o.buyer_id FROM item i LEFT JOIN orders o ON i.item_id = o.item_id WHERE i.seller_id = 'u001' ORDER BY i.item_id", ()),
        }
        if field(params, "mode") == "custom":
            title, sql, sql_params = self.custom_query(params)
            selected = ""
        else:
            title, sql, sql_params = fixed.get(selected, fixed["unsold"])
        buttons = "".join(f'<a class="button {"active" if k == selected else ""}" href="/queries?q={k}">{escape(v[0])}</a>' for k, v in fixed.items())
        body = f"""
        <h1>\u67e5\u8be2\u4e2d\u5fc3</h1>
        <section class="panel"><h2>\u5feb\u901f\u67e5\u8be2</h2><div class="actions">{buttons}</div></section>
        {self.query_form(params)}
        <section class="panel"><h2>{escape(title)}</h2>{table(query(sql, sql_params))}</section>
        """
        return page("\u67e5\u8be2\u5c55\u793a", body, message, "/queries")

    def custom_query(self, params: dict) -> tuple[str, str, tuple]:
        target = field(params, "target", "items")
        keyword = field(params, "keyword")
        category = field(params, "category")
        status = field(params, "status")
        seller_id = field(params, "seller_id")
        buyer_id = field(params, "buyer_id")
        min_price = field(params, "min_price")
        max_price = field(params, "max_price")
        where, values = [], []
        if target == "orders":
            sql = "SELECT o.order_id, i.item_name, o.buyer_id, u.user_name AS buyer_name, o.order_date FROM orders o JOIN item i ON o.item_id = i.item_id JOIN user u ON o.buyer_id = u.user_id"
            if buyer_id:
                where.append("o.buyer_id = ?")
                values.append(buyer_id)
            if keyword:
                where.append("i.item_name LIKE ?")
                values.append(f"%{keyword}%")
            order = " ORDER BY o.order_id"
            title = "\u81ea\u5b9a\u4e49\u67e5\u8be2\uff1a\u8ba2\u5355"
        elif target == "sold":
            sql = "SELECT i.item_id, i.item_name, i.category, i.price, o.buyer_id, u.user_name AS buyer_name FROM item i JOIN orders o ON i.item_id = o.item_id JOIN user u ON o.buyer_id = u.user_id"
            if seller_id:
                where.append("i.seller_id = ?")
                values.append(seller_id)
            if buyer_id:
                where.append("o.buyer_id = ?")
                values.append(buyer_id)
            order = " ORDER BY i.item_id"
            title = "\u81ea\u5b9a\u4e49\u67e5\u8be2\uff1a\u5df2\u552e\u5546\u54c1"
        else:
            sql = "SELECT item_id, item_name, category, price, CASE status WHEN 0 THEN '\u672a\u552e\u51fa' ELSE '\u5df2\u552e\u51fa' END AS status, seller_id FROM item"
            if keyword:
                where.append("item_name LIKE ?")
                values.append(f"%{keyword}%")
            if category:
                where.append("category = ?")
                values.append(category)
            if status:
                where.append("status = ?")
                values.append(int(status))
            if seller_id:
                where.append("seller_id = ?")
                values.append(seller_id)
            if min_price:
                where.append("price >= ?")
                values.append(float(min_price))
            if max_price:
                where.append("price <= ?")
                values.append(float(max_price))
            order = " ORDER BY item_id"
            title = "\u81ea\u5b9a\u4e49\u67e5\u8be2\uff1a\u5546\u54c1"
        if where:
            sql += " WHERE " + " AND ".join(where)
        return title, sql + order, tuple(values)

    def query_form(self, params: dict) -> str:
        target = field(params, "target", "items")
        target_options = option("items", "\u5546\u54c1", target) + option("orders", "\u8ba2\u5355", target) + option("sold", "\u5df2\u552e\u5546\u54c1", target)
        category_options = option("", "\u4e0d\u9650", field(params, "category")) + "".join(option(c, c, field(params, "category")) for c in CATEGORIES)
        status_options = option("", "\u4e0d\u9650", field(params, "status")) + option("0", "\u672a\u552e\u51fa", field(params, "status")) + option("1", "\u5df2\u552e\u51fa", field(params, "status"))
        return f"""
        <section class="panel">
          <h2>\u81ea\u5b9a\u4e49\u67e5\u8be2</h2>
          <form class="form form-grid" method="get" action="/queries">
            <input type="hidden" name="mode" value="custom">
            <label>\u67e5\u8be2\u5bf9\u8c61<select name="target">{target_options}</select></label>
            <label>\u5546\u54c1\u540d<input name="keyword" value="{escape(field(params, "keyword"))}"></label>
            <label>\u7c7b\u522b<select name="category">{category_options}</select></label>
            <label>\u72b6\u6001<select name="status">{status_options}</select></label>
            <label>\u6700\u4f4e\u4ef7<input name="min_price" type="number" step="0.01" value="{escape(field(params, "min_price"))}"></label>
            <label>\u6700\u9ad8\u4ef7<input name="max_price" type="number" step="0.01" value="{escape(field(params, "max_price"))}"></label>
            <label>\u5356\u5bb6\u7f16\u53f7<input name="seller_id" value="{escape(field(params, "seller_id"))}"></label>
            <label>\u4e70\u5bb6\u7f16\u53f7<input name="buyer_id" value="{escape(field(params, "buyer_id"))}"></label>
            <button type="submit">\u67e5\u8be2</button>
          </form>
        </section>"""

    def operations(self, _params, message: str) -> bytes:
        rows = query("SELECT item_id, item_name, category, price, CASE status WHEN 0 THEN '\u672a\u552e\u51fa' ELSE '\u5df2\u552e\u51fa' END AS status, seller_id FROM item ORDER BY item_id")
        users = query("SELECT user_id, user_name FROM user ORDER BY user_id")
        seller_options = "".join(option(r["user_id"], f'{r["user_id"]} - {r["user_name"]}', "u003") for r in users)
        category_options = "".join(option(c, c, "Electronics") for c in CATEGORIES)
        body = f"""
        <h1>\u6570\u636e\u64cd\u4f5c</h1>
        <section class="grid three">
          <form class="card form" method="post">
            <h3>\u65b0\u589e\u5546\u54c1</h3><input type="hidden" name="action" value="insert">
            <label>\u5546\u54c1\u7f16\u53f7<input name="item_id" value="i006" required></label>
            <label>\u5546\u54c1\u540d<input name="item_name" value="Keyboard" required></label>
            <label>\u7c7b\u522b<select name="category">{category_options}</select></label>
            <label>\u4ef7\u683c<input name="price" type="number" step="0.01" value="45" required></label>
            <label>\u72b6\u6001<select name="status"><option value="0">\u672a\u552e\u51fa</option><option value="1">\u5df2\u552e\u51fa</option></select></label>
            <label>\u5356\u5bb6<select name="seller_id">{seller_options}</select></label>
            <button type="submit">\u63d0\u4ea4\u65b0\u5546\u54c1</button>
          </form>
          <form class="card form" method="post">
            <h3>\u4fee\u6539\u4ef7\u683c</h3><input type="hidden" name="action" value="update">
            <label>\u5546\u54c1\u7f16\u53f7<input name="item_id" value="i003" required></label>
            <label>\u65b0\u4ef7\u683c<input name="price" type="number" step="0.01" value="88" required></label>
            <button type="submit">\u66f4\u65b0\u4ef7\u683c</button>
          </form>
          <form class="card form" method="post">
            <h3>\u5220\u9664\u5546\u54c1</h3><input type="hidden" name="action" value="delete">
            <label>\u5546\u54c1\u7f16\u53f7<input name="item_id" value="i005" required></label>
            <p>\u4ec5\u5141\u8bb8\u5220\u9664\u672a\u552e\u51fa\u5546\u54c1\u3002</p>
            <button type="submit">\u5220\u9664</button>
          </form>
        </section>
        <section class="panel"><h2>\u5f53\u524d\u5546\u54c1</h2>{table(rows)}</section>"""
        return page("\u6570\u636e\u64cd\u4f5c", body, message, "/operations")

    def handle_operation(self, data: dict) -> str:
        action = field(data, "action")
        if action == "insert":
            values = (
                field(data, "item_id"),
                field(data, "item_name"),
                field(data, "category"),
                float(field(data, "price")),
                int(field(data, "status", "0")),
                field(data, "seller_id"),
            )
            execute("INSERT INTO item (item_id, item_name, category, price, status, seller_id) VALUES (?, ?, ?, ?, ?, ?)", values)
            return "\u5546\u54c1\u5df2\u65b0\u589e\u3002"
        if action == "update":
            changed = execute("UPDATE item SET price = ? WHERE item_id = ?", (float(field(data, "price")), field(data, "item_id")))
            return "\u4ef7\u683c\u5df2\u66f4\u65b0\u3002" if changed else "\u672a\u627e\u5230\u8be5\u5546\u54c1\u3002"
        if action == "delete":
            changed = execute("DELETE FROM item WHERE item_id = ? AND status = 0", (field(data, "item_id"),))
            return "\u5546\u54c1\u5df2\u5220\u9664\u3002" if changed else "\u672a\u5220\u9664\uff1a\u5546\u54c1\u4e0d\u5b58\u5728\u6216\u5df2\u552e\u51fa\u3002"
        return "\u672a\u8bc6\u522b\u7684\u64cd\u4f5c\u3002"

    def purchase(self, _params, message: str) -> bytes:
        items = query("SELECT item_id, item_name, price, CASE status WHEN 0 THEN '\u53ef\u8d2d\u4e70' ELSE '\u5df2\u552e\u51fa' END AS status FROM item ORDER BY item_id")
        users = query("SELECT user_id, user_name FROM user ORDER BY user_id")
        item_options = "".join(option(r["item_id"], f'{r["item_id"]} - {r["item_name"]} - {r["status"]}') for r in items)
        user_options = "".join(option(r["user_id"], f'{r["user_id"]} - {r["user_name"]}') for r in users)
        body = f"""
        <h1>\u5546\u54c1\u8d2d\u4e70</h1>
        <section class="panel narrow">
          <form method="post" class="form">
            <label>\u5546\u54c1<select name="item_id">{item_options}</select></label>
            <label>\u4e70\u5bb6<select name="buyer_id">{user_options}</select></label>
            <label>\u8ba2\u5355\u65e5\u671f<input name="order_date" type="date" value="{date.today().isoformat()}"></label>
            <button type="submit">\u786e\u8ba4\u8d2d\u4e70</button>
          </form>
        </section>
        <section class="panel"><h2>\u5546\u54c1\u72b6\u6001</h2>{table(items)}</section>"""
        return page("\u8d2d\u4e70\u5546\u54c1", body, message, "/purchase")

    def handle_purchase(self, data: dict) -> str:
        item_id = field(data, "item_id")
        buyer_id = field(data, "buyer_id")
        order_date = field(data, "order_date", date.today().isoformat()) or date.today().isoformat()
        with get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            item = conn.execute("SELECT item_name, status FROM item WHERE item_id = ?", (item_id,)).fetchone()
            if item is None:
                conn.rollback()
                return "\u5546\u54c1\u4e0d\u5b58\u5728\u3002"
            if item["status"] != 0:
                conn.rollback()
                return f"{item['item_name']} \u5df2\u552e\u51fa\uff0c\u4e0d\u80fd\u91cd\u590d\u8d2d\u4e70\u3002"
            order_id = next_order_id()
            conn.execute("INSERT INTO orders (order_id, item_id, buyer_id, order_date) VALUES (?, ?, ?, ?)", (order_id, item_id, buyer_id, order_date))
            conn.commit()
        return f"\u8d2d\u4e70\u6210\u529f\uff0c\u8ba2\u5355 {order_id} \u5df2\u751f\u6210\u3002"

    def stats(self, _params, message: str) -> bytes:
        total = scalar("SELECT COUNT(*) FROM item")
        avg_price = scalar("SELECT ROUND(AVG(price), 2) FROM item")
        category_rows = query("SELECT category, COUNT(*) AS item_count FROM item GROUP BY category ORDER BY item_count DESC, category")
        top_user = query("SELECT u.user_id, u.user_name, COUNT(i.item_id) AS item_count FROM user u JOIN item i ON u.user_id = i.seller_id GROUP BY u.user_id, u.user_name ORDER BY item_count DESC, u.user_id LIMIT 1")
        sold_view = query("SELECT item_name, buyer_id FROM sold_item_view ORDER BY item_name")
        unsold_view = query("SELECT item_id, item_name, category, price, seller_id FROM unsold_item_view ORDER BY item_id")
        body = f"""
        <h1>\u7edf\u8ba1\u4e0e\u89c6\u56fe</h1>
        <section class="grid two">{card("\u5546\u54c1\u603b\u6570", str(total), "")}{card("\u5e73\u5747\u4ef7\u683c", str(avg_price), "")}</section>
        <section class="panel"><h2>\u5404\u7c7b\u5546\u54c1\u6570\u91cf</h2>{table(category_rows)}</section>
        <section class="panel"><h2>\u53d1\u5e03\u5546\u54c1\u6700\u591a\u7684\u7528\u6237</h2>{table(top_user)}</section>
        <section class="panel"><h2>\u5df2\u552e\u5546\u54c1\u89c6\u56fe</h2>{table(sold_view)}</section>
        <section class="panel"><h2>\u672a\u552e\u5546\u54c1\u89c6\u56fe</h2>{table(unsold_view)}</section>"""
        return page("\u7edf\u8ba1\u4e0e\u89c6\u56fe", body, message, "/stats")

    def report(self, _params, message: str) -> bytes:
        body = """
        <h1>\u5b89\u5168\u4e0e\u6062\u590d</h1>
        <section class="panel"><h2>\u6570\u636e\u5220\u9664\u63a7\u5236</h2><p>\u666e\u901a\u7528\u6237\u4ec5\u5f00\u653e\u6d4f\u89c8\u3001\u67e5\u8be2\u548c\u8d2d\u4e70\u6743\u9650\uff0c\u5220\u9664\u6570\u636e\u5e94\u7531\u7ba1\u7406\u5458\u8d26\u53f7\u6267\u884c\uff0c\u5e76\u5728\u6570\u636e\u5e93\u5c42\u9650\u5236 DELETE \u6743\u9650\u3002</p></section>
        <section class="panel"><h2>\u53ea\u8bfb\u67e5\u8be2\u6743\u9650</h2><p>\u53ef\u4ee5\u4f7f\u7528\u53ea\u8bfb\u8fde\u63a5\u6216\u53ea\u8bfb\u8d26\u53f7\uff0c\u5e94\u7528\u5c42\u4ec5\u63d0\u4f9b\u67e5\u8be2\u8def\u7531\uff0c\u4e0d\u66b4\u9732\u65b0\u589e\u3001\u4fee\u6539\u3001\u5220\u9664\u63a5\u53e3\u3002</p></section>
        <section class="panel"><h2>\u5e76\u53d1\u8d2d\u4e70</h2><p>\u4e24\u4e2a\u7528\u6237\u540c\u65f6\u8d2d\u4e70\u540c\u4e00\u5546\u54c1\u65f6\u53ef\u80fd\u51fa\u73b0\u91cd\u590d\u4e0b\u5355\u3002\u7cfb\u7edf\u901a\u8fc7\u4e8b\u52a1\u3001\u5546\u54c1\u72b6\u6001\u68c0\u67e5\u548c orders.item_id \u552f\u4e00\u7ea6\u675f\u9632\u6b62\u91cd\u590d\u4ea4\u6613\u3002</p></section>
        <section class="panel"><h2>\u6545\u969c\u6062\u590d</h2><p>\u8ba2\u5355\u63d2\u5165\u548c\u5546\u54c1\u72b6\u6001\u66f4\u65b0\u653e\u5728\u540c\u4e00\u4e8b\u52a1\u4e2d\uff0c\u672a\u63d0\u4ea4\u65f6\u5d29\u6e83\u4f1a\u56de\u6eda\uff0c\u5df2\u63d0\u4ea4\u6570\u636e\u4f1a\u4fdd\u5b58\u5728\u6570\u636e\u5e93\u6587\u4ef6\u4e2d\u3002</p></section>"""
        return page("\u5b89\u5168\u4e0e\u6062\u590d", body, message, "/report")

    def log_message(self, _format: str, *_args) -> None:
        return


def main() -> None:
    if not DB_PATH.exists():
        init_database()
    server = ThreadingHTTPServer((HOST, PORT), CampusHandler)
    print(f"Campus secondhand system running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
