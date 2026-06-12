import hashlib
import hmac
import os
import secrets
import time
from contextlib import contextmanager

import psycopg
from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from psycopg.rows import dict_row

app = FastAPI(title="Hengqu API")
SESSION_TTL = 7 * 24 * 60 * 60
SCHEMA_READY = False

PRODUCTS = [
    ("电感耦合等离子体光谱/质谱 ICP-OES/MS", "材料测试", "PlasmaMS 300", "assets/product-1.jpg", 25641, "3-5", "93.2%", "适用于多元素定性定量分析。"),
    ("X射线光电子能谱仪（XPS）", "材料测试", "Thermo Kalpha / ESCALAB", "assets/product-2.png", 24830, "3-5", "96.2%", "提供全谱、精细谱、价带谱等分析服务。"),
    ("单晶X射线衍射仪（SC-XRD）", "材料测试", "Bruker smart Apex", "assets/product-3.png", 28654, "3-5", "96.5%", "用于晶体结构解析与分子构型分析。"),
    ("电子顺磁/自旋共振（EPR/ESR）", "材料测试", "Bruker EMXplus / A300", "assets/product-4.png", 36561, "2-4", "93.5%", "分析含未成对电子的顺磁性物质。"),
    ("等温滴定量热仪（ITC）", "生物服务", "TA NANO ITC / iTC200", "assets/product-5.jpg", 2654, "3-6", "100%", "用于分子相互作用热力学参数测定。"),
]


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000)
    return salt, digest.hex()


@contextmanager
def database():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise HTTPException(503, "线上数据库尚未连接")
    with psycopg.connect(url, row_factory=dict_row) as connection:
        ensure_schema(connection)
        yield connection


