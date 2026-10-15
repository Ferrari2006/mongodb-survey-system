# MongoDB 问卷系统课程项目

数据管理系统课程大作业：使用 MongoDB 实现支持账号、问卷管理、题目校验、条件跳转、答卷提交和统计的问卷系统。

当前状态：已实现初始需求对应的注册登录、本人问卷管理、题型和校验、可配置跳转、发布与截止/关闭、分享填写、匿名/重复控制及统计。29项真实MongoDB自动化测试通过，并完成浏览器流程。文件未明确的规则已在[需求核对](docs/需求与进度.md)说明，后续课堂补充可继续调整。

## 两阶段提交

网页规定：GitHub保存可运行的前后端、测试和README；水杉只上传项目完成报告PDF，仓库链接放报告最前面。第一阶段文件名为2026_ECNU_PJ1_1_温正泽.pdf，截止2026-10-23 00:00；第二阶段为2026_ECNU_PJ1_2_温正泽.pdf，截止2026-10-30 00:00。详见[网页提交要求](docs/网页提交要求.md)。

- 第一阶段：完成初始需求对应的可运行系统、数据库设计、API 和关键逻辑说明、测试用例、AI 使用日志及报告。
- 第二阶段：根据后续需求变更，在第一阶段代码上修改，保留核心结构、旧数据及主要功能，记录兼容性处理和回归测试。
- 两阶段共用本仓库。第一阶段代码可保留为阶段一基线；用户验收并准备提交时再标记stage1-submission。第二阶段完成后标记stage2-submission。

## 当前文件

- `大作业一.docx`：课程要求。
- `第一阶段/大作业一第一阶段.docx`：第一阶段提供的要求，当前核对正文与总要求一致。
- `skills/mongodb-course-project/`：开发和学习辅助规范，包含需求基线、AI 记录及不同读者的表达规则；不是项目完成报告。
- `ai_logs/`：真实 AI 协作记录，从已有可核实的工作开始记录。

目录包括backend、frontend、database、tests、docs、reports、ai_logs和scripts。Schema与索引以backend/database.py为准，database/schema.json是导出结构。第二阶段需求尚未收到。

## 本地运行

