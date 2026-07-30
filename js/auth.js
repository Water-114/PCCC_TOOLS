window.PcccAuth = (function(){
  // Khi chạy local qua server tĩnh riêng (vd. python -m http.server ở cổng khác 5000) thì
  // gọi thẳng tới Flask dev server ở cổng 5000. Khi đã lên production (Render), backend
  // phục vụ luôn cả index.html/css/js cùng domain nên gọi API cùng gốc (rỗng = same-origin),
  // không cần biết trước domain thật.
  var isLocalDev = (location.hostname === '127.0.0.1' || location.hostname === 'localhost') && location.port !== '5000';
  var BACKEND_BASE = isLocalDev ? 'http://127.0.0.1:5000' : '';
  var TOKEN_KEY = 'pcccAuthToken';
  var currentUser = null;
  var listeners = [];

  function getToken(){ return localStorage.getItem(TOKEN_KEY); }
  function setToken(t){ if(t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); }
  function getUser(){ return currentUser; }
  function notify(){ listeners.forEach(function(fn){ fn(currentUser); }); }
  function onChange(fn){ listeners.push(fn); }
  function authHeaders(){
    var h = {};
    var t = getToken();
    if(t) h['Authorization'] = 'Bearer ' + t;
    return h;
  }

  function refreshMe(){
    var token = getToken();
    if(!token){ currentUser = null; notify(); return Promise.resolve(null); }
    return fetch(BACKEND_BASE + '/api/auth/me', {headers: authHeaders()})
      .then(function(res){
        if(!res.ok){ setToken(null); currentUser = null; notify(); return null; }
        return res.json().then(function(data){ currentUser = data.user; notify(); return currentUser; });
      })
      .catch(function(){ notify(); return null; });
  }

  function login(email, password){
    return fetch(BACKEND_BASE + '/api/auth/login', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: email, password: password})
    }).then(function(res){ return res.json().then(function(data){ return {ok: res.ok, data: data}; }); })
      .then(function(r){ if(r.ok){ setToken(r.data.token); currentUser = r.data.user; notify(); } return r; });
  }

  function register(email, password){
    return fetch(BACKEND_BASE + '/api/auth/register', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: email, password: password})
    }).then(function(res){ return res.json().then(function(data){ return {ok: res.ok, data: data}; }); })
      .then(function(r){ if(r.ok){ setToken(r.data.token); currentUser = r.data.user; notify(); } return r; });
  }

  function logout(){ setToken(null); currentUser = null; notify(); }
  function setUserQuota(quota){ if(currentUser){ currentUser.quota = quota; notify(); } }

  return {
    BACKEND_BASE: BACKEND_BASE,
    getToken: getToken,
    getUser: getUser,
    authHeaders: authHeaders,
    refreshMe: refreshMe,
    login: login,
    register: register,
    logout: logout,
    onChange: onChange,
    setUserQuota: setUserQuota
  };
})();

(function(){
  var A = window.PcccAuth;
  var authStatusEl = document.getElementById('authStatus');
  var authOpenBtn = document.getElementById('authOpenBtn');
  var authLogoutBtn = document.getElementById('authLogoutBtn');
  var authModal = document.getElementById('authModal');
  var authModalClose = document.getElementById('authModalClose');
  var authForm = document.getElementById('authForm');
  var authEmail = document.getElementById('authEmail');
  var authPassword = document.getElementById('authPassword');
  var authFormMsg = document.getElementById('authFormMsg');
  var authSubmitBtn = document.getElementById('authSubmitBtn');
  var authToggleBtn = document.getElementById('authToggleBtn');
  var authToggleText = document.getElementById('authToggleText');
  var authModalTitle = document.getElementById('authModalTitle');
  var authMode = 'login';

  function updateAuthUI(user){
    if(user){
      authStatusEl.textContent = user.email + ' · còn ' + user.quota.remaining_today + '/' + user.quota.limit + ' lượt đọc bản vẽ hôm nay' + (user.role === 'admin' ? ' · admin' : '');
      authOpenBtn.hidden = true;
      authLogoutBtn.hidden = false;
    } else {
      authStatusEl.textContent = 'Chưa đăng nhập';
      authOpenBtn.hidden = false;
      authLogoutBtn.hidden = true;
    }
  }

  window.openAuthModal = function(){
    authFormMsg.classList.remove('show');
    authForm.reset();
    authModal.hidden = false;
  };
  window.closeAuthModal = function(){ authModal.hidden = true; };

  authOpenBtn.addEventListener('click', window.openAuthModal);
  authModalClose.addEventListener('click', window.closeAuthModal);
  authModal.addEventListener('click', function(e){ if(e.target === authModal) window.closeAuthModal(); });

  authToggleBtn.addEventListener('click', function(){
    authMode = authMode === 'login' ? 'register' : 'login';
    authModalTitle.textContent = authMode === 'login' ? 'Đăng nhập' : 'Đăng ký';
    authSubmitBtn.textContent = authMode === 'login' ? 'Đăng nhập' : 'Đăng ký';
    authToggleText.textContent = authMode === 'login' ? 'Chưa có tài khoản?' : 'Đã có tài khoản?';
    authToggleBtn.textContent = authMode === 'login' ? 'Đăng ký ngay' : 'Đăng nhập';
    authFormMsg.classList.remove('show');
  });

  authForm.addEventListener('submit', function(e){
    e.preventDefault();
    var email = authEmail.value.trim();
    var password = authPassword.value;
    authSubmitBtn.disabled = true;
    var action = authMode === 'login' ? A.login : A.register;
    action(email, password).then(function(r){
      authSubmitBtn.disabled = false;
      if(!r.ok){
        authFormMsg.textContent = r.data.error || 'Có lỗi xảy ra, thử lại sau.';
        authFormMsg.classList.add('show');
        return;
      }
      window.closeAuthModal();
    }).catch(function(){
      authSubmitBtn.disabled = false;
      authFormMsg.textContent = 'Không kết nối được tới máy chủ — kiểm tra backend đã chạy chưa.';
      authFormMsg.classList.add('show');
    });
  });

  authLogoutBtn.addEventListener('click', function(){ A.logout(); });

  A.onChange(updateAuthUI);
  A.refreshMe();
})();
