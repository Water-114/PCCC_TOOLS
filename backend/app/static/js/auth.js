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

  function sendVerificationEmail(){
    return fetch(BACKEND_BASE + '/api/auth/send-verification-email', {
      method: 'POST', headers: authHeaders()
    }).then(function(res){ return res.json().then(function(data){ return {ok: res.ok, data: data}; }); });
  }

  function verifyEmail(token){
    return fetch(BACKEND_BASE + '/api/auth/verify-email', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: token})
    }).then(function(res){ return res.json().then(function(data){ return {ok: res.ok, data: data}; }); })
      .then(function(r){ if(r.ok){ currentUser = r.data.user; notify(); } return r; });
  }

  function logout(){ setToken(null); currentUser = null; notify(); }
  function setUserBoHoSo(boHoSo){ if(currentUser){ currentUser.bo_ho_so = boHoSo; notify(); } }

  return {
    BACKEND_BASE: BACKEND_BASE,
    getToken: getToken,
    getUser: getUser,
    authHeaders: authHeaders,
    refreshMe: refreshMe,
    login: login,
    register: register,
    sendVerificationEmail: sendVerificationEmail,
    verifyEmail: verifyEmail,
    logout: logout,
    onChange: onChange,
    setUserBoHoSo: setUserBoHoSo
  };
})();

// Script nap som (ngay sau <nav>, xem index.html) de window.PcccAuth san sang
// truoc cac script khac o cuoi body - nhung phan doc DOM ben duoi can cho DOM
// parse xong het (vd #verifyEmailCta nam trong #view-aiho, o rat xa phia
// duoi trong document) nen phai cho DOMContentLoaded thay vi chay ngay.
document.addEventListener('DOMContentLoaded', function(){
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
  var authGlobalMsg = document.getElementById('authGlobalMsg');
  var verifyEmailCta = document.getElementById('verifyEmailCta');
  var verifyEmailCtaBtn = document.getElementById('verifyEmailCtaBtn');
  var verifyEmailCtaMsg = document.getElementById('verifyEmailCtaMsg');
  var authMode = 'login';

  function showAuthGlobalMsg(text, isError){
    authGlobalMsg.textContent = text;
    authGlobalMsg.style.color = isError ? '' : 'var(--green)';
    authGlobalMsg.classList.toggle('show', !!text);
  }

  // Nho email cua lan cuoi CTA hien de reset lai nut/thong bao khi doi sang
  // tai khoan chua xac thuc KHAC (dang xuat roi dang nhap tai khoan khac) -
  // khong reset khi van cung 1 tai khoan (vd updateAuthUI chay lai chi vi so
  // du Bo ho so thay doi) de giu dung trang thai "da gui, khoa nut" nhu yeu cau.
  var verifyEmailCtaShownFor = null;
  function updateAuthUI(user){
    if(user){
      authStatusEl.textContent = user.email + ' · còn ' + user.bo_ho_so.con_lai + ' Bộ hồ sơ' + (user.role === 'admin' ? ' · admin' : '');
      authOpenBtn.hidden = true;
      authLogoutBtn.hidden = false;
      verifyEmailCta.hidden = !!user.email_verified;
      if(!user.email_verified && verifyEmailCtaShownFor !== user.email){
        verifyEmailCtaShownFor = user.email;
        verifyEmailCtaBtn.disabled = false;
        verifyEmailCtaBtn.textContent = 'Gửi email xác thực';
        verifyEmailCtaMsg.classList.remove('show');
      }
    } else {
      authStatusEl.textContent = 'Chưa đăng nhập';
      authOpenBtn.hidden = false;
      authLogoutBtn.hidden = true;
      verifyEmailCta.hidden = true;
      verifyEmailCtaShownFor = null;
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
    var wasRegister = authMode === 'register';
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
      if(wasRegister){
        A.sendVerificationEmail().then(function(vr){
          if(vr.ok){
            showAuthGlobalMsg('Đã gửi email xác thực tới ' + email + ' — kiểm tra hộp thư (kể cả Spam) để nhận 1 Bộ hồ sơ dùng thử.', false);
          } else {
            showAuthGlobalMsg(vr.data.error || 'Không gửi được email xác thực — vui lòng thử lại sau bằng nút "Gửi lại email xác thực".', true);
          }
        }).catch(function(){
          showAuthGlobalMsg('Không kết nối được tới máy chủ — chưa gửi được email xác thực.', true);
        });
      }
    }).catch(function(){
      authSubmitBtn.disabled = false;
      authFormMsg.textContent = 'Không kết nối được tới máy chủ — kiểm tra backend đã chạy chưa.';
      authFormMsg.classList.add('show');
    });
  });

  function showVerifyEmailCtaMsg(text, isError){
    verifyEmailCtaMsg.textContent = text;
    verifyEmailCtaMsg.style.color = isError ? '' : 'var(--green)';
    verifyEmailCtaMsg.classList.toggle('show', !!text);
  }

  verifyEmailCtaBtn.addEventListener('click', function(){
    verifyEmailCtaBtn.disabled = true;
    A.sendVerificationEmail().then(function(vr){
      var user = A.getUser();
      if(vr.ok){
        // Khoa han nut lai (khong mo lai) - da gui thanh cong, tranh bam gui
        // lien tuc; chi mo lai khi that su that bai (nhanh else ben duoi) hoac
        // khi doi sang tai khoan khac (xem verifyEmailCtaShownFor o updateAuthUI).
        verifyEmailCtaBtn.textContent = 'Đã gửi email xác thực';
        showVerifyEmailCtaMsg('Đã gửi email xác thực tới ' + (user ? user.email : '') + ' — kiểm tra hộp thư (kể cả Spam) để nhận 1 Bộ hồ sơ dùng thử.', false);
      } else {
        verifyEmailCtaBtn.disabled = false;
        showVerifyEmailCtaMsg(vr.data.error || 'Không gửi được email xác thực — vui lòng thử lại sau.', true);
      }
    }).catch(function(){
      verifyEmailCtaBtn.disabled = false;
      showVerifyEmailCtaMsg('Không kết nối được tới máy chủ — chưa gửi được email xác thực.', true);
    });
  });

  authLogoutBtn.addEventListener('click', function(){ A.logout(); });

  A.onChange(updateAuthUI);

  // Xu ly link xac thuc email dang ?verify-email=TOKEN (xem
  // backend/app/routes/auth.py _verification_email_content) - tu dong goi
  // verify-email luc tai trang, hien ket qua, roi xoa query param khoi URL de
  // khong xu ly lap lai neu user tai lai trang (F5/bookmark link cu).
  var verifyToken = new URLSearchParams(location.search).get('verify-email');
  if(verifyToken){
    A.verifyEmail(verifyToken).then(function(vr){
      if(vr.ok){
        showAuthGlobalMsg(vr.data.message || 'Xác thực email thành công!', false);
      } else {
        showAuthGlobalMsg(vr.data.error || 'Xác thực email thất bại — liên kết có thể sai hoặc đã hết hạn.', true);
      }
    }).catch(function(){
      showAuthGlobalMsg('Không kết nối được tới máy chủ — chưa xác thực được email.', true);
    }).then(function(){
      A.refreshMe();
      var url = new URL(location.href);
      url.searchParams.delete('verify-email');
      history.replaceState({}, '', url.toString());
    });
  } else {
    A.refreshMe();
  }
});
