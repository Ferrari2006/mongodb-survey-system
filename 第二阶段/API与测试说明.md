# 第二阶段 API 与测试

沿用第一阶段 Flask、PyMongo、原生网页和 Bearer 会话。全部新增 API 需要登录，JSON 请求；输入错误400、无权或不存在404、修订冲突409。接口返回完整版本ID，不使用界面中的8位缩写作为请求ID。题库列表及题目列表每页20条。

## 新增接口

下表路径相对于 /api，原有23个接口见 docs/API说明.md。

| 方法 | 路径 | 输入 | 输出与权限 |
|---|---|---|---|
| GET | /banks | page | 本人题库 items、total、page |
| POST | /banks | title、description可选 | 201 题库对象 |
| PATCH | /banks/{bid} | title或description | 本人题库修改结果 |
| GET | /library/questions | scope=mine/shared、page、bank_id可选 | 题目摘要，不返回工作稿；共享题不返回所属私有题库 |
| POST | /library/questions | bank_id、question；或bank_id、survey_id、question_id | 201 item与jumps_removed，保存题目及首个不可变版本 |
| GET | /library/questions/{lid} | 无 | 本人或获共享的题目版本；工作稿和共享名单仅作者可读 |
| PATCH | /library/questions/{lid} | revision、question可选、create_version、base_version可选、bank_id可选 | 仅作者修改；false保存工作稿，true生成版本；可调整所属题库 |
| POST | /library/questions/{lid}/restore | revision、version | 仅作者；新增恢复版本，返回完整题目 |
| PUT | /library/questions/{lid}/sharing | revision、usernames数组 | 仅作者；替换共享名单，不存在的账号拒绝；空数组撤销 |
| POST | /surveys/{sid}/library-import | revision、library_id、version、question_id | 本人草稿问卷加入指定版本副本，返回问卷 |
| GET | /library/questions/{lid}/usage | 无 | 仅题主；本人位置、获授权外部名称及题号；未授权部分只计数，不返回链接或账号 |
| GET | /library/questions/{lid}/statistics | scope=mine/all、version可选、page为文本页码 | 默认本人；all仅题主汇总获授权的跨用户问卷，不返回使用位置ID和文本原文；本人文本每页20条，数字含分布 |

| PATCH | /surveys/{sid}/library-permissions/{qid} | revision、usage布尔、statistics布尔 | 仅问卷作者；设置或撤回该来源题的两项授权，支持已发布问卷；不改变题目或答卷，revision条件更新；全卷汇总越权403 |

## 版本语义与统计口径

revision是并发控制修订号；versions[].id是题目业务版本。工作稿不供他人读取、不被问卷引用。更新工作稿不会变更现有版本内容；提交和恢复都追加版本。base_version记录分支父版本，restored_from记录恢复来源。版本达到100时拒绝继续追加，后续可拆分集合。

题目导入问卷后即为独立副本。问卷内可继续编辑来源题，但source元数据由服务器保留，客户端不能伪造。跳转指向本卷的局部题号，所以入库时明确去除跳转并提示，导入后重新配置。

统计按“来源版本ID + 实际定义摘要”分组。改选项、标题、必答或约束的本卷副本分开计算，不自动假定语义等价。跳转配置不影响定义摘要。分母为已提交答卷中的该题有效作答次数，空答和跳过题不计；同一题在两份问卷中各作答一次算两次。多选每项占比除以该题作答次数，合计可能大于100%。数字0参与均值，空组均值为null。共享题不授予查看别人答卷的权限。页面版本缩写仅作展示。

数字组增加minimum、maximum、distribution和distribution_method；distribution每项包含minimum、maximum、count及upper_inclusive。MongoDB自动划分最多10个区间，左闭右开、末项右闭，空组为空数组；它不是固定年龄段。文本组增加page与page_size=20，values仅当前页；answer_count仍为全部有效文本数。page对本次所有文本分组一致，排序为created_at、答卷_id，界面按每组总量控制翻页。

## 实际测试记录

运行 `python tests/run_tests.py`，结果写入tests/results/stage2-latest.json。最近一次完整运行通过58项，其中第一阶段38项回归、第二阶段20项扩展。第一阶段原始结果保留在tests/results/latest.json。以下为题库主要用例，对应tests/test_library.py。

