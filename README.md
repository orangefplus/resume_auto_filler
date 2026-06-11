# 📝 简历自动填写助手 (Resume Auto-Filler)

> 一个 **Chrome 扩展 + Python 后端 Qwen Agent** 的智能简历自动填写系统。
> 用户在任意招聘网站打开后，点击扩展图标 → 粘贴 Markdown 简历 + 选择文件 → 一键填写。

## ✨ 核心特性

- **零结构约束**：粘贴一份自由格式 Markdown 简历即可，Agent 自动抽取
- **多网站通用**：内置 CSS Selector + 标签/placeholder 识别，不绑定特定网站
- **规则 + LLM 双引擎**：常见字段（姓名/邮箱/手机）走精确规则，复杂字段由 Qwen 兜底
- **文件上传支持**：图片、PDF、Word 都能上传（DataTransfer 注入，不依赖文件系统 API）
- **本地运行**：简历数据全程不出本机，隐私可控
- **实时反馈**：侧栏显示每步执行结果与未匹配字段

## 🏗 架构

```
┌──────────────────┐         ┌──────────────────┐
│  Chrome 扩展     │  HTTP   │  FastAPI 后端    │
│  (Side Panel)    │ ──────► │  + Qwen Agent    │
│  抓 DOM / 注入值 │         │  生成 FillPlan   │
└──────────────────┘         └──────────────────┘
                                       │
                                       ▼
                              DashScope Qwen-Plus
```

## 📦 目录结构

```
resume_auto_filler/
├── backend/                    # FastAPI 后端
│   ├── main.py
│   ├── config.py
│   ├── models/                 # LLM 客户端 + Pydantic schemas
│   ├── agent/                  # LangGraph 编排 + prompts + tools
│   └── services/               # 解析器 / 分析器 / 规划器
├── extension/                  # Chrome 扩展 (MV3)
│   ├── manifest.json
│   ├── sidepanel.{html,js,css}
│   ├── content.js
│   ├── background.js
│   ├── lib/
│   │   ├── dom_extractor.js
│   │   └── fill_executor.js
│   └── icons/
├── user_data/
│   └── profile_template.md     # 简历模板
├── tests/                      # 单元测试
├── config.yml                  # DashScope Key（gitignore）
├── config.yml.example
├── requirements.txt
├── start_backend.bat           # Windows 一键启动
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```powershell
# 克隆仓库
git clone https://github.com/<your-username>/resume_auto_filler.git
cd resume_auto_filler

# 复制配置
copy config.yml.example config.yml
# 编辑 config.yml，填入你的 DashScope API Key（在 https://dashscope.console.aliyun.com/apiKey 申请）

# 安装 Python 依赖（建议用 venv）
pip install -r requirements.txt
```

### 2. 启动后端

**方式 A：双击脚本（推荐）**

双击 `start_backend.bat`

**方式 B：命令行**

```powershell
cd resume_auto_filler
python -m backend.main
# 监听 http://127.0.0.1:8765
```

### 3. 安装 Chrome 扩展

1. 打开 Chrome，访问 `chrome://extensions/`
2. 打开右上角 **开发者模式**
3. 点击 **加载已解压的扩展程序**
4. 选择 `resume_auto_filler/extension/` 文件夹
5. 扩展图标出现在工具栏

### 4. 使用

1. 打开任意招聘页面（如 https://campus.10g1aks.com.cn）
2. 点击扩展图标，侧边栏打开
3. 复制 `user_data/profile_template.md` 的内容到简历文本框（或点击"加载模板"），按需修改
4. 点击"选择文件"上传你的简历 PDF、证件照等
5. 点击 **🚀 智能填写**
6. 等待几秒，页面自动填好；侧栏日志显示每步结果

## 🔌 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/api/health` | 健康检查，返回 `model` / `api_key_configured` |
| POST | `/api/fill`   | 接收 `{page_url, fields, user_markdown, file_names}`，返回 `{plan, profile_summary}` |

启动后访问 `http://127.0.0.1:8765/docs` 查看完整 API 文档。

## 🧠 工作原理

后端 LangGraph 编排：

```
parse_user_info → summarize_fields → plan_fill → END
       │                │                │
       ▼                ▼                ▼
  Qwen 抽结构化     纯字符串渲染     规则+LLM 双引擎
  Profile           字段表格         生成 FillPlan
```

**为什么规则 + LLM 兜底？**
- 规则零 token 成本、零延迟、稳定
- LLM 处理"标签文字与字段语义不直接匹配"的复杂情况

**字段匹配关键字示例**（`backend/services/fill_planner.py`）：

```python
PROFILE_FIELD_KEYWORDS = {
    "name": ["姓名", "名字", "name", "fullname", ...],
    "email": ["邮箱", "邮件", "email", ...],
    "phone": ["手机", "联系电话", "phone", "tel", ...],
    "self_evaluation": ["自我评价", "自我介绍", ...],
    ...
}
```

## 🧪 测试

```powershell
# 单元测试（无需 DashScope Key）
python tests/test_user_info_parser.py
python tests/test_fill_planner.py
python tests/test_page_analyzer.py
```

## ❓ 常见问题

**Q: 后端报 "api_key_configured: false"？**
A: 编辑 `config.yml`，把 `dashscope_api_key` 改成你的真实 Key。

**Q: 扩展点开没反应？**
A: 确认 `chrome://extensions/` 中扩展是"已启用"状态。也可点击工具栏扩展图标查看错误。

**Q: 字段没填上？**
A: 在侧栏日志查看"未匹配字段"列表，可能原因：
- 简历 Markdown 里没写该字段
- 页面标签文字与规则不匹配（可在 [fill_planner.py](backend/services/fill_planner.py) 增加关键字后提交 PR）

**Q: 文件上传没生效？**
A: 招聘网站的 file input 可能有特殊的 onChange 回调。我们已尽量触发标准事件，少数网站可能需要点击上传按钮手动确认。

**Q: 支持哪些网站？**
A: 理论上所有标准 HTML 表单都支持。SPA 框架（React/Vue）也能识别。

## 🔒 隐私

- 简历数据从浏览器侧栏 → 后端 → 大模型 API 全程经过本地网络或 DashScope 公网
- 默认绑定 `127.0.0.1`，仅本机可访问
- 不写任何云端数据库

## 📜 License

MIT
