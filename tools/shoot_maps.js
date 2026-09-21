/* 把每天的手繪地圖截成 PNG，給 tools/make_docx.py 貼進 Word 用。
   用法：NODE_PATH=<playwright 所在> node tools/shoot_maps.js
   輸出：assets/print/dayN.png（N 是 DAYS 的 n）。行程改過就重跑一次。 */
const {chromium}=require('playwright');
const path=require('path');
const ROOT=path.resolve(__dirname,'..');
(async()=>{
  const exe=process.env.CHROME||'/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  const b=await chromium.launch({executablePath:exe});
  // deviceScaleFactor 2＝列印時不會糊；寬度抓 900 讓標籤相對大一點
  const p=await b.newPage({viewport:{width:900,height:1200},deviceScaleFactor:2,reducedMotion:'reduce'});
  await p.goto('file://'+path.join(ROOT,'index.html'),{waitUntil:'load'});
  await p.waitForTimeout(2500);
  // 逐日展開，把動畫直接跑完（列印要的是最終狀態）
  const n=await p.evaluate(()=>{
    document.querySelectorAll('.mapcard').forEach(c=>c.classList.remove('real'));
    document.querySelectorAll('.mapwrap>svg .leg').forEach(l=>{
      l.style.strokeDasharray='none';l.style.strokeDashoffset='0';l.style.opacity='1';});
    document.querySelectorAll('.mapwrap>svg .pin,.mapwrap>svg .plabel').forEach(e=>e.style.opacity='1');
    return document.querySelectorAll('.day').length;
  });
  let out=0;
  for(let i=0;i<n;i++){
    const day=p.locator('.day').nth(i);
    const id=await day.evaluate(e=>e.id);            // day1…day10
    const maps=day.locator('.mapcard');
    const cnt=await maps.count();
    for(let m=0;m<cnt;m++){
      const wrap=maps.nth(m).locator('.mapwrap');
      if(!await wrap.count()) continue;
      const name=id.replace('day','day')+(m?'_'+(m+1):'')+'.png';
      await wrap.screenshot({path:path.join(ROOT,'assets/print',name)});
      console.log('  寫出 assets/print/'+name); out++;
    }
  }
  console.log('共 '+out+' 張');
  await b.close();
})();
