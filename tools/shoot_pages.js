/* 把 index.html 整頁截圖，並算好「不會切到東西」的分頁位置。
   用法：NODE_PATH=<playwright 位置> node tools/shoot_pages.js
   輸出：assets/print/full.png（整頁）與 assets/print/cuts.json（切點）
   接著跑 python3 tools/make_docx.py 把它切成一頁一張貼進 Word。

   分頁分兩層：
   ① 先切「單元」——封面、行前、每一天各是一個單元，單元邊界一定是頁的邊界。
      所以翻頁永遠不會翻到一半就換成別天，一天的東西自己成一疊。
   ② 單元內部再平均分成 n 頁（n = 這個單元塞得下的最少頁數），
      切點取自不會切斷文字、照片或表格列的候選位置。
      平均分而不是把前面塞滿，兩頁的那一天才不會第一頁滿、第二頁只有兩行。

   最後的參考區塊（每天吃什麼、訂票、出發前確認、三段巴士、頁尾）不是「一天」，
   讓它們連續排下去；各自獨立成單元只會多出好幾頁半空白的紙。

   單元高度容許超出一點點（TOL）：make_docx 會把超過的圖等比縮小塞進頁面，
   縮 8% 以內看不太出來，但可以讓「差一點就一頁」的日子真的變成一頁。 */
const {chromium}=require('playwright');
const fs=require('fs'), path=require('path');
const ROOT=path.resolve(__dirname,'..');
const OUT=path.join(ROOT,'assets','print');

const W=+process.env.PRINT_W||680;   // 渲染寬度（CSS px）。窄一點＝印出來字相對變大：
                          // 680px 換算後內文約 12pt，而且在 860px 斷點以下會排成單欄。
                          // 想拿字級換頁數就設 PRINT_W（760 約 10.7pt、820 約 10pt）
const SCALE=2;             // 2 倍解析度，列印才不糊
const RATIO=27.7/19.0;     // A4 扣掉 1cm 邊界後的高寬比
const H=Math.round(W*RATIO);
const TOL=1.08;            // 單元可以超出頁高的比例；超出的部分由 make_docx 等比縮小吸收
const HMAX=Math.round(H*TOL);

