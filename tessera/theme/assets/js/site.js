/* Shared by every page. window.SITE is written by the build into /data/site.js:
   SITE.nodes  every page, reference and topic, by id: {type, kl (kind label), title, url, desc, kicker, go}
   SITE.kinds  the label of each type on the map (read, paper, proj, ext, ref, topic) */
const SITE=window.SITE||{nodes:{},kinds:{}};
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
const KIND=Object.assign({read:'Read',paper:'Paper',proj:'Project',ext:'Article',ref:'Reference',topic:'Tag'},SITE.kinds||{});
const node=id=>SITE.nodes[id];
const nodeHref=id=>(node(id)||{}).url||'#';
const kindOf=id=>{const n=node(id);return n?(n.kl||KIND[n.type]||''):'';};

/* preview card: any element with data-x="<id>" shows a card on hover or focus */
document.addEventListener('DOMContentLoaded',function(){
 const pop=document.createElement('div');pop.className='pop';pop.setAttribute('role','tooltip');document.body.appendChild(pop);
 function fill(id){const n=node(id);if(!n||n.type==='topic')return false;
  pop.innerHTML=`<div class="kind${n.type==='ref'?'':' int'}">${esc(n.kicker||'')}</div><div class="ti">${esc(n.title)}</div>${n.desc?`<div>${esc(n.desc)}</div>`:''}<div class="go">${esc(n.go||'')}</div>`;return true;}
 function show(e){const el=e.target.closest&&e.target.closest('[data-x]');if(!el||!fill(el.dataset.x))return;
  const r=el.getBoundingClientRect();pop.classList.add('on');
  const w=pop.offsetWidth,h=pop.offsetHeight;
  let left=Math.min(window.innerWidth-w-16,Math.max(16,r.left));
  let top=r.bottom+8;if(top+h>window.innerHeight-8)top=r.top-h-8;
  if(el.closest('.askpanel')){const pr=el.closest('.askpanel').getBoundingClientRect();left=Math.max(16,pr.left-w-12);top=Math.min(Math.max(8,r.top),window.innerHeight-h-8);}   // beside the floating Ask, never under it
  top=Math.min(Math.max(8,top),Math.max(8,window.innerHeight-h-8));
  pop.style.left=(left+scrollX)+'px';pop.style.top=(top+scrollY)+'px';}
 function hide(e){if(e.target.closest&&e.target.closest('[data-x]'))pop.classList.remove('on');}
 document.addEventListener('mouseover',show);document.addEventListener('focusin',show);
 document.addEventListener('mouseout',hide);document.addEventListener('focusout',hide);
});

/* the rail highlights the section being read; [data-reveal] elements animate once when they scroll in */
function spy(){
 const links=[...document.querySelectorAll('.rail nav a[href^="#"]')];
 const map=new Map(links.map(a=>[document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1))),a]));
 if('IntersectionObserver' in window){
  const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){links.forEach(a=>a.removeAttribute('aria-current'));const a=map.get(e.target);if(a)a.setAttribute('aria-current','true');}}),{rootMargin:'-20% 0px -70% 0px'});
  map.forEach((a,el)=>el&&io.observe(el));
  const rv=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('on');rv.unobserve(e.target);}}),{threshold:.3});
  document.querySelectorAll('[data-reveal]').forEach(el=>rv.observe(el));
 }else document.querySelectorAll('[data-reveal]').forEach(el=>el.classList.add('on'));
 document.querySelectorAll('.draw').forEach(p=>{try{p.style.setProperty('--len',p.getTotalLength().toFixed(1));}catch(e){}});
 if(new URLSearchParams(location.search).has('still'))document.querySelectorAll('[data-reveal]').forEach(el=>el.classList.add('on'));
}
document.addEventListener('DOMContentLoaded',spy);

/* the two lists Explore and Ask fill in (the same lists are rendered at build time on every page) */
const itemLink=n=>n.type==='topic'?esc(n.title):`<a data-x="${esc(n.id)}" href="${esc(n.url||nodeHref(n.id))}">${esc(n.title)}</a>`;
function relatedHTML(list){return list.map(r=>`<li><div>${itemLink(r)}</div><div class="why">${esc(r.kl||kindOf(r.id)||KIND[r.type]||'')} · ${esc(r.why)}</div></li>`).join('')||'<li class="why">Nothing connected yet.</li>';}
function pathHTML(path,cap=6){const tag={before:'Start with',here:'You are here',after:'Then',also:'Also worth reading'};let last='',seenAfter=0,hidden=0;
 const rows=path.map(p=>{const head=p.role!==last?`<div class="role">${tag[p.role]}</div>`:'';last=p.role;
  const extra=p.role==='after'&&++seenAfter>cap?(hidden++,' class="more-row"'):'';
  return `<li class="${p.role}"${extra?' data-more="1"':''}${extra?' hidden':''}>${head}<div>${p.role==='here'?`<b>${esc(p.title)}</b>`:itemLink(p)}</div><div class="why">${esc(p.kl||kindOf(p.id)||KIND[p.type]||'')}</div></li>`}).join('');
 return rows+(hidden?`<li class="why"><button class="chip" type="button" data-more-btn>Show ${hidden} more</button></li>`:'');}
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-more-btn]');if(!b)return;b.closest('ol').querySelectorAll('[data-more]').forEach(l=>l.hidden=false);b.closest('li').remove();});

/* a tag opens its topic page (/topics/<tag>/); on the map page it filters the map instead */
document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('[data-tag]');if(!a)return;
 const sel=document.getElementById('m-tag');
 if(sel&&[...sel.options].some(o=>o.value===a.dataset.tag)){e.preventDefault();sel.value=a.dataset.tag;sel.dispatchEvent(new Event('change'));document.getElementById('m').scrollIntoView({behavior:'smooth',block:'start'});}});

/* the "pick one" buttons in the home page's about: say back what the chosen one deserves */
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('.starters .btn');if(!b)return;
 const box=b.closest('.starters');box.querySelectorAll('.btn').forEach(x=>x.setAttribute('aria-pressed',x===b));
 box.querySelector('.verdict').textContent=b.dataset.say;});
