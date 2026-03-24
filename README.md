# OKX Builder Eye v5.0 — Vercel Edition

> KOL 发现 → 拓展 → 运营 → 转化 全链路闭环

## 部署到 Vercel（10 分钟）

### 1. 前置条件

- [GitHub 账号](https://github.com)
- [Vercel 账号](https://vercel.com)（用 GitHub 登录）
- [Anthropic API Key](https://console.anthropic.com)（Claude AI 用）

### 2. 推送代码到 GitHub

```bash
cd builder-eye-vercel
git init
git add .
git commit -m "init: builder eye v5"
# 在 GitHub 创建仓库 builder-eye，然后：
git remote add origin https://github.com/你的用户名/builder-eye.git
git push -u origin main
```

### 3. Vercel 部署

1. 打开 [vercel.com/new](https://vercel.com/new)
2. Import 你的 `builder-eye` 仓库
3. Framework Preset: **Other**
4. Root Directory: **留空**
5. 点 **Deploy**

### 4. 添加 Postgres 数据库

1. 进入项目 → **Storage** → **Create Database** → 选 **Postgres**
2. 选免费计划 → 创建
3. Vercel 会自动注入 `POSTGRES_URL` 环境变量

### 5. 配置环境变量

进入项目 → **Settings** → **Environment Variables**，添加：

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-你的key` |
| `FEISHU_WEBHOOK` | `https://open.larksuite.com/open-apis/bot/v2/hook/xxx` |

点 **Save** → 回到 **Deployments** → 点最新一次的 **Redeploy**

### 6. 导入数据

打开你的 Vercel 域名（如 `https://builder-eye.vercel.app`），通过页面上传：

1. 上传 CRM 周报 Excel（必须）
2. 上传 Google Sheet KOL 数据库（可选，用于区分合作/非合作）

### 7. 完成！

团队成员打开链接即可使用，所有数据存在 Vercel Postgres 中，多人共享。

---

## 本地开发

```bash
pip install -r requirements.txt
# 创建 .env 填入 POSTGRES_URL 和 ANTHROPIC_API_KEY
uvicorn api.index:app --reload --port 8000
# 打开 http://localhost:8000
```

## 文件结构

```
builder-eye-vercel/
├── api/
│   └── index.py          ← 全部后端逻辑（FastAPI）
├── static/               ← 静态资源（预留）
├── vercel.json           ← Vercel 部署配置
├── requirements.txt      ← Python 依赖
├── .env.example          ← 环境变量模板
└── README.md             ← 本文件
```

## API 文档

部署后访问 `https://你的域名/docs` 查看 Swagger 自动生成的 API 文档。