def ensure_schema(connection):
    global SCHEMA_READY
    if SCHEMA_READY:
        return
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE, phone TEXT NOT NULL DEFAULT '',
          password_hash TEXT NOT NULL, password_salt TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'user', created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          expires_at BIGINT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS products (
          id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
          instrument TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
          tested_count INTEGER NOT NULL DEFAULT 0, turnaround TEXT NOT NULL DEFAULT '',
          satisfaction TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
          featured INTEGER NOT NULL DEFAULT 1, active INTEGER NOT NULL DEFAULT 1,
          created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS reservations (
          id BIGSERIAL PRIMARY KEY, order_no TEXT NOT NULL UNIQUE,
          user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
          product_id BIGINT NOT NULL REFERENCES products(id),
          contact_name TEXT NOT NULL, phone TEXT NOT NULL, organization TEXT NOT NULL DEFAULT '',
          sample_info TEXT NOT NULL, requirements TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT '待确认', created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS demands (
          id BIGSERIAL PRIMARY KEY, demand_no TEXT NOT NULL UNIQUE,
          user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
          title TEXT NOT NULL, category TEXT NOT NULL, budget TEXT NOT NULL DEFAULT '',
          contact_name TEXT NOT NULL, phone TEXT NOT NULL, details TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT '待联系', created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS inquiries (
          id BIGSERIAL PRIMARY KEY, user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
          name TEXT NOT NULL, phone TEXT NOT NULL, message TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT '未处理', created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    if connection.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"] == 0:
        connection.executemany("""INSERT INTO products
            (title, category, instrument, image, tested_count, turnaround, satisfaction, description)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", PRODUCTS)
    email = os.environ.get("ADMIN_EMAIL", "admin@hengqu.local").lower()
    if not connection.execute("SELECT id FROM users WHERE email=%s", (email,)).fetchone():
        salt, digest = password_hash(os.environ.get("ADMIN_PASSWORD", "Admin123!"))
        connection.execute("""INSERT INTO users(name,email,phone,password_hash,password_salt,role)
            VALUES(%s,%s,%s,%s,%s,'admin')""", ("系统管理员", email, "029-88186855", digest, salt))
    connection.commit()
    SCHEMA_READY = True


def current_user(token):
    if not token:
        return None
    with database() as connection:
        return connection.execute("""SELECT users.id,users.name,users.email,users.phone,users.role
            FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE sessions.token=%s AND sessions.expires_at>%s""", (token, int(time.time()))).fetchone()


def require_user(token, admin=False):
    user = current_user(token)
    if not user:
        raise HTTPException(401, "请先登录")
    if admin and user["role"] != "admin":
        raise HTTPException(403, "没有管理权限")
    return user


def required(data, names):
    if any(not str(data.get(name, "")).strip() for name in names):
        raise HTTPException(400, "请完整填写信息")


@app.get("/health")
def health():
    return {"ok": True, "database": bool(os.environ.get("DATABASE_URL"))}


@app.get("/me")
def me(hq_session: str | None = Cookie(default=None)):
    return {"user": current_user(hq_session)}


@app.get("/products")
def products(q: str = "", category: str = ""):
    with database() as connection:
        sql = "SELECT * FROM products WHERE active=1"
        params = []
        if q.strip():
            sql += " AND (title ILIKE %s OR instrument ILIKE %s OR description ILIKE %s)"
            params.extend([f"%{q.strip()}%"] * 3)
        if category.strip():
            sql += " AND category=%s"
            params.append(category.strip())
        return {"items": connection.execute(sql + " ORDER BY featured DESC,id LIMIT 50", params).fetchall()}


@app.post("/register")
async def register(request: Request, response: Response):
    data = await request.json()
    required(data, ("name", "email", "password"))
    if "@" not in data["email"] or len(data["password"]) < 8:
        raise HTTPException(400, "请填写有效邮箱和至少8位密码")
    salt, digest = password_hash(data["password"])
    try:
        with database() as connection:
            user = connection.execute("""INSERT INTO users(name,email,phone,password_hash,password_salt)
                VALUES(%s,%s,%s,%s,%s) RETURNING id,name,email,phone,role""",
                (data["name"].strip(), data["email"].strip().lower(), data.get("phone", "").strip(), digest, salt)).fetchone()
            connection.commit()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "该邮箱已注册")
    create_session(user, response)
    return {"user": user}


@app.post("/login")
async def login(request: Request, response: Response):
    data = await request.json()
    with database() as connection:
        user = connection.execute("SELECT * FROM users WHERE email=%s", (data.get("email", "").strip().lower(),)).fetchone()
    if not user:
        raise HTTPException(401, "邮箱或密码错误")
    _, digest = password_hash(data.get("password", ""), user["password_salt"])
    if not hmac.compare_digest(digest, user["password_hash"]):
        raise HTTPException(401, "邮箱或密码错误")
    public_user = {key: user[key] for key in ("id", "name", "email", "phone", "role")}
    create_session(public_user, response)
    return {"user": public_user}


def create_session(user, response):
    token = secrets.token_urlsafe(32)
    with database() as connection:
        connection.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(%s,%s,%s)",
            (token, user["id"], int(time.time()) + SESSION_TTL))
        connection.commit()
    response.set_cookie("hq_session", token, max_age=SESSION_TTL, httponly=True, samesite="lax", secure=True)


@app.post("/logout")
def logout(response: Response, hq_session: str | None = Cookie(default=None)):
    if hq_session:
        with database() as connection:
            connection.execute("DELETE FROM sessions WHERE token=%s", (hq_session,))
            connection.commit()
    response.delete_cookie("hq_session")
    return {"ok": True}


@app.post("/reservations")
async def reservation(request: Request, hq_session: str | None = Cookie(default=None)):
    user = require_user(hq_session)
    data = await request.json()
    required(data, ("product_id", "contact_name", "phone", "sample_info"))
    order_no = "HQ" + time.strftime("%Y%m%d") + secrets.token_hex(3).upper()
    with database() as connection:
        connection.execute("""INSERT INTO reservations(order_no,user_id,product_id,contact_name,phone,organization,sample_info,requirements)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (order_no, user["id"], int(data["product_id"]), data["contact_name"], data["phone"], data.get("organization", ""), data["sample_info"], data.get("requirements", "")))
        connection.commit()
    return {"ok": True, "order_no": order_no}


@app.post("/demands")
async def demand(request: Request, hq_session: str | None = Cookie(default=None)):
    user = require_user(hq_session)
    data = await request.json()
    required(data, ("title", "category", "contact_name", "phone", "details"))
    demand_no = "XQ" + time.strftime("%Y%m%d") + secrets.token_hex(3).upper()
    with database() as connection:
        connection.execute("""INSERT INTO demands(demand_no,user_id,title,category,budget,contact_name,phone,details)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (demand_no, user["id"], data["title"], data["category"], data.get("budget", ""), data["contact_name"], data["phone"], data["details"]))
        connection.commit()
    return {"ok": True, "demand_no": demand_no}


@app.post("/inquiries")
async def inquiry(request: Request, hq_session: str | None = Cookie(default=None)):
    data = await request.json()
    required(data, ("name", "phone", "message"))
    user = current_user(hq_session)
    with database() as connection:
        connection.execute("INSERT INTO inquiries(user_id,name,phone,message) VALUES(%s,%s,%s,%s)",
            (user["id"] if user else None, data["name"], data["phone"], data["message"]))
        connection.commit()
    return {"ok": True}


@app.get("/my/orders")
def my_orders(hq_session: str | None = Cookie(default=None)):
    user = require_user(hq_session)
    with database() as connection:
        reservations = connection.execute("""SELECT reservations.*,products.title AS product_title FROM reservations
            JOIN products ON products.id=reservations.product_id WHERE user_id=%s ORDER BY reservations.id DESC""", (user["id"],)).fetchall()
        demands = connection.execute("SELECT * FROM demands WHERE user_id=%s ORDER BY id DESC", (user["id"],)).fetchall()
    return {"reservations": reservations, "demands": demands}


@app.get("/admin/summary")
def admin_summary(hq_session: str | None = Cookie(default=None)):
    require_user(hq_session, True)
    with database() as connection:
        return {table: connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in ("users", "products", "reservations", "demands", "inquiries")}


@app.get("/admin/orders")
def admin_orders(hq_session: str | None = Cookie(default=None)):
    require_user(hq_session, True)
    with database() as connection:
        reservations = connection.execute("""SELECT reservations.*,products.title AS product_title,COALESCE(users.email,'') AS user_email
            FROM reservations JOIN products ON products.id=reservations.product_id
            LEFT JOIN users ON users.id=reservations.user_id ORDER BY reservations.id DESC LIMIT 100""").fetchall()
        demands = connection.execute("""SELECT demands.*,COALESCE(users.email,'') AS user_email FROM demands
            LEFT JOIN users ON users.id=demands.user_id ORDER BY demands.id DESC LIMIT 100""").fetchall()
        inquiries = connection.execute("SELECT * FROM inquiries ORDER BY id DESC LIMIT 100").fetchall()
    return {"reservations": reservations, "demands": demands, "inquiries": inquiries}


@app.patch("/admin/{resource}/{item_id}")
async def update_status(resource: str, item_id: int, request: Request, hq_session: str | None = Cookie(default=None)):
    require_user(hq_session, True)
    tables = {"reservations": "reservations", "demands": "demands", "inquiries": "inquiries"}
    if resource not in tables:
        raise HTTPException(404, "资源不存在")
    status = str((await request.json()).get("status", "")).strip()
    if not status:
        raise HTTPException(400, "状态不正确")
    with database() as connection:
        connection.execute(f"UPDATE {tables[resource]} SET status=%s WHERE id=%s", (status, item_id))
        connection.commit()
    return {"ok": True}
