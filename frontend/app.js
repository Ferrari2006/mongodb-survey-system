"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("survey_token"), survey = null, editing = null, page = 1;
function message(text, error=false) { $("message").textContent=text; $("message").className=error?"error":""; }
async function api(path, method="GET", body) {
  const response = await fetch(`/api${path}`, {method, headers:{"Content-Type":"application/json", ...(token?{Authorization:`Bearer ${token}`}:{})}, body:body===undefined?undefined:JSON.stringify(body)});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error?.message || `请求失败：${response.status}`);
  return result;
}
function action(fn) { return async event => { event?.preventDefault(); try { await fn(event); } catch(error) { message(error.message,true); } }; }
function show(id) { for(const section of ["auth","dashboard","editor"]) $(section).hidden=section!==id; }
function node(tag,text,cls) { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(cls)e.className=cls; return e; }
function button(text,fn) { const e=node("button",text,"secondary"); e.type="button"; e.onclick=action(fn); return e; }
async function identify() {
  if(!token) { show("auth"); $("identity").replaceChildren(); return; }
  try { const user=await api("/auth/me"); $("identity").replaceChildren(node("span",user.username+" "),button("退出",async()=>{await api("/auth/logout","POST",{});token=null;sessionStorage.removeItem("survey_token");await identify();})); await list(); }
  catch(e) {token=null;sessionStorage.removeItem("survey_token");show("auth");message(e.message,true);}
}
$("auth-form").onsubmit=action(async()=>{
  const result=await api("/auth/login","POST",{username:$("username").value,password:$("password").value});
  token=result.token;page=1;sessionStorage.setItem("survey_token",token);$("password").value="";message("登录成功");await identify();
});
$("register").onclick=action(async()=>{if(!$("auth-form").reportValidity())return;await api("/auth/register","POST",{username:$("username").value,password:$("password").value});message("注册成功，请点击登录。");});
async function list() {
  const result=await api(`/surveys?page=${page}`); show("dashboard");$("survey-list").replaceChildren();
  if(!result.items.length) $("survey-list").append(node("p","还没有问卷。点击“新建问卷”开始。","muted"));
  for(const item of result.items) {const card=node("article",undefined,"card");card.append(node("h2",item.title),node("p",item.description||"暂无说明","muted"),button("编辑草稿",()=>open(item._id)));$("survey-list").append(card);}
  $("page-info").textContent=`第 ${page} 页 · 共 ${result.total} 份`;
  $("previous-page").disabled=page===1;$("next-page").disabled=page*20>=result.total;
}
$("previous-page").onclick=action(async()=>{page--;await list();});$("next-page").onclick=action(async()=>{page++;await list();});
$("new-survey").onclick=action(async()=>{survey=null;resetQuestion();show("editor");$("survey-form").reset();$("editor-heading").textContent="新建问卷";$("question-list").replaceChildren(node("p","先保存问卷基本信息，再添加题目。"));$("question-form").hidden=true;$("validation-form").hidden=true;});
$("back").onclick=action(list);
async function open(id) {survey=await api(`/surveys/${id}`);render();resetQuestion();}
function render() {
  show("editor");$("editor-heading").textContent="编辑问卷";$("survey-title").value=survey.title;$("survey-description").value=survey.description;
  $("question-form").hidden=false;$("validation-form").hidden=false;$("question-list").replaceChildren();$("validation-question").replaceChildren();
  const labels={single:"单选",multiple:"多选",text:"文本",number:"数字"};
  for(const [index,q] of survey.questions.entries()) {
    const row=node("article",undefined,"question-row");row.append(node("strong",`${index+1}. ${q.title}`),node("p",`${q.id} · ${labels[q.type]} · ${q.required?"必答":"选答"}`,"muted"));
    if(q.options)row.append(node("p",q.options.map(o=>`${o.id}: ${o.label}`).join("；")));
    row.append(node("pre",JSON.stringify(q.validation)));
    const acts=node("div",undefined,"actions");acts.append(button("编辑",()=>edit(q)),button("删除",async()=>{if(!confirm(`删除题目“${q.title}”？`))return;survey=await api(`/surveys/${survey._id}/questions/${q.id}`,"DELETE",{revision:survey.revision});render();resetQuestion();}));row.append(acts);$("question-list").append(row);
    const opt=node("option",q.title);opt.value=q.id;$("validation-question").append(opt);
  }
  if(!survey.questions.length)$("question-list").append(node("p","尚未添加题目。","muted"));
}
$("survey-form").onsubmit=action(async()=>{const body={title:$("survey-title").value,description:$("survey-description").value};survey=survey?await api(`/surveys/${survey._id}`,"PATCH",{...body,revision:survey.revision}):await api("/surveys","POST",body);render();message("问卷已保存");});
function fields() {
  const kind=$("question-type").value;$("options-panel").hidden=!["single","multiple"].includes(kind);$("bounds-panel").hidden=kind==="single";$("integer-panel").hidden=kind!=="number";
  $("min-label").textContent={multiple:"最少选择数量",text:"最少字符数",number:"最小值"}[kind]||"最小值";
  $("max-label").textContent={multiple:"最多选择数量（与最少相同可限制恰好数量）",text:"最多字符数",number:"最大值"}[kind]||"最大值";
}
function resetQuestion(){editing=null;$("question-form").reset();$("question-id").disabled=false;$("question-id").value=`q${crypto.randomUUID().slice(0,8)}`;$("question-heading").textContent="添加题目";fields();}
function edit(q){editing=q.id;$("question-id").value=q.id;$("question-id").disabled=true;$("question-title").value=q.title;$("question-type").value=q.type;$("question-required").checked=q.required;$("question-options").value=(q.options||[]).map(o=>`${o.id} | ${o.label}`).join("\n");const keys=q.type==="multiple"?["min_choices","max_choices"]:q.type==="text"?["min_length","max_length"]:["min","max"];$("question-min").value=q.validation[keys[0]]??"";$("question-max").value=q.validation[keys[1]]??"";$("question-integer").checked=!!q.validation.integer;$("question-heading").textContent="编辑题目";fields();$("question-form").scrollIntoView({behavior:"smooth"});}
$("question-type").onchange=fields;$("reset-question").onclick=resetQuestion;
$("question-form").onsubmit=action(async()=>{
  const q={id:$("question-id").value,title:$("question-title").value,type:$("question-type").value,required:$("question-required").checked,validation:{}};
  if(["single","multiple"].includes(q.type))q.options=$("question-options").value.split("\n").filter(line=>line.trim()).map(line=>{const i=line.indexOf("|");if(i<0)throw new Error("每行选项请使用 ID | 文字 格式");return {id:line.slice(0,i).trim(),label:line.slice(i+1).trim()};});
  if(q.type!=="single"){const keys=q.type==="multiple"?["min_choices","max_choices"]:q.type==="text"?["min_length","max_length"]:["min","max"];["question-min","question-max"].forEach((id,i)=>{if($(id).value!=="")q.validation[keys[i]]=Number($(id).value);});}
  if(q.type==="number")q.validation.integer=$("question-integer").checked;
  survey=await api(`/surveys/${survey._id}/questions${editing?"/"+editing:""}`,editing?"PUT":"POST",{revision:survey.revision,question:q});render();resetQuestion();message("题目已保存");
});
$("validation-form").onsubmit=action(async()=>{const q=survey.questions.find(q=>q.id===$("validation-question").value);if(!q)throw new Error("请先添加题目");let value=$("validation-value").value;if(value!==""){if(q.type==="multiple")value=value.split(",").map(s=>s.trim());if(q.type==="number"){value=Number(value);if(!Number.isFinite(value))throw new Error("请输入有效数字");}}await api(`/surveys/${survey._id}/questions/${q.id}/validate`,"POST",{value});message("答案符合该题的校验要求（未保存答卷）。");});
fields();identify();