(async()=>{
  fs.mkdirSync(OUT,{recursive:true});
  const exe=process.env.CHROME||'/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  const b=await chromium.launch({executablePath:exe});
  const p=await b.newPage({viewport:{width:W,height:H},deviceScaleFactor:SCALE,reducedMotion:'reduce'});
  await p.goto('file://'+path.join(ROOT,'index.html'),{waitUntil:'load'});
  await p.waitForTimeout(2500);

  // 照片是 lazy load 的，要先整頁捲過一遍才會下載
  await p.evaluate(async()=>{
    document.querySelectorAll('img').forEach(i=>{i.loading='eager';});
    for(let y=0;y<document.body.scrollHeight;y+=500){scrollTo(0,y);await new Promise(r=>setTimeout(r,70));}
    scrollTo(0,0);
    await Promise.all([...document.querySelectorAll('img')].map(i=>
      i.complete?null:new Promise(r=>{i.onload=i.onerror=r;})));
  });
  await p.waitForTimeout(1500);

  const info=await p.evaluate(()=>{
    const hide=s=>document.querySelectorAll(s).forEach(e=>e.style.display='none');
    hide('nav.strip');                       // 置頂導覽列，每一片都會重複出現
    hide('.poitog'); hide('.replay');        // 只有滑鼠點得到才有意義的按鈕
    hide('.bigver');                         // 「改看大字版」的連結，紙本上沒用
    // 頁尾那行「下載紙本版 Word」——印在 Word 裡面很怪
    document.querySelectorAll('footer a[href$=".docx"]').forEach(a=>{
      (a.closest('p')||a).style.display='none';});

    // 載不到的照片（維基百科那幾張）會留一個灰框，整格藏掉比較乾淨
    let empty=0;
    document.querySelectorAll('img').forEach(i=>{
      if(!i.naturalWidth){ empty++; const box=i.closest('.ph')||i; box.style.display='none'; }
    });

    // 動畫直接跳到最後一格
    document.querySelectorAll('.mapwrap>svg .leg').forEach(l=>{
      l.style.strokeDasharray='none';l.style.strokeDashoffset='0';l.style.opacity='1';});
    document.querySelectorAll('.mapwrap>svg .pin,.mapwrap>svg .plabel')
      .forEach(e=>e.style.opacity='1');
    document.querySelectorAll('#heroMap .leg').forEach(l=>{l.style.opacity='1';l.style.stroke='';});

    const Y=e=>{const r=e.getBoundingClientRect();
                return [Math.round(r.top+scrollY),Math.round(r.bottom+scrollY),r.height];};

    // 不可以從中間切開的東西。切在它們的上下緣可以，切進去就會把標題、
    // 一張照片或表格的一列剖成兩半。
    const atomic=[];
    document.querySelectorAll(
      '.day-head, .mapcard, .ph, .money, .one, .plan-head, .mapfoot, tr, li, h1, h2, h3, p, dt, dd'
    ).forEach(e=>{const [t,b,h]=Y(e); if(h>0) atomic.push([t,b]);});

    // 候選切點：所有區塊的下緣，扣掉落在上面那些東西內部的
    const raw=new Set([0]);
    document.querySelectorAll(
      'section, .day, .mapcard, .tlrow, .notes>*, .ph, table, tr, h2, h3, p, li, .one, .money, .plan, footer, dl, dd'
    ).forEach(e=>{const [t,b,h]=Y(e); if(h>0) raw.add(b);});
    const cuts=[...raw].filter(c=>!atomic.some(([t,b])=>c>t&&c<b)).sort((a,b)=>a-b);

    // 單元邊界：行前與每一天。這些位置一定要落在頁的邊界上。
    const units=[];
    document.querySelectorAll('#pre, .day').forEach(e=>{const [t]=Y(e);
      units.push({top:t, name:(e.querySelector('.day-head .date, h2')||e).textContent.trim().slice(0,26)||e.id});});
    units.sort((a,b)=>a.top-b.top);
    // 最後一天結束的位置：之後全部當成「參考區塊」連續排
    const tailTop=Y(document.querySelector('#meals'))[0];

    return {total:document.body.scrollHeight, cuts, units, tailTop,
            imgs:document.querySelectorAll('img').length, empty};
  });
  await p.waitForTimeout(400);

  // 單元 = [開頭, 結尾)，最前面那段（封面）也算一個，最後收在最後一天結束處
  const bounds=[0,...info.units.map(u=>u.top).filter(t=>t>0),info.tailTop]
    .filter((v,i,a)=>i===0||v>a[i-1]);
  const names=['封面',...info.units.map(u=>u.name)];

  // 單元內部平均分頁：切點盡量靠近等分位置，且不會切斷任何東西
  function split(a,b){
    const h=b-a, n=Math.max(1,Math.ceil(h/HMAX)), out=[];
    let y=a;
    for(let k=1;k<n;k++){
      const target=a+Math.round(h*k/n);
      const hi=Math.min(y+HMAX,b-1);            // 這一頁塞不下更多
      const lo=Math.max(y+1,b-(n-k)*HMAX);      // 剩下的頁數要塞得完
      let best=null,bd=Infinity;
      for(const c of info.cuts){
        if(c<lo||c>hi) continue;
        const d=Math.abs(c-target); if(d<bd){bd=d;best=c;}
      }
      if(best===null) best=Math.min(hi,Math.max(lo,target));   // 沒有乾淨切點才硬切
      out.push([y,best-y]); y=best;
    }
    out.push([y,b-y]);
    return out;
  }

  const slices=[]; const report=[];
  for(let i=0;i<bounds.length-1;i++){
    const parts=split(bounds[i],bounds[i+1]);
    report.push([names[i]||`單元${i}`,parts.length,bounds[i+1]-bounds[i]]);
    slices.push(...parts);
  }

  // 參考區塊：不綁單元，照舊往下貪心填滿，切在乾淨的位置
  let y=info.tailTop, tail=0;
  while(y<info.total-4){
    const limit=y+H;
    if(limit>=info.total){ slices.push([y,info.total-y]); tail++; break; }
    let cut=0;
    for(const c of info.cuts){ if(c<=limit && c>y+H*0.45) cut=c; }
    if(!cut) cut=limit;
    slices.push([y,cut-y]); tail++; y=cut;
  }
  report.push(['（每天吃什麼 → 頁尾，連續排）',tail,info.total-info.tailTop]);

  await p.screenshot({path:path.join(OUT,'full.png'),fullPage:true});
  fs.writeFileSync(path.join(OUT,'cuts.json'),
    JSON.stringify({width:W,scale:SCALE,pageHeight:H,total:info.total,slices},null,1));
  console.log(`整頁 ${W}×${info.total}px（${SCALE} 倍）；照片 ${info.imgs} 張，其中 ${info.empty} 張載不到已藏起來`);
  console.log(`切成 ${slices.length} 頁，頁高 ${H}px（單元最多可超出到 ${HMAX}px，由縮圖吸收）`);
  console.log('每個單元佔幾頁：');
  for(const [n,pages,h] of report)
    console.log(`  ${pages} 頁${pages>2&&!n.startsWith('（')?'  ← 超過兩頁':'    '}  ${String(h).padStart(5)}px  ${n}`);
  await b.close();
})();
