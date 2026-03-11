---
name: zhihu-cli
description: "Install, use, develop, debug, test, and extend the zhihu-cli (pyzhihu-cli) project. Use when: installing pyzhihu-cli, running zhihu CLI commands, logging in to Zhihu, searching/browsing content, adding new CLI commands, fixing bugs, writing tests, modifying display output, updating auth flow, or understanding the project architecture."
---

# zhihu-cli Skill

## What is zhihu-cli

zhihu-cli（PyPI 包名 `pyzhihu-cli`）是一个 Python 命令行工具，在终端中浏览知乎内容。支持搜索、热榜、问题、回答、用户、投票、关注等 20 个子命令。

- **PyPI 包名**: `pyzhihu-cli`
- **CLI 命令名**: `zhihu`
- **Python 要求**: >= 3.10

---

## Installation（安装）

### 用户安装（从 PyPI）

```bash
# 推荐方式：使用 uv（全局命令行工具）
uv tool install pyzhihu-cli

# 或使用 pipx
pipx install pyzhihu-cli

# 或使用 pip
pip install pyzhihu-cli
```

### 开发安装（从源码）

```bash
# 克隆仓库
git clone https://github.com/BAIGUANGMEI/zhihu-cli.git
cd zhihu-cli

# 创建虚拟环境并安装
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -e .
```

### 安装 Playwright 浏览器（二维码登录需要）

```bash
playwright install chromium
```

> **注意**: 如果只使用 `--cookie` 方式登录，可跳过此步。

---

## Usage（使用方法）

### 1. 登录（首次使用必须先登录）

```bash
# 方式一：二维码扫码登录（推荐，需要 Playwright）
zhihu login --qrcode

# 方式二：手动提供 Cookie 字符串（至少包含 z_c0）
zhihu login --cookie "z_c0=xxx; _xsrf=yyy; d_c0=zzz"
```

Cookie 获取方法：在浏览器登录知乎 → F12 → Network → 任意请求 → Headers → Cookie，复制完整值。

### 2. 验证登录状态

```bash
# 离线检查（只查本地 cookie 文件）
zhihu status

# 在线验证并显示个人资料
zhihu whoami

# JSON 格式输出
zhihu whoami --json
```

### 3. 搜索

```bash
zhihu search "Python 学习"
zhihu search "机器学习" --type topic
zhihu search "张三" --type people
zhihu search "Python" --limit 20
zhihu search "Python" --json
```

### 4. 热榜

```bash
zhihu hot
zhihu hot --limit 10
zhihu hot --json
```

### 5. 问题与回答

```bash
# 查看问题详情
zhihu question 12345678

# 查看问题下的回答
zhihu answers 12345678 --limit 5

# 查看单个回答详情
zhihu answer 87654321
zhihu answer 87654321 --json
```

### 6. 用户

```bash
# 查看用户资料（URL Token = 知乎主页路径 /people/xxx 中的 xxx）
zhihu user some-url-token

# 查看用户的回答、文章
zhihu user-answers some-url-token
zhihu user-articles some-url-token

# 粉丝和关注
zhihu followers some-url-token
zhihu following some-url-token
```

### 7. 推荐与话题

```bash
zhihu feed
zhihu topic 12345678
```

### 8. 互动

```bash
# 赞同回答
zhihu vote 87654321

# 取消赞同
zhihu vote --neutral 87654321

# 关注 / 取消关注问题
zhihu follow-question 12345678
zhihu follow-question --unfollow 12345678
```

### 9. 其他

```bash
zhihu collections           # 收藏夹
zhihu notifications         # 通知
zhihu logout                # 退出登录
zhihu --version             # 版本
zhihu -v search "Python"    # 开启调试日志
zhihu --help                # 帮助
```

### 所有命令汇总

