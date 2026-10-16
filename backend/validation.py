"""Pure validation functions; no database or HTTP dependencies."""

import math
import re


class DomainError(Exception):
    def __init__(self, message, status=400, code="invalid_input"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def require(condition, message):
    if not condition:
        raise DomainError(message)


def string(value, label, minimum=0, maximum=200):
    require(isinstance(value, str), f"{label}必须是文本")
    value = value.strip()
    require(minimum <= len(value) <= maximum, f"{label}长度须在 {minimum}～{maximum} 之间")
    return value


def identifier(value, label="标识"):
    require(isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value)),
            f"{label}须以英文字母开头，仅含字母、数字、下划线或连字符，最多64位")
    return value


def number(value):
    return type(value) in (int, float) and abs(value) <= 1e15 and math.isfinite(value)


def question(data):
    require(isinstance(data, dict), "题目必须是对象")
    allowed = {"id", "title", "type", "required", "options", "validation", "jumps"}
    require(not (set(data) - allowed), "题目包含未支持字段")
    kind = data.get("type")
    require(kind in ("single", "multiple", "text", "number"), "不支持的题型")
    required = data.get("required", False)
    require(type(required) is bool, "必答设置必须是布尔值")
    result = {"id": identifier(data.get("id"), "题目ID"),
              "title": string(data.get("title"), "题目标题", 1, 300),
              "type": kind, "required": required}
    options = data.get("options", [])
    require(isinstance(options, list), "选项必须是数组")
    if kind in ("single", "multiple"):
        require(2 <= len(options) <= 50, "选择题须有2～50个选项")
        cleaned = []
        for option in options:
            require(isinstance(option, dict) and set(option) == {"id", "label"}, "选项须包含id和label")
            cleaned.append({"id": identifier(option["id"], "选项ID"),
                            "label": string(option["label"], "选项文字", 1, 200)})
        require(len({o["id"] for o in cleaned}) == len(cleaned), "选项ID不能重复")
        result["options"] = cleaned
    else:
        require(not options, "填空题不应包含选项")

    rules = data.get("validation", {})
    require(isinstance(rules, dict), "校验配置必须是对象")
    fields = {"single": set(), "multiple": {"min_choices", "max_choices"},
              "text": {"min_length", "max_length"}, "number": {"min", "max", "integer"}}[kind]
    require(not (set(rules) - fields), "该题型包含不适用的校验字段")
    if kind in ("multiple", "text"):
        low, high = ("min_choices", "max_choices") if kind == "multiple" else ("min_length", "max_length")
        limit = len(options) if kind == "multiple" else 5000
        lo, hi = rules.get(low, 0), rules.get(high, limit)
        require(type(lo) is int and type(hi) is int and 0 <= lo <= hi <= limit,
                "数量或长度的上下限不合法")
        require(not required or hi >= 1, "必答题的上限不能为0")
        rules = {low: lo, high: hi}
    if kind == "number":
        require(type(rules.get("integer", False)) is bool, "整数限制必须是布尔值")
        require(all(number(rules[k]) for k in ("min", "max") if k in rules), "数字边界不合法")
        require(rules.get("min", -1e15) <= rules.get("max", 1e15), "数字最小值不能大于最大值")
        if rules.get("integer"):
            require(math.ceil(rules.get("min", -1e15)) <= math.floor(rules.get("max", 1e15)),
                    "当前数字范围内没有整数，请调整范围或取消整数限制")
    result["validation"] = rules
    jumps = data.get("jumps", [])
    require(isinstance(jumps, list) and len(jumps) <= 50, "跳转规则须为数组，最多50条")
    result["jumps"] = jumps
    return result


def validate_answer(q, value):
    """Validate one visited question. Path selection is intentionally separate."""
    kind, rules = q["type"], q["validation"]
    empty = value is None or value == "" or (kind == "multiple" and value == []) or (isinstance(value, str) and not value.strip())
    if empty:
        require(not q["required"], f"{q['title']}为必答题")
        return None
    if kind == "single":
        require(isinstance(value, str) and value in {o["id"] for o in q["options"]}, "单选答案不在选项中")
    elif kind == "multiple":
        require(isinstance(value, list) and all(isinstance(v, str) for v in value), "多选答案须为选项ID数组")
        require(len(value) == len(set(value)), "多选答案不能重复")
        require(set(value) <= {o["id"] for o in q["options"]}, "多选包含非法选项")
        require(rules["min_choices"] <= len(value) <= rules["max_choices"], "多选数量不符合限制")
    elif kind == "text":
        require(isinstance(value, str), "文本答案必须是字符串")
        value = value.strip()
        require(rules["min_length"] <= len(value) <= rules["max_length"], "文本长度不符合限制")
    else:
        require(number(value), "答案须为有限数字，绝对值不超过10^15")
        require(not rules.get("integer") or float(value).is_integer(), "答案必须为整数")
        require(rules.get("min", -1e15) <= value <= rules.get("max", 1e15), "数字不在允许范围内")
    return value
