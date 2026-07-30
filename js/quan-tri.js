(function(){
  var A = window.PcccAuth;
  var gate = document.getElementById('adminGate');
  var dashboard = document.getElementById('adminDashboard');

  function fmtDate(iso){
    try { return new Date(iso).toLocaleString('vi-VN'); } catch(e){ return iso; }
  }

  function renderUsers(users){
    var rows = '<tr><th>Email</th><th>Vai trò</th><th>Ngày tạo</th><th>Đã dùng / hạn mức hôm nay</th><th>Chỉnh hạn mức/ngày</th></tr>';
    users.forEach(function(u){
      var isCustom = u.daily_quota !== null && u.daily_quota !== undefined;
      var effective = isCustom ? u.daily_quota : u.default_quota;
      rows += '<tr>' +
        '<td>' + u.email + '</td>' +
        '<td>' + u.role + '</td>' +
        '<td>' + fmtDate(u.created_at) + '</td>' +
        '<td>' + u.used_today + ' / ' + effective + '</td>' +
        '<td>' +
          '<span class="quota-edit">' +
            '<input type="number" min="0" class="quota-input" value="' + effective + '">' +
            '<button type="button" class="btn-quota-save" data-id="' + u.id + '">Lưu</button>' +
            (isCustom ? '<button type="button" class="btn-quota-reset" data-id="' + u.id + '">Về mặc định (' + u.default_quota + ')</button>' : '<span class="hint-default">mặc định chung</span>') +
          '</span>' +
          '<span class="quota-err" hidden></span>' +
        '</td>' +
      '</tr>';
    });
    document.getElementById('adminUsersTable').innerHTML = rows;
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
    if(!items.length){
      document.getElementById('adminFeedbackTable').innerHTML = '<tr><td style="color:var(--ink-soft)">Chưa có góp ý nào.</td></tr>';
      return;
    }
    var rows = '<tr><th>Sao</th><th>Nhận xét</th><th>Người gửi</th><th>Tính năng</th><th>Thời gian</th></tr>';
    items.forEach(function(f){
      var stars = f.rating ? '★'.repeat(f.rating) + '☆'.repeat(5 - f.rating) : '—';
      rows += '<tr><td>' + stars + '</td><td>' + (f.comment || '—') + '</td><td>' + (f.user_email || 'Ẩn danh') + '</td><td>' + f.feature + '</td><td>' + fmtDate(f.created_at) + '</td></tr>';
    });
    document.getElementById('adminFeedbackTable').innerHTML = rows;
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
      gate.innerHTML = 'Tài khoản <b>' + user.email + '</b> không có quyền quản trị.';
    } else {
      gate.innerHTML = 'Cần đăng nhập bằng tài khoản có quyền quản trị để xem trang này.' +
        '<div class="actions" style="margin-top:10px"><button type="button" class="btn-main" id="adminLoginBtn">Đăng nhập</button></div>';
      document.getElementById('adminLoginBtn').addEventListener('click', function(){ window.openAuthModal(); });
    }
  }

  A.onChange(refresh);
  refresh(A.getUser());
})();
