/* Lists (every kind): the filter box narrows the rows, the pager shows them ten at a time.
   Markup: #find (input), #t-list tbody tr[data-text], #list-count (the line under the table), #pager (prev · n / N · next). */
(()=>{
 const PER=10,rows=[...document.querySelectorAll('#t-list tbody tr')],count=document.getElementById('list-count'),pager=document.getElementById('pager'),word=(pager&&pager.dataset.word)||'entries';
 if(!rows.length||!pager)return;
 let page=1,f='';
 function show(){const hit=rows.filter(tr=>!f||tr.dataset.text.includes(f));const pages=Math.max(1,Math.ceil(hit.length/PER));page=Math.min(Math.max(1,page),pages);
  rows.forEach(tr=>tr.hidden=true);hit.slice((page-1)*PER,page*PER).forEach(tr=>tr.hidden=false);
  pager.hidden=hit.length<=PER;pager.querySelector('.pg-n').textContent=`${page} / ${pages}`;pager.querySelector('.pg-prev').disabled=page<=1;pager.querySelector('.pg-next').disabled=page>=pages;
  count.textContent=hit.length?(hit.length>PER?`${(page-1)*PER+1}–${Math.min(page*PER,hit.length)} of ${hit.length} ${word}${f?' matching':''}.`:`${hit.length} ${hit.length===1?word.replace(/s$/,''):word}${f?' matching':''}.`):'Nothing matches that. Try another word.';
  if(hit.length>PER)document.getElementById('t-list').scrollIntoView({block:'nearest'});}
 pager.querySelector('.pg-prev').onclick=()=>{page--;show();};pager.querySelector('.pg-next').onclick=()=>{page++;show();};
 const find=document.getElementById('find');if(find)find.addEventListener('input',e=>{f=e.target.value.trim().toLowerCase();page=1;show();});
 document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;if(e.key==='ArrowRight'&&!pager.querySelector('.pg-next').disabled){page++;show();}if(e.key==='ArrowLeft'&&!pager.querySelector('.pg-prev').disabled){page--;show();}});
 show();
})();
