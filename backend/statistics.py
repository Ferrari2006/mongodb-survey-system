"""Statistics use real MongoDB aggregation, not cached sample outputs."""


def statistics(db, survey, qid=None):
    questions = survey["questions"]
    if qid:
        questions = [q for q in questions if q["id"] == qid]
    result = []
    for q in questions:
        base = [{"$match": {"survey_id": survey["_id"]}}, {"$unwind": "$answers"},
                {"$match": {"answers.question_id": q["id"]}}]
        count = list(db.responses.aggregate(base + [{"$count": "n"}]))
        item = {"question_id": q["id"], "title": q["title"], "type": q["type"],
                "answer_count": count[0]["n"] if count else 0}
        if q["type"] in ("single", "multiple"):
            stages = [{"$unwind": "$answers.value"}] if q["type"] == "multiple" else []
            counts = {r["_id"]: r["count"] for r in db.responses.aggregate(base + stages + [
                {"$group": {"_id": "$answers.value", "count": {"$sum": 1}}}])}
            item["options"] = [{**o, "count": counts.get(o["id"], 0)} for o in q["options"]]
        else:
            item["values"] = [r["value"] for r in db.responses.aggregate(base + [
                {"$project": {"_id": 0, "value": "$answers.value"}}])]
            if q["type"] == "number":
                average = list(db.responses.aggregate(base + [{"$group": {"_id": None, "average": {"$avg": "$answers.value"}}}]))
                item["average"] = average[0]["average"] if average else None
        result.append(item)
    return {"survey_id": survey["_id"], "response_count": db.responses.count_documents({"survey_id": survey["_id"]}),
            "counting_unit": "submitted_response", "questions": result}
