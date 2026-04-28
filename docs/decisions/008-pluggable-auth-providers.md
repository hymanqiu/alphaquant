# ADR 008: Pluggable Auth Providers

**状态**: 已采纳
**日期**: 2026-04-25 (v0.7.0, Phase 2)
**影响节点**: `/api/auth/*` 路由, `/api/analyze` 的 `Depends(get_optional_user)`
**相关代码**: `backend/services/auth/`, `backend/api/auth.py`, `backend/alembic/versions/20260425_0001_init_users.py`

## 背景

Phase 2 要引入用户身份系统。要回答：

1. 支持哪几种登录方式？（密码 / Magic link / Google OAuth / Apple / GitHub / SAML / ...）
2. 选什么不影响"以后想换 / 加"的灵活性？
3. 数据库 schema 怎么设计才能支持"同一邮箱可挂多种登录方式"？

合作开发者明确要求：**Auth 这个部分能够单独作为一个模块 push**。意味着模块化抽象是硬要求。

## 考虑的方案

### 方案 A: 仅邮箱 + 密码
- 最少代码
- 问题：用户体验差（必须记密码）；MVP 转化率受影响
- 问题：不支持 enterprise SSO（未来路径堵死）

### 方案 B: 用第三方 auth-as-a-service（Auth0 / Clerk / Supabase Auth）
- 完全托管，开箱即用
- 问题：每月固定成本（Auth0 ~$23/mo for 1000 users）
- 问题：用户数据在第三方，未来迁移成本高
- 问题：合规要求（GDPR / SOC 2）依赖第三方

### 方案 C: 自建 + 三种 provider，模块化抽象 ✓
- 三种登录方式（邮箱密码 / Magic link / Google OAuth）覆盖 95% 用户偏好
- 每种 provider 是独立 Python 模块，符合"模块单独 push"要求
- 数据自主，未来可加 GitHub / Apple / SAML 不需要重构
- 零月租，仅在使用 Resend / Google OAuth 时付服务费

## 决策

采用方案 C。

### 模块边界（`backend/services/auth/`）

```
__init__.py         公共出口：User / AuthService / Tier / get_current_user / require_pro
models.py           SQLAlchemy ORM：User + IdentityProvider
service.py          AuthService：唯一的"业务逻辑入口"，外部不直接调 provider
passwords.py        bcrypt 哈希 + 校验（cost=12）
tokens.py           JWT (HS256) 签发 + 解码
dependencies.py     FastAPI deps: get_current_user / get_optional_user / require_pro / require_admin_tier
providers/
    email_password  通过 service 直接处理（无独立 module，逻辑简单）
    magic_link.py   itsdangerous URLSafeTimedSerializer + Resend HTTP API + stderr fallback
    google_oauth.py authlib OIDC client（lazy init, is_configured() check）
```

### Schema 设计：两表，one-to-many

```
users (
  id, email UNIQUE, password_hash NULL, tier CHECK (free|pro|admin),
  is_active, email_verified, display_name, ...
)
identity_providers (
  id, user_id FK→users CASCADE, kind CHECK (email_password|magic_link|google),
  external_id, ...,
  UNIQUE (user_id, kind),       ← 同一用户同一 kind 至多一行
  UNIQUE (kind, external_id)    ← 同一 Google sub 不能挂两个用户
)
```

**为什么不用 polymorphic columns**: 把 `google_sub` / `magic_token` 全塞 users 表会让 schema 跟着 provider 数量膨胀，每加一个 provider = 一次 migration。`identity_providers` 表用 `kind` + `external_id` 通用化，加 GitHub / Apple 只需在 CHECK 约束里加一行。

### 上层 funnel：`AuthService`

三种 provider 的 verify 完成后都进同一个 `AuthService.upsert_*_user`：

```
邮箱密码  ──┐
Magic Link ─┼─→ AuthService.upsert_*_user(...)  
Google     ─┘     ├── 1. 优先用 provider-specific external_id 找
                  ├── 2. 其次按 email 找现有用户并链接 identity 行
                  ├── 3. 都没找到 → 新建 user + identity
                  └── 返回 User → routes 签 JWT cookie
```

**关键性质**：同一邮箱用三种方式登录，最终都映射到同一个 `users.id`。后续行为按 `user_id` 操作，与登录方式解耦。

### 加新 provider 的步骤（e.g. GitHub）

1. 加一个 `services/auth/github_oauth.py`（mirror `google_oauth.py`）
2. `AuthService` 加 `upsert_github_user(github_id, email, ...)`（可复用 `upsert_google_user` 模式）
3. 配置加 `AQ_GITHUB_OAUTH_*` env vars
4. routes 加 `/api/auth/github/start` + `/callback`
5. 前端 login 页加一个 "Sign in with GitHub" tab
6. **Migration**: 加一行 `ALTER TABLE identity_providers DROP CONSTRAINT ck_identity_kind; ALTER TABLE ... ADD CONSTRAINT ck_identity_kind CHECK (kind IN ('email_password', 'magic_link', 'google', 'github'));`

无需改 `AuthService` 的核心逻辑、JWT、tier、依赖、前端 AuthContext。

### 会话凭证：JWT 双下发

| 渠道 | 适用 |
|------|------|
| `aq_session` HTTP-only cookie (SameSite=Lax) | 浏览器 SPA |
| 响应 body `{token}` | API 客户端（放 `Authorization: Bearer`） |

`get_optional_user` 同时读 cookie 和 header，优先 cookie。tier 字段从 DB 实时读（不依赖 JWT 内 tier），admin 升降级**立即生效**。

## 后果

**正面**:
- 加 provider = 加一个文件 + migration 一行；零核心改动
- 用户多种登录方式可以混用（邮箱密码注册 → 后续用 Google 直接登录同一账号）
- AuthService 是单一测试边界，每个 provider 模块独立 mock
- 数据自主：用户表是我们自己的，未来 BYOK / SSO / 数据导出全可控
- JWT + cookie 让前端 AuthContext 实现简单（自动跟随 fetch）

**负面**:
- 比第三方方案多 ~600 行代码 + Alembic + bcrypt 等依赖（缓解：长期价值高）
- 多 provider 测试矩阵复杂（缓解：smoke test 用 mock；E2E 用 staging Google OAuth）
- 没有 MFA / passkey 支持（缓解：MVP 不要求；未来加在 service 层）
- Magic link 在 Resend 没配时只能 stderr 兜底（缓解：dev 友好；prod 必须配 Resend）

**未决问题**:
- [ ] 邮箱验证流程（密码注册的用户 `email_verified=False` 但没有"发验证邮件"端点）—— Magic link 路径已经能做兜底验证
- [ ] "忘记密码"流程 —— 故意不做，让 magic link 兼任
- [ ] 用户偏好（如 BYOK / 默认 LLM）—— 加 `users.preferences` JSONB 列即可，未触动 auth 模块边界
- [ ] Stripe 订阅集成 —— 加 `webhooks.py` 监听 Stripe events 调 `AuthService.set_tier`，模块边界稳定
