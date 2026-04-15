# 部署指南

## 后端部署到 Render

### 方式一：通过 Render Dashboard（推荐）

1. 访问 [Render Dashboard](https://dashboard.render.com/)
2. 点击 **New +** → **Web Service**
3. 连接 GitHub 仓库
4. 配置如下：
   - **Name**: `open-convert-backend`
   - **Region**: Oregon (US West)
   - **Branch**: `main`
   - **Root Directory**: `doc-convert/backend`
   - **Environment**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Plan**: Free
   - **Health Check Path**: `/doc-convert/api/health`

5. 添加环境变量：
   ```
   ALLOWED_ORIGINS=https://your-domain.com,http://localhost:5173
   MAX_FILE_SIZE_MB=50
   MAX_MULTI_FILES=50
   JOB_TTL_HOURS=1
   ```

6. 点击 **Create Web Service**

### 方式二：使用 render.yaml（自动部署）

1. 修改 `render.yaml` 中的 `ALLOWED_ORIGINS` 为你的域名
2. 确保 `render.yaml` 已提交到仓库根目录
3. 在 Render Dashboard 中点击 **New +** → **Blueprint**
4. 选择你的 GitHub 仓库
5. Render 会自动读取 `render.yaml` 并创建服务

### 部署后

部署完成后，你会得到一个 URL，类似：
```
https://your-service-name.onrender.com
```

测试健康检查：
```bash
curl https://your-service-name.onrender.com/doc-convert/api/health
```

---

## 前端部署到 Cloudflare Pages

### 1. 构建配置

前端已配置好构建脚本，位于 `doc-convert/frontend/package.json`：
```json
{
  "scripts": {
    "build": "vite build"
  }
}
```

### 2. 通过 Cloudflare Dashboard 部署

1. 访问 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 **Workers & Pages** → **Create application** → **Pages**
3. 连接你的 GitHub 仓库
4. 配置如下：
   - **Project name**: `open-convert`
   - **Production branch**: `main`
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory**: `doc-convert/frontend`

5. 添加环境变量：
   ```
   VITE_API_BASE=https://your-backend-url.onrender.com/doc-convert/api
   ```

6. 点击 **Save and Deploy**

### 3. 配置自定义域名（可选）

1. 在 Cloudflare Pages 项目设置中，进入 **Custom domains**
2. 添加你的域名
3. 按照提示配置 DNS 记录（CNAME 指向 Cloudflare Pages）

---

## Cloudflare Worker（可选 - API 网关）

如果需要 Worker 作为 API 网关：

1. 进入 `doc-convert/worker` 目录
2. 修改 `wrangler.toml` 中的配置
3. 部署：
   ```bash
   cd doc-convert/worker
   npx wrangler deploy
   ```

---

## CI/CD 自动部署

### GitHub Actions 配置

参考 `.github/workflows/deploy.yml` 和 `GITHUB_SECRETS.md`

### 触发条件

- **后端**: 推送到 `main` 分支且 `doc-convert/backend/**` 有变更
- **前端**: 推送到 `main` 分支且 `doc-convert/frontend/**` 有变更

### 部署流程

1. 代码推送到 `main` 分支
2. GitHub Actions 自动触发
3. Render 和 Cloudflare Pages 自动构建部署
4. 部署完成后发送通知（可选）

---

## 验证部署

### 后端验证
```bash
curl https://your-backend-url.onrender.com/doc-convert/api/health
curl https://your-backend-url.onrender.com/doc-convert/api/config
```

### 前端验证
访问你的前端域名，测试文件上传和转换功能

---

## 注意事项

1. **Render 免费版限制**：
   - 15 分钟无请求后会休眠
   - 首次唤醒需要 30-60 秒
   - 每月 750 小时免费运行时间

2. **Cloudflare Pages 限制**：
   - 每月 500 次构建
   - 每次构建最多 20 分钟

3. **文件大小限制**：
   - 当前设置为 50MB
   - 可通过环境变量 `MAX_FILE_SIZE_MB` 调整

4. **CORS 配置**：
   - 确保后端 `ALLOWED_ORIGINS` 包含前端域名
   - 前端域名变更后需要更新后端环境变量
