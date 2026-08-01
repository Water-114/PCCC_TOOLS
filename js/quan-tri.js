(function(){
  var A = window.PcccAuth;
  var gate = document.getElementById('adminGate');
  var dashboard = document.getElementById('adminDashboard');

  function fmtDate(iso){
    try { return new Date(iso).toLocaleString('vi-VN'); } catch(e){ return iso; }
  }

  function headerRow(labels){
    var tr = document.createElement('tr');
    labels.forEach(function(label){
      var th = document.createElement('th');
      th.textContent = label;
      tr.appendChild(th);
    });
    return tr;
  }

  // Dung DOM API (textContent) thay vi noi chuoi + innerHTML cho moi gia tri
  // nguoi dung/AI kiem soat (email, comment, feature...) - tranh XSS luu tru.
  // Xem Batch 1 (docs/02-implementation-batches.md).
  function renderUsers(users){
    var table = document.getElementById('adminUsersTable');
    table.innerHTML = '';
    table.appendChild(headerRow(['Email', 'Vai trò', 'Ngày tạo', 'Đã dùng / hạn mức hôm nay', 'Chỉnh hạn mức/ngày']));

    users.forEach(function(u){
      var isCustom = u.daily_quota !== null && u.daily_quota !== undefined;
      var effective = isCustom ? u.daily_quota : u.default_quota;
      var tr = document.createElement('tr');

      var tdEmail = document.createElement('td');
      tdEmail.textContent = u.email;
      tr.appendChild(tdEmail);

      var tdRole = document.createElement('td');
      tdRole.textContent = u.role;
      tr.appendChild(tdRole);

      var tdCreated = document.createElement('td');
      tdCreated.textContent = fmtDate(u.created_at);
      tr.appendChild(tdCreated);

      var tdUsage = document.createElement('td');
      tdUsage.textContent = u.used_today + ' / ' + effective;
      tr.appendChild(tdUsage);

      var tdQuota = document.createElement('td');
      var span = document.createElement('span');
      span.className = 'quota-edit';

      var input = document.createElement('input');
      input.type = 'number';
      input.min = '0';
      input.className = 'quota-input';
      input.value = effective;
      span.appendChild(input);

      var saveBtn = document.createElement('button');
      saveBtn.type = 'button';
      saveBtn.className = 'btn-quota-save';
      saveBtn.dataset.id = u.id;
      saveBtn.textContent = 'Lưu';
      span.appendChild(saveBtn);

      if(isCustom){
        var resetBtn = document.createElement('button');
        resetBtn.type = 'button';
        resetBtn.className = 'btn-quota-reset';
        resetBtn.dataset.id = u.id;
        resetBtn.textContent = 'Về mặc định (' + u.default_quota + ')';
        span.appendChild(resetBtn);
      } else {
        var hint = document.createElement('span');
        hint.className = 'hint-default';
        hint.textContent = 'mặc định chung';
        span.appendChild(hint);
      }
      tdQuota.appendChild(span);

      var errEl = document.createElement('span');
      errEl.className = 'quota-err';
      errEl.hidden = true;
      tdQuota.appendChild(errEl);

      tr.appendChild(tdQuota);
      table.appendChild(tr);
    });
    wireQuotaControls();
  }

  function saveQuota(id, value, errEl){
    var headers = Object.assign({'Content-Type': 'application/json'}, A.authHeaders());
    return fetch(A.BACKEND_BASE + '/api/admin/users/' + id + '/quota', {
      method: 'PATCH',
      headers: headers,
      body: JSON.stringify({daily_quota: value})
    }).then(function(r){ return r.json().then(function(data){ return {ok: r.ok, data: data}; }); })
      .then(function(res){
        if(!res.ok){
          errEl.textContent = res.data.error || 'Không lưu được hạn mức.';
          errEl.hidden = false;
          return;
        }
        errEl.hidden = true;
        loadDashboard();
      })
      .catch(function(){
        errEl.textContent = 'Không kết nối được tới máy chủ.';
        errEl.hidden = false;
      });
  }

  function wireQuotaControls(){
    Array.prototype.forEach.call(document.querySelectorAll('.btn-quota-save'), function(btn){
      btn.addEventListener('click', function(){
        var id = btn.dataset.id;
        var cell = btn.closest('td');
        var input = cell.querySelector('.quota-input');
        var errEl = cell.querySelector('.quota-err');
        var raw = input.value.trim();
        if(raw === '' || isNaN(Number(raw)) || Number(raw) < 0){
          errEl.textContent = 'Nhập một số nguyên từ 0 trở lên.';
          errEl.hidden = false;
          return;
        }
        saveQuota(id, Math.trunc(Number(raw)), errEl);
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.btn-quota-reset'), function(btn){
      btn.addEventListener('click', function(){
        var id = btn.dataset.id;
        var errEl = btn.closest('td').querySelector('.quota-err');
        saveQuota(id, null, errEl);
      });
    });
  }

  function renderFeedback(items){
    var table = document.getElementById('adminFeedbackTable');
    table.innerHTML = '';
    if(!items.length){
      var trEmpty = document.createElement('tr');
      var tdEmpty = document.createElement('td');
      tdEmpty.style.color = 'var(--ink-soft)';
      tdEmpty.textContent = 'Chưa có góp ý nào.';
      trEmpty.appendChild(tdEmpty);
      table.appendChild(trEmpty);
      return;
    }
    table.appendChild(headerRow(['Sao', 'Nhận xét', 'Người gửi', 'Tính năng', 'Thời gian']));
    items.forEach(function(f){
      var stars = f.rating ? '★'.repeat(f.rating) + '☆'.repeat(5 - f.rating) : '—';
      var tr = document.createElement('tr');
      [stars, f.comment || '—', f.user_email || 'Ẩn danh', f.feature, fmtDate(f.created_at)].forEach(function(text){
        var td = document.createElement('td');
        td.textContent = text;
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
  }

  function loadDashboard(){
    var headers = A.authHeaders();
    Promise.all([
      fetch(A.BACKEND_BASE + '/api/admin/stats', {headers: headers}),
      fetch(A.BACKEND_BASE + '/api/admin/users', {headers: headers}),
      fetch(A.BACKEND_BASE + '/api/admin/feedback', {headers: headers})
    ]).then(function(responses){
      if(responses.some(function(r){ return r.status === 401 || r.status === 403; })) return null;
      return Promise.all(responses.map(function(r){ return r.json(); }));
    }).then(function(data){
      if(!data) return;
      document.getElementById('adminStatUsers').textContent = data[0].total_users;
      document.getElementById('adminStatCalls').textContent = data[0].total_calls;
      document.getElementById('adminStatCallsToday').textContent = data[0].calls_today;
      document.getElementById('adminStatFeedback').textContent = data[0].total_feedback;
      renderUsers(data[1].users);
      renderFeedback(data[2].feedback);
    }).catch(function(){});
  }

  function refresh(user){
    if(user && user.role === 'admin'){
      gate.hidden = true;
      dashboard.hidden = false;
      loadDashboard();
      return;
    }
    dashboard.hidden = true;
    gate.hidden = false;
    if(user){
      gate.innerHTML = '';
      gate.appendChild(document.createTextNode('Tài khoản '));
      var b = document.createElement('b');
      b.textContent = user.email;
      gate.appendChild(b);
      gate.appendChild(document.createTextNode(' không có quyền quản trị.'));
    } else {
      gate.innerHTML = 'Cần đăng nhập bằng tài khoản có quyền quản trị để xem trang này.' +
        '<div class="actions" style="margin-top:10px"><button type="button" class="btn-main" id="adminLoginBtn">Đăng nhập</button></div>';
      document.getElementById('adminLoginBtn').addEventListener('click', function(){ window.openAuthModal(); });
    }
  }

  A.onChange(refresh);
  refresh(A.getUser());
})();
