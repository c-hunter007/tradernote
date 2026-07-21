# TradeNote

A股跟踪记录应用，面向个人或小型团队：用户可以记录自己发掘的具备跟踪价值的 A 股股票。

## 技术栈

- Python 3.10+
- Streamlit（多页应用）
- SQLAlchemy 2.x（ORM）
- SQLite（WAL 模式）
- bcrypt（密码哈希）
- akshare（A 股代码 → 名称映射）
- 本地文件系统存储图片

## 目录结构

```
tradernote/
├── app.py                      # 入口：登录页 + 会话管理
├── requirements.txt
├── .env.example
├── config.py                   # 配置加载（dotenv）
├── README.md                   # 本文件
├── scripts/
│   └── init_admin.py           # 交互式创建首个管理员 / 重置密码
├── database/
│   ├── models.py               # ORM 模型
│   ├── db.py                   # engine + session
│   └── init_db.py              # 建表
├── auth/
│   ├── session.py              # session 管理（cookie 持久化）
│   └── password.py             # bcrypt 工具
├── services/
│   ├── user_service.py
│   ├── pool_service.py          # 股票池 CRUD + 成员管理
│   ├── stock_service.py         # 股票增删 + 关键关注
│   ├── analysis_service.py      # 分析笔记 + 图片管理 + 评论
│   ├── activity_service.py      # 活动日志
│   ├── akshare_service.py       # A 股代码查询
│   └── feishu_service.py        # 飞书机器人通知
├── pages/                       # Streamlit 多页应用
│   ├── 0_📊_仪表盘.py           # 登录页 + 仪表盘
│   ├── 0_🛡️_管理后台.py
│   ├── 0_🔧_系统初始化.py       # 首次部署初始化（隐藏页）
│   ├── 1_📈_我的股票池.py
│   ├── 2_👥_共享池成员.py
│   ├── 3_🔍_股票池详情.py
│   ├── 4_📝_股票分析.py
│   ├── 5_♻️_复盘归档.py
│   └── 9_🚧_交易记录.py         # 占位（后期开发）
├── utils/
│   ├── ui.py                   # 卡片样式、空状态、消息提示
│   ├── page.py                 # 页面通用辅助
│   └── date_util.py
├── data/                       # SQLite 数据库（gitignore）
└── uploads/                    # 图片本地存储（gitignore）
```

## 快速开始

### 1. 创建并激活虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

### 4. 启动应用

```bash
streamlit run app.py --server.port=8501 --server.address=127.0.0.1
```

浏览器访问 `http://127.0.0.1:8501`。

### 5. 初始化系统

首次访问时，登录页会自动检测系统状态，显示「🔧 初始化系统」入口。点击进入后：

1. 自动创建数据库表
2. 填写管理员用户名和密码
3. 提交后自动登录并跳转仪表盘

也可通过命令行初始化：

```bash
python -m scripts.init_admin
```

### 6. 重置管理员密码（如需）

```bash
python -m scripts.init_admin --reset-password <用户名>
```

## 功能说明

| 模块 | 说明 |
|---|---|
| 系统初始化 | 首次部署时通过 Web 页面创建数据库表和管理员账号，仅可执行一次 |
| 用户体系 | 仅管理员预创建账号；无自助注册；支持启用/禁用、角色升降 |
| 股票池 | 自定义名称；私有 / 共享两种；共享池支持成员协作 |
| 股票纳入 | 输入 6 位代码，akshare 自动补全名称（仅新增时调用一次） |
| 持续跟踪 | 添加分析结论 + 多张配图（单次最多 5 张，单张 ≤ 3MB） |
| 重点关注 | 自动顶置 + 金色背景醒目样式 |
| 移出复盘 | 填写移出原因后从池中移除，可在「复盘归档」页查看历史 |
| 图片预览 | 卡片内全宽展示，支持 Streamlit 内置 Fullscreen 查看原图 |
| 评论系统 | 池成员可对分析笔记进行点评 |
| 飞书通知 | 配置 Webhook 后，池内操作自动推送飞书消息卡片 |
| 活动日志 | 记录所有用户操作，仪表盘展示近期活动 |
| 交易记录 | 后期开发，目前仅占位页 |