| 分类 | 命令 | 说明 |
|------|------|------|
| 认证 | `login --qrcode` / `login --cookie "..."` | 登录 |
| 认证 | `logout` | 退出登录 |
| 认证 | `status` | 检查登录状态（离线） |
| 认证 | `whoami [--json]` | 查看个人资料 |
| 内容 | `search QUERY [--type general/people/topic] [--limit N] [--json]` | 搜索 |
| 内容 | `hot [--limit N] [--json]` | 热榜 |
| 内容 | `question ID [--json]` | 问题详情 |
| 内容 | `answers ID [--limit N] [--json]` | 问题下的回答列表 |
| 内容 | `answer ID [--json]` | 回答详情 |
| 内容 | `feed [--json]` | 推荐 Feed |
| 内容 | `topic ID [--json]` | 话题详情 |
| 用户 | `user URL_TOKEN [--json]` | 用户资料 |
| 用户 | `user-answers URL_TOKEN [--limit N] [--json]` | 用户回答 |
| 用户 | `user-articles URL_TOKEN [--limit N] [--json]` | 用户文章 |
| 用户 | `followers URL_TOKEN [--limit N] [--json]` | 粉丝列表 |
| 用户 | `following URL_TOKEN [--limit N] [--json]` | 关注列表 |
| 互动 | `vote ANSWER_ID [--neutral]` | 赞同/取消赞同 |
| 互动 | `follow-question QID [--unfollow]` | 关注/取消关注问题 |
| 其他 | `collections [--limit N] [--json]` | 收藏夹 |
| 其他 | `notifications [--limit N] [--json]` | 通知 |

> **所有数据命令均支持 `--json` 输出原始 JSON。**

---

## Architecture（项目架构）

```
zhihu_cli/
├── __init__.py          # __version__ = "0.1.0", __app_name__
├── config.py            # 集中配置：路径、URL、HTTP 默认值
├── display.py           # Rich 主题、表格工厂、格式化工具函数
├── exceptions.py        # LoginError, DataFetchError
├── auth.py              # Cookie 管理、QR 码登录（Playwright）
├── client.py            # ZhihuClient — 所有 API 调用封装
├── cli.py               # Click group 入口，注册所有子命令
└── commands/
    ├── auth.py           # login, logout, status, whoami
    ├── content.py        # search, hot, question, answer, answers, feed, topic
    ├── user.py           # user, user-answers, user-articles, followers, following
    └── interact.py       # vote, follow-question, collections, notifications
```

### Module Responsibilities

| Module | 职责 | 不应包含 |
|--------|------|----------|
| `config.py` | 常量、路径、URL | 任何逻辑 |
| `display.py` | Rich 主题、`print_*` 辅助函数、`strip_html`、`format_count`、`truncate`、`make_table`、`make_kv_table`、`format_stats_line` | API 调用 |
| `auth.py` | Cookie 读写、QR 登录、cookie 解析验证 | CLI 命令定义 |
| `client.py` | `ZhihuClient` 类，所有 API 端点方法 | 终端输出 |
| `commands/*.py` | Click 命令定义、调用 client 并格式化输出 | 直接 HTTP 请求 |

### Key Coding Patterns

1. **懒导入 ZhihuClient** — 命令模块在函数体内 `from ..client import ZhihuClient`，避免顶层导入
2. **`_get_client()` 上下文管理器** — `content.py`、`user.py`、`interact.py` 各有一个，负责获取 cookie + 创建客户端
3. **统一输出** — 所有终端输出使用 `display.py` 的 `print_success`/`print_error`/`print_warning`/`print_info`/`print_hint`，禁止裸 `print()`
4. **JSON 输出** — 所有数据命令通过 `--json` flag 支持 `click.echo(json.dumps(...))`
5. **错误退出** — 认证失败 `sys.exit(1)`，使用 `print_error()` 输出错误信息

### API Endpoints

- **V4 基础**: `https://www.zhihu.com/api/v4`（大多数端点）
- **V3 备用**: `https://www.zhihu.com/api/v3`（热榜、Feed）
- **认证**: Cookie-based，`z_c0` 为必需 token
- **存储**: `~/.zhihu-cli/cookies.json`

