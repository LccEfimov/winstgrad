// /static/js/telegram.js
(function(){
  const gate = document.getElementById('tgGate');
  const app  = document.getElementById('appContent');
  const showApp = ()=>{
    gate?.classList.add('d-none');
    app?.classList.remove('d-none');
    window.__WG_SHOW_APP__?.();
    const after = window.__WG_AFTER_LOGIN__;
    if (typeof after === 'function'){
      window.__WG_AFTER_LOGIN__ = null;
      setTimeout(()=>{
        try{ after(); }
        catch(err){ console.warn('after login hook error', err); }
      }, 50);
    }
  };
  const diag = (txt)=> window.__WG_DIAG__?.(txt);

  async function cookiesFirst(){
    try{
      diag('Проверяем сохранённую сессию…');
      const r = await fetch('/app/me', {credentials:'include'});
      if (r.ok) { showApp(); return true; }
    }catch(_){ diag('Не удалось использовать сохранённую сессию.'); }
    return false;
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
    if (!have){ diag('Запустите страницу из Telegram.'); return false; }

    try{
      const tg = Telegram.WebApp;
      tg.ready();
      tg.expand();

      const initData = tg.initData || "";
      if (!initData){ diag('Не получили данные от Telegram.'); return false; }

      diag('Авторизуемся через Telegram…');
      const r = await fetch('/app/api/telegram/auth', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        credentials:'include',
        body: JSON.stringify({ initData })
      });
      const j = await r.json();
      if (j.success){
        diag('Готово! Загружаем приложение…');
        showApp();
        return true;
      }
      diag(j.error || 'Не удалось авторизоваться.');
    }catch(err){
      diag('Ошибка связи с сервером: ' + (err?.message || 'неизвестно'));
    }
    return false;
  }

  async function boot(){
    if (await cookiesFirst()) return;
    await authViaTelegram();
  }

  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
