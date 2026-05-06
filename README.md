# HR 管理系统（演示版）

基于 Python + Flask + SQLite 的可运行 HR 自动化系统，采用简洁产品化界面风格。

## 核心功能

1. 面试安排自动化
2. 候选人状态通知自动化
3. 月度 HR 报表自动生成
4. 职位发布管理
5. 管理员安全体系（记住登录/修改密码/账号锁定）
6. CSV 导入候选人（模板下载 + 错误明细报告）
7. 列表统一分页、搜索、筛选、排序

## 快速启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 启动服务

```bash
python app.py
```

3. 访问地址

`http://127.0.0.1:5000`

## 管理员账号（演示）

- 用户名：`admin`
- 密码：`Admin@123`
- 连续输错 5 次后锁定 15 分钟
- 支持“记住登录（30天）”

## 候选人导入格式

- 文件类型：`.csv`
- 列头要求：`name,email,role,status`
- 其中 `status` 可选，留空时默认 `Applied`

示例：

```csv
name,email,role,status
张三,zhangsan@example.com,招聘专员,Applied
李四,lisi@example.com,HRBP,Interview Scheduled
```

- 导入模板下载：`/candidates/import-template`
- 导入错误报告下载：`/candidates/import-error-report`

## 页面

- 职位发布：`/jobs`
- 修改密码：`/account/password`
- HR 效率工具（日程 ICS、候选人触达、数据洞察）：`/automation`

## 时间格式

- 系统统一使用秒级时间格式：`YYYY-MM-DD HH:MM:SS`

## 数据存储

- SQLite 数据库：`hr_demo.db`
- 首次启动会自动初始化并写入演示数据

## DEEPSEEK_API_KEY（可选）

「HR 效率工具」中的候选人触达与高管报告使用 [DeepSeek](https://platform.deepseek.com/) 开放 API（与 OpenAI 兼容的 `chat/completions`）。

1. 复制 `.env.example` 为 `.env`（根目录与 `app.py` 同级）。
2. 写入：`DEEPSEEK_API_KEY=你的密钥`。
3. 可选：`DEEPSEEK_MODEL`（默认 `deepseek-chat`）、`DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com/v1`）。
4. 重启 `python app.py`。

CLI 脚本见 `hr_demos/candidate_touch_gemini.py`、`hr_demos/hr_insight_report_gemini.py`（同样读取 `DEEPSEEK_API_KEY`）。

##报错说明

Error Code: -102
URL: http://127.0.0.1:5000/
错误 -102 表示连接被拒绝，通常是 Flask 未在运行。
需要用时在项目根执行：
```
cd c:\CursorProgram`
`python app.py
```
并保持该窗口不要关。
