"""Create an owner, a respondent and a branched demo through the actual HTTP API."""
import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5050")
    args = parser.parse_args()
    token = None

    def call(path, data=None, method=None):
        headers = {"Content-Type":"application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = Request(args.base+"/api"+path, data=json.dumps(data).encode() if data is not None else None,
                      headers=headers, method=method or ("POST" if data is not None else "GET"))
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    suffix = uuid4().hex[:6]
    owner, respondent = "demo_owner_"+suffix, "demo_reader_"+suffix
    password = "Demo-only-123"
    for username in (owner, respondent):
        call("/auth/register", {"username":username,"password":password})
    token = call("/auth/login", {"username":owner,"password":password})["token"]
    survey = call("/surveys", {"title":"校园服务体验问卷", "description":"选择不使用校园服务将跳到建议题；使用者继续评价。", "allow_anonymous":True, "allow_repeat":True})
    qs = [
        {"id":"q1","title":"你是否使用校园服务？","type":"single","required":True,
         "options":[{"id":"yes","label":"使用"},{"id":"no","label":"不使用"}],
         "jumps":[{"op":"eq","value":"no","target":"q4"}]},
        {"id":"q2","title":"你使用哪些服务？（至少1项）","type":"multiple","required":True,
         "options":[{"id":"library","label":"图书馆"},{"id":"canteen","label":"食堂"},{"id":"sports","label":"体育场馆"}],
         "validation":{"min_choices":1,"max_choices":3}},
        {"id":"q3","title":"满意度评分（0～10整数）","type":"number","required":True,
         "validation":{"min":0,"max":10,"integer":True}},
        {"id":"q4","title":"你的建议（可不填）","type":"text","validation":{"max_length":200}}
    ]
    for q in qs:
        survey = call(f"/surveys/{survey['_id']}/questions", {"revision":survey["revision"],"question":q})
    survey = call(f"/surveys/{survey['_id']}/publish", {"revision":survey["revision"]})
    # Demo credentials are synthetic, with no role outside this local application.
    print(json.dumps({"owner":owner,"respondent":respondent,"password":password,"survey_id":survey["_id"],
                      "url":args.base+"/survey/"+survey["_id"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise SystemExit(1)
