# 问卷系统 API

默认基地址 http://127.0.0.1:5050/api。请求体使用application/json。除health、register、login外均须Authorization: Bearer <token>。public表示分享填写用途，仍须登录。管理接口只允许创建者访问。

错误格式：{"error":{"code":"invalid_input","message":"说明"}}。400输入校验失败，401未登录，404无权/不存在/未开放，409重名/版本冲突/重复，410截止，413请求过大，503数据库异常。响应日期为Flask默认GMT字符串；截止时间输入为带时区ISO字符串。页码1～10000，每页20条。

| 方法 | 路径 | 输入 | 成功结果 |
|---|---|---|---|
| GET | /health | 无 | 200 status、milestone |
| POST | /auth/register | username、password | 201 id、username |
| POST | /auth/login | username、password | 200 token、expires_at、username |
| GET | /auth/me | 无 | 200 当前账号，排除密码哈希 |
| POST | /auth/logout | {} | 200 撤销令牌 |
| GET | /surveys?page=1 | 页码 | 200 items、page、total，仅本人 |
| POST | /surveys | title，可选description、allow_anonymous、allow_repeat、deadline | 201 草稿、revision=1 |
| GET | /surveys/{sid} | 无 | 200 含题目的本人问卷 |
| PATCH | /surveys/{sid} | revision、要修改的基本信息和设置 | 200 新版本草稿 |
| POST | /surveys/{sid}/questions | revision、question | 200 更新后的草稿 |
| PUT | /surveys/{sid}/questions/{qid} | revision、完整question | 200，ID不变 |
| DELETE | /surveys/{sid}/questions/{qid} | revision | 200 删除后的草稿 |
| POST | /surveys/{sid}/questions/{qid}/validate | value | 200 valid、标准化value；不保存答卷 |
| POST | /surveys/{sid}/publish | revision | 200 published；空问卷、无效目标、过去截止时间拒绝 |
| POST | /surveys/{sid}/close | revision | 200 closed |
| GET | /public/surveys/{sid} | 无 | 200 可填写的题目与设置，不含owner_id |
| POST | /public/surveys/{sid}/evaluate | answers | 200 complete、next_question_id、path、标准化answers |
| POST | /public/surveys/{sid}/responses | answers、request_id、可选anonymous | 201新答卷或同次重试200，id、message、replayed |
| GET | /surveys/{sid}/statistics | 无 | 200 response_count、counting_unit、questions |
| GET | /surveys/{sid}/questions/{qid}/statistics | 无 | 200 单题统计 |
| GET | /surveys/{sid}/responses?page=1 | 页码 | 200 脱敏答卷分页 |

用户名3～32位字母数字下划线、保存为小写；密码8～128位；会话8小时。所有权由服务端确定，客户端不能提交owner_id。revision是编辑时读取的整数版本，成功递增，旧版本409。

## 题目和跳转

题目含id、title、type、required、validation、jumps，选择题有options（id与label）。type为single/multiple/text/number。多选min_choices/max_choices，相同即恰好数量；文本min_length/max_length；数字min/max/integer。jumps默认空。

规则例：{"op":"eq","value":"no","target":"q4"}；多选使用any/all且value为非空选项ID数组；数字使用eq/lt/lte/gt/gte及有限数字。target为后续题ID或END。草稿可引用未来题，发布时检查存在。文本不提供条件跳转。

## 路径和提交示例

evaluate输入：{"answers":{"q1":"yes","q2":["library","canteen"],"q3":8,"q4":null}}。

从第一题解释，到未提供答案的题返回next_question_id，到END返回complete=true。选答跳过须明确提供null或多选空数组。预览不保存数据，提交重算全部有效路径。

提交输入：{"answers":{"q1":"no","q4":"建议"},"request_id":"客户端生成的独立UUID","anonymous":true}。

request_id为8～100字符，同次重试保持不变，再次填写使用新值。同问卷、同用户、同request_id仅保存一次；重试返回原答卷，不修改原内容，即使携带不同内容也不会覆盖。非法状态、截止、匿名未允许、路径或答案错误都拒绝。禁止重复时以唯一索引阻止再次提交，包括匿名填写。

匿名答卷管理接口不返回user_id、request_id、submission_key，respondent显示匿名；实名显示用户名。数据库内部保留身份关联。

关闭/截止与提交并发时，以surveys原子准入更新为界：关闭前已准入的请求允许随后保存，之后新请求拒绝。准入计数不是有效答卷数，统计只读responses。本地单节点不使用跨集合事务。

统计单选/多选返回options（id、label、count），零次也显示；文本/数字返回values，数字另含average。answer_count只算实际非空回答。当前全部填空内容一次返回，适用于课程规模。
