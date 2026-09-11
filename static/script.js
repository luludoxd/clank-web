const $=id=>document.getElementById(id);
let key=sessionStorage.getItem("clank_api_key")||"";
let results=[], selected=-1;

function setApiState(){ $("sideApi").textContent=key?"● Connected":"● Not configured"; $("sideApi").style.color=key?"#86efac":"#fca5a5"; }
function openKey(){ $("apiKey").value=key; $("modal").classList.remove("hidden"); $("apiKey").focus(); }
$("apiNav").onclick=openKey;
$("cancelKey").onclick=()=>$("modal").classList.add("hidden");
$("saveKey").onclick=()=>{key=$("apiKey").value.trim();if(!key){alert("Please enter a YouTube API key.");return}sessionStorage.setItem("clank_api_key",key);$("modal").classList.add("hidden");setApiState();};
$("statusNav").onclick=()=>alert(key?"🟢 API key configured for this browser session.":"🔴 No API key configured.\n\nGo to Settings → API Key.");
document.querySelectorAll(".nav[data-tab]").forEach(b=>b.onclick=()=>{document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));$(b.dataset.tab).classList.add("active");if(b.dataset.tab==="library")renderLibrary();});

function library(){try{return JSON.parse(localStorage.getItem("clank_library")||"[]")}catch{return[]}}
function saveLibrary(x){localStorage.setItem("clank_library",JSON.stringify(x))}
function addLibrary(r){let x=library().filter(a=>a.channel_id!==r.channel_id);x.push({channel_id:r.channel_id,url:r.channel_url,name:r.name,score:r.score,flags:r.flags||[],added:new Date().toISOString()});saveLibrary(x);renderLibrary();}

function renderLibrary(){const x=library();$("libAll").textContent=x.length;$("libDown").textContent="—";$("libOnline").textContent="—";$("libraryRows").innerHTML=x.map((r,i)=>`<tr data-i="${i}"><td>${r.score??"-"}</td><td>${esc(r.name)}</td><td>⚪ Unknown</td><td>${(r.flags||[]).map(f=>`<span>${esc(f)}</span>`).join(" ")||"-"}</td><td><a target="_blank" href="${esc(r.url)}">${esc(r.url)}</a></td><td>${esc((r.added||"").slice(0,16).replace("T"," "))}</td></tr>`).join("");document.querySelectorAll("#libraryRows tr").forEach(tr=>tr.onclick=()=>{document.querySelectorAll("#libraryRows tr").forEach(x=>x.classList.remove("selected"));tr.classList.add("selected");selected=Number(tr.dataset.i)});}

$("refreshLib").onclick=async()=>{const x=library();if(!key||!x.length){renderLibrary();return}try{const r=await fetch("/api/library-status",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api_key:key,ids:x.map(a=>a.channel_id)})});const d=await r.json();if(!r.ok)throw Error(d.error);const online=new Set(d.online);$("libOnline").textContent=[...online].length;$("libDown").textContent=x.length-online.size;document.querySelectorAll("#libraryRows tr").forEach((tr,i)=>tr.children[2].textContent=online.has(x[i].channel_id)?"🟢 Still Online":"🔴 Taken Down")}catch(e){alert(e.message)}};
$("libOpen").onclick=()=>{const x=library()[selected];if(x)window.open(x.url,"_blank");else alert("Please select an account first.")};
$("libRemove").onclick=()=>{const x=library();if(selected<0){alert("Please select an account first.");return}x.splice(selected,1);selected=-1;saveLibrary(x);renderLibrary()};

function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]))}
function render(){ $("comments").textContent=(window.lastData?.comments||0).toLocaleString();$("accounts").textContent=(window.lastData?.accounts||0).toLocaleString();$("hits").textContent=(window.lastData?.hits||0).toLocaleString();$("results").innerHTML=results.map((r,i)=>`<tr class="${i===selected?"selected":""}" data-i="${i}"><td class="score">${r.score} / 50</td><td><b>${esc(r.name)}</b><br><a target="_blank" href="${esc(r.channel_url)}">Open channel</a></td><td class="comment">${esc(r.comment)}</td><td>${esc(r.age)}</td><td class="flags">${(r.flags||[]).map(f=>`<span>${esc(f)}</span>`).join("")||"-"}</td><td class="actions"><button class="cyan" onclick="addLibrary(results[${i}]);event.stopPropagation()">Add to library</button></td></tr>`).join("");document.querySelectorAll("#results tr").forEach(tr=>tr.onclick=()=>{selected=Number(tr.dataset.i);render()})}
$("start").onclick=async()=>{if(!key){openKey();return}const url=$("url").value.trim();if(!url){alert("Enter a YouTube video or Short URL.");return}selected=-1;results=[];$("results").innerHTML="";$("statusBadge").textContent="SCANNING";$("statusBadge").className="badge scanning";$("start").disabled=true;$("start").textContent="⏳  ANALYZING...";try{const d=await (await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api_key:key,url,ignored_ids:library().map(x=>x.channel_id)})})).json();if(d.error)throw Error(d.error);window.lastData=d;results=d.results||[];render();$("statusBadge").textContent="READY";$("statusBadge").className="badge ready"}catch(e){$("statusBadge").textContent="ERROR";$("statusBadge").className="badge scanning";alert(e.message)}finally{$("start").disabled=false;$("start").textContent="▶  START ANALYSIS"}};

function current(){return results[selected]||null}
async function copy(text){await navigator.clipboard.writeText(text);alert("Copied to clipboard.")}
$("copyFlags").onclick=()=>{const r=current();if(!r){alert("Select a result first.");return}copy((r.flags||[]).map(x=>"- "+x).join("\n")||"No specific flags recorded.")};
$("openChannel").onclick=()=>{const r=current();if(!r){alert("Select a result first.");return}window.open(r.channel_url,"_blank");copy(r.report)};
$("report").onclick=()=>{const r=current();if(!r){alert("Select a result first.");return}copy(r.report);window.open(r.channel_url,"_blank")};
$("profileReport").onclick=()=>{const r=current();if(!r){alert("Select a result first.");return}copy(r.profile_report);window.open(r.channel_url,"_blank")};
setApiState();renderLibrary();