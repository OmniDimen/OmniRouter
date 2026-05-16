# OmniRouter

OmniRouter 是一个本地运行的大模型 API 路由器。你可以把多个 OpenAI 协议兼容的上游 API 接入 OmniRouter，配置 Provider、模型和分组后，对外只使用一个统一的 OpenAI 兼容接口。

## 主要功能

- 统一 OpenAI 兼容入口：`/v1/chat/completions`
- 支持多个 Provider 和多个模型
- 支持模型分组，例如通用、代码、写作等
- 支持顺序轮询、随机轮询和权重配置
- 支持流式响应 `stream=true`
- 支持通过 `@模型名` 或请求体 `model` 字段指定模型
- 支持视觉模型标记，图片请求会跳过不支持视觉的模型
- 支持超时处理、重试和失败自动禁用
- 支持智能路由：根据对话内容自动选择模型分组
- 内置 Web 管理界面，可管理 Provider、模型、分组、设置和日志
- 启动后自动打开浏览器，并在仪表盘显示可直接使用的 API URL

## 运行环境

- Windows / macOS / Linux
- Python 3.11 或更高版本推荐

## 安装依赖

在项目目录中执行：

```bash
pip install -r requirements.txt
```

如果你的系统同时安装了多个 Python 版本，可以使用：

```bash
python -m pip install -r requirements.txt
```

## 启动

### Windows

双击运行：

```text
start.bat
```

或在命令行中执行：

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 9090
```

启动后程序会自动打开浏览器。也可以手动访问：

```text
http://127.0.0.1:9090
```

局域网内其他设备访问时，请使用仪表盘中显示的 LAN 地址，例如：

```text
http://你的局域网IP:9090
```

## 基本使用流程

1. 打开 OmniRouter 网页界面。
2. 在 Provider 页面添加上游服务商：
   - 名称：自定义，例如 OpenAI、硅基流动、OpenRouter
   - Base URL：上游 OpenAI 兼容接口地址，例如 `https://api.openai.com/v1`
   - API Key：该上游服务商的密钥
3. 在模型页面添加模型：
   - 选择 Provider
   - 填写上游模型 ID，例如 `gpt-4o`、`claude-sonnet-4-5` 等
   - 填写自定义名称，例如 `GPT4o`、`代码模型`
   - 如果模型支持图片输入，打开视觉支持
4. 在分组页面配置模型分组和权重。
5. 在仪表盘复制 API URL，填入你的客户端。
6. 客户端按 OpenAI Chat Completions 格式请求 OmniRouter。

## 对外 API

OmniRouter 对外暴露 OpenAI 兼容接口：

```text
POST http://你的IP:9090/v1/chat/completions
```

请求示例：

```bash
curl http://127.0.0.1:9090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [
      {"role": "user", "content": "你好，介绍一下你自己"}
    ],
    "stream": false
  }'
```

流式请求：

```json
{
  "model": "default",
  "messages": [
    {"role": "user", "content": "写一首短诗"}
  ],
  "stream": true
}
```

## 指定模型

OmniRouter 默认会根据设置执行智能路由或分组轮询。你也可以手动指定模型。

### 方式一：使用 `@模型名`

在最后一条用户消息开头写：

```text
@模型名 你的问题
```

例如：

```text
@GPT4o 帮我解释这段代码
```

如果 `GPT4o` 匹配到某个模型的自定义名称或上游模型 ID，OmniRouter 会直接使用该模型，并自动移除消息开头的 `@GPT4o `。

### 方式二：使用请求体 `model` 字段

如果请求体里的 `model` 字段匹配到某个模型的自定义名称或上游模型 ID，也会直接使用该模型。

优先级：

```text
@模型名 > model 字段 > 智能路由 / 默认分组轮询
```

## 分组和轮询

每个分组可以包含多个模型，并为每个模型设置权重。

例如一个分组中有：

```text
模型 A：权重 2
模型 B：权重 1
模型 C：权重 3
```

顺序轮询时，队列类似：

```text
A, A, B, C, C, C
```

随机轮询时，会基于权重生成队列后随机打乱。

权重为 `0` 表示该模型不会参与轮询，相当于在该分组内手动停用。

## 智能路由

开启智能路由后，OmniRouter 会使用你指定的路由模型，根据最近几轮对话内容判断应该使用哪个分组。

典型用法：

- 代码问题路由到“代码”分组
- 写作问题路由到“写作”分组
- 普通问答路由到“通用”分组

如果路由模型调用失败，OmniRouter 会回退到默认分组，不影响正常请求。

## 视觉请求

如果请求中包含图片，OmniRouter 会检查选中的模型是否支持视觉。

- 如果模型支持视觉：直接转发
- 如果模型不支持视觉：在当前分组中继续寻找支持视觉的模型
- 如果当前分组没有任何视觉模型：返回错误

## 超时、重试和自动禁用

设置页中可以配置：

- 请求超时时间
- 超时后的动作：报错、重试当前模型、轮询下一个模型
- 连续失败多少次后自动禁用模型
- 自动禁用多久后恢复

自动禁用状态保存在内存中，程序重启后会重置。

## 日志

日志页面会展示请求、路由、超时、重试、错误、自动禁用和自动恢复等事件。

日志保留最近 7 天，程序启动时会自动清理更早的日志。

## 数据和隐私

OmniRouter 默认使用项目根目录下的 SQLite 数据库：

```text
omnirouter.db
```

你配置的 Provider API Key 会保存在这个数据库中。请不要把自己的 `omnirouter.db` 发给别人。

程序还可能生成本地数据目录：

```text
data/
```

其中可能包含本机使用的 API Key 文件。请不要把 `data/` 目录发给别人。

如果要分享项目代码，建议只分享：

```text
backend/
frontend/
requirements.txt
start.bat
README.md
```

不要分享：

```text
omnirouter.db
data/
.env
__pycache__/
*.pyc
```

## 修改端口和数据库路径

默认端口是 `9090`。可以通过环境变量修改：

```bash
OMNIROUTER_PORT=9090
```

默认数据库路径是项目根目录下的 `omnirouter.db`。可以通过环境变量修改：

```bash
OMNIROUTER_DB_PATH=/path/to/omnirouter.db
```

Windows PowerShell 示例：

```powershell
$env:OMNIROUTER_PORT="9090"
$env:OMNIROUTER_DB_PATH="D:\\data\\omnirouter.db"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 9090
```

## 注意事项

- 这是本地部署工具，请不要直接暴露到公网。
- Provider API Key 当前以明文形式保存在本地 SQLite 数据库中。
- 如果要发给别人，请先删除 `omnirouter.db` 和 `data/`。
- 如果客户端和 OmniRouter 不在同一台设备上，请使用仪表盘显示的局域网 API URL。
