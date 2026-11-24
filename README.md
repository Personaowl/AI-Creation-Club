# AI-Creation-Club

AI Creation Club 作品平台，用于展示和审核竞赛作品。

## 项目结构

- [frontend/](frontend/) 存放 Vue 3、TypeScript 和 Vite 前端。
- [backend/](backend/) 存放 Django REST API、账号管理和作品审核。
- [后端设计](backend/DESIGN.md) 记录作品、权限与在线预览规则。

## 本地启动

先按 [后端启动说明](backend/README.md#本地启动) 初始化数据库和管理员，在 8000 端口运行后端。另开一个终端运行：

~~~sh
cd frontend
npm ci
npm run dev
~~~

打开前端终端显示的 Local 地址，使用管理员账号登录。在 frontend 运行 npm run build 可生成生产构建。
