# zhihu-cli

知乎命令行工具 — 在终端搜索问题、查看回答、浏览热榜

## 功能

- **认证** — QR码扫描登录（终端二维码渲染），或直接复制 Cookie 登录
- **搜索** — 按关键词搜索问题、回答、文章
- **热榜** — 查看知乎热榜
- **问题** — 查看问题详情及回答
- **回答** — 查看回答详情及评论
- **用户** — 查看用户资料、回答、文章、关注/粉丝
- **推荐** — 获取首页推荐内容
- **话题** — 查看话题详情及热门问题
- **互动** — 赞同/取消赞同回答，关注/取消关注问题
- **收藏** — 查看收藏夹列表
- **通知** — 查看通知消息
- **JSON 输出** — 所有数据命令支持 `--json`

## 命令一览

| 分类       | 命令                                     | 说明                           |
|------------|------------------------------------------|--------------------------------|
| Auth       | login, logout, status, whoami            | 登录、退出、状态检查、查看资料 |
| Read       | search, hot, question, answer            | 搜索、热榜、问题详情、回答详情 |
| Users      | user, user-answers, user-articles        | 查看资料、回答列表、文章列表   |
| Social     | followers, following                     | 查看粉丝、关注列表             |
| Feed       | feed, topic                              | 推荐 Feed、话题详情            |
| Interact   | vote, follow-question                    | 赞同回答、关注问题             |
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

安装后需要初始化 Playwright 浏览器（二维码登录需要）：

```bash
playwright install chromium
```

## 使用

### 登录

```bash
# 二维码扫码登录（推荐）
zhihu login --qrcode

# 手动提供 cookie 字符串（至少包含 z_c0）
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

# 包含评论
zhihu answer <answer_id> --comments
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
zhihu feed
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

### 其他

```bash
zhihu collections
zhihu notifications
zhihu --version
zhihu -v search "Python"   # 调试日志
zhihu --help
```

## 架构

```
CLI (click) → ZhihuClient (requests)
                  ↓ API 请求
              Zhihu V4 API → JSON 响应
```

使用 `requests` 库通过知乎 V4 API 获取数据。登录认证通过浏览器二维码扫描或手动提供 Cookie 完成。

## 工作原理

1. **认证** — 优先读取 `~/.zhihu-cli/cookies.json`；未命中时启动 Playwright 浏览器展示二维码，等待用户扫码登录。也可通过 `--cookie` 直接提供 cookie 字符串。
2. **登录态校验** — 登录后通过 `/api/v4/me` 接口验证会话有效性。
3. **数据获取** — 使用 requests 通过知乎 V4 API 获取结构化 JSON 数据。
4. **CLI 展示** — 使用 Rich 库渲染美观的终端表格输出。

## 注意事项

- Cookie 存储在 `~/.zhihu-cli/cookies.json`，权限 `0600`
- `zhihu status` 只检查本地已保存的 cookie，不发起网络请求
- `zhihu login --cookie` 要求 cookie 至少包含 `z_c0`
- 用户查询使用 URL Token（即知乎个人主页的路径部分，如 `zhihu.com/people/xxx` 中的 `xxx`）
- 二维码登录需要先安装 Playwright 浏览器：`playwright install chromium`

## License

Apache License 2.0
