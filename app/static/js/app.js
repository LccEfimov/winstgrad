(function(){
  const state = {
    cart: [],
  };

  const toastStack = document.getElementById('toastStack');

  function flash(message, type='info', timeout=4000){
    if (!toastStack || typeof bootstrap === 'undefined'){
      return alert(message);
    }
    const id = `toast-${Date.now()}`;
    const el = document.createElement('div');
    el.className = `toast align-items-center text-bg-${type} border-0`;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.id = id;
    el.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Закрыть"></button>
      </div>`;
    toastStack.appendChild(el);
    const toast = new bootstrap.Toast(el, {delay: timeout});
    toast.show();
    el.addEventListener('hidden.bs.toast', ()=> el.remove());
  }

  async function postJSON(url, payload){
    const resp = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'include',
      body: JSON.stringify(payload || {})
    });
    const data = await resp.json().catch(()=>({}));
    if (!resp.ok){
      const err = new Error(data.error || resp.statusText || 'Ошибка запроса');
      err.response = data;
      throw err;
    }
    return data;
  }

  function formatMoney(value){
    return (Math.round(Number(value || 0) * 100) / 100).toFixed(2);
  }

  function ensureCartUnique(item){
    const existing = state.cart.find(i => i.type === item.type && i.id === item.id);
    if (existing){
      existing.qty += item.qty;
    } else {
      state.cart.push(item);
    }
  }

  function updateCartUI(){
    const container = document.getElementById('orderItems');
    const totalEl = document.getElementById('orderTotal');
    const submitBtn = document.getElementById('submitOrder');
    const emptyEl = container ? container.querySelector('[data-role="empty-cart"]') : null;
    const deliveryInput = document.getElementById('orderDelivery');

    if (!container){ return; }

    container.querySelectorAll('.cart-item').forEach(el => el.remove());

    if (!state.cart.length){
      emptyEl && emptyEl.classList.remove('d-none');
      if (submitBtn) submitBtn.disabled = true;
      if (totalEl) totalEl.textContent = formatMoney(deliveryInput ? deliveryInput.value : 0);
      return;
    }

    emptyEl && emptyEl.classList.add('d-none');

    let total = 0;
    state.cart.forEach((item, index) => {
      const line = document.createElement('div');
      line.className = 'cart-item border rounded p-2 bg-body-tertiary';
      line.dataset.index = index;
      total += item.price * item.qty;
      line.innerHTML = `
        <div class="d-flex flex-column flex-sm-row gap-2 justify-content-between align-items-sm-center">
          <div>
            <div class="fw-semibold">${item.name}</div>
            <div class="small text-secondary">${item.type === 'product' ? 'Товар' : 'Услуга'} · ${item.unit}</div>
          </div>
          <div class="d-flex align-items-center gap-2">
            <div class="input-group input-group-sm" style="width: 140px;">
              <span class="input-group-text">Кол-во</span>
              <input type="number" class="form-control" min="0.1" step="0.1" value="${item.qty}" data-action="change-qty">
            </div>
            <div class="text-end small">
              <div>${formatMoney(item.price)} ₽</div>
              <div class="fw-semibold">${formatMoney(item.price * item.qty)} ₽</div>
            </div>
            <button type="button" class="btn btn-outline-danger btn-sm" data-action="remove-item">×</button>
          </div>
        </div>`;
      container.appendChild(line);
    });

    const delivery = parseFloat(deliveryInput && deliveryInput.value ? deliveryInput.value : 0) || 0;
    total += delivery;
    if (totalEl) totalEl.textContent = formatMoney(total);
    if (submitBtn) submitBtn.disabled = false;
  }

  function handleAddToCart(event){
    const btn = event.target.closest('.js-add-to-cart');
    if (!btn) return;
    const card = btn.closest('[data-item-id]');
    if (!card) return;
    const qtyInput = card.querySelector('[data-role="qty-input"]');
    let qty = qtyInput ? parseFloat(qtyInput.value) : 1;
    if (!qty || qty <= 0){
      flash('Укажите корректное количество.', 'warning');
      return;
    }
    const item = {
      type: card.dataset.itemType,
      id: Number(card.dataset.itemId),
      name: card.dataset.itemName,
      unit: card.dataset.itemUnit,
      price: parseFloat(card.dataset.itemPrice || '0'),
      qty: qty
    };
    ensureCartUnique(item);
    updateCartUI();
    flash(`${item.name} добавлен в калькулятор.`, 'success');
  }

  function handleCartInteraction(event){
    const container = document.getElementById('orderItems');
    if (!container) return;
    const itemRow = event.target.closest('.cart-item');
    if (!itemRow) return;
    const index = Number(itemRow.dataset.index);
    const item = state.cart[index];
    if (!item) return;

    if (event.target.dataset.action === 'remove-item'){
      state.cart.splice(index, 1);
      updateCartUI();
      flash('Позиция удалена из заказа.', 'info');
    }
    if (event.target.dataset.action === 'change-qty'){
      const val = parseFloat(event.target.value);
      if (!val || val <= 0){
        flash('Количество должно быть больше нуля.', 'warning');
        event.target.value = item.qty;
        return;
      }
      item.qty = val;
      updateCartUI();
    }
  }

  async function submitOrder(){
    const submitBtn = document.getElementById('submitOrder');
    if (!state.cart.length || !submitBtn) return;
    submitBtn.disabled = true;
    submitBtn.classList.add('disabled');
    const comment = document.getElementById('orderComment');
    const deliveryInput = document.getElementById('orderDelivery');

    try{
      const payload = {
        items: state.cart.map(item => ({type: item.type, id: item.id, qty: item.qty})),
        comment: comment ? comment.value : '',
        delivery_price: deliveryInput && deliveryInput.value ? Number(deliveryInput.value) : 0
      };
      const data = await postJSON('/app/order', payload);
      flash(`Заявка №${data.order_id} принята. Менеджер свяжется с вами.`, 'success', 6000);
      state.cart = [];
      if (comment) comment.value = '';
      if (deliveryInput) deliveryInput.value = '0';
      updateCartUI();
      setTimeout(()=>{ window.location.href = '/app/orders'; }, 1500);
    }catch(err){
      flash(err.message || 'Не удалось оформить заказ.', 'danger', 6000);
      submitBtn.disabled = false;
      submitBtn.classList.remove('disabled');
    }
  }

  async function handleReviewSubmit(event){
    const form = event.target.closest('.review-form');
    if (!form) return;
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      target_type: form.dataset.targetType,
      target_id: Number(form.dataset.targetId),
      rating: Number(formData.get('rating')),
      text: (formData.get('text') || '').trim()
    };
    if (!payload.rating || !payload.text){
      flash('Заполните оценку и комментарий.', 'warning');
      return;
    }
    form.querySelectorAll('button, input, select, textarea').forEach(el => el.disabled = true);
    try{
      await postJSON('/app/reviews', payload);
      flash('Спасибо! Отзыв отправлен на модерацию.', 'success');
      form.reset();
    }catch(err){
      flash(err.message || 'Не удалось отправить отзыв.', 'danger');
    }finally{
      form.querySelectorAll('button, input, select, textarea').forEach(el => el.disabled = false);
    }
  }

  async function handleProfileSubmit(event){
    const form = event.target.closest('#profileForm');
    if (!form) return;
    event.preventDefault();
    const payload = {
      phone: form.phone.value,
      email: form.email.value,
      delivery_address: form.delivery_address.value
    };
    form.querySelectorAll('button').forEach(btn => btn.disabled = true);
    try{
      await postJSON('/app/profile', payload);
      flash('Профиль обновлён.', 'success');
    }catch(err){
      flash(err.message || 'Не удалось обновить профиль.', 'danger');
    }finally{
      form.querySelectorAll('button').forEach(btn => btn.disabled = false);
    }
  }

  function handleProfileRefresh(event){
    const btn = event.target.closest('#profileRefresh');
    if (!btn) return;
    event.preventDefault();
    if (window.Telegram && Telegram.WebApp){
      Telegram.WebApp.HapticFeedback?.impactOccurred?.('light');
      Telegram.WebApp.showAlert('Откройте бота @WinstGradBot и отправьте команду /start для синхронизации имени и логина.');
    } else {
      flash('Запустите приложение из Telegram, чтобы обновить данные автоматически.', 'info');
    }
  }

  async function handleFeedbackSubmit(event){
    const form = event.target.closest('#feedbackForm');
    if (!form) return;
    event.preventDefault();
    const payload = {
      name: form.name.value,
      phone: form.phone.value,
      email: form.email.value,
      subject: form.subject.value,
      message: form.message.value
    };
    form.querySelectorAll('button, input, textarea').forEach(el => el.disabled = true);
    try{
      await postJSON('/app/feedback', payload);
      flash('Сообщение отправлено. Менеджер свяжется с вами.', 'success');
      form.reset();
    }catch(err){
      flash(err.message || 'Не удалось отправить сообщение.', 'danger');
    }finally{
      form.querySelectorAll('button, input, textarea').forEach(el => el.disabled = false);
    }
  }

  function decorateRatings(){
    document.querySelectorAll('.rating-stars').forEach(el => {
      const avg = parseFloat(el.dataset.average || '0');
      if (!avg){
        el.innerHTML = '☆☆☆☆☆';
        return;
      }
      const full = Math.floor(avg);
      const half = avg - full >= 0.5;
      let stars = '';
      for (let i=0; i<full; i++) stars += '★';
      if (half) stars += '☆';
      while (stars.length < 5) stars += '☆';
      el.textContent = stars;
    });
  }

  function initAdminLinks(){
    document.querySelectorAll('[data-admin-link]').forEach(link => {
      link.addEventListener('click', (ev)=>{
        ev.preventDefault();
        window.open(link.href, '_blank');
      });
    });
  }

  document.addEventListener('click', handleAddToCart);
  document.addEventListener('click', handleCartInteraction);
  document.addEventListener('change', handleCartInteraction);
  document.addEventListener('submit', handleReviewSubmit);
  document.addEventListener('submit', handleProfileSubmit);
  document.addEventListener('submit', handleFeedbackSubmit);
  document.addEventListener('click', handleProfileRefresh);
  const submitOrderBtn = document.getElementById('submitOrder');
  if (submitOrderBtn){
    submitOrderBtn.addEventListener('click', submitOrder);
  }
  const deliveryInput = document.getElementById('orderDelivery');
  if (deliveryInput){
    deliveryInput.addEventListener('input', updateCartUI);
  }

  decorateRatings();
  initAdminLinks();
  updateCartUI();
})();
