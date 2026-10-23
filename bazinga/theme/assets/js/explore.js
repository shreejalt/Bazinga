/* The map. The build lays it out (/data/map.json) and works out, for every page, what a hover shows and how the map
   plays it (/data/view/<id>.json): the rings nearest first, then the walk through the reading order. This file draws
   and plays them; clicking a page opens it. The series box finds chains in the map (/data/series.json at build time;
   "chain between" and "in reading order" are computed in the browser by the same code the build uses). */
(function(){
const q=s=>document.querySelector(s);
const BASE=(q('meta[name="bazinga-base"]')||{}).content||'';   // the path the site is served under, "" at the root
const M={hover:null,shown:null,filter:'all',q:'',tag:'',nodes:{},edges:{},layout:null,views:{},topics:{}};
const V=(window.BazingaConfig&&window.BazingaConfig.version)||'';
const stat=q('#m-stat');
const topicsOf=id=>M.topics[id]||[];
const label=id=>(SITE.nodes[id]||{}).kl||KIND[(M.nodes[id]||{}).type]||'';

// the map: boxes as on the read pages, every curve already a path string computed at build time
function draw(L){
 M.layout=L;M.nodes={};M.edges={};L.nodes.forEach(n=>M.nodes[n.id]=n);
 let s='';
 ['also','tag','builds'].forEach(kind=>L.edges.forEach(e=>{if(e.kind!==kind)return;M.edges[e.a+'>'+e.b]=e;
  s+=`<path class="e ${e.kind}" data-a="${esc(e.a)}" data-b="${esc(e.b)}" d="${e.d}"/>`;}));
 s+='<g id="fx-lines"></g>';
 L.nodes.forEach(n=>{const cx=n.x+n.w/2,two=n.lines.length>1,ty=two?n.y+28:n.y+34,sn=SITE.nodes[n.id]||{title:n.label,url:'#'};
  s+=`<a class="n t-${n.type}" data-id="${esc(n.id)}" href="${esc(sn.url)}" aria-label="${esc(label(n.id)+': '+sn.title)}">
  <rect class="rip" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}"/><rect class="p" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}"/>
  <text class="kd" x="${cx}" y="${n.y+14}" text-anchor="middle">${esc(label(n.id).toUpperCase())}</text>
  <text class="tt" x="${cx}" y="${ty}" text-anchor="middle">${n.lines.map((l,i)=>`<tspan x="${cx}"${i?' dy="13"':''}>${esc(l)}</tspan>`).join('')}</text>
  <g class="k"><circle cx="${n.x}" cy="${n.y}" r="8.5"/><text x="${n.x}" y="${n.y+3.4}" text-anchor="middle"></text></g>
  <g class="d"><circle cx="${n.x+n.w}" cy="${n.y}" r="8.5"/><text x="${n.x+n.w}" y="${n.y+3.4}" text-anchor="middle"></text></g></a>`;});
 s+='<g id="fx-top"></g>';
 const svg=q('#m');svg.setAttribute('viewBox',`0 0 ${L.width} ${L.height}`);svg.setAttribute('width',L.width);svg.setAttribute('height',L.height);svg.innerHTML=s;
 // when the map is wider than the screen, start with the top root in view instead of the left edge
 const wrap=svg.closest('.mapwrap');if(wrap&&L.nodes.length&&wrap.scrollWidth>wrap.clientWidth+1&&!wrap.dataset.scrolled){wrap.dataset.scrolled=1;
  const top=L.nodes.reduce((a,n)=>n.y<a.y?n:a,L.nodes[0]),k=svg.getBoundingClientRect().width/L.width;
  wrap.scrollLeft=Math.max(0,(top.x+top.w/2)*k-wrap.clientWidth/2);}}

// filters and the hovered page; the two walks themselves are played by play()
function paint(){
 const svg=q('#m'),filtering=!!(M.q||M.tag);
 svg.querySelectorAll('.n').forEach(g=>{const id=g.dataset.id,n=M.nodes[id],t=((SITE.nodes[id]||{}).title||'').toLowerCase();
  g.classList.toggle('off',M.filter!=='all'&&n.type!==M.filter);
  g.classList.toggle('sel',id===M.shown);
  g.classList.toggle('hit',!M.shown&&filtering&&((!M.q||n.label.toLowerCase().includes(M.q)||t.includes(M.q))&&(!M.tag||topicsOf(id).includes(M.tag))));});
 const off=id=>M.filter!=='all'&&M.nodes[id]&&M.nodes[id].type!==M.filter;
 svg.querySelectorAll('.e').forEach(e=>e.classList.toggle('off',off(e.dataset.a)||off(e.dataset.b)));
 q('#m-clear').hidden=!filtering;}

/* The two walks, played on the map from the schedule the build computed:
   the wave, nearest first, pops each page at its distance × step and draws the lines it crossed in rust;
   the walk, reading order, sends one dot along the lines, numbering each page as it arrives, in blue. */
const byId=id=>document.querySelector(`#m .n[data-id="${CSS.escape(id)}"]`);
const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
function clearPlay(){const svg=q('#m');q('#fx-lines')&&(q('#fx-lines').innerHTML='');q('#fx-top')&&(q('#fx-top').innerHTML='');svg.classList.remove('playing');
 svg.querySelectorAll('.e.far').forEach(e=>e.classList.remove('far'));
 document.querySelectorAll('#m .n').forEach(g=>{g.classList.remove('w','num','far');g.style.removeProperty('--t');g.style.removeProperty('--k');g.querySelector('.d text').textContent='';g.querySelector('.k text').textContent='';});}
function play(m){clearPlay();if(!m)return;const svg=q('#m'),still=reduced();let s='';
 const keep=new Set(m.wave.nodes.map(w=>w.id).concat(m.walk.stamps.map(st=>st.id)));if(M.shown)keep.add(M.shown);
 document.querySelectorAll('#m .n').forEach(g=>g.classList.toggle('far',!keep.has(g.dataset.id)));
 svg.querySelectorAll('.e').forEach(e=>e.classList.toggle('far',!keep.has(e.dataset.a)||!keep.has(e.dataset.b)));
 svg.classList.add('playing');
 m.wave.nodes.forEach(w=>{const g=byId(w.id);if(!g)return;g.classList.add('w');g.style.setProperty('--t',(still?0:w.t)+'ms');if(w.d)g.querySelector('.d text').textContent=w.d;});
 m.wave.edges.forEach(e=>{const E=M.edges[e.a+'>'+e.b];if(!E)return;
  s+=`<path class="wv" d="${e.src===e.a?E.d:E.rd}" style="--t0:${still?0:e.t0}ms;--dur:${still?0:e.t1-e.t0}ms"/>`;});
 m.walk.steps.forEach(st=>{if(!st.first)return;const E=M.edges[st.a+'>'+st.b];if(!E)return;
  s+=`<path class="wk" d="${st.down?E.d:E.rd}" style="--t0:${still?0:st.t0}ms;--dur:${still?0:st.t1-st.t0}ms"/>`;});
 const lines=q('#fx-lines');lines.innerHTML=s;lines.style.setProperty('--s',(still?0:m.walk.start)+'ms');
 lines.querySelectorAll('path').forEach(p=>p.style.setProperty('--len',p.getTotalLength().toFixed(1)));
 m.walk.stamps.forEach(st=>{const g=byId(st.id);if(!g)return;g.classList.add('num');g.style.setProperty('--k',(still?0:st.t)+'ms');g.querySelector('.k text').textContent=st.n;});
 if(m.walk.path.length>1&&!still&&m.walk.length>0&&'offsetPath' in document.documentElement.style){
  const d=m.walk.path.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join(''),S=m.walk.start,T=Math.max(1,m.walk.duration-S),len=m.walk.length;
  q('#fx-top').innerHTML='<circle class="dot" r="6"/>';const dot=q('#fx-top .dot');dot.style.offsetPath=`path("${d}")`;
  const kf=[{offsetDistance:'0%',offset:0}];
  m.walk.steps.forEach(st=>{kf.push({offsetDistance:(st.s0/len*100).toFixed(3)+'%',offset:Math.min(1,Math.max(0,(st.t0-S)/T))});kf.push({offsetDistance:(st.s1/len*100).toFixed(3)+'%',offset:Math.min(1,Math.max(0,(st.t1-S)/T))});});
  kf.push({offsetDistance:'100%',offset:1});
  for(let i=1;i<kf.length;i++)if(kf[i].offset<kf[i-1].offset)kf[i].offset=kf[i-1].offset;
  try{dot.animate(kf,{duration:T,delay:S,fill:'both',easing:'linear'});
   dot.animate([{opacity:0},{opacity:0,offset:Math.max(0,(S-300)/(m.walk.duration+600))},{opacity:1,offset:S/(m.walk.duration+600)},{opacity:1,offset:.97},{opacity:0}],{duration:m.walk.duration+600,fill:'forwards'});}catch(e){}}
 const w=m.wave.nodes.length-1,k=m.walk.stamps.length,sec=ms=>(ms/1000).toFixed(1).replace(/\.0$/,'');
 q('#m-play').textContent=`First, nearest first: ${w} item${w===1?'':'s'} within ${m.wave.reach} links, one ring every ${sec(m.wave.step)} s. Then the reading order: ${k} item${k===1?'':'s'}, walked in ${sec(m.walk.duration-m.walk.start)} s.`;}

async function viewOf(id){
 if(M.views[id])return M.views[id];
 const r=await fetch(BASE+'/data/view/'+id.replace(':','-')+'.json'+(V?'?v='+V:''));
 return (M.views[id]=await r.json());}
let timer=null;
function show(id){M.shown=id;const n=SITE.nodes[id]||{title:id};
 q('#m-head').innerHTML=`<a href="${esc(nodeHref(id))}">${esc(n.title)}</a><small>${esc(label(id))} · ${matchMedia('(hover: none)').matches?'tap again to open':'click to open'}</small>`;
 viewOf(id).then(v=>{if(M.shown!==id)return;q('#m-related').innerHTML=relatedHTML(v.related);q('#m-path').innerHTML=pathHTML(v.path);paint();play(v.motion);document.documentElement.dataset.sel=id;})
  .catch(()=>{stat.hidden=false;stat.textContent='The connections of this item could not be loaded.';});
 paint();}
function hover(id){clearTimeout(timer);timer=setTimeout(()=>show(id),90);}      // a short pause so sweeping across the map does not flicker

const svg=q('#m');
svg.addEventListener('pointerover',e=>{const g=e.target.closest('.n');if(g&&e.pointerType!=='touch')hover(g.dataset.id);});
svg.addEventListener('pointerleave',()=>clearTimeout(timer));
svg.addEventListener('focusin',e=>{const g=e.target.closest('.n');if(g)hover(g.dataset.id);});
let lastPointer='mouse';
svg.addEventListener('pointerdown',e=>{lastPointer=e.pointerType;});
svg.addEventListener('click',e=>{const g=e.target.closest('.n');if(!g)return;
 const touch=(e.pointerType||lastPointer)==='touch';
 if(touch&&M.shown!==g.dataset.id){e.preventDefault();show(g.dataset.id);}});   // on touch: the first tap shows, the second opens
q('#m-clear').onclick=()=>{M.q='';M.tag='';q('#m-find').value='';q('#m-tag').value='';paint();};
q('#m-find').oninput=e=>{M.q=e.target.value.trim().toLowerCase();M.shown=null;clearPlay();paint();};
q('#m-tag').onchange=e=>{M.tag=e.target.value;M.shown=null;clearPlay();paint();};
document.querySelectorAll('.chip[data-f]').forEach(c=>c.onclick=()=>{M.filter=c.dataset.f;document.querySelectorAll('.chip[data-f]').forEach(x=>x.setAttribute('aria-pressed',x===c));paint();});

const wanted=new URLSearchParams(location.search).get('tag');
Promise.all([fetch(BASE+'/data/map.json').then(r=>r.json()),fetch(BASE+'/data/mapdata.json').then(r=>r.json())]).then(([L,D])=>{
 (D.items||[]).forEach(it=>{M.topics[it.id]=it.topics||[];});
 draw(L);
 if(wanted&&SITE.nodes['topic:'+wanted]){M.tag=wanted;q('#m-tag').value=wanted;paint();}
}).catch(()=>{stat.hidden=false;stat.textContent='The map could not be loaded here.';});

/* ---- series found in the map ---- */
const box=q('#series');if(!box)return;
const sOut=q('#s-out'),sStat=q('#s-stat'),mod=box.dataset.mapview||BASE+'/figures/_mapview.py';
function seriesHTML(list,heading){
 if(!list||!list.length)return `<p class="why">${esc(heading)}: nothing found.</p>`;
 return list.map(s=>`<div class="gen" data-ids="${esc(s.ids.join(' '))}"><div class="sub">${esc(s.name)} · ${s.length} parts${s.declared===false?' · found on the map, not yet declared':s.declared?' · declared':''}</div>
  <ol class="series">${s.parts.map(p=>`<li><span class="n">${p.part}</span><a href="${esc(nodeHref(p.id))}">${esc(p.title)}</a><span class="dim"> · ${esc(label(p.id)||KIND[p.type]||'')}</span>${p.read_first&&p.read_first.length?`<span class="dim"> · read first: ${p.read_first.map(r=>`<a href="${esc(nodeHref(r.id))}">${esc(r.title)}</a>`).join(', ')}</span>`:''}</li>`).join('')}</ol>
  ${s.declared?'':`<details class="src"><summary>Make it official: the header lines</summary><pre>${esc(s.yaml)}</pre></details>`}</div>`).join('');}
function showChain(ids){M.shown=null;paint();const set=new Set(ids);
 svg.querySelectorAll('.n').forEach(g=>g.classList.toggle('hit',set.has(g.dataset.id)));}
sOut.addEventListener('pointerover',e=>{const g=e.target.closest('.gen');if(g&&e.pointerType!=='touch')showChain(g.dataset.ids.split(' '));});
async function runSeries(fn,args,heading){sStat.textContent='Finding the chains …';
 try{const py=window.Bazinga&&window.Bazinga.py;if(!py)throw new Error('not ready');
  const r=await py.call(mod,fn,Object.assign({data:{$json:BASE+'/data/mapdata.json'}},args));
  const list=Array.isArray(r)?r:(r?[r]:[]);sOut.innerHTML=seriesHTML(list,heading);
  sStat.textContent=`${heading}: ${list.length} series.`;sStat.classList.add('live');}
 catch(e){sStat.textContent='Still getting ready; try again in a moment.';}}
q('#s-between').onclick=()=>{const a=q('#s-from').value,b=q('#s-to').value;if(a&&b)runSeries('series_between',{start:a,end:b},'Chain between');};
q('#s-bytag').onclick=()=>{const t=q('#s-tag').value;if(t)runSeries('series_for_tag',{tag:t},'In reading order');};
fetch(BASE+'/data/series.json').then(r=>r.json()).then(list=>{sOut.innerHTML=seriesHTML(list,'Found on the map');sStat.textContent=`Found on the map: ${list.length} series.`;sStat.classList.add('live');}).catch(()=>{});
})();
