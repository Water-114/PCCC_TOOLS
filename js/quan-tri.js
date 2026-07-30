(function(){
  var A = window.PcccAuth;
  var gate = document.getElementById('adminGate');
  var dashboard = document.getElementById('adminDashboard');

  function fmtDate(iso){
    try { return new Date(iso).toLocaleString('vi-VN'); } catch(e){ return iso; }
  }

  function renderUsers(users){
    var rows = '<tr><th>Email</th><th>Vai trò</th><th>Ngày tạo</th><th>Lượt dùng hôm nay</th><th>Còn lại</th></tr>';
    users.forEach(function(u){
      rows += '<tr><td>' + u.email + '</td><td>' + u.role + '</td><td>' + fmtDate(u.created_at) + '</td><td>' + u.used_today + '</td><td>' + u.remaining_today + '</td></tr>';
    });
    document.getElementById('adminUsersTable').innerHTML = rows;
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
