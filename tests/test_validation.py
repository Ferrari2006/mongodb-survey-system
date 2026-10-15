import unittest
from backend.validation import DomainError, question, validate_answer


class ValidationTests(unittest.TestCase):
    def test_number_boundaries(self):
        q = question({"id": "age", "title": "年龄", "type": "number", "required": True,
                      "validation": {"min": 0, "max": 120, "integer": True}})
        for value in (0, 120, 18):
            assert validate_answer(q, value) == value
        for value in (-1, 121, 1.5, True, "18", float("nan"), float("inf"), None, 10**1000):
            with self.subTest(value=value), self.assertRaises(DomainError):
                validate_answer(q, value)

    def test_text_limits(self):
        q = question({"id": "q1", "title": "姓名", "type": "text", "required": True,
                      "validation": {"min_length": 2, "max_length": 4}})
        assert validate_answer(q, "张三") == "张三"
        for value in ("一", "一二三四五", "  ", 3):
            with self.subTest(value=value), self.assertRaises(DomainError):
                validate_answer(q, value)

    def test_selection_constraints(self):
        options = [{"id": x, "label": x} for x in "abc"]
        q = question({"id": "q1", "title": "水果", "type": "multiple", "options": options,
                      "required": True, "validation": {"min_choices": 2, "max_choices": 2}})
        assert validate_answer(q, ["a", "c"]) == ["a", "c"]
        for value in (["a"], ["a", "b", "c"], ["a", "a"], ["a", "z"], [], "ab"):
            with self.subTest(value=value), self.assertRaises(DomainError):
                validate_answer(q, value)
        single = question({"id": "q2", "title": "选择", "type": "single", "options": options})
        assert validate_answer(single, "a") == "a"
        with self.assertRaises(DomainError):
            validate_answer(single, "d")

    def test_optional_empty(self):
        q = question({"id": "q1", "title": "选填", "type": "text", "validation": {"min_length": 2}})
        assert validate_answer(q, "") is None
        with self.assertRaises(DomainError):
            validate_answer(q, "a")
        for value in ([], {}, False):
            with self.subTest(value=value), self.assertRaises(DomainError):
                validate_answer(q, value)

    def test_invalid_question_definitions(self):
        samples = [
            {"id": "q1", "title": "测试", "type": "number", "validation": {"min": 9, "max": 2}},
            {"id": "q1", "title": "测试", "type": "text", "validation": {"min_length": 4, "max_length": 2}},
            {"id": "q1", "title": "测试", "type": "single", "options": [{"id": "a", "label": "A"}, {"id": "a", "label": "B"}]},
            {"id": "q1", "title": "测试", "type": "multiple", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "validation": {"min_choices": 3}},
            {"id": "q1", "title": "测试", "type": "text", "required": "yes"},
            {"id": "q1", "title": "测试", "type": "text", "jump": "q3"},
        ]
        for sample in samples:
            with self.subTest(sample=sample), self.assertRaises(DomainError):
                question(sample)
