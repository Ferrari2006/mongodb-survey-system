# 当前可用 API

基地址为 http://127.0.0.1:5050/api。请求体使用 application/json。除健康检查、注册和登录外，接口须带 Authorization: Bearer <登录返回的token>。前端通过同源请求调用。

错误统一为 `{"error":{"code":"...","message":"..."}}`。常见状态码：400输入非法，401未登录或过期，404资源不存在或无权访问，409重名或版本冲突，413请求过大，503数据库异常。日期响应采用 Flask 默认 HTTP 日期字符串，MongoDB 中保存 BSON Date。身份和所有权由服务端确定。

| 方法 | 路径 | 输入 | 成功响应 |
|---|---|---|---|
| GET | /health | 无 | 200，status和当前milestone |
| POST | /auth/register | username、password | 201，id、username |
| POST | /auth/login | username、password | 200，token、expires_at、username |
| GET | /auth/me | 无 | 200，当前用户，排除password_hash |
| POST | /auth/logout | 空对象 | 200，message；令牌立即失效 |
| GET | /surveys?page=1 | 页码1～10000，每页20条 | 200，items、page、total；仅当前用户 |
| POST | /surveys | title、可选description | 201，新建问卷对象，revision=1 |
| GET | /surveys/{sid} | 无 | 200，含questions的本人问卷 |
| PATCH | /surveys/{sid} | revision、可选title和description | 200，更新后的问卷 |
| POST | /surveys/{sid}/questions | revision、question | 200，更新后的问卷 |
| PUT | /surveys/{sid}/questions/{qid} | revision、完整question | 200，替换后的问卷；题目ID不可变 |
| DELETE | /surveys/{sid}/questions/{qid} | revision | 200，删除题目后的问卷 |
| POST | /surveys/{sid}/questions/{qid}/validate | value | 200，valid=true及标准化value；非法返回400 |

用户名3～32位，仅英文字母、数字、下划线，保存前转为小写；密码8～128位。登录有效期8小时，服务器保存令牌的SHA256摘要。接口不接受未经约定的字段。

## 添加多选题示例

```json
{
  "revision": 1,
  "question": {
    "id": "fruit", "title": "请选择两种水果", "type": "multiple", "required": true,
    "options": [{"id":"apple","label":"苹果"},{"id":"banana","label":"香蕉"},{"id":"orange","label":"橙子"}],
    "validation": {"min_choices":2,"max_choices":2}
  }
}
```

成功后 revision 变为2，下一次修改须携带2。旧版本请求返回409；客户端应重新读取并合并用户修改，不自动覆盖。

单选validation为空对象；文本使用min_length、max_length，默认0和5000；多选默认最少0、最多全部选项；数字使用min、max、integer，边界可省略。所有题型支持required。

## 校验预览示例

向多选题的validate接口发送 `{"value":["apple","banana"]}` 返回200；只选择一个或包含非法ID返回400。年龄题设置0～120且必须整数时，`{"value":120}` 返回200，`{"value":121}` 返回400。

此接口仅供创建者检查题目定义，**不会保存答卷**。发布、分享、答卷提交、匿名、重复填写及统计 API 尚未实现，不能把本表当作完整第一阶段接口清单。
