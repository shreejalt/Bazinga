import { chromium } from 'playwright';
const [,, file, dir, theme, fps] = process.argv;
const b = await chromium.launch({channel:'chrome'});
const p = await (await b.newContext({viewport:{width:1280,height:440},deviceScaleFactor:1})).newPage();
await p.goto('file://'+file,{waitUntil:'networkidle'}); await p.evaluate(()=>document.fonts.ready);
if (theme==='dark') await p.evaluate(()=>document.body.classList.add('dark'));
const T = await p.evaluate(()=>window.T); const n=Math.round(T*fps);
for (let i=0;i<n;i++){ await p.evaluate(t=>window.render(t), i/fps); await p.screenshot({path:`${dir}/f${String(i).padStart(4,'0')}.png`}); }
await b.close(); console.log(n,'frames');
