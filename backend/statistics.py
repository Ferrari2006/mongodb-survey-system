"""Statistics use real MongoDB aggregation, not cached sample outputs."""


def statistics(db, survey, qid=None):
    questions = survey["questions"]
    if qid:
        questions = [q for q in questions if q["id"] == qid]
    ids = [q["id"] for q in questions]
    choice_ids = [q["id"] for q in questions if q["type"] in ("single", "multiple")]
    value_ids = [q["id"] for q in questions if q["type"] in ("text", "number")]
    number_ids = [q["id"] for q in questions if q["type"] == "number"]

    def answers_for(selected):
        return [{"$unwind": "$answers"}, {"$match": {"answers.question_id": {"$in": selected}}}]

    # All facets receive the same stream of response documents. Separate queries
    # could otherwise combine an old denominator with newly submitted answers.
    facets = {
        "total": [{"$count": "n"}],
        "counts": answers_for(ids) + [{"$group": {"_id": "$answers.question_id", "n": {"$sum": 1}}}],
        "options": answers_for(choice_ids) + [{"$unwind": "$answers.value"}, {"$group": {
            "_id": {"question_id": "$answers.question_id", "value": "$answers.value"}, "n": {"$sum": 1}}}],
        "values": answers_for(value_ids) + [{"$group": {"_id": "$answers.question_id", "items": {"$push": "$answers.value"}}}],
        "averages": answers_for(number_ids) + [{"$group": {"_id": "$answers.question_id", "value": {"$avg": "$answers.value"}}}],
    }
    rows = list(db.responses.aggregate([{"$match": {"survey_id": survey["_id"]}}, {"$facet": facets}]))
    data = rows[0]
    counts = {r["_id"]: r["n"] for r in data["counts"]}
    options = {(r["_id"]["question_id"], r["_id"]["value"]): r["n"] for r in data["options"]}
    values = {r["_id"]: r["items"] for r in data["values"]}
    averages = {r["_id"]: r["value"] for r in data["averages"]}
    result = []
    for q in questions:
        item = {"question_id": q["id"], "title": q["title"], "type": q["type"], "answer_count": counts.get(q["id"], 0)}
        if q["type"] in ("single", "multiple"):
            item["options"] = [{**o, "count": options.get((q["id"], o["id"]), 0)} for o in q["options"]]
        else:
            item["values"] = values.get(q["id"], [])
            if q["type"] == "number":
                item["average"] = averages.get(q["id"])
        result.append(item)
    return {"survey_id": survey["_id"], "response_count": data["total"][0]["n"] if data["total"] else 0,
            "counting_unit": "submitted_response", "questions": result}
