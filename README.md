# zhihu-cli

[![PyPI version](https://img.shields.io/pypi/v/pyzhihu-cli?label=PyPI)](https://pypi.org/project/pyzhihu-cli/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pyzhihu-cli)](https://pypi.org/project/pyzhihu-cli/)
[![PyPI - License](https://img.shields.io/pypi/l/pyzhihu-cli)](https://pypi.org/project/pyzhihu-cli/)
[![ClawHub](https://img.shields.io/badge/ClawHub-install-E65100)](https://clawhub.ai/BAIGUANGMEI/pyzhihu-cli)

知乎命令行工具 — 在终端搜索问题、查看回答、发布提问、发布想法、发布文章(图文混合，富文本支持)、浏览热榜

## 功能

- **认证** — 二维码扫码登录（终端渲染）或手动粘贴 Cookie 登录（不支持从浏览器自动获取 Cookie）
- **搜索** — 按关键词搜索问题、回答、文章
- **热榜** — 查看知乎热榜
- **问题** — 查看问题详情及回答
- **回答** — 查看回答详情及评论（支持 `--comments` 显示评论，`--limit` 控制数量，默认全部）
- **发布** — 发布提问、发布想法、发布文章（图文混合，富文本支持）
- **用户** — 查看用户资料、回答、文章、关注/粉丝
- **推荐** — 获取首页推荐内容（`feed` 显示列表，`feeds` 显示内容+评论）
- **话题** — 查看话题详情及热门问题
- **互动** — 赞同/取消赞同回答，关注/取消关注问题
- **收藏** — 查看收藏夹列表
- **通知** — 查看通知消息
- **JSON 输出** — 所有数据命令支持 `--json`
- **降低风控/反爬** — 全局统一 Chrome 浏览器指纹（`User-Agent` + `sec-ch-ua` + `sec-ch-ua-platform` 一致，版本号集中管理于 `config.CHROME_VERSION`）；登录与写操作带 CSRF（`_xsrf` / `x-xsrftoken`）。

## 命令一览

| 分类       | 命令                                     | 说明                           |
|------------|------------------------------------------|--------------------------------|
| Auth       | login, logout, status, whoami            | 登录、退出、状态检查、查看资料 |
| Read       | search, hot, question, answer            | 搜索、热榜、问题详情、回答详情 |
| Users      | user, user-answers, user-articles        | 查看资料、回答列表、文章列表   |
| Social     | followers, following                     | 查看粉丝、关注列表             |
| Feed       | feed, feeds, topic                      | 推荐 Feed、推荐+评论、话题详情 |
| Interact   | vote, follow-question                    | 赞同回答、关注问题             |
| Create     | ask, pin, article                        | 发布提问、发布想法、发布文章（图文混合，富文本支持）     |
| Delete     | delete-question, delete-pin, delete-article | 删除自己的提问、想法、文章（需确认，可 -y 跳过） |
| Other      | collections, notifications               | 收藏夹、通知                   |

> 所有数据命令支持 `--json` 输出。

## 安装

需要 Python 3.10+。

```bash
# 推荐：使用 uv
uv tool install pyzhihu-cli

# 或使用 pipx
pipx install pyzhihu-cli

# 从源码安装（开发用）
pip install -e .
```

二维码登录使用知乎 API（`/api/v3/account/api/login/qrcode`），**无需安装 Playwright**，仅需本工具依赖的 `requests` 与 `qrcode`。

## AI Agent Skill

本项目提供了 AI Agent Skill，可通过 [OpenClaw](https://openclaw.ai) 下载使用：

```
clawhub install pyzhihu-cli
```

安装后，AI Agent 可自动获取 zhihu-cli 的完整使用说明、命令参考、项目架构和开发指南。

**扫码登录与 Agent**：执行 `zhihu login --qrcode` 时，二维码会保存为 **`~/.zhihu-cli/login_qrcode.png`**（Windows 为 `%USERPROFILE%\.zhihu-cli\login_qrcode.png`）。Agent 可读取该图片并发送给用户，由用户在知乎 App 中扫码完成登录。

## 使用

### 登录

仅支持两种方式：**二维码扫码** 或 **手动粘贴 Cookie**。

```bash
# 二维码扫码登录（推荐）；二维码会保存为 ~/.zhihu-cli/login_qrcode.png，供 AI Agent 发送给用户扫码
zhihu login --qrcode

# 手动粘贴 Cookie（至少包含 z_c0、_xsrf、d_c0）
zhihu login --cookie "z_c0=xxx; _xsrf=yyy; d_c0=zzz"

# 检查登录状态
zhihu status

# 查看个人资料
zhihu whoami
zhihu whoami --json

# 退出登录
zhihu logout
```

### 搜索

```bash
zhihu search "Python 学习"
zhihu search "机器学习" --type topic
zhihu search "张三" --type people
zhihu search "Python" --json
```

### 热榜

```bash
zhihu hot
zhihu hot --limit 10
zhihu hot --json
```

### 问题

```bash
# 查看问题详情
zhihu question <question_id>

# 包含回答
zhihu question <question_id> --answers

# 限制回答数量
zhihu question <question_id> --answers --limit 10
```

### 回答

```bash
# 查看回答详情
zhihu answer <answer_id>

# 包含评论（默认显示全部）
zhihu answer <answer_id> --comments
zhihu answer <answer_id> -c

# 限制评论数量
zhihu answer <answer_id> -c -l 5
```

### 用户

```bash
# 查看用户资料（使用 URL Token）
zhihu user <url_token>

# 查看用户回答
zhihu user-answers <url_token>
zhihu user-answers <url_token> --sort voteups

# 查看用户文章
zhihu user-articles <url_token>

# 粉丝 / 关注
zhihu followers <url_token>
zhihu following <url_token>
```

### 推荐 & 话题

```bash
# 推荐列表（仅 ID、类型、标题、作者）
zhihu feed
zhihu feed --limit 5

# 推荐 + 回答内容 + 评论
zhihu feeds
zhihu feeds -l 3          # 3 条推荐
zhihu feeds -c 5          # 每条 5 条评论
zhihu feeds -c 0          # 仅推荐内容，不带评论

# 话题
zhihu topic <topic_id> --questions
```

### 互动

```bash
# 赞同 / 取消赞同
zhihu vote <answer_id>
zhihu vote <answer_id> --undo

# 关注 / 取消关注问题
zhihu follow-question <question_id>
zhihu follow-question <question_id> --undo
```

### 创作

发布提问、想法、文章时，**描述/正文均支持 HTML 富文本**（如 `<p>`、`<strong>`、`<a>` 等）。

```bash
# 发布提问
zhihu ask "如何学习 Python？"
zhihu ask "什么是机器学习？" -d "请详细解释" -t 19550517 -t 19551275

# 发布想法（标题 + 可选正文，正文可用 HTML）
zhihu pin "今天天气真好！"
zhihu pin "标题" -c "想法正文内容"

# 发布文章
zhihu article "文章标题" "文章内容"
zhihu article "标题" "内容" -t 19550517

# 带图片发布（-i 可重复使用以添加多张图片）
zhihu ask "求推荐" -d "详情" -i photo.jpg
zhihu pin "标题" -c "正文" -i image1.jpg -i image2.jpg
zhihu article "标题" "内容" -i cover.jpg

# 删除自己发布的内容（会提示确认，加 -y 跳过确认）
zhihu delete-question <问题ID>
zhihu delete-pin <想法ID>
zhihu delete-article <文章ID>
zhihu delete-question 12345678 -y
```

### 其他

```bash
zhihu collections
zhihu notifications
zhihu --version
zhihu -v search "Python"   # 调试日志
zhihu --help
```

## 后续开发

- [ ] 发布回答
- [ ] 发布评论
- [ ] 发布视频


## 架构

```
CLI (click) → ZhihuClient (requests)
                  ↓ API 请求
              Zhihu V4 API → JSON 响应

zhihu_cli/
├── config.py      # 集中配置：路径、URL、统一 UA/Chrome 版本
├── auth.py        # Cookie 管理、QR 码登录、scan_info 轮询
├── client.py      # ZhihuClient — 所有 API 调用封装
├── display.py     # Rich 终端输出
└── commands/      # Click 子命令
```

使用 `requests` 库通过知乎 V4 API 获取数据。登录认证通过二维码扫描或手动提供 Cookie 完成。

## 工作原理

1. **认证** — 通过 `zhihu login --qrcode`（二维码扫码）或 `zhihu login --cookie "z_c0=...; _xsrf=...; d_c0=..."`（手动粘贴 Cookie）完成登录，登录态保存于 `~/.zhihu-cli/cookies.json`。
2. **登录态校验** — 登录后通过 `/api/v4/me` 接口验证会话有效性。
3. **数据获取** — 使用 requests 通过知乎 V4 API 获取结构化 JSON 数据。
4. **CLI 展示** — 使用 Rich 库渲染美观的终端表格输出。

## 注意事项

- Cookie 存储在 `~/.zhihu-cli/cookies.json`，权限 `0600`
- `zhihu status` 只检查本地已保存的 cookie，不发起网络请求
- `zhihu login --cookie` 要求 Cookie 至少包含 `z_c0`、`_xsrf`、`d_c0`
- 用户查询使用 URL Token（即知乎个人主页的路径部分，如 `zhihu.com/people/xxx` 中的 `xxx`）
- 二维码登录使用知乎官方 API，无需安装 Playwright
- 浏览器指纹版本号集中管理于 `config.py` 的 `CHROME_VERSION`，修改一处即可全局生效

## 网络安全设计

本工具在设计与实现上遵循以下安全原则，以降低凭证与隐私风险：

- **凭证仅存本地**  
  登录态（Cookie）仅写入用户本机 `~/.zhihu-cli/cookies.json`，文件权限为 `0600`（仅当前用户可读写）。程序不会将 Cookie 或任何登录凭证上传至本工具维护方或第三方服务。

- **全程 HTTPS**  
  所有与知乎的通信均使用 HTTPS，请求仅发往知乎官方域名（如 `www.zhihu.com`、`api.zhihu.com`），避免凭证或内容在网络上明文传输。

- **无密码落地**  
  支持两种登录方式：二维码扫码（调用知乎官方登录 API，由用户在手机端完成授权）和手动粘贴 Cookie。本工具不收集、不存储账号密码。

- **最小权限与最小请求**  
  仅请求完成当前命令所需的知乎 API，不额外拉取或上报用户数据；Cookie 仅用于向知乎证明身份，不用于其他用途。

- **可审计与可复现**  
  项目开源，依赖列表在 `pyproject.toml` 中声明，无混淆或闭源运行时；用户可自行审查代码与依赖，或在隔离环境中安装运行。

建议仅在可信环境中使用本工具，并妥善保管本地 Cookie 文件；通过 `zhihu logout` 可清除本地保存的登录态。

## 发布到 PyPI

发布前请确认 `pyproject.toml` 中 `version` 已更新（每次发布需递增）。

```bash
# 1. 安装构建与上传工具
pip install build twine

# 2. 在项目根目录构建（生成 dist/ 下的 wheel 与 sdist）
python -m build

# 3. 检查打包内容（可选）
twine check dist/*

# 4. 上传到 PyPI（需已配置 PyPI 账号或 token）
twine upload dist/*
```

- 首次上传需在 [PyPI](https://pypi.org) 注册并配置 API Token；使用 token 时用户名填 `__token__`，密码填 token 值。
- 若使用 TestPyPI 测试：`twine upload --repository testpypi dist/*`

## License

Apache License 2.0
