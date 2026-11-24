# AI Creation Club 作品平台前端

基于 Vue 3、TypeScript 和 Vite 的竞赛作品展示界面。

先启动 [Django 后端](../backend/README.md#本地启动)，再在 frontend 目录运行 npm ci 和 npm run dev。前端会将 /api/、/admin/ 和 /static/ 代理到本机 8000 端口。运行 npm run build 可生成生产构建。

成员通过管理员发放的账号登录，可提交整件作品，查看审核状态，并在作品详情切换附件。收藏按登录账号保存在当前浏览器。作品和附件由后端保存。PPT/PPTX 的在线浏览使用 [ONLYOFFICE Docs](../backend/README.md#ppt-与-pptx-查看器)。

全局颜色与磨砂玻璃样式在 src/theme.css。