| 场景 | 输入与步骤 | 预期及实测 |
|---|---|---|
| 工作稿与分支恢复 | 保存工作稿、提交、从首版分支、恢复首版 | 原版本不变，父版本与恢复来源准确；通过 |
| 旧问卷保护 | 导入首版并发布、改题库，再导入旧版 | 已发布内容不变、旧版仍可用；通过 |
| 共享和撤销 | 共享给另一个真实测试账号、尝试修改、导入、撤销 | 可导入不可改原题；撤销后不能再读，已导入副本保留；通过 |
| 本卷改题 | 导入相同版本到两卷，一卷修改选项 | 来源保留、跨卷统计分成两组；通过 |
| 跨卷数字统计 | 两卷同题答案0、8 | 作答2次、平均4；通过 |
| 多版本统计 | 两版同题各有答卷，并筛选首版 | 版本不混算；通过 |
| 并发修改 | 两请求携带相同revision提交 | 仅一个200，另一个409，不丢历史；通过 |
| 入库与题库管理 | 问卷题有跳转、保存到题库、移动题库；对象型ID | 明确去除跳转、分组准确、非法ID拒绝；通过 |
| 多选统计 | 一次作答选择两项 | 作答分母1、每项次数1；通过 |

补充边界用例覆盖数字分布与选答空值、空数字组、23条文本分页、共享双方答卷隔离，以及非法导入和未知共享对象不落库，均已通过。

浏览器脚本tests/browser_library.js验证注册登录、题库创建、工作稿、提交与恢复、旧版导入、使用位置、数字分布、文本翻页和390px宽度布局。数字分布以0与8检查，文本翻页用21条回答检查。前置答卷通过API准备，页面操作由Playwright执行，结果保存在tests/results/stage2-browser.json，未发现页面JavaScript异常。

自动测试使用随机survey_test_数据库，浏览器使用独立测试数据库，原业务库不受影响。环境问题和脚本修正过程见[AI开发记录](../ai_logs/2026-10-23-stage2-review.md)。

## 运行与检查

沿用README的MongoDB与Python环境，执行 python run.py。新建两个集合与索引为增量操作，旧五集合和历史业务数据不需要清空。完整当前结构为 database/schema-stage2.json；database/schema.json保持第一阶段快照。

执行 `python scripts/check_stage2.py` 核对集合导出、全部API、真实测试记录、页面结果及第一阶段报告不变。原scripts/check_submission.py用于第一阶段提交快照；第二阶段使用check_stage2.py检查当前工作树。

第二阶段报告已生成正式PDF与可编辑源，入口为提交材料目录。2026-10-28独立环境执行52项通过；10月29日授权扩展后完整执行58项通过，另完成双账号连续浏览器验收与独立源码启动复现。记录在stage2-latest.json、stage2-acceptance.json和stage2-reproduction.json。已提交的阶段一PDF保持原样。

## 跨用户授权协议

来源题导入后默认不对外开放。问卷管理页的题目卡片有两个独立复选框：向题主公开本卷名称和使用位置、允许题主汇总该题统计。设置与撤回都调用library-permissions接口；usage与statistics不能互相替代。授权绑定来源题ID，旧问卷缺失library_permissions时为关闭。发布后仅更新授权元数据和管理修订号，不改变questions、responses或题目版本。

题主请求statistics?scope=all时纳入本人及获得statistics授权的引用；共享接收者不能请求all。数字和选项只返回分组聚合，文本只返回作答次数；全部范围移除instances，不提供账号、链接或原始答卷。usage接口对usage授权的位置返回名称、题号及版本，用稳定usage_ref区分外部问卷，不返回其survey_id。撤回影响后续请求，不承诺擦除已经查看过的结果或为并发请求提供事务隔离。

新增六项实际用例覆盖授权及撤回、两账号0与8汇总均值4、默认不授权、文本原文不泄露、权限/类型/旧修订号拒绝、两类授权独立。对应tests/test_library.py中的test_explicit_usage_grant_and_revoke_without_question_changes等六项。浏览器通过真实复选框完成授权和撤回，初次脚本读取旧DOM过早，改为等待旧结果移除后再次通过；当前结果为58项回归及双账号验收。