需要 Python 3.10或以上和可连接的 MongoDB（本机验证版本为Python 3.13.7、MongoDB 6.0.1）。从仓库根目录执行：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:MONGO_URI = "mongodb://127.0.0.1:27017/"
$env:MONGO_DB = "mongodb_survey_course"
.\.venv\Scripts\python.exe run.py
```

浏览器打开 http://127.0.0.1:5050，自行注册账号后创建问卷。MongoDB须先启动；应用不会自动启动或安装数据库，也不会创建内置管理员账号。已有安装依赖的Python环境可直接运行 `python run.py`。

本机也可执行start.ps1，它使用已安装的Python或项目虚拟环境，并在需要时调用同级lab1的已有MongoDB启动脚本。该快捷方式依赖本机课程目录；其他机器使用上述标准步骤。

如曾运行“账号与草稿”旧版本，在同一MONGO_DB上先执行python scripts/migrate_drafts.py。该脚本只扩展已知validator和补默认设置，不删除旧问卷；新安装的数据库无需迁移。勿直接修改数据库跳过验证。

可选演示：应用启动后执行python scripts/seed_demo.py，会通过真实HTTP接口创建合成创建者/填写者及一份四题问卷，控制台显示本次账号密码与链接，不创建内置生产账号。修改端口时加--base http://127.0.0.1:端口。

`.env.example` 只展示配置变量，本应用不自动读取.env文件。可通过PORT修改端口。初始化会创建当前缺少的集合和索引，不清空现有数据，不自动覆盖已有validator。应用运行不需要任何AI API Key。

## 测试与设计资料

### 技术组成与版本

后端为 Python Flask + PyMongo，前端为原生 HTML/CSS/JavaScript，数据库为 MongoDB。已有验证环境为 Python 3.13.7、MongoDB 6.0.1、Flask 3.1.2、PyMongo 4.18.1；Python 依赖以 requirements.txt 为准。前端不需要 Node.js 构建。启动、端口和数据库配置见上文。

### 数据库结构摘要

本系统使用五个 MongoDB 集合，集合不等同于关系数据库表。

| 集合 | Schema 主要字段 | 作用和组织方式 |
|---|---|---|
| users | _id、username、password_hash、created_at | 用户账号；密码保存带盐哈希 |
| sessions | _id、user_id、expires_at | 可撤销会话；令牌摘要作为 ID，引用用户 |
| surveys | _id、owner_id、title、description、status、allow_anonymous、allow_repeat、deadline、questions、revision、schema_version、created_at、updated_at、published_at | 问卷引用创建者；questions 数组嵌入题目、options、validation、jumps |
| fill_progress | _id、survey_id、user_id、survey_revision、revision、answers、anonymous、request_id、updated_at | 每账号每问卷一份有效进度，保存已确认答案；不进入统计 |
| responses | _id、survey_id、user_id、anonymous、submission_key、request_id、survey_revision、answers、path、created_at | 每次提交独立文档，引用问卷及用户；answers 嵌入题目 ID 与回答值 |

ID 使用字符串，时间使用 BSON Date，版本为整数。题目随问卷读取所以嵌入，答卷持续增长所以单独保存；用稳定 ID 关联答案，避免依赖可变文案。完整字段、约束、索引与嵌套取舍见[数据库设计](docs/数据库与系统设计.md)、[Schema](database/schema.json)及初始化实现 backend/database.py。

### API 摘要

接口前缀为 /api，JSON 请求；除健康检查、注册、登录外均须 Bearer token，管理操作须属于本人。完整输入、输出、错误码见[API说明](docs/API说明.md)。

| 方法 | 路径（省略 /api） | 用途 |
|---|---|---|
| POST | /auth/register、/auth/login、/auth/logout | 注册、登录、退出 |
| GET | /auth/me | 当前用户 |
| GET / POST | /surveys | 本人列表 / 创建草稿 |
| GET / PATCH | /surveys/{sid} | 读取 / 编辑本人草稿 |
| POST | /surveys/{sid}/questions | 添加题目 |
| PUT / DELETE | /surveys/{sid}/questions/{qid} | 编辑 / 删除题目 |
| POST | /surveys/{sid}/questions/{qid}/validate | 单题校验预览 |
| POST | /surveys/{sid}/publish、/surveys/{sid}/close | 发布、关闭 |
| GET | /public/surveys/{sid} | 登录后读取分享问卷 |
| POST | /public/surveys/{sid}/evaluate | 按答案计算有效路径与下一题 |
| GET / PUT | /public/surveys/{sid}/progress | 读取 / 乐观版本保存本人的填写进度 |
| POST | /public/surveys/{sid}/responses | 校验路径并保存答卷 |
| GET | /surveys/{sid}/statistics | 整卷统计 |
| GET | /surveys/{sid}/questions/{qid}/statistics | 单题统计 |
| GET | /surveys/{sid}/responses | 本人问卷脱敏答卷列表 |

### 测试证据与课堂补充

tests/ 保存自动化与浏览器测试，docs/测试说明.md 列出步骤、输入和期望，tests/results/latest.json 保存已有自动化实际结果，tests/results/浏览器检查.md 保存页面实际结果。详细证据不以“计划测试”代替“测试通过”。

2026-10-16 助教补充强调后端、Schema、AI 引导与可扩展性，详见[补充核对与交付清单](docs/课堂补充核对-2026-10-16.md)。随后新增填写进度保存与恢复，29项真实MongoDB自动化测试通过，并实际验证浏览器刷新、分支切换和统计。

```powershell
.\.venv\Scripts\python.exe tests/run_tests.py
```

测试须连接MongoDB，会创建随机测试库并在结束时清理，结果写入 `tests/results/latest.json`；不要用Python的-O参数。手工测试步骤、API和设计理由分别见：

- [数据库与系统设计](docs/数据库与系统设计.md)
- [API说明](docs/API说明.md)
- [测试说明](docs/测试说明.md)
- [需求核对与实现约定](docs/需求与进度.md)
- [操作与演示](docs/操作与演示.md)
- [第一阶段完成报告](reports/第一阶段完成报告.md)及[可打印HTML](reports/第一阶段完成报告.html)

可选重导出报告HTML需mistune，执行python scripts/export_materials.py；应用运行和自动化测试不依赖它。HTML可直接用浏览器打印为PDF。

## 提交材料

两个阶段均须提供可运行代码及配置说明、MongoDB Schema、系统和数据库设计、API 与关键逻辑说明、测试步骤和实际结果、完整报告以及真实 AI 使用说明。设计决定及未确认事项须注明依据。

当前测试覆盖创建、题目、跳转、校验、提交、统计及权限/并发/兼容性。报告和真实AI日志已整理；尚未进行公网部署或压力测试，尚未创建最终提交标签。

仓库当前采用私有权限；向教师提交前应确认教师有访问权限及课程的提交要求。真实凭据、本地数据库文件和未脱敏用户数据不提交。
