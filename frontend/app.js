"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("survey_token"), survey = null, editing = null, page = 1, jumps=[];
let filling=null, answers={}, visited=[], current=null, requestId=null, responsePage=1, progressRevision=0, fillBusy=false;
const sharedId=location.pathname.startsWith("/survey/")?location.pathname.split("/")[2]:null;
function message(text, error=false) { $("message").textContent=text; $("message").className=error?"error":""; }
async function api(path, method="GET", body) {
  const response = await fetch(`/api${path}`, {method, headers:{"Content-Type":"application/json", ...(token?{Authorization:`Bearer ${token}`}:{})}, body:body===undefined?undefined:JSON.stringify(body)});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error?.message || `请求失败：${response.status}`);
  return result;
}
function action(fn) { return async event => { event?.preventDefault(); try { await fn(event); } catch(error) { message(error.message,true); } }; }
function show(id) { for(const section of ["auth","dashboard","editor","fill","statistics"]) $(section).hidden=section!==id; }
function node(tag,text,cls) { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(cls)e.className=cls; return e; }
function constraintText(q) {
  const v=q.validation;
  if(q.type==="single")return "请选择一个选项。";
  if(q.type==="multiple")return v.min_choices===v.max_choices?`请选择恰好 ${v.min_choices} 项。`:`请选择 ${v.min_choices}～${v.max_choices} 项。`;
  if(q.type==="text")return `填写 ${v.min_length}～${v.max_length} 个字符，首尾空白不计入。`;
  return `${v.integer?"请输入整数":"可输入整数或小数"}${v.min!==undefined?`，最小 ${v.min}`:""}${v.max!==undefined?`，最大 ${v.max}`:""}。`;
}
function answerText(q,value) {
  if(value===null||value===undefined)return "未回答";
  if(q?.options){const labels=new Map(q.options.map(o=>[o.id,o.label]));return (Array.isArray(value)?value:[value]).map(v=>labels.get(v)||v).join("、");}
  return String(value);
}
const jumpLabels={eq:"等于",any:"包含任一",all:"包含全部",lt:"小于",lte:"小于等于",gt:"大于",gte:"大于等于"};
function optionDefinitions(){return $("question-options").value.split("\n").filter(s=>s.includes("|")).map(s=>{const i=s.indexOf("|");return {id:s.slice(0,i).trim(),label:s.slice(i+1).trim()};});}
function jumpText(rule,q){const target=rule.target==="END"?"结束问卷":survey?.questions.find(item=>item.id===rule.target)?.title||`${rule.target}（待添加）`;return `当答案${jumpLabels[rule.op]||rule.op} ${answerText(q,rule.value)} → ${target}`;}
function button(text,fn) { const e=node("button",text,"secondary"); e.type="button"; e.onclick=action(fn); return e; }
async function identify() {
  if(!token) { show("auth"); $("identity").replaceChildren(); return; }
  try { const user=await api("/auth/me"); $("identity").replaceChildren(node("span",user.username+" "),button("退出",async()=>{await api("/auth/logout","POST",{});token=null;sessionStorage.removeItem("survey_token");await identify();})); }
  catch(e) {token=null;sessionStorage.removeItem("survey_token");show("auth");message(e.message,true);}
  if(token) { try { if(sharedId)await startFill(sharedId);else await list(); }catch(e){try{await list();}catch(ignore){show("dashboard");}message(e.message,true);} }
}
$("auth-form").onsubmit=action(async()=>{
  const result=await api("/auth/login","POST",{username:$("username").value,password:$("password").value});
  token=result.token;page=1;sessionStorage.setItem("survey_token",token);$("password").value="";message("登录成功");await identify();
});
$("register").onclick=action(async()=>{if(!$("auth-form").reportValidity())return;await api("/auth/register","POST",{username:$("username").value,password:$("password").value});message("注册成功，请点击登录。");});
async function list() {
  const result=await api(`/surveys?page=${page}`); show("dashboard");$("survey-list").replaceChildren();
  if(!result.items.length) $("survey-list").append(node("p","还没有问卷。点击“新建问卷”开始。","muted"));
  for(const item of result.items) {const card=node("article",undefined,"card");card.append(node("h2",item.title),node("p",`${item.status==="draft"?"草稿":item.status==="published"?"已发布":"已关闭"} · ${item.description||"暂无说明"}`,"muted"),button("管理问卷",()=>open(item._id)));$("survey-list").append(card);}
  $("page-info").textContent=`第 ${page} 页 · 共 ${result.total} 份`;
  $("previous-page").disabled=page===1;$("next-page").disabled=page*20>=result.total;
}
$("previous-page").onclick=action(async()=>{page--;await list();});$("next-page").onclick=action(async()=>{page++;await list();});
$("new-survey").onclick=action(async()=>{survey=null;resetQuestion();show("editor");$("survey-form").reset();for(const e of $("survey-form").elements)e.disabled=false;$("editor-heading").textContent="新建问卷";$("question-list").replaceChildren(node("p","先保存问卷基本信息，再添加题目。"));$("question-form").hidden=true;$("validation-form").hidden=true;$("publish-survey").disabled=true;$("close-survey").disabled=true;$("view-statistics").disabled=true;$("share-url").value="";$("survey-state").textContent="先保存问卷基本信息";});
$("back").onclick=action(list);
async function open(id) {survey=await api(`/surveys/${id}`);render();resetQuestion();}
function render() {
  show("editor");$("editor-heading").textContent="编辑问卷";$("survey-title").value=survey.title;$("survey-description").value=survey.description;
  const draft=survey.status==="draft";$("allow-anonymous").checked=!!survey.allow_anonymous;$("allow-repeat").checked=!!survey.allow_repeat;
  if(survey.deadline){const dt=new Date(survey.deadline);$("deadline").value=new Date(dt.getTime()-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);}else $("deadline").value="";
  for(const e of $("survey-form").elements)e.disabled=!draft;
  $("publish-survey").disabled=!draft;$("close-survey").disabled=survey.status!=="published";$("view-statistics").disabled=false;
  $("survey-state").textContent=`状态：${draft?"草稿":survey.status==="published"?"已发布":"已关闭"} · 版本 ${survey.revision}`;
  $("editor").querySelector(".badge").textContent=draft?"草稿":survey.status==="published"?"已发布":"已关闭";
  $("share-url").value=survey.status==="draft"?"发布后生成可填写链接":`${location.origin}/survey/${survey._id}`;
  $("question-form").hidden=false;$("validation-form").hidden=false;$("question-list").replaceChildren();$("validation-question").replaceChildren();
  const labels={single:"单选",multiple:"多选",text:"文本",number:"数字"};
  for(const [index,q] of survey.questions.entries()) {
    const row=node("article",undefined,"question-row");row.append(node("strong",`${index+1}. ${q.title}`),node("p",`${q.id} · ${labels[q.type]} · ${q.required?"必答":"选答"}`,"muted"));
    if(q.options)row.append(node("p",q.options.map(o=>`${o.id}: ${o.label}`).join("；")));
    row.append(node("p",constraintText(q),"muted"));
    for(const rule of q.jumps||[])row.append(node("p",jumpText(rule,q)));
    if(!q.jumps?.length)row.append(node("p","按顺序进入下一题","muted"));
    if(draft){const acts=node("div",undefined,"actions");acts.append(button("编辑",()=>edit(q)),button("删除",async()=>{if(!confirm(`删除题目“${q.title}”？`))return;survey=await api(`/surveys/${survey._id}/questions/${q.id}`,"DELETE",{revision:survey.revision});render();resetQuestion();}));row.append(acts);}$("question-list").append(row);
    const opt=node("option",q.title);opt.value=q.id;$("validation-question").append(opt);
  }
  if(!survey.questions.length)$("question-list").append(node("p","尚未添加题目。","muted"));
  $("question-form").hidden=!draft;
}
$("survey-form").onsubmit=action(async()=>{const body={title:$("survey-title").value,description:$("survey-description").value,allow_anonymous:$("allow-anonymous").checked,allow_repeat:$("allow-repeat").checked,deadline:$("deadline").value?new Date($("deadline").value).toISOString():null};survey=survey?await api(`/surveys/${survey._id}`,"PATCH",{...body,revision:survey.revision}):await api("/surveys","POST",body);render();message("问卷已保存");});
function fields() {
  const kind=$("question-type").value;$("options-panel").hidden=!["single","multiple"].includes(kind);$("bounds-panel").hidden=kind==="single";$("integer-panel").hidden=kind!=="number";
  $("min-label").textContent={multiple:"最少选择数量",text:"最少字符数",number:"最小值"}[kind]||"最小值";
  $("max-label").textContent={multiple:"最多选择数量（与最少相同可限制恰好数量）",text:"最多字符数",number:"最大值"}[kind]||"最大值";
  const allowed={single:["eq"],multiple:["any","all"],number:["eq","lt","lte","gt","gte"],text:[]}[kind];
  for(const opt of $("jump-op").options){opt.disabled=!allowed.includes(opt.value);opt.hidden=opt.disabled;}
  if(!allowed.includes($("jump-op").value))$("jump-op").value=allowed[0]||"";
  $("jump-editor").hidden=kind==="text";
  jumpSuggestions();
}
function jumpSuggestions(){
  $("jump-targets").replaceChildren();const end=node("option","结束问卷");end.value="END";$("jump-targets").append(end);
  const index=survey?.questions.findIndex(q=>q.id===$("question-id").value)??-1;
  for(const [i,q] of (survey?.questions||[]).entries())if(index>=0&&i>index){const opt=node("option",q.title);opt.value=q.id;$("jump-targets").append(opt);}
  $("jump-values").replaceChildren();if($("question-type").value==="single")for(const o of optionDefinitions()){const opt=node("option",o.label);opt.value=o.id;$("jump-values").append(opt);}
}
$("question-options").oninput=jumpSuggestions;$("question-id").oninput=jumpSuggestions;
function resetQuestion(){editing=null;jumps=[];renderJumps();$("question-form").reset();$("question-id").disabled=false;$("question-id").value=`q${crypto.randomUUID().slice(0,8)}`;$("question-heading").textContent="添加题目";fields();}
function edit(q){editing=q.id;$("question-id").value=q.id;$("question-id").disabled=true;$("question-title").value=q.title;$("question-type").value=q.type;$("question-required").checked=q.required;$("question-options").value=(q.options||[]).map(o=>`${o.id} | ${o.label}`).join("\n");const keys=q.type==="multiple"?["min_choices","max_choices"]:q.type==="text"?["min_length","max_length"]:["min","max"];$("question-min").value=q.validation[keys[0]]??"";$("question-max").value=q.validation[keys[1]]??"";$("question-integer").checked=!!q.validation.integer;$("question-heading").textContent="编辑题目";fields();$("question-form").scrollIntoView({behavior:"smooth"});}
$("question-type").onchange=fields;$("reset-question").onclick=resetQuestion;
function renderJumps(){$("jump-list").replaceChildren();jumps.forEach((r,i)=>{const row=node("div",undefined,"rule-row");row.append(node("p",`${i+1}. ${jumpText(r,{options:optionDefinitions()})}`));const acts=node("div",undefined,"actions");if(i>0)acts.append(button("上移",()=>{[jumps[i-1],jumps[i]]=[jumps[i],jumps[i-1]];renderJumps();}));if(i<jumps.length-1)acts.append(button("下移",()=>{[jumps[i+1],jumps[i]]=[jumps[i],jumps[i+1]];renderJumps();}));acts.append(button("移除",()=>{jumps.splice(i,1);renderJumps();}));row.append(acts);$("jump-list").append(row);});}
const originalEdit=edit;edit=q=>{originalEdit(q);jumps=structuredClone(q.jumps||[]);renderJumps();};
$("add-jump").onclick=action(async()=>{let value=$("jump-value").value;const kind=$("question-type").value;if(kind==="text")throw new Error("文本填空不设置条件跳转");if(kind==="multiple")value=value.split(",").map(v=>v.trim());if(kind==="number"){if(!value.trim()||!Number.isFinite(Number(value)))throw new Error("比较值须为数字");value=Number(value);}jumps.push({op:$("jump-op").value,value,target:$("jump-target").value.trim()});renderJumps();});
$("question-form").onsubmit=action(async()=>{
  const q={id:$("question-id").value,title:$("question-title").value,type:$("question-type").value,required:$("question-required").checked,validation:{},jumps};
  if(["single","multiple"].includes(q.type))q.options=$("question-options").value.split("\n").filter(line=>line.trim()).map(line=>{const i=line.indexOf("|");if(i<0)throw new Error("每行选项请使用 ID | 文字 格式");return {id:line.slice(0,i).trim(),label:line.slice(i+1).trim()};});
  if(q.type!=="single"){const keys=q.type==="multiple"?["min_choices","max_choices"]:q.type==="text"?["min_length","max_length"]:["min","max"];["question-min","question-max"].forEach((id,i)=>{if($(id).value!=="")q.validation[keys[i]]=Number($(id).value);});}
  if(q.type==="number")q.validation.integer=$("question-integer").checked;
  survey=await api(`/surveys/${survey._id}/questions${editing?"/"+editing:""}`,editing?"PUT":"POST",{revision:survey.revision,question:q});render();resetQuestion();message("题目已保存");
});
$("validation-form").onsubmit=action(async()=>{const q=survey.questions.find(q=>q.id===$("validation-question").value);if(!q)throw new Error("请先添加题目");let value=$("validation-value").value;if(value!==""){if(q.type==="multiple")value=value.split(",").map(s=>s.trim());if(q.type==="number"){value=Number(value);if(!Number.isFinite(value))throw new Error("请输入有效数字");}}await api(`/surveys/${survey._id}/questions/${q.id}/validate`,"POST",{value});message("答案符合该题的校验要求（未保存答卷）。");});
$("publish-survey").onclick=action(async()=>{if(!confirm("发布后题目和设置固定，确定发布？"))return;survey=await api(`/surveys/${survey._id}/publish`,"POST",{revision:survey.revision});render();message("发布成功，可复制分享链接。");});
$("close-survey").onclick=action(async()=>{if(!confirm("确定关闭问卷？关闭后不再接受新的填写。"))return;survey=await api(`/surveys/${survey._id}/close`,"POST",{revision:survey.revision});render();message("问卷已关闭");});
$("fill-home").onclick=()=>{location.href="/";};
async function startFill(sid){filling=await api(`/public/surveys/${sid}`);const saved=(await api(`/public/surveys/${sid}/progress`)).progress;answers=saved?.answers||{};progressRevision=saved?.revision||0;visited=[];requestId=saved?.request_id||crypto.randomUUID();$("fill-review").disabled=false;$("fill-anonymous").disabled=false;$("fill-title").textContent=filling.title;$("fill-description").textContent=filling.description;$("fill-anonymous").checked=saved?.anonymous||false;$("anonymous-choice").hidden=!filling.allow_anonymous;show("fill");await advance();if(saved)message("已恢复上次保存的进度。每次点击下一题后保存；当前未确认输入不自动保存。");}
async function persistProgress(){const saved=await api(`/public/surveys/${filling._id}/progress`,"PUT",{answers,revision:progressRevision,anonymous:$("fill-anonymous").checked,request_id:requestId});progressRevision=saved.revision;}
async function advance(persist=false){const state=await api(`/public/surveys/${filling._id}/evaluate`,"POST",{answers});if(persist)await persistProgress();visited=state.path;current=state.next_question_id;$("fill-form").hidden=state.complete;$("fill-submit").hidden=!state.complete;$("fill-progress").textContent=`已完成 ${visited.length} 道题 · 点击下一题后保存进度`;$("fill-back").disabled=visited.length===0;
  if(state.complete){$("fill-question-title").textContent="回答已完成，请确认提交";return;}
  const q=filling.questions.find(q=>q.id===current);$("fill-question-title").textContent=`${q.title}${q.required?"（必答）":"（选答）"}`;$("fill-input").replaceChildren();
  if(q.type==="single"||q.type==="multiple"){for(const o of q.options){const label=node("label",undefined,"check");const input=document.createElement("input");input.type=q.type==="single"?"radio":"checkbox";input.name="answer";input.value=o.id;label.append(input,document.createTextNode(o.label));$("fill-input").append(label);}}
  else {const input=document.createElement(q.type==="text"?"textarea":"input");input.id="answer-input";input.setAttribute("aria-label","填写答案");if(q.type==="number"){input.type="number";input.step="any";}$("fill-input").append(input);}
  $("fill-input").append(node("p",constraintText(q)+(q.required?"":" 本题选答，可留空后点击下一题。"),"muted"));
}
function fillAction(fn){return action(async()=>{if(fillBusy)return;fillBusy=true;try{await fn();}finally{fillBusy=false;}});}
$("fill-form").onsubmit=fillAction(async()=>{const q=filling.questions.find(q=>q.id===current);let value=null;if(q.type==="single")value=$("fill-input").querySelector("input:checked")?.value??null;else if(q.type==="multiple")value=Array.from($("fill-input").querySelectorAll("input:checked")).map(e=>e.value);else{const raw=$("answer-input").value;value=raw===""?null:q.type==="number"?Number(raw):raw;}const before=structuredClone(answers);answers[current]=value;try{await advance(true);message("进度已保存。");}catch(e){answers=before;throw e;}});
$("fill-back").onclick=fillAction(async()=>{if(!visited.length)return;const before=structuredClone(answers);delete answers[visited[visited.length-1]];try{await advance(true);}catch(e){answers=before;throw e;}message("请重新选择，后续答案将按新路径填写。进度已保存。");});
$("fill-anonymous").onchange=fillAction(async()=>{await persistProgress();message("匿名设置及已确认进度已保存。");});
$("fill-review").onclick=$("fill-back").onclick;
$("submit-response").onclick=fillAction(async()=>{$("submit-response").disabled=true;try{await api(`/public/surveys/${filling._id}/responses`,"POST",{answers,anonymous:$("fill-anonymous").checked,request_id:requestId});$("fill-submit").hidden=true;$("fill-back").disabled=true;$("fill-review").disabled=true;$("fill-anonymous").disabled=true;$("fill-question-title").textContent="提交成功，感谢填写";message("答卷已保存。");}finally{$("submit-response").disabled=false;}});
$("view-statistics").onclick=action(async()=>{show("statistics");$("stats-title").textContent=`${survey.title} · 统计`;$("stats-question").replaceChildren(node("option","全部题目"));$("stats-question").firstChild.value="";for(const q of survey.questions){const opt=node("option",q.title);opt.value=q.id;$("stats-question").append(opt);}responsePage=1;await loadStatistics();await loadResponses();});
async function loadStatistics(){const qid=$("stats-question").value;const result=await api(`/surveys/${survey._id}${qid?"/questions/"+qid:""}/statistics`);$("stats-total").textContent=`共 ${result.response_count} 份有效答卷，按答卷份数计数。`;$("stats-content").replaceChildren();for(const q of result.questions){const card=node("article",undefined,"card");card.append(node("h2",q.title),node("p",`有效回答：${q.answer_count}`));if(q.options){
      card.append(node("p",q.type==="multiple"?"比例 = 选择该项的答卷数 ÷ 本题有效回答份数。多选比例之和可能超过100%。":"比例 = 选择该项的答卷数 ÷ 本题有效回答份数。", "muted"));
      const table=node("table",undefined,"option-stats");const caption=node("caption",`${q.title} · 选项分布`);table.append(caption);
      const head=node("thead"),hr=node("tr");for(const title of ["选项","次数 / 比例","分布"]) {const th=node("th",title);th.scope="col";hr.append(th);}head.append(hr);table.append(head);
      const body=node("tbody");
      for(const o of q.options){const row=node("tr");const label=node("th",o.label);label.scope="row";const text=node("td",`${o.count} · ${q.answer_count?(o.count/q.answer_count*100).toFixed(1)+"%":"—"}`);const visual=node("td");const bar=node("meter");bar.min=0;bar.max=Math.max(q.answer_count,1);bar.value=o.count;bar.setAttribute("aria-label",`${o.label}，${o.count}份，本题有效回答${q.answer_count}份`);bar.textContent=String(o.count);visual.append(bar);row.append(label,text,visual);body.append(row);}
      table.append(body);card.append(table);
    }else{if(q.type==="number")card.append(node("p",`平均值：${q.average??"暂无数据"}`));if(!q.values.length)card.append(node("p","暂无填写内容","muted"));else{const entries=node("ol");for(const value of q.values)entries.append(node("li",String(value)));card.append(entries);}}$("stats-content").append(card);}}
async function loadResponses(){const result=await api(`/surveys/${survey._id}/responses?page=${responsePage}`);$("response-list").replaceChildren();for(const r of result.items){const card=node("article",undefined,"card");card.append(node("p",`${r.respondent} · ${new Date(r.created_at).toLocaleString("zh-CN")}`));for(const answer of r.answers){const q=survey.questions.find(q=>q.id===answer.question_id);card.append(node("p",`${q?.title||answer.question_id}：${answerText(q,answer.value)}`));}$("response-list").append(card);}$("response-page").textContent=`第 ${responsePage} 页`;$("response-previous").disabled=responsePage===1;$("response-next").disabled=responsePage*20>=result.total;}
$("stats-question").onchange=action(loadStatistics);$("stats-back").onclick=()=>render();$("response-previous").onclick=action(async()=>{responsePage--;await loadResponses();});$("response-next").onclick=action(async()=>{responsePage++;await loadResponses();});
fields();identify();
