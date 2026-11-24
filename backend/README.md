# AI Creation Club 作品平台后端

后端提供登录、管理员发放和回收账号、整件作品投稿与审核、作品级展示与下载控制，以及 PPT/PPTX 和视频预览接入。业务规则见 [后端设计](DESIGN.md)。

## 本地启动

从项目的 backend 目录运行以下 PowerShell 命令。Python 需要 3.11 或以上版本。

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ENTRYSTAGE_DEBUG = "1"
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_admin
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
~~~

首次执行 bootstrap_admin 时，为初始管理员设置密码。默认用户名为 admin，可通过 --username 指定。自动化部署可用 ENTRYSTAGE_ADMIN_USERNAME、ENTRYSTAGE_ADMIN_PASSWORD 与 --no-input。重复运行时会保留已存在的管理员。

另开终端，在 frontend 目录运行 npm ci 和 npm run dev。打开终端显示的前端地址，用管理员账号登录。开发服务器会代理 API、管理页和静态文件。

## 管理员操作

1. 从账号菜单打开「管理后台」，在「用户」里添加普通成员。
2. 成员登录后，以一件作品添加多份附件并提交。作者可在账号菜单的「我的投稿」查看状态与退回意见。
3. 在管理后台打开「竞赛作品」，检查附件并保存审核结果。通过审核后，勾选「上架展示」和需要的原件下载选项，再保存。
4. 在「用户」列表中选中账号，执行「回收选中的普通账号」。再次发放时先重设密码，再执行「启用已重设密码的普通账号」。

## 数据库和文件

本地调试默认使用 SQLite，业务文件在 var/uploads，数据库在 var/db.sqlite3。ENTRYSTAGE_VAR_DIR 可指定持久数据目录，ENTRYSTAGE_UPLOAD_ROOT 可单独指定文件存储目录。数据库与上传目录都需要备份。

部署时设置 ENTRYSTAGE_SECRET_KEY、ENTRYSTAGE_ALLOWED_HOSTS，以及下面的 MySQL 连接参数，然后运行 migrate。建议使用 MySQL 8.4 LTS 与 utf8mb4。正式服务在 HTTPS 下运行。反向代理将 /api/、/admin/、/static/ 分发给 Django。前端从同域访问 API。管理页和查看器静态资源用 collectstatic 收集。上传目录由后端的授权接口读取。

| 环境变量 | 用途 |
| --- | --- |
| ENTRYSTAGE_MYSQL_DATABASE | 已建立的 MySQL 库名 |
| ENTRYSTAGE_MYSQL_USER | 数据库用户 |
| ENTRYSTAGE_MYSQL_PASSWORD | 数据库密码 |
| ENTRYSTAGE_MYSQL_HOST | 默认 127.0.0.1 |
| ENTRYSTAGE_MYSQL_PORT | 默认 3306 |
| ENTRYSTAGE_MAX_UPLOAD_MB | 单附件大小，默认 512 MB |
| ENTRYSTAGE_CSRF_TRUSTED_ORIGINS | 有需要时使用逗号分隔的可信来源，来源包含协议 |

## PPT 与 PPTX 查看器

部署独立的 ONLYOFFICE Docs，启用浏览器 JWT 与出站请求 JWT。应用通过只读查看器打开原件。站内原件下载根据作品权限授权。

| 环境变量 | 用途 |
| --- | --- |
| ENTRYSTAGE_ONLYOFFICE_URL | 浏览器可访问的 Docs 服务地址 |
| ENTRYSTAGE_ONLYOFFICE_SOURCE_ORIGIN | Docs 服务可访问的 Django 内网地址 |
| ENTRYSTAGE_ONLYOFFICE_BROWSER_SECRET | 与 Docs 浏览器 JWT 密钥一致 |
| ENTRYSTAGE_ONLYOFFICE_OUTBOX_SECRET | 与 Docs 出站 JWT 密钥一致 |
| ENTRYSTAGE_ONLYOFFICE_OUTBOX_HEADER | 出站 JWT 请求头，默认 Authorization |

将 Docs 取件地址的主机名列入 ENTRYSTAGE_ALLOWED_HOSTS。反向代理仅向 Docs 网络开放 /internal/office/source/。这个入口还会验证 JWT、短期票据和作品当前的查看权限。Docs 的站点地址使用浏览器可访问的 HTTPS 地址。服务配置完成后，使用实际参赛 PPT/PPTX 核对浏览效果。 [ONLYOFFICE 配置](https://api.onlyoffice.com/docs/docs-api/additional-api/signature) · [出站请求协议](https://api.onlyoffice.com/docs/docs-api/additional-api/signature/request/token-in-header)

## 测试

在本地调试环境运行 .\.venv\Scripts\python.exe manage.py test。测试覆盖登录校验、账号回收、整件投稿、退回重提、展示和下载矩阵、视频范围读取以及 PPT 签名取件。
