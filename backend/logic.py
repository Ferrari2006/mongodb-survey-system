"""Data-driven forward branching and server-side path validation."""
from backend.validation import identifier, number, require, validate_answer


def validate_jumps(questions, publishing=False):
    positions = {q["id"]: i for i, q in enumerate(questions)}
    for i, q in enumerate(questions):
        for rule in q.get("jumps", []):
            require(isinstance(rule, dict) and set(rule) == {"op", "value", "target"}, "跳转须包含op、value、target")
            op, value, target = rule["op"], rule["value"], rule["target"]
            require(isinstance(op, str) and isinstance(target, str), "跳转操作和目标须为文本")
            if target != "END":
                identifier(target, "跳转目标题目ID")
                if target in positions:
                    require(positions[target] > i, "跳转只能指向后续题目，不能回跳或循环")
                elif publishing:
                    require(False, "跳转目标题目不存在")
            if q["type"] == "single":
                require(op == "eq" and isinstance(value, str) and value in {o["id"] for o in q["options"]}, "单选跳转须使用eq及合法选项ID")
            elif q["type"] == "multiple":
                require(op in ("any", "all") and isinstance(value, list) and value and all(isinstance(v, str) for v in value), "多选跳转须使用any或all及非空选项数组")
                require(len(value) == len(set(value)) and set(value) <= {o["id"] for o in q["options"]}, "多选跳转包含重复或非法选项")
            elif q["type"] == "number":
                require(op in ("eq", "lt", "lte", "gt", "gte") and number(value), "数字跳转操作或比较值不合法")
            else:
                require(False, "文本填空暂不设置跳转条件")


def next_id(questions, index, value):
    q = questions[index]
    if value is not None:
        for rule in q.get("jumps", []):
            op, expected = rule["op"], rule["value"]
            match = ((op == "eq" and value == expected)
                     or (op == "any" and bool(set(value) & set(expected)))
                     or (op == "all" and set(expected) <= set(value))
                     or (op == "lt" and value < expected)
                     or (op == "lte" and value <= expected)
                     or (op == "gt" and value > expected)
                     or (op == "gte" and value >= expected))
            if match:
                return rule["target"]
    return questions[index+1]["id"] if index+1 < len(questions) else "END"


def evaluate(questions, answers, complete=False):
    require(isinstance(answers, dict), "answers须为题目ID到答案的对象")
    by_id = {q["id"]: i for i, q in enumerate(questions)}
    require(set(answers) <= set(by_id), "答案包含未知题目")
    validate_jumps(questions, publishing=True)
    current = questions[0]["id"] if questions else "END"
    path, cleaned = [], []
    while current != "END":
        q = questions[by_id[current]]
        if current not in answers:
            if complete:
                require(False, f"尚未完成题目：{q['title']}；选答题请明确提交null")
            return {"complete": False, "next_question_id": current, "path": path, "answers": cleaned}
        path.append(current)
        value = validate_answer(q, answers[current])
        if value is not None:
            cleaned.append({"question_id": current, "value": value})
        current = next_id(questions, by_id[current], value)
    if complete:
        require(set(answers) <= set(path), "提交包含被跳过题目的答案，请重新确认答题路径")
    return {"complete": True, "next_question_id": "END", "path": path, "answers": cleaned}
