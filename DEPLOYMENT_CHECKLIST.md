# 部署检查清单

按照以下步骤完成部署配置。

---

## ✅ 第一步：后端部署到 Render

### 1.1 创建 Render 服务

- [ ] 访问 https://dashboard.render.com/
- [ ] 点击 **New +** → **Web Service**
- [ ] 连接 GitHub 仓库
- [ ] 选择仓库后，配置：
  - Name: `open-convert-backend`（或自定义）
  - Region: `Oregon (US West)`
  - Branch: `main`
  - Root Directory: `doc-convert/backend`
  - Environment: `Docker`
  - Dockerfile Path: `./Dockerfile`
  - Plan: `Free`

### 1.2 配置环境变量

在 Render 服务设置中添加：

- [ ] `ALLOWED_ORIGINS` = `https://你的前端域名.com,http://localhost:5173`
- [ ] `MAX_FILE_SIZE_MB` = `50`
- [ ] `MAX_MULTI_FILES` = `50`
- [ ] `JOB_TTL_HOURS` = `1`

### 1.3 配置健康检查

- [ ] Health Check Path: `/doc-convert/api/health`

### 1.4 部署并验证

- [ ] 点击 **Create Web Service**，等待部署完成（约 5-10 分钟）
- [ ] 复制服务 URL（例如：`https://open-convert-backend-xxx.onrender.com`）
- [ ] 测试健康检查：
  ```bash
  curl https://你的后端URL/doc-convert/api/health
  ```
  应该返回：`{"status":"ok","libreoffice":true,"tesseract":true}`

---

## ✅ 第二步：前端部署到 Cloudflare Pages

### 2.1 创建 Cloudflare Pages 项目

- [ ] 访问 https://dash.cloudflare.com/
- [ ] 进入 **Workers & Pages** → **Create application** → **Pages**
- [ ] 连接 GitHub 仓库
- [ ] 配置：
  - Project name: `open-convert`（或自定义）
  - Production branch: `main`
  - Build command: `npm run build`
  - Build output directory: `dist`
  - Root directory: `doc-convert/frontend`

### 2.2 配置环境变量

- [ ] 添加环境变量：
  - `VITE_API_BASE` = `https://你的后端URL/doc-convert/api`
  
  **注意**：使用第一步中获取的 Render 后端 URL

### 2.3 部署并验证

- [ ] 点击 **Save and Deploy**，等待构建完成（约 2-3 分钟）
- [ ] 访问 Cloudflare 提供的 URL（例如：`https://open-convert.pages.dev`）
- [ ] 测试上传文件转换功能

### 2.4 配置自定义域名（可选）

- [ ] 在 Cloudflare Pages 项目中，进入 **Custom domains**
- [ ] 添加你的域名
- [ ] 配置 DNS 记录（CNAME）
- [ ] 等待 DNS 生效（通常几分钟）

---

## ✅ 第三步：配置 GitHub Secrets（启用 CI/CD）

### 3.1 获取必要信息

- [ ] **RENDER_BACKEND_URL**: 从第一步获取的 Render 后端 URL
- [ ] **CLOUDFLARE_API_TOKEN**: 
  1. 访问 https://dash.cloudflare.com/profile/api-tokens
  2. 创建 Token，权限：`Account - Cloudflare Pages: Edit`
- [ ] **CLOUDFLARE_ACCOUNT_ID**: 
  1. 在 Cloudflare Dashboard 右侧栏查看
  2. 或从 URL 中获取
- [ ] **VITE_API_BASE**: `{RENDER_BACKEND_URL}/doc-convert/api`

### 3.2 添加 Secrets

- [ ] 访问 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions**
- [ ] 点击 **New repository secret**，逐个添加：
  - [ ] `RENDER_BACKEND_URL`
  - [ ] `CLOUDFLARE_API_TOKEN`
  - [ ] `CLOUDFLARE_ACCOUNT_ID`
  - [ ] `VITE_API_BASE`

### 3.3 验证 CI/CD

- [ ] 修改任意代码文件（例如 README.md）
- [ ] 提交并推送到 `main` 分支
- [ ] 访问 GitHub Actions 页面，查看部署状态
- [ ] 确认部署成功

---

## ✅ 第四步：更新后端 CORS 配置

**重要**：前端域名确定后，需要更新后端的 CORS 配置

- [ ] 在 Render Dashboard 中，进入后端服务设置
- [ ] 修改环境变量 `ALLOWED_ORIGINS`，添加前端域名：
  ```
  https://你的前端域名.com,https://open-convert.pages.dev,http://localhost:5173
  ```
- [ ] 保存后，Render 会自动重新部署

---

## ✅ 第五步：最终测试

### 5.1 功能测试

- [ ] 访问前端网站
- [ ] 测试单文件上传转换（PDF → Word）
- [ ] 测试多图片合并为 PDF
- [ ] 测试 HEIC 图片转换
- [ ] 测试下载转换后的文件

### 5.2 性能测试

- [ ] 测试大文件上传（接近 50MB）
- [ ] 测试多图片上传（10+ 张）
- [ ] 检查转换速度是否正常

### 5.3 错误处理测试

- [ ] 测试上传不支持的格式
- [ ] 测试超大文件（超过 50MB）
- [ ] 测试网络中断后的恢复

---

## 📝 部署完成后

### 记录信息

- 后端 URL: `_______________________________`
- 前端 URL: `_______________________________`
- 自定义域名: `_______________________________`
- 部署时间: `_______________________________`

### 监控和维护

- [ ] 设置 Render 服务监控（可选）
- [ ] 定期检查日志
- [ ] 关注 GitHub Actions 构建状态
- [ ] 监控 Cloudflare Pages 构建配额

---

## 🔧 常见问题

### 后端休眠问题
- Render 免费版 15 分钟无请求会休眠
- 首次唤醒需要 30-60 秒
- 解决方案：使用定时 ping 服务（如 UptimeRobot）

### CORS 错误
- 检查后端 `ALLOWED_ORIGINS` 是否包含前端域名
- 确保 URL 格式正确（不要以 `/` 结尾）

### 构建失败
- 检查 GitHub Secrets 是否配置正确
- 查看 GitHub Actions 日志
- 确认 Cloudflare API Token 权限

---

## 📚 相关文档

- [DEPLOYMENT.md](./DEPLOYMENT.md) - 详细部署指南
- [GITHUB_SECRETS.md](./GITHUB_SECRETS.md) - Secrets 配置说明
- [README.md](./README.md) - 项目说明
