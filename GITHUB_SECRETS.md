# GitHub Secrets 配置指南

在使用 GitHub Actions 自动部署之前，需要在 GitHub 仓库中配置以下 Secrets。

## 配置步骤

1. 访问 GitHub 仓库：https://github.com/DEGv587/open-convert
2. 进入 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret** 添加以下密钥

---

## 必需的 Secrets

### 1. RENDER_BACKEND_URL
- **说明**: Render 后端服务的 URL
- **示例**: `https://open-convert-backend.onrender.com`
- **获取方式**: 
  1. 在 Render Dashboard 部署后端服务
  2. 复制服务的 URL

### 2. CLOUDFLARE_API_TOKEN
- **说明**: Cloudflare API Token（用于部署 Pages）
- **获取方式**:
  1. 访问 [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
  2. 点击 **Create Token**
  3. 使用模板 **Edit Cloudflare Workers**
  4. 或自定义权限：
     - Account - Cloudflare Pages: Edit
  5. 创建后复制 Token

### 3. CLOUDFLARE_ACCOUNT_ID
- **说明**: Cloudflare 账户 ID
- **获取方式**:
  1. 访问 [Cloudflare Dashboard](https://dash.cloudflare.com/)
  2. 选择任意域名
  3. 在右侧栏找到 **Account ID**
  4. 或在 URL 中查看：`https://dash.cloudflare.com/{account_id}/...`

### 4. VITE_API_BASE
- **说明**: 前端 API 基础路径
- **示例**: `https://open-convert-backend.onrender.com/doc-convert/api`
- **格式**: `{RENDER_BACKEND_URL}/doc-convert/api`

---

## 配置示例

```
RENDER_BACKEND_URL=https://open-convert-backend.onrender.com
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token_here
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id_here
VITE_API_BASE=https://open-convert-backend.onrender.com/doc-convert/api
```

---

## 验证配置

配置完成后，推送代码到 `main` 分支：

```bash
git add .
git commit -m "chore: 配置 CI/CD"
git push origin main
```

然后访问 GitHub Actions 页面查看部署状态：
https://github.com/DEGv587/open-convert/actions

---

## 注意事项

1. **API Token 权限**: 确保 Cloudflare API Token 有 Pages 编辑权限
2. **URL 格式**: 所有 URL 不要以 `/` 结尾
3. **安全性**: 不要将 Secrets 提交到代码仓库
4. **更新**: 如果后端 URL 变更，需要同时更新 `RENDER_BACKEND_URL` 和 `VITE_API_BASE`

---

## 可选：Render Deploy Hook

如果想通过 GitHub Actions 主动触发 Render 部署：

1. 在 Render Dashboard 中，进入服务设置
2. 找到 **Deploy Hook**
3. 创建一个新的 Deploy Hook
4. 将 URL 添加到 GitHub Secrets：`RENDER_DEPLOY_HOOK`
5. 修改 `.github/workflows/deploy.yml`，添加触发步骤：
   ```yaml
   - name: Trigger Render Deploy
     run: curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK }}
   ```
