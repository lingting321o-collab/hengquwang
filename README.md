# 横渠科研服务平台

这是一个使用 Python 标准库和 SQLite 构建的全栈网站，无需安装第三方依赖。

## 启动

```bash
python3 server.py
```

打开 `http://127.0.0.1:4173`。

默认后台账号：

- 邮箱：`admin@hengqu.local`
- 密码：`Admin123!`

正式部署前请通过环境变量修改管理员密码：

```bash
ADMIN_PASSWORD='新的强密码' python3 server.py
```

数据库首次启动时自动创建在 `data/hengqu.db`。

## 页面

- `/`：网站首页
- `/account`：用户订单和需求
- `/admin`：后台管理

## 主要接口

- `GET /api/products`
- `POST /api/register`
- `POST /api/login`
- `POST /api/reservations`
- `POST /api/demands`
- `POST /api/inquiries`
- `GET /api/my/orders`
- `GET /api/admin/orders`