### ZhihuClient Methods

| 方法 | 端点 | 说明 |
|------|------|------|
| `get_self_info()` | `/me` | 当前用户信息 |
| `search(keyword, ...)` | `/search_v3` | 搜索 |
| `get_hot_list(limit)` | V3 `/feed/topstory/hot-lists/total` | 热榜 |
| `get_question(id)` | `/questions/{id}` | 问题详情 |
| `get_question_answers(id, ...)` | `/questions/{id}/answers` | 问题下的回答 |
| `get_answer(id)` | `/answers/{id}` | 回答详情 |
| `get_user_profile(token)` | `/members/{token}` | 用户资料 |
| `get_user_answers(token, ...)` | `/members/{token}/answers` | 用户回答 |
| `get_user_articles(token, ...)` | `/members/{token}/articles` | 用户文章 |
| `get_followers(token, ...)` | `/members/{token}/followers` | 粉丝 |
| `get_following(token, ...)` | `/members/{token}/followees` | 关注 |
| `get_feed(...)` | V3 `/feed/topstory/recommend` | 推荐 |
| `get_topic(id)` | `/topics/{id}` | 话题 |
| `vote_up(id)` / `vote_neutral(id)` | POST `/answers/{id}/voters` | 投票 |
| `follow_question(id)` / `unfollow_question(id)` | POST/DELETE `/questions/{id}/followers` | 关注问题 |
| `get_collections(...)` | `/members/{token}/favlists` | 收藏夹 |
| `get_notifications(...)` | `/notifications` | 通知 |

---

## Adding a New Command

1. **在 `client.py` 添加 API 方法**：
   ```python
   def get_xxx(self, ...) -> dict:
       url = f"{ZHIHU_API_V4}/xxx"
       return self._get(url, params={...})
   ```

2. **在对应的 `commands/*.py` 添加 Click 命令**：
   ```python
   @click.command()
   @click.argument("xxx_id", type=int)
   @click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
   def xxx(xxx_id: int, as_json: bool):
       """Command description."""
       with _get_client() as client:
           try:
               data = client.get_xxx(xxx_id)
           except Exception as e:
               print_error(f"Failed: {e}")
               sys.exit(1)
           if as_json:
               click.echo(json.dumps(data, indent=2, ensure_ascii=False))
               return
           # Rich table rendering...
   ```

3. **在 `cli.py` 注册命令**：
   ```python
   from .commands.content import xxx
   cli.add_command(xxx)
   ```

4. **添加测试**（在 `tests/test_cli.py` 和 `tests/test_client.py`）

---

## Testing

- **框架**: pytest + pytest-cov
- **运行**: `python -m pytest tests/ -v --cov=zhihu_cli`
- **命令测试**: `click.testing.CliRunner`
- **客户端测试**: `unittest.mock.patch`，Patch 目标 `zhihu_cli.client.ZhihuClient`（命令模块懒导入）
- **Fixtures**: `tmp_config_dir`（隔离配置目录）、`saved_cookies`（预写 cookie 文件）
- **标记**: `@pytest.mark.integration` 用于需要真实登录的测试，默认跳过

---

## Build & Publish

```bash
# 构建
pip install build twine
python -m build

# 检查
python -m twine check dist/*

# 上传到 PyPI
python -m twine upload dist/*
```

## Dependencies

| 包 | 用途 |
|----|------|
| `click>=8.0` | CLI 框架 |
| `requests>=2.28` | HTTP 客户端 |
| `rich>=13.0` | 终端美化输出 |
| `playwright>=1.40` | QR 码登录浏览器自动化 |
| `qrcode>=7.4` | QR 码生成 |
| `pytest>=8.3` | 测试框架（dev） |
| `ruff>=0.11.0` | Linter（dev） |
