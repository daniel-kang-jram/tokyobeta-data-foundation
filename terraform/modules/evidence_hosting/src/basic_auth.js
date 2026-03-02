function handler(e){
var r=e.request,h=r.headers||{},u=${auth_users_json},m="${auth_ui_mode}",ttl=${auth_session_max_age_seconds},lang="${auth_login_copy_language}";
if(m==="browser_basic"){return ai(hv(h,"authorization"),u)>=0?r:b401();}
return flow(r,h,u,ttl,lang);
}
function flow(r,h,u,ttl,lang){
var uri=r.uri||"/",q=r.querystring||"",qraw=qs(q),rt=norm(qp(q,"return_to"));
if(uri.indexOf("/__auth/assets/")===0){return r;}
if(uri==="/__auth/logout"){return red("/__auth/login",delc());}
var tok=ck(r,h,"evidence_session"),ok=tokv(tok,u);
if(uri==="/__auth/login"){
var a=hv(h,"authorization");
if(!a){return ok?red(rt):page(rt,false,lang,200);}
var idx=ai(a,u);
if(idx<0){return page(rt,true,lang,401);}
return red(rt,setc(idx,u,ttl));
}
if(!ok){
var cur=uri+(qraw?"?"+qraw:"");
return red("/__auth/login?return_to="+encodeURIComponent(cur));
}
return rw(r);
}
function rw(r){
var u=r.uri||"/";
if(u==="/"||u===""){r.uri="/index.html";return r;}
if(sw(u,"/__auth")||sw(u,"/api")||sw(u,"/_app")||sw(u,"/data")){return r;}
if(u==="/fix-tprotocol-service-worker.js"){return r;}
if(u.charAt(u.length-1)==="/"){r.uri=u+"index.html";return r;}
if(u.indexOf(".")>=0){return r;}
r.uri=u+"/index.html";
return r;
}
function sw(u,p){return u===p||u.indexOf(p+"/")===0;}
function b401(){return{statusCode:401,statusDescription:"Unauthorized",headers:{"www-authenticate":{value:"Basic realm=\"Evidence Dashboard\""},"cache-control":{value:"no-store, no-cache, max-age=0"}}};}
function red(loc,c){var x={statusCode:302,statusDescription:"Found",headers:{location:{value:loc},"cache-control":{value:"no-store, no-cache, max-age=0"}}};if(c){x.cookies={};x.cookies[c.name]={value:c.value,attributes:c.attributes};}return x;}
function page(rt,err,lang,st){return{statusCode:st,statusDescription:st===401?"Unauthorized":"OK",headers:{"content-type":{value:"text/html; charset=utf-8"},"cache-control":{value:"no-store, no-cache, max-age=0"},pragma:{value:"no-cache"}},body:html(norm(rt),err,lang)};}
function hv(h,k){var v=h&&h[k];return v&&v.value?v.value:"";}
function ai(a,u){if(!a||a.indexOf("Basic ")!==0){return-1;}var t=a.slice(6);for(var i=0;i<u.length;i++){if(t===u[i]){return i;}}return-1;}
function qp(q,k){
if(!q){return"";}
if(typeof q!=="string"){
var o=q[k];if(!o){return"";}
if(o.multiValue&&o.multiValue.length){return dc((o.multiValue[0].value||"").replace(/\+/g,"%20"));}
return dc((o.value||"").replace(/\+/g,"%20"));
}
var p=q.split("&");
for(var i=0;i<p.length;i++){
var s=p[i],j=s.indexOf("="),x=j>=0?s.slice(0,j):s;
if(dc(x.replace(/\+/g,"%20"))!==k){continue;}
var v=j>=0?s.slice(j+1):"";
return dc(v.replace(/\+/g,"%20"));
}
return"";
}
function qs(q){
if(!q){return"";}
if(typeof q==="string"){return q;}
var a=[],keys=Object.keys(q);
for(var i=0;i<keys.length;i++){
var k=keys[i],o=q[k];
if(!o){continue;}
if(o.multiValue&&o.multiValue.length){
for(var j=0;j<o.multiValue.length;j++){a.push(k+"="+encodeURIComponent(o.multiValue[j].value||""));}
}else{a.push(k+"="+encodeURIComponent(o.value||""));}
}
return a.join("&");
}
function norm(rt){var x=String(rt||"");if(!x||x.charAt(0)!=="/"||x.indexOf("//")===0||x.indexOf("/__auth")===0||x.indexOf("\\")>=0||/%2f|%5c/i.test(x)||/[\r\n]/.test(x)){return"/";}return x;}
function ck(r,h,key){var c=r.cookies&&r.cookies[key];if(c&&c.value){return c.value;}var raw=hv(h,"cookie");if(!raw){return"";}var p=raw.split(";");for(var i=0;i<p.length;i++){var s=p[i].trim(),j=s.indexOf("=");if(j<=0){continue;}if(s.slice(0,j).trim()!==key){continue;}return dc(s.slice(j+1).trim());}return"";}
function setc(idx,u,ttl){var t=ttl>0?ttl:28800,exp=Math.floor(Date.now()/1000)+t,seed=hx(u.join("|")),sig=hx(idx+"."+exp+"."+seed),tok="v1."+idx+"."+exp+"."+sig;return{name:"evidence_session",value:tok,attributes:"Max-Age="+t+"; Path=/; HttpOnly; Secure; SameSite=Lax"};}
function delc(){return{name:"evidence_session",value:"",attributes:"Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax"};}
function tokv(tok,u){if(!tok){return false;}var p=tok.split(".");if(p.length!==4||p[0]!=="v1"){return false;}var i=parseInt(p[1],10),exp=parseInt(p[2],10),sig=p[3];if(isNaN(i)||i<0||i>=u.length||isNaN(exp)||Math.floor(Date.now()/1000)>=exp){return false;}return hx(i+"."+exp+"."+hx(u.join("|")))==sig;}
function hx(s){s=String(s||"");var h=2166136261;for(var i=0;i<s.length;i++){h^=s.charCodeAt(i);h+=(h<<1)+(h<<4)+(h<<7)+(h<<8)+(h<<24);}return("00000000"+(h>>>0).toString(16)).slice(-8);}
function dc(v){try{return decodeURIComponent(v);}catch(e){return"";}}
function txt(lang){
return{t:"IM Dashboard Sign In",s:"Enter credentials to continue",u:"User ID",p:"Password",b:"Sign in",e:"Invalid ID or password."};
}
function esc(v){return String(v||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");}
function html(rt,err,lang){
var c=txt(lang),er=err?"<p class='e'>"+esc(c.e)+"</p>":"";
return"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+esc(c.t)+"</title><style>*,:before,:after{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:14px;font:12.5px 'Segoe UI',Inter,sans-serif;background:#dbe5f3;overflow:hidden}.bg{position:fixed;inset:0;z-index:0;overflow:hidden}.bgv{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.95;filter:saturate(1.04) contrast(1.1) brightness(.78);animation:bgPan 26s ease-in-out infinite alternate;transform:scale(1.06) translateX(-.5%)}.veil{position:absolute;inset:0;background:radial-gradient(1000px 520px at 50% -12%,rgba(255,255,255,.08),rgba(255,255,255,.03) 44%,rgba(205,218,236,.14) 100%),linear-gradient(180deg,rgba(221,231,245,.08) 0%,rgba(208,221,238,.12) 100%)}.wave{position:absolute;left:0;right:0;bottom:-12vh;height:34vh;background:linear-gradient(180deg,rgba(223,232,243,0) 0%,rgba(205,217,234,.12) 100%);clip-path:ellipse(70% 54% at 50% 100%)}@keyframes bgPan{0% {transform:scale(1.06) translateX(-.5%) translateY(0)}100% {transform:scale(1.09) translateX(.8%) translateY(-.5%)}}.c{width:min(430px,calc(100vw - 28px));background:rgba(250,253,255,.84);backdrop-filter:blur(7px);border-radius:14px;box-shadow:0 18px 45px rgba(12,18,31,.18);overflow:hidden;border:1px solid rgba(255,255,255,.72);position:relative;z-index:2}.hd{background:transparent;color:#0f172a;padding:18px 20px;border-bottom:1px solid #d7e1ee}.hd b{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.11em}.hd h1{margin:4px 0 4px;font-size:17px;line-height:1.25}.hd p{margin:0;font-size:11px;color:#4b5c74}.bd{padding:16px 20px 18px}.r{margin:0 0 10px}.r label{display:block;font-size:11px;font-weight:600;margin:0 0 5px}.r input{width:100%;height:36px;border:1px solid #bfd0e6;border-radius:9px;padding:0 10px;background:rgba(255,255,255,.9);font-size:13px;outline:none}button{width:100%;height:38px;border:0;border-radius:9px;background:#0f172a;color:#fff;font-weight:600;font-size:14px;cursor:pointer}.e{margin:0 0 10px;padding:9px 10px;border-radius:8px;background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;font-size:11px}</style></head><body><div class='bg' aria-hidden='true'><video class='bgv' autoplay muted loop playsinline preload='auto' src='/__auth/assets/bg.mp4'></video><div class='veil'></div><div class='wave'></div></div><div class='c'><div class='hd'><b>TokyoBeta Evidence</b><h1>"+esc(c.t)+"</h1><p>"+esc(c.s)+"</p></div><div class='bd'>"+er+"<form id='f'><div class='r'><label for='u'>"+esc(c.u)+"</label><input id='u' required></div><div class='r'><label for='p'>"+esc(c.p)+"</label><input id='p' type='password' required></div><button type='submit'>"+esc(c.b)+"</button></form></div></div><script>(function(){var rt="+JSON.stringify(rt)+",f=document.getElementById('f'),v=document.querySelector('.bgv');if(v){var pr=v.play&&v.play();if(pr&&pr.catch){pr.catch(function(){});}}function b64(s){try{return btoa(unescape(encodeURIComponent(s)));}catch(e){return btoa(s);}}f.onsubmit=function(e){e.preventDefault();var u=document.getElementById('u').value||'',p=document.getElementById('p').value||'';if(!u||!p){return;}fetch('/__auth/login?return_to='+encodeURIComponent(rt),{method:'GET',headers:{Authorization:'Basic '+b64(u+':'+p)},credentials:'same-origin',redirect:'manual'}).then(function(r){if(r.type==='opaqueredirect'||r.status===302||r.status===0){window.location.assign(r.headers.get('location')||rt||'/');return null;}return r.text();}).then(function(t){if(t){document.open();document.write(t);document.close();}}).catch(function(){window.location.assign('/__auth/login?return_to='+encodeURIComponent(rt));});};})();</script></body></html>";
}
