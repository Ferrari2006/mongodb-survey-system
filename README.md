# MongoDB 问卷系统

数据管理系统课程项目。系统支持账号管理、问卷编辑、条件跳转、填写进度、答卷提交和统计，并提供题库共享、历史版本及跨问卷统计。

后端使用Flask和PyMongo，前端为原生HTML/CSS/JavaScript，业务数据保存在MongoDB。前端无需构建，应用运行不需要AI API Key。

## 功能

| 模块 | 功能 |
|---|---|
| 账号与权限 | 注册、登录、退出；问卷管理按创建者隔离，密码保存带盐哈希 |
| 问卷编辑 | 标题、说明、匿名与重复填写设置、截止时间；单选、多选、文本和数字题 |
| 校验与跳转 | 必答、选项数量、文本长度、数字范围和整数限制；按配置计算答题路径 |
| 发布与填写 | 分享链接、发布冻结、截止与关闭；已确认进度保存和恢复，提交时后端重新校验 |
| 答卷与统计 | 匿名展示、重复控制、请求重试防重；整卷和单题统计 |
| 题库与版本 | 新建题库、保存和复用题目、指定账号共享、工作稿、历史版本、分支及恢复 |
| 使用追踪 | 查看本人问卷的引用位置和版本；其他账号的引用仅显示数量 |
| 跨问卷统计 | 按来源版本及实际定义分组，统计选项次数、数字均值和分布，文本回答分页 |

发布后的问卷保持原题目内容。题库更新不会自动改动已导入的问卷。共享题目授予读取和使用权，接收者不能编辑源题，也不能因此读取他人的问卷或答卷。

## 本地运行

需要Python 3.10及以上和可连接的MongoDB。已验证环境：Python 3.13.7、MongoDB 6.0.1、Flask 3.1.2、PyMongo 4.18.1。依赖版本见[requirements.txt](requirements.txt)。

先启动MongoDB，再在仓库根目录执行：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:MONGO_URI = "mongodb://127.0.0.1:27017/"
$env:MONGO_DB = "mongodb_survey_course"
.\.venv\Scripts\python.exe run.py
```

打开 http://127.0.0.1:5050，注册账号后登录。已有依赖环境可直接执行 `python run.py`。

| 变量 | 默认值 | 用途 |
|---|---|---|
| MONGO_URI | mongodb://127.0.0.1:27017/ | 数据库连接地址 |
| MONGO_DB | mongodb_survey_course | 应用数据库名称 |
| PORT | 5050 | 本地服务端口 |
| TEST_MONGO_URI | mongodb://127.0.0.1:27017/ | 自动化测试数据库服务器 |

[.env.example](.env.example)提供配置示例；程序读取进程环境变量，不自动加载.env。初始化会创建缺少的集合和索引，不清空现有数据，也不覆盖已有验证器。服务绑定本机地址，未进行公网部署或压力测试。

从早期“账号与草稿”版本升级时，先运行 `python scripts/migrate_drafts.py`，扩展已知验证器并补齐默认设置。完整第一阶段升级到第二阶段无需清空数据库。旧服务需重启后加载新增接口。

本机快捷启动可使用start.ps1，它依赖同级lab1的MongoDB启动脚本；其他机器使用上述标准步骤。可选演示脚本 `python scripts/seed_demo.py` 通过HTTP接口生成测试账号和一份四题问卷，输出登录信息及分享链接。修改端口时传入 `--base http://127.0.0.1:端口`。

## 数据库设计

当前使用七个集合，完整字段与约束见[Schema](database/schema-stage2.json)，初始化和索引见[backend/database.py](backend/database.py)。

| 集合 | 主要字段 | 作用与组织方式 |
|---|---|---|
| users | _id、username、password_hash、created_at | 账号与密码哈希 |
| sessions | _id、user_id、expires_at | 令牌摘要、用户引用和过期时间 |
| surveys | owner_id、title、status、questions、revision、schema_version | 题目、选项、校验和跳转规则嵌入问卷；来源题另记source |
| fill_progress | survey_id、user_id、survey_revision、revision、answers、request_id | 每账号每问卷一份有效进度，与正式答卷分开 |
| responses | survey_id、user_id、anonymous、submission_key、request_id、answers、path、created_at | 每次提交独立保存，answers嵌入题目ID和回答值 |
| question_banks | owner_id、title、description、created_at | 题库分组及所有者 |
| library_questions | owner_id、bank_id、shared_with、working_copy、versions、current_version、revision | 题目权限、工作稿与不可变历史版本 |

ID采用字符串，时间使用BSON Date。revision是整数并发修订号，题库版本使用独立字符串ID。题目随问卷一起读取，因此保留嵌入副本；答卷持续增长，独立存储。题库历史与当前指针同文档条件更新，每题最多100个已提交版本。

第一阶段五集合设计见[数据库与系统设计](docs/数据库与系统设计.md)；第二阶段的扩展理由、版本语义及权限范围见[实施设计](第二阶段/实施设计-2026-10-23.md)。[database/schema.json](database/schema.json)保留第一阶段结构。

## API

