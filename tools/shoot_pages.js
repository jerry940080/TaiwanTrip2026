/* 把 index.html 整頁截圖，並算好「不會切到東西」的分頁位置。
   用法：NODE_PATH=<playwright 位置> node tools/shoot_pages.js
   輸出：assets/print/full.png（整頁）與 assets/print/cuts.json（切點）
   接著跑 python3 tools/make_docx.py 把它切成一頁一張貼進 Word。

   切點不是固定高度：收集所有小區塊的下緣當候選，每頁取不超過頁高的最後一個，
   這樣不會把一行字、一張照片或表格的一列從中間切斷。 */
const {chromium}=require('playwright');
const fs=require('fs'), path=require('path');
const ROOT=path.resolve(__dirname,'..');
const OUT=path.join(ROOT,'assets','print');

const W=680;              // 渲染寬度（CSS px）。窄一點＝印出來字相對變大：
                          // 680px 換算後內文約 12pt，而且在 860px 斷點以下會排成單欄
const SCALE=2;             // 2 倍解析度，列印才不糊
const RATIO=27.7/19.0;     // A4 扣掉 1cm 邊界後的高寬比
const H=Math.round(W*RATIO);

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

    // 每一天盡量從新的一頁開始
    const dayTops=[...document.querySelectorAll('.day')].map(e=>Y(e)[0]).sort((a,b)=>a-b);

    return {total:document.body.scrollHeight, cuts, dayTops,
            imgs:document.querySelectorAll('img').length, empty};
  });
  await p.waitForTimeout(400);

  // 貪心切頁：每頁盡量吃滿，但優先切在「新的一天開始」的位置
  const slices=[]; let y=0;
  while(y<info.total-4){
    const limit=y+H;
    if(limit>=info.total){ slices.push([y,info.total-y]); break; }
    let cut=0;
    for(const d of info.dayTops){ if(d<=limit && d>y+H*0.55) cut=d; }   // 一天的開頭
    if(!cut) for(const c of info.cuts){ if(c<=limit && c>y+H*0.45) cut=c; }
    if(!cut) cut=limit;                                                 // 真的沒得切才硬切
    slices.push([y,cut-y]);
    y=cut;
  }

  await p.screenshot({path:path.join(OUT,'full.png'),fullPage:true});
  fs.writeFileSync(path.join(OUT,'cuts.json'),
    JSON.stringify({width:W,scale:SCALE,pageHeight:H,total:info.total,slices},null,1));
  console.log(`整頁 ${W}×${info.total}px（${SCALE} 倍）；照片 ${info.imgs} 張，其中 ${info.empty} 張載不到已藏起來`);
  console.log(`切成 ${slices.length} 頁，頁高上限 ${H}px`);
  await b.close();
})();
