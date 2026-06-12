#!/usr/bin/env python3
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import time
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "hengqu.db"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "4173"))
SESSION_TTL = 7 * 24 * 60 * 60


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000)
    return salt, digest.hex()


def verify_password(password, salt, expected):
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected)


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE COLLATE NOCASE,
              phone TEXT NOT NULL DEFAULT '',
              password_hash TEXT NOT NULL,
              password_salt TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              expires_at INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS products (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              category TEXT NOT NULL,
              instrument TEXT NOT NULL DEFAULT '',
              image TEXT NOT NULL DEFAULT '',
              tested_count INTEGER NOT NULL DEFAULT 0,
              turnaround TEXT NOT NULL DEFAULT '',
              satisfaction TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              featured INTEGER NOT NULL DEFAULT 1,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reservations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_no TEXT NOT NULL UNIQUE,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              product_id INTEGER NOT NULL REFERENCES products(id),
              contact_name TEXT NOT NULL,
              phone TEXT NOT NULL,
              organization TEXT NOT NULL DEFAULT '',
              sample_info TEXT NOT NULL,
              requirements TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT '待确认',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS demands (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              demand_no TEXT NOT NULL UNIQUE,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              title TEXT NOT NULL,
              category TEXT NOT NULL,
              budget TEXT NOT NULL DEFAULT '',
              contact_name TEXT NOT NULL,
              phone TEXT NOT NULL,
              details TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT '待联系',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS inquiries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              name TEXT NOT NULL,
              phone TEXT NOT NULL,
              message TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT '未处理',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_products_title ON products(title);
            CREATE INDEX IF NOT EXISTS idx_reservations_user ON reservations(user_id);
            CREATE INDEX IF NOT EXISTS idx_demands_user ON demands(user_id);
            """
        )
        if connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            products = [
                ("电感耦合等离子体光谱/质谱 ICP-OES/MS", "材料测试", "PlasmaMS 300", "assets/product-1.jpg", 25641, "3-5", "93.2%", "适用于多元素定性定量分析。"),
                ("X射线光电子能谱仪（XPS）", "材料测试", "Thermo Kalpha / ESCALAB", "assets/product-2.png", 24830, "3-5", "96.2%", "提供全谱、精细谱、价带谱等分析服务。"),
                ("单晶X射线衍射仪（SC-XRD）", "材料测试", "Bruker smart Apex", "assets/product-3.png", 28654, "3-5", "96.5%", "用于晶体结构解析与分子构型分析。"),
                ("电子顺磁/自旋共振（EPR/ESR）", "材料测试", "Bruker EMXplus / A300", "assets/product-4.png", 36561, "2-4", "93.5%", "分析含未成对电子的顺磁性物质。"),
                ("等温滴定量热仪（ITC）", "生物服务", "TA NANO ITC / iTC200", "assets/product-5.jpg", 2654, "3-6", "100%", "用于分子相互作用热力学参数测定。"),
            ]
            connection.executemany(
                """INSERT INTO products
                (title, category, instrument, image, tested_count, turnaround, satisfaction, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                products,
            )
        admin = connection.execute(
            "SELECT id FROM users WHERE email = ?", ("admin@hengqu.local",)
        ).fetchone()
        if not admin:
            salt, digest = hash_password(os.environ.get("ADMIN_PASSWORD", "Admin123!"))
            connection.execute(
                """INSERT INTO users
                (name, email, phone, password_hash, password_salt, role)
                VALUES (?, ?, ?, ?, ?, 'admin')""",
                ("系统管理员", "admin@hengqu.local", "029-88186855", digest, salt),
            )


def row_dict(row):
    return dict(row) if row else None


class Handler(SimpleHTTPRequestHandler):
    server_version = "HengquServer/1.0"

    def log_message(self, format_string, *args):
        print("[%s] %s" % (self.log_date_time_string(), format_string % args))

    def send_json(self, status, payload, extra_headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024 * 1024:
                raise ValueError("请求内容过大")
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            raise ValueError("请求格式不正确")

    def session_user(self):
        raw_cookie = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        jar.load(raw_cookie)
        token = jar.get("hq_session")
        if not token:
            return None
        now = int(time.time())
        with db() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            return connection.execute(
                """SELECT users.id, users.name, users.email, users.phone, users.role
                FROM sessions JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ? AND sessions.expires_at > ?""",
                (token.value, now),
            ).fetchone()

    def require_user(self, admin=False):
        user = self.session_user()
        if not user:
            self.send_json(401, {"error": "请先登录"})
            return None
        if admin and user["role"] != "admin":
            self.send_json(403, {"error": "没有管理权限"})
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            return self.api_get(parsed.path, parse_qs(parsed.query))
        if parsed.path == "/admin":
            self.path = "/admin.html"
        elif parsed.path == "/account":
            self.path = "/account.html"
        elif parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self.send_json(404, {"error": "接口不存在"})
        try:
            payload = self.read_json()
            return self.api_post(parsed.path, payload)
        except ValueError as error:
            return self.send_json(400, {"error": str(error)})
        except sqlite3.IntegrityError:
            return self.send_json(409, {"error": "数据冲突，请检查后重试"})
        except Exception as error:
            print("Unhandled error:", repr(error))
            return self.send_json(500, {"error": "服务器处理失败"})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            return self.api_patch(parsed.path, payload)
        except ValueError as error:
            return self.send_json(400, {"error": str(error)})
        except Exception as error:
            print("Unhandled error:", repr(error))
            return self.send_json(500, {"error": "服务器处理失败"})

    def api_get(self, path, query):
        if path == "/api/health":
            return self.send_json(200, {"ok": True, "database": str(DB_PATH.name)})
        if path == "/api/me":
            return self.send_json(200, {"user": row_dict(self.session_user())})
        if path == "/api/products":
            keyword = query.get("q", [""])[0].strip()
            category = query.get("category", [""])[0].strip()
            sql = "SELECT * FROM products WHERE active = 1"
            params = []
            if keyword:
                sql += " AND (title LIKE ? OR instrument LIKE ? OR description LIKE ?)"
                like = f"%{keyword}%"
                params.extend([like, like, like])
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY featured DESC, id ASC LIMIT 50"
            with db() as connection:
                items = [dict(row) for row in connection.execute(sql, params)]
            return self.send_json(200, {"items": items})
        if path == "/api/my/orders":
            user = self.require_user()
            if not user:
                return
            with db() as connection:
                reservations = [
                    dict(row)
                    for row in connection.execute(
                        """SELECT reservations.*, products.title AS product_title
                        FROM reservations JOIN products ON products.id = reservations.product_id
                        WHERE reservations.user_id = ? ORDER BY reservations.id DESC""",
                        (user["id"],),
                    )
                ]
                demands = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM demands WHERE user_id = ? ORDER BY id DESC",
                        (user["id"],),
                    )
                ]
            return self.send_json(200, {"reservations": reservations, "demands": demands})
        if path == "/api/admin/summary":
            user = self.require_user(admin=True)
            if not user:
                return
            with db() as connection:
                counts = {
                    name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                    for name in ("users", "products", "reservations", "demands", "inquiries")
                }
            return self.send_json(200, counts)
        if path == "/api/admin/orders":
            user = self.require_user(admin=True)
            if not user:
                return
            with db() as connection:
                reservations = [
                    dict(row)
                    for row in connection.execute(
                        """SELECT reservations.*, products.title AS product_title,
                        COALESCE(users.email, '') AS user_email
                        FROM reservations JOIN products ON products.id = reservations.product_id
                        LEFT JOIN users ON users.id = reservations.user_id
                        ORDER BY reservations.id DESC LIMIT 100"""
                    )
                ]
                demands = [
                    dict(row)
                    for row in connection.execute(
                        """SELECT demands.*, COALESCE(users.email, '') AS user_email
                        FROM demands LEFT JOIN users ON users.id = demands.user_id
                        ORDER BY demands.id DESC LIMIT 100"""
                    )
                ]
                inquiries = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM inquiries ORDER BY id DESC LIMIT 100"
                    )
                ]
            return self.send_json(
                200,
                {"reservations": reservations, "demands": demands, "inquiries": inquiries},
            )
        return self.send_json(404, {"error": "接口不存在"})

    def api_post(self, path, data):
        if path == "/api/register":
            name = str(data.get("name", "")).strip()
            email = str(data.get("email", "")).strip().lower()
            phone = str(data.get("phone", "")).strip()
            password = str(data.get("password", ""))
            if not name or "@" not in email or len(password) < 8:
                return self.send_json(400, {"error": "请填写姓名、有效邮箱和至少8位密码"})
            salt, digest = hash_password(password)
            with db() as connection:
                cursor = connection.execute(
                    """INSERT INTO users
                    (name, email, phone, password_hash, password_salt)
                    VALUES (?, ?, ?, ?, ?)""",
                    (name, email, phone, digest, salt),
                )
                user_id = cursor.lastrowid
            return self.create_session(user_id)
        if path == "/api/login":
            email = str(data.get("email", "")).strip().lower()
            password = str(data.get("password", ""))
            with db() as connection:
                user = connection.execute(
                    "SELECT * FROM users WHERE email = ?", (email,)
                ).fetchone()
            if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
                return self.send_json(401, {"error": "邮箱或密码错误"})
            return self.create_session(user["id"])
        if path == "/api/logout":
            jar = cookies.SimpleCookie()
            jar.load(self.headers.get("Cookie", ""))
            token = jar.get("hq_session")
            if token:
                with db() as connection:
                    connection.execute("DELETE FROM sessions WHERE token = ?", (token.value,))
            return self.send_json(
                200,
                {"ok": True},
                {"Set-Cookie": "hq_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"},
            )
        if path == "/api/reservations":
            user = self.require_user()
            if not user:
                return
            required = ("product_id", "contact_name", "phone", "sample_info")
            if any(not str(data.get(key, "")).strip() for key in required):
                return self.send_json(400, {"error": "请完整填写预约信息"})
            order_no = "HQ" + time.strftime("%Y%m%d") + secrets.token_hex(3).upper()
            with db() as connection:
                connection.execute(
                    """INSERT INTO reservations
                    (order_no, user_id, product_id, contact_name, phone, organization,
                    sample_info, requirements) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order_no,
                        user["id"],
                        int(data["product_id"]),
                        str(data["contact_name"]).strip(),
                        str(data["phone"]).strip(),
                        str(data.get("organization", "")).strip(),
                        str(data["sample_info"]).strip(),
                        str(data.get("requirements", "")).strip(),
                    ),
                )
            return self.send_json(201, {"ok": True, "order_no": order_no})
        if path == "/api/demands":
            user = self.require_user()
            if not user:
                return
            required = ("title", "category", "contact_name", "phone", "details")
            if any(not str(data.get(key, "")).strip() for key in required):
                return self.send_json(400, {"error": "请完整填写需求信息"})
            demand_no = "XQ" + time.strftime("%Y%m%d") + secrets.token_hex(3).upper()
            with db() as connection:
                connection.execute(
                    """INSERT INTO demands
                    (demand_no, user_id, title, category, budget, contact_name, phone, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        demand_no,
                        user["id"],
                        str(data["title"]).strip(),
                        str(data["category"]).strip(),
                        str(data.get("budget", "")).strip(),
                        str(data["contact_name"]).strip(),
                        str(data["phone"]).strip(),
                        str(data["details"]).strip(),
                    ),
                )
            return self.send_json(201, {"ok": True, "demand_no": demand_no})
        if path == "/api/inquiries":
            required = ("name", "phone", "message")
            if any(not str(data.get(key, "")).strip() for key in required):
                return self.send_json(400, {"error": "请完整填写咨询信息"})
            user = self.session_user()
            with db() as connection:
                connection.execute(
                    "INSERT INTO inquiries (user_id, name, phone, message) VALUES (?, ?, ?, ?)",
                    (
                        user["id"] if user else None,
                        str(data["name"]).strip(),
                        str(data["phone"]).strip(),
                        str(data["message"]).strip(),
                    ),
                )
            return self.send_json(201, {"ok": True})
        return self.send_json(404, {"error": "接口不存在"})

    def api_patch(self, path, data):
        user = self.require_user(admin=True)
        if not user:
            return
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[:2] != ["api", "admin"]:
            return self.send_json(404, {"error": "接口不存在"})
        resource, item_id = parts[2], parts[3]
        tables = {"reservations": "reservations", "demands": "demands", "inquiries": "inquiries"}
        if resource not in tables or not item_id.isdigit():
            return self.send_json(404, {"error": "资源不存在"})
        status = str(data.get("status", "")).strip()
        if not status or len(status) > 30:
            return self.send_json(400, {"error": "状态不正确"})
        with db() as connection:
            cursor = connection.execute(
                f"UPDATE {tables[resource]} SET status = ? WHERE id = ?",
                (status, int(item_id)),
            )
        if cursor.rowcount == 0:
            return self.send_json(404, {"error": "记录不存在"})
        return self.send_json(200, {"ok": True})

    def create_session(self, user_id):
        token = secrets.token_urlsafe(32)
        expires_at = int(time.time()) + SESSION_TTL
        with db() as connection:
            connection.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token, user_id, expires_at),
            )
            user = connection.execute(
                "SELECT id, name, email, phone, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        cookie = (
            f"hq_session={token}; Path=/; Max-Age={SESSION_TTL}; "
            "HttpOnly; SameSite=Lax"
        )
        return self.send_json(200, {"user": dict(user)}, {"Set-Cookie": cookie})


if __name__ == "__main__":
    mimetypes.add_type("application/javascript", ".js")
    init_db()
    os.chdir(ROOT)
    print(f"横渠网已启动：http://{HOST}:{PORT}")
    print("管理员：admin@hengqu.local / Admin123!（可通过 ADMIN_PASSWORD 修改）")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