## 部署说明（Nginx HTTPS 反向代理）

生产环境推荐使用 Nginx 反向代理 + HTTPS。

### 1. 启动 Streamlit 仅本地监听

```bash
# 在虚拟环境内运行
streamlit run app.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --server.enableWebsocketCompression=false
```

或使用 systemd 服务（见下文）。

### 2. 安装 Nginx

```bash
sudo apt install -y nginx
```

### 3. 生成 SSL 证书

**测试环境**（自签证书）：

```bash
sudo openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout /etc/ssl/private/tradernote.key \
    -out /etc/ssl/certs/tradernote.crt \
    -subj "/C=CN/ST=Local/L=Local/O=TradeNote/CN=tradernote.local"
```

**生产环境**（推荐 Let's Encrypt + certbot）：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tradernote.example.com
```

### 4. 配置 Nginx

将以下内容写入 `/etc/nginx/sites-available/tradernote`：

```nginx
server {
    listen 80;
    server_name tradernote.example.com;
    # 强制重定向到 HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name tradernote.example.com;

    # SSL 证书
    ssl_certificate     /etc/ssl/certs/tradernote.crt;
    ssl_certificate_key /etc/ssl/private/tradernote.key;

    # 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH';
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 反向代理到 Streamlit
    location / {
        proxy_pass http://127.0.0.1:8501;

        # WebSocket 支持（Streamlit 必需）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 超时（Streamlit 长连接）
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # 上传文件大小限制（图片 + 其他）
    client_max_body_size 10M;
}
```

### 5. 启用并重载 Nginx

```bash
sudo ln -s /etc/nginx/sites-available/tradernote /etc/nginx/sites-enabled/
sudo nginx -t           # 校验配置
sudo systemctl reload nginx
```

### 6. （可选）systemd 服务

创建 `/etc/systemd/system/tradernote.service`：

```ini
[Unit]
Description=TradeNote Streamlit App
After=network.target

[Service]
Type=simple
User=hunter
WorkingDirectory=/home/hunter/tradernote
Environment="PATH=/home/hunter/tradernote/.venv/bin:/usr/bin:/bin"
ExecStart=/home/hunter/tradernote/.venv/bin/streamlit run app.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --server.enableWebsocketCompression=false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tradernote
sudo systemctl status tradernote
```

### 7. 部署清单

- [ ] 创建虚拟环境并安装依赖
- [ ] 复制 `.env.example` 为 `.env`
- [ ] 启动应用，访问后通过 Web 页面初始化系统（或命令行 `python -m scripts.init_admin`）
- [ ] 配置 Nginx HTTPS 反向代理
- [ ] 配置 systemd 服务（可选）
- [ ] 配置防火墙：仅允许 80/443 端口，禁止 8501 直接访问外网

## 服务层权限契约

本项目的服务层（`services/*.py`）**信任调用方（UI 层）已校验访问权限**，service 函数本身不再重复校验 `can_access_pool` 等权限。例外：

- `set_key_focus()` / `remove_stock_from_pool()` 在服务层复检 `can_access_pool`（防御纵深，因这两个操作改动状态较敏感）

**UI 层（pages/*.py）必须在调用 service 前完成以下校验**：

| 服务函数 | UI 层必须校验 |
|---|---|
| `add_member` / `remove_member` | 调用者为该共享池的 owner |
| `create_note` | 调用者对该池有 `can_access_pool` 权限 |
| `list_removed_pool_stocks` | 调用者对该池有 `can_access_pool` 权限 |
| `list_recent_notes_for_user` / `count_*_for_user` | 仅按 user_id 过滤，无需额外校验 |

未来如需更严格的防御纵深，可在各 service 函数顶部补充 `can_access_pool` 复检。

## 安全建议

- `.env` 文件务必妥善保管，不要提交到版本控制
- `data/` 与 `uploads/` 目录已加入 `.gitignore`，请勿提交
- 定期备份 `data/tradernote.db` 与 `uploads/` 目录
- 如需公网部署，务必使用 HTTPS（推荐 Let's Encrypt）
