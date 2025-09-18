// /static/js/telegram.js
(function(){
  const gate = document.getElementById('tgGate');
  const app  = document.getElementById('appContent');
  const showApp = ()=>{ gate?.classList.add('d-none'); app?.classList.remove('d-none'); };

  async function cookiesFirst(){
    try{
      const r = await fetch('/app/me', {credentials:'include'});
      if (r.ok) { showApp(); return true; }
    }catch(_){} return false;
  }

  function waitTelegram(max=7000){
    return new Promise(r=>{
      const t0=Date.now();
      (function tick(){
        if (window.Telegram && Telegram.WebApp) return r(true);
        if (Date.now()-t0>max) return r(false);
        setTimeout(tick,50);
      })();
    });
  }

  async function authViaTelegram(){
    const have = await waitTelegram();
    if (!have) return false;

    try{
      const tg = Telegram.WebApp;
      tg.ready();             // сообщаем клиенту, что UI готов
      tg.expand();            // можно занять максимум высоты

      const initData = tg.initData || ""; // именно строка из доки
      if (!initData) return false;

      const r = await fetch('/app/api/telegram/auth', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        credentials:'include',
        body: JSON.stringify({ initData })
      });
      const j = await r.json();
      if (j.success){ showApp(); return true; }
    }catch(_){}
    return false;
  }

  async function boot(){
    if (await cookiesFirst()) return;
    await authViaTelegram(); // если не вышло — останемся на гейте с ссылкой в бота
  }

  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
