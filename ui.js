"use strict";
const $ = id => document.getElementById(id);
function node(tag, value, ...children) {
  const result = document.createElement(tag);
  if (value !== null && value !== undefined) result.textContent = value;
  result.append(...children);
  return result;
}
function button(label, fn) {
  const b = node("button",label);
  b.type="button";
  b.addEventListener("click",()=>run(fn,b));
  return b;
}
async function run(fn,b) {
  if(b) b.disabled=true;
  try { await fn(); } catch(error) { status(error.message,true); }
  finally { if(b) b.disabled=false; }
}
function status(message,error=false) {
  $("status").textContent=message;
  $("status").classList.toggle("error",error);
}
async function api(action,data) {
  const response=await fetch("/api/"+action,data===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
  const value=await response.json();
  if(!response.ok) throw Error(value.error || "Request failed.");
  return value;
}
let controller;
async function stream(action,data) {
  if(controller) controller.abort();
  const request=new AbortController();
  controller=request;
  $("cancel").hidden=false;
  $("answer").textContent="";
  if($("sources")) $("sources").replaceChildren();
  status("Waiting for local Ollama…");
  try {
    const response=await fetch("/api/"+action,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data),signal:request.signal});
    if(!response.ok) throw Error((await response.json()).error);
    const reader=response.body.getReader(), decoder=new TextDecoder();
    let pending="";
    while(true) {
      const {done,value}=await reader.read();
      pending+=decoder.decode(value,{stream:!done});
      let end;
      while((end=pending.indexOf("\n"))>=0) {
        const item=JSON.parse(pending.slice(0,end)); pending=pending.slice(end+1);
        if(item.error) throw Error(item.error);
        if(item.sources) showSources(item.sources);
        if(item.token) $("answer").textContent+=item.token;
      }
      if(done) break;
    }
    status("Response complete.");
  } catch(error) {
    if(error.name!=="AbortError") throw error;
    status("Response cancelled.");
  } finally {
    if(controller===request) {controller=null; $("cancel").hidden=true;}
  }
}
function option(select,value,label,selected=false) {
  const item=node("option",label); item.value=value; item.selected=selected; select.append(item);
}
function selectList(id,items,empty) {
  const select=$(id), current=select.value;
  select.replaceChildren();
  option(select,"",empty);
  for(const [value,label] of items) option(select,value,label,String(value)===current);
}
function form(id,fn) {
  $(id).addEventListener("submit",event=>{
    event.preventDefault();
    run(()=>fn(Object.fromEntries(new FormData(event.target)),event.target),event.submitter);
  });
}
function textBlock(parent,title,body) {
  const item=node("details",null,node("summary",title),node("pre",body));
  parent.append(item);return item;
}
function empty(parent,value) {parent.append(node("p",value));}
function download(name,text,type="text/plain") {
  const blob=text instanceof Blob?text:new Blob([text],{type});
  const a=node("a"); a.href=URL.createObjectURL(blob); a.download=name; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function binary(file) {
  if(file.size>30_000_000) throw Error(file.name+" exceeds 30 MB.");
  return new Promise((resolve,reject)=>{
    const reader=new FileReader(); reader.onerror=()=>reject(reader.error);
    reader.onload=()=>resolve({name:file.name,data:reader.result.split(",")[1]});
    reader.readAsDataURL(file);
  });
}
function graph(container,edges,open) {
  container.replaceChildren();
  if(!edges.length) return empty(container,"No relationships match.");
  const ns="http://www.w3.org/2000/svg";
  const svg=document.createElementNS(ns,"svg");
  const visible=edges.slice(0,25);
  svg.setAttribute("viewBox","0 0 840 "+(visible.length*38+30));
  visible.forEach((edge,i)=>{
    const y=26+i*38;
    const line=document.createElementNS(ns,"path");
    line.setAttribute("d","M260 "+y+" H568");
    line.setAttribute("class","connection");
    svg.append(line);
    for(const [x,label,anchor] of [[245,edge.from,"end"],[414,edge.kind,"middle"],[587,edge.to,"start"]]) {
      const text=document.createElementNS(ns,"text");
      text.setAttribute("x",x); text.setAttribute("y",y+5); text.setAttribute("text-anchor",anchor);
      text.textContent=label.length>32?label.slice(0,29)+"…":label;
      const title=document.createElementNS(ns,"title"); title.textContent=label;text.append(title);
      if(open && x!==414) {
        text.setAttribute("tabindex","0"); text.setAttribute("role","button");
        text.addEventListener("click",()=>run(()=>open(label)));
        text.addEventListener("keydown",event=>{if(event.key==="Enter")run(()=>open(label));});
      }
      svg.append(text);
    }
  });
  container.append(svg);
  if(edges.length>visible.length) empty(container,"Showing "+visible.length+" of "+edges.length+" links. Filter to narrow the graph.");
}
async function loadModels() {
  const value=await api("models");
  if($("model")) selectList("model",value.chat.map(name=>[name,name]),"Automatic chat model");
  if($("embedding")) selectList("embedding",value.embedding.map(name=>[name,name]),"Automatic embedding model");
  const health=$("health");
  health.textContent=value.offline?"Ollama offline":value.chat.length+" chat · "+value.embedding.length+" embedding";
  health.dataset.online=String(!value.offline);
}
function showPane(id) {
  for(const pane of document.querySelectorAll("main > section")) pane.hidden=pane.id!==id;
  for(const tab of document.querySelectorAll("nav button[data-pane]")) tab.setAttribute("aria-current",String(tab.dataset.pane===id));
}
function metrics(parent,items) {
  parent.replaceChildren(...items.map(([label,value])=>node("div",null,node("strong",value),node("span",label))));
}
function today() {
  const now=new Date();return new Date(now-Date.parse("1970-01-01")-now.getTimezoneOffset()*60000).toISOString().slice(0,10);
}
function showSources(items) {
  const list=$("sources");list.replaceChildren();
  for(const [i,item] of items.entries()) textBlock(list,item.name?"[D"+item.id+"] "+item.name+" · "+item.section:
    "[S"+(i+1)+"] "+item.path+":"+item.start+"–"+item.end,item.text);
}

document.addEventListener("DOMContentLoaded",()=>{
  document.documentElement.dataset.theme=localStorage.getItem("theme") || (matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");
  $("theme").addEventListener("click",()=>{
    document.documentElement.dataset.theme=document.documentElement.dataset.theme==="dark"?"light":"dark";
    localStorage.setItem("theme",document.documentElement.dataset.theme);
  });
  $("sidebar").addEventListener("click",()=>document.body.classList.toggle("collapsed"));
  $("health").addEventListener("click",()=>run(loadModels));
  for(const tab of document.querySelectorAll("nav button[data-pane]")) tab.addEventListener("click",()=>showPane(tab.dataset.pane));
  document.addEventListener("keydown",event=>{
    if(event.key==="/"&&!event.metaKey&&!event.ctrlKey&&!["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)){
      const search=document.querySelector("section:not([hidden]) [type=search]");
      if(search){event.preventDefault();search.focus();}
    }
  });
  if($("cancel")) $("cancel").addEventListener("click",()=>controller?.abort());
  run(loadModels);
  run(startApp);
});
const fields=["company","role","location","url","stipend","deadline","followup","notes","tags","priority","stage"];
let applications=[], stages=[], history=[], practice=[], cvs=[], timer, deadline, remaining;
async function startApp(){
  stages=await api("stages");
  for(const stage of stages) option($("stage"),stage,stage);
  selectList("l-stage",stages.map(x=>[x,x]),"All stages");
  form("application",async(data,target)=>{await api("save",data);target.reset();await refresh();status("Application saved.");});
  $("clear-app").addEventListener("click",()=>$("application").reset());
  for(const id of ["l-find","l-stage","view"]) $(id).addEventListener(id==="l-find"?"input":"change",renderApps);
  $("import-csv").addEventListener("change",()=>run(async()=>{
    const file=$("import-csv").files[0];if(!file)return;
    const value=await api("import",{csv:await file.text()});$("import-csv").value="";await refresh();status(value.imported+" applications imported.");
  }));
  $("export-csv").addEventListener("click",()=>download("launchpad-applications.csv",csv(applications),"text/csv"));
  $("csv-template").addEventListener("click",()=>download("launchpad-template.csv",csv([]),"text/csv"));
  form("cv-upload",async(_,target)=>{await api("cv",await binary($("cv-file").files[0]));target.reset();await loadCvs();status("CV saved.");});
  form("match",async(data)=>{
    const result=await api("match",data);
    $("match-result").replaceChildren(node("h3",result.score+"% · "+result.matched.length+" matched"),
      node("p","Matched: "+(result.matched.join(", ")||"None")),node("p","Missing: "+(result.missing.join(", ")||"None")));
  });
  form("assist",data=>stream("assist",data));
  form("practice-form",async(data,target)=>{await api("practice",data);target.reset();await refresh();status("Practice session saved.");});
  $("start-timer").addEventListener("click",toggleTimer);
  $("reset-timer").addEventListener("click",resetTimer);
  $("timer-minutes").addEventListener("change",resetTimer);
  resetTimer();
  $("gmail-connect").addEventListener("click",()=>run(async()=>{
    const info=await api("gmail-connect",{});
    const url=new URL(info.url);
    if(url.origin!=="https://accounts.google.com")throw Error("Invalid OAuth destination.");
    location.assign(url.href);
  }));
  $("gmail-refresh").addEventListener("click",()=>run(loadInbox,$("gmail-refresh")));
  $("gmail-disconnect").addEventListener("click",()=>run(async()=>{
    if(confirm("Revoke LAUNCHPAD’s read access to Gmail?")){
      await api("gmail-disconnect",{});
      $("gmail-list").replaceChildren();
      await gmailStatus();
    }
  }));
  await Promise.all([refresh(),loadCvs(),gmailStatus()]);
}
function csv(items){
  const cell=value=>'"'+String(value??"").replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';
  return [fields.join(","),...items.map(item=>fields.map(field=>cell(item[field])).join(","))].join("\r\n");
}
async function refresh(){
  [applications,history,practice]=await Promise.all([api("applications"),api("history"),api("practice")]);
  for(const id of ["ai-app","practice-app","mail-app"]) selectList(id,applications.map(x=>[x.id,x.company+" · "+x.role]),"No linked application");
  const active=applications.filter(x=>!["Offer","Rejected","Withdrawn"].includes(x.stage));
  const upcoming=active.filter(x=>[x.deadline,x.followup].some(d=>d&&d>=today()&&d<=new Date(Date.now()+7*86400000).toISOString().slice(0,10)));
  metrics($("pipeline-metrics"),[["Applications",applications.length],["Active",active.length],["Due in 7 days",upcoming.length],["Offers",applications.filter(x=>x.stage==="Offer").length]]);
  renderApps();renderAnalytics();renderPractice();
}
function edit(item){
  const f=$("application");for(const name of ["id",...fields]) f.elements[name].value=item[name]||"";
  f.scrollIntoView({block:"start"});f.elements.company.focus();
}
function card(item){
  const article=node("article",null,node("h3",item.company+" · "+item.role),node("p",[item.location,item.priority,item.tags].filter(Boolean).join(" · ")),
    node("p",[item.deadline?"Due "+item.deadline:"",item.followup?"Follow up "+item.followup:""].filter(Boolean).join(" · ")),button("Edit",()=>edit(item)));
  try{const url=new URL(item.url);if(["https:","http:"].includes(url.protocol)){
    const link=node("a","Open posting");link.href=url.href;link.className="jump";link.target="_blank";link.rel="noopener noreferrer";article.append(" ",link);
  }}catch{}
  return article;
}
function renderApps(){
  const target=$("applications");target.replaceChildren();
  const q=$("l-find").value.toLowerCase(), stage=$("l-stage").value;
  const found=applications.filter(item=>(!stage||item.stage===stage)&&fields.map(x=>item[x]).join(" ").toLowerCase().includes(q));
  if(!found.length)return empty(target,"No applications match.");
  if($("view").value==="board"){
    const board=node("div");board.className="boards";
    for(const name of stages.filter(x=>!stage||x===stage)){
      const lane=node("div",null,node("h3",name));board.append(lane);
      lane.addEventListener("dragover",event=>event.preventDefault());
      lane.addEventListener("drop",event=>{event.preventDefault();run(async()=>{
        const item=applications.find(x=>String(x.id)===event.dataTransfer.getData("text/plain"));
        if(item&&item.stage!==name){await api("save",{...item,stage:name});await refresh();}
      });});
      for(const item of found.filter(x=>x.stage===name)){
        const a=card(item);a.draggable=true;a.addEventListener("dragstart",event=>event.dataTransfer.setData("text/plain",String(item.id)));lane.append(a);
      }
    }
    target.append(board);
  }else if($("view").value==="calendar"){
    const dates=found.flatMap(x=>[[x.deadline,"Deadline",x],[x.followup,"Follow-up",x]]).filter(x=>x[0]).sort((a,b)=>a[0].localeCompare(b[0]));
    if(!dates.length)return empty(target,"Add a deadline or follow-up to see it on the calendar.");
    for(const date of [...new Set(dates.map(x=>x[0]))]){
      target.append(node("h3",date));
      for(const [,type,item] of dates.filter(x=>x[0]===date)) target.append(node("p",null,button(type+" · "+item.company+" · "+item.role,()=>edit(item))));
    }
  }else{
    const table=node("table",null,node("thead",null,node("tr",null,...["Company","Role","Stage","Deadline","Follow-up","Actions"].map(x=>node("th",x)))));
    const body=node("tbody");table.append(body);
    for(const item of found) {
      const stage=node("select");stage.setAttribute("aria-label","Stage for "+item.company);
      for(const name of stages)option(stage,name,name,name===item.stage);
      stage.addEventListener("change",()=>run(async()=>{await api("save",{...item,stage:stage.value});await refresh();}));
      body.append(node("tr",null,node("td",item.company),node("td",item.role),node("td",null,stage),node("td",item.deadline||"—"),node("td",item.followup||"—"),
        node("td",null,button("Edit",()=>edit(item)),button("Delete",async()=>{
          if(confirm("Delete "+item.company+" · "+item.role+" and its stage history?")){await api("delete",{id:item.id});await refresh();}
        }))));
    }
    const frame=node("div",null,table);frame.className="scroll";target.append(frame);
  }
}
async function loadCvs(){
  cvs=await api("cvs");
  for(const id of ["match-cv","ai-cv"])selectList(id,cvs.map(x=>[x.id,x.name]),"Choose a CV");
  const list=$("cv-list");list.replaceChildren();
  for(const cv of cvs)textBlock(list,cv.name,cv.text).append(button("Delete CV",async()=>{
    if(confirm("Delete this CV?")){await api("delete-cv",{id:cv.id});await loadCvs();}
  }));
  if(!cvs.length)empty(list,"No CV versions yet.");
}
function bars(target,values,max){
  target.replaceChildren();
  for(const [name,count] of values){
    const bar=node("div");bar.className="bar";bar.style.width=(max?100*count/max:0)+"%";
    target.append(node("div",name+" · "+count),bar);
  }
}
function renderAnalytics(){
  const reached=names=>new Set(history.filter(x=>names.includes(x.stage)).map(x=>x.application)).size;
  const submitted=reached(["Applied","Online assessment","Technical interview","HR interview","Offer"]);
  const interviews=reached(["Technical interview","HR interview","Offer"]);
  const offers=reached(["Offer"]);
  const responses=reached(["Online assessment","Technical interview","HR interview","Offer","Rejected"]);
  const pct=(n,d)=>d?Math.round(n*100/d)+"%":"—";
  const repliedAfterSubmission=[...new Set(history.filter(x=>["Online assessment","Technical interview","HR interview","Offer","Rejected"].includes(x.stage))
    .filter(x=>history.some(h=>h.application===x.application&&["Applied","Online assessment","Technical interview","HR interview","Offer"].includes(h.stage))).map(x=>x.application))].length;
  metrics($("l-metrics"),[["Submitted",submitted],["Recorded response rate",pct(repliedAfterSubmission,submitted)],["Interview conversion",pct(interviews,submitted)],["Offers",offers]]);
  bars($("funnel"),[["Submitted",submitted],["Reached online assessment",reached(["Online assessment"])],["Interview or offer",interviews],["Offer",offers]],submitted);
  const target=$("breakdown");target.replaceChildren();
  for(const field of ["company","role","location"]){
    const counts={};for(const item of applications){const value=item[field]||"Unspecified";counts[value]=(counts[value]||0)+1;}
    textBlock(target,field[0].toUpperCase()+field.slice(1),Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(x=>x.join(" · ")).join("\n")||"No applications.");
  }
  const weekly={};for(const item of applications){const time=new Date(item.created.replace(" ","T")+"Z");time.setUTCDate(time.getUTCDate()-(time.getUTCDay()+6)%7);const key=time.toISOString().slice(0,10);weekly[key]=(weekly[key]||0)+1;}
  textBlock(target,"Weekly application activity",Object.entries(weekly).sort().reverse().map(x=>x.join(" · ")).join("\n")||"No activity yet.");
  $("l-history").replaceChildren(...history.slice(0,20).map(x=>node("p",x.company+" · "+x.stage+" · "+x.created.slice(0,10))));
  const performance=$("performance");performance.replaceChildren();
  if(!practice.length) empty(performance,"No sessions yet.");
  else bars(performance,practice.slice(0,10).map(x=>[x.topic+" "+x.created.slice(0,10),x.score]),100);
}
function renderPractice(){
  const target=$("practice-list");target.replaceChildren();
  for(const item of practice)textBlock(target,[item.company,item.topic,item.question].filter(Boolean).join(" · "),
    item.score+"% · "+item.minutes+" min\n"+item.mistake);
  if(!practice.length)empty(target,"No sessions logged yet.");
}
function displayClock(){
  $("clock").textContent=String(Math.floor(remaining/60)).padStart(2,"0")+":"+String(remaining%60).padStart(2,"0");
}
function resetTimer(){
  clearInterval(timer);timer=null;remaining=(Number($("timer-minutes").value)||25)*60;
  displayClock();$("start-timer").textContent="Start";
}
function toggleTimer(){
  if(timer){clearInterval(timer);timer=null;$("start-timer").textContent="Resume";return;}
  if(!remaining)resetTimer();
  deadline=Date.now()+remaining*1000;$("start-timer").textContent="Pause";
  timer=setInterval(()=>{
    remaining=Math.max(0,Math.ceil((deadline-Date.now())/1000));displayClock();
    if(!remaining){clearInterval(timer);timer=null;$("start-timer").textContent="Start";status("Practice timer finished.");}
  },250);
}

async function gmailStatus(){
  const value=await api("gmail-status");
  $("gmail-state").textContent=value.connected?"Gmail is connected. Fetch recent updates when you are ready.":value.configured?
    "Connect using your Google account. LAUNCHPAD requests read-only access.":
    "Gmail is optional. Set LAUNCHPAD_GOOGLE_CLIENT to your Desktop OAuth JSON file and restart LAUNCHPAD to connect.";
  $("gmail-connect").hidden=!value.configured||value.connected;
  $("gmail-refresh").hidden=!value.connected;
  $("gmail-disconnect").hidden=!value.connected;
}
async function loadInbox(){
  await gmailStatus();
  const target=$("gmail-list");target.replaceChildren();
  const messages=await api("gmail-inbox",{});
  for(const item of messages){
    const details=textBlock(target,item.subject||"No subject",[item.from,item.sent,item.snippet,item.stage,item.dates.join(", ")].filter(Boolean).join("\n"));
    const dates=node("select");dates.setAttribute("aria-label","Candidate deadline");
    option(dates,"","Keep existing deadline");
    for(const value of item.dates)option(dates,value,value);
    if(item.dates.length)details.append(dates);
    if(item.stage||item.dates.length)details.append(button("Apply selected updates",async()=>{
      const current=applications.find(x=>String(x.id)===$("mail-app").value);
      if(!current)throw Error("Choose an application above.");
      const next={...current,stage:item.stage||current.stage,deadline:dates.value||current.deadline};
      if(confirm("Update "+current.company+" to "+next.stage+(dates.value?" and set deadline to "+dates.value:"")+"?")){
        await api("save",next);await refresh();status("Application updated.");
      }
    }));
  }
  if(!messages.length)empty(target,"No matching recent messages.");
}