接口前缀为/api，使用JSON。除健康检查、注册和登录外，需要 `Authorization: Bearer <token>`。问卷管理接口校验所有者；共享题目的读取与导入按共享名单授权。

| 模块 | 主要接口 |
|---|---|
| 账号 | /auth/register、/auth/login、/auth/logout、/auth/me |
| 问卷 | /surveys、/surveys/{sid}、/surveys/{sid}/questions |
| 发布与关闭 | /surveys/{sid}/publish、/surveys/{sid}/close |
| 填写与进度 | /public/surveys/{sid}及其/evaluate、/progress、/responses |
| 单卷统计 | /surveys/{sid}/statistics、/surveys/{sid}/questions/{qid}/statistics |
| 答卷列表 | /surveys/{sid}/responses |
| 题库 | /banks、/banks/{bid}、/library/questions |
| 题目版本与共享 | /library/questions/{lid}及其/restore、/sharing |
| 导入与跨卷查询 | /surveys/{sid}/library-import、/library/questions/{lid}/usage、/library/questions/{lid}/statistics |

上表为分组摘要。35个接口的完整路径、方法、输入、响应及错误码见[基础API](docs/API说明.md)和[题库API](第二阶段/API与测试说明.md)。

## 测试与检查

```powershell
.\.venv\Scripts\python.exe tests/run_tests.py
.\.venv\Scripts\python.exe scripts/check_stage2.py
```

自动化测试使用真实MongoDB，创建随机survey_test_数据库并在结束后清理。请勿使用Python的-O参数，测试依赖assert。最近一次完整运行通过52项，结果保存在[stage2-latest.json](tests/results/stage2-latest.json)。其中包括第一阶段38项回归，以及题库版本、权限、并发、旧问卷保护、数字分布和文本分页等14项测试。

浏览器检查覆盖题库创建、工作稿、版本提交与恢复、旧版本导入、引用位置、数字分布、文本翻页和390px宽度布局，记录见[stage2-browser.json](tests/results/stage2-browser.json)。测试范围和输入输出见[API与测试说明](第二阶段/API与测试说明.md)。尚未进行大规模性能和全浏览器兼容性验证。

2026-10-28另完成[双账号连续验收](tests/results/stage2-acceptance.json)和[新环境复现](tests/results/stage2-reproduction.json)。独立源码副本在新虚拟环境安装并启动，两个浏览器账号走通共享、导入、发布填写、改版、撤销和恢复。复现环境的完整依赖版本保存在结果JSON中。

check_stage2.py检查Schema、API、保存的测试结果及报告文件是否一致，不重新执行业务测试。启动环境可用 `python scripts/check_environment.py` 检查；未启动MongoDB时可加--skip-mongo。第一阶段38项原始记录在[latest.json](tests/results/latest.json)，旧材料检查脚本check_submission.py适用于第一阶段提交快照。

## 文档与报告

| 内容 | 入口 |
|---|---|
| 第二阶段需求覆盖 | [需求实现与验收对应](第二阶段/需求实现与验收对应.md) |
| 第二阶段设计 | [实施设计](第二阶段/实施设计-2026-10-23.md) |
| 第二阶段报告 | [正文](第二阶段/第二阶段完成报告.md)、[PDF](第二阶段/提交材料/2026_ECNU_PJ1_2_温正泽.pdf)、[Word](第二阶段/提交材料/2026_ECNU_PJ1_2_温正泽-可编辑.docx)、[可编辑网页](第二阶段/提交材料/2026_ECNU_PJ1_2_温正泽-可编辑.html) |
| 第一阶段报告 | [正文](reports/第一阶段完成报告.md)、[PDF](第一阶段/提交材料/AI过程修订版/2026_ECNU_PJ1_1_温正泽.pdf) |
| 基础功能操作 | [操作与演示](docs/操作与演示.md) |
| AI使用记录 | [ai_logs](ai_logs/)，包含实际需求引导、问题、修正与测试依据 |

第二阶段报告已整理为8页，包含版本管理与跨卷统计的实际页面截图，提交入口见[提交说明](第二阶段/提交材料/提交说明.md)。旧草稿保留在报告草稿目录。第一阶段报告保留已提交版本。

## 提交材料

两阶段共用本仓库。第一阶段提交快照为stage1-submission-20261023（0cdfefd）；第二阶段在main上继续开发。仓库为公开仓库。

GitHub保存可运行的前后端、配置说明、README、Schema、系统设计、API、测试用例和结果，以及AI使用说明。水杉上传项目完成报告PDF，仓库链接放在报告最前面。

| 阶段 | 报告文件名 | 截止时间（北京时间） |
|---|---|---|
| 第一阶段 | 2026_ECNU_PJ1_1_温正泽.pdf | 2026-10-23 00:00 |
| 第二阶段 | 2026_ECNU_PJ1_2_温正泽.pdf | 2026-10-30 00:00 |

第二阶段应在10月29日结束前提交，正式PDF已按规定名称保存。完整规则见[网页提交要求](docs/网页提交要求.md)。仓库不保存真实凭据、本地数据库文件或未脱敏业务数据。
