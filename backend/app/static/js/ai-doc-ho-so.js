(function(){
  var grid = document.getElementById('aihoGrid');
  if(!grid) return;

  /* Bảng "Chú ý" hiện 1 lần/phiên (tới khi tải lại trang) ngay khi bấm vào tab AI kiểm tra hồ sơ */
  var aihoTab = document.querySelector('.tab[data-view="aiho"]');
  var noticeModal = document.getElementById('aihoNoticeModal');
  var noticeShown = false;
  if(aihoTab && noticeModal){
    function closeNoticeModal(){ noticeModal.hidden = true; }
    aihoTab.addEventListener('click', function(){
      if(noticeShown) return;
      noticeShown = true;
      noticeModal.hidden = false;
    });
    document.getElementById('aihoNoticeClose').addEventListener('click', closeNoticeModal);
    document.getElementById('aihoNoticeOk').addEventListener('click', closeNoticeModal);
    noticeModal.addEventListener('click', function(e){ if(e.target === noticeModal) closeNoticeModal(); });
  }

  /* Nut "HUONG DAN" - khoi xo ra ngay duoi tieu de, khong phu thuoc dang nhap */
  var guideToggle = document.getElementById('aihoGuideToggle');
  var guidePanel = document.getElementById('aihoGuidePanel');
  if(guideToggle && guidePanel){
    guideToggle.addEventListener('click', function(){
      guidePanel.hidden = !guidePanel.hidden;
    });
    var guideCloseBtn = document.getElementById('aihoGuideClose');
    if(guideCloseBtn){
      guideCloseBtn.addEventListener('click', function(){ guidePanel.hidden = true; });
    }
  }

  /* Đăng nhập/phiên làm việc dùng chung toàn trang qua window.PcccAuth (xem script ngay sau <nav>) */
  var A = window.PcccAuth;
  var BACKEND_BASE = A.BACKEND_BASE;
  var currentUser = A.getUser();
  function getToken(){ return A.getToken(); }
  function updateBoHoSoDisplay(boHoSo){ A.setUserBoHoSo(boHoSo); }
  A.onChange(function(user){ currentUser = user; updateCta(); });

  /* ===================================================================
     Bộ hồ sơ: số dư + nạp thêm (Batch 5A sub-bước 4) — dùng route đã có ở
     sub-bước 3 (POST /api/topup/request, POST /api/topup/<id>/confirm-transfer,
     GET /api/topup/ledger). 2 bước đúng theo state machine backend: tạo yêu
     cầu (cho_chuyen_khoan) rồi mới bấm "Tôi đã chuyển khoản" (cho_xac_nhan).
     =================================================================== */
  var topupSection = document.getElementById('topupSection');
  var topupBalanceEl = document.getElementById('topupBalance');
  var topupCreateBtn = document.getElementById('topupCreateBtn');
  var topupHistoryToggle = document.getElementById('topupHistoryToggle');
  var topupFlowCard = document.getElementById('topupFlowCard');
  var topupHistoryWrap = document.getElementById('topupHistoryWrap');
  var topupHistoryTable = document.getElementById('topupHistoryTable');
  var topupMsg = document.getElementById('topupMsg');

  var LEDGER_REASON_LABELS = {
    email_verification: 'Xác thực email',
    usage_deduction: 'Dùng Bộ hồ sơ',
    refund_technical_error: 'Hoàn (lỗi kỹ thuật)',
    topup_confirmed: 'Nạp tiền được xác nhận',
    feedback_bonus: 'Thưởng góp ý'
  };

  function fmtTopupDate(iso){
    try { return new Date(iso).toLocaleString('vi-VN'); } catch(e){ return iso; }
  }

  function showTopupMsg(text, isError){
    topupMsg.textContent = text;
    topupMsg.classList.toggle('show', !!text);
    topupMsg.style.color = isError ? '' : 'var(--green)';
  }

  function updateBoHoSoBalanceDisplay(){
    if(!topupSection) return;
    topupSection.hidden = !currentUser;
    if(!currentUser) return;
    topupBalanceEl.textContent = currentUser.bo_ho_so ? currentUser.bo_ho_so.con_lai : '—';
  }
  A.onChange(updateBoHoSoBalanceDisplay);
  updateBoHoSoBalanceDisplay();

  function renderTopupFlowPending(referenceCode){
    topupFlowCard.innerHTML = '';
    topupFlowCard.hidden = false;
    var h4 = document.createElement('h4');
    h4.textContent = 'Yêu cầu nạp — mã giao dịch ' + referenceCode;
    topupFlowCard.appendChild(h4);
    var p = document.createElement('p');
    p.style.marginTop = '8px';
    p.style.color = 'var(--amber)';
    p.textContent = 'Đã ghi nhận — đang chờ admin đối chiếu và xác nhận chuyển khoản.';
    topupFlowCard.appendChild(p);
  }

  function renderTopupFlowCreated(data){
    topupFlowCard.innerHTML = '';
    topupFlowCard.hidden = false;

    var h4 = document.createElement('h4');
    h4.textContent = 'Yêu cầu nạp — mã giao dịch ' + data.reference_code;
    topupFlowCard.appendChild(h4);

    var p1 = document.createElement('p');
    p1.style.marginTop = '8px';
    p1.textContent = 'Chuyển khoản đúng ' + data.amount_vnd.toLocaleString('vi-VN') + 'đ, ghi rõ nội dung chuyển khoản là mã giao dịch ở trên, để được cộng ' + data.credits_to_grant + ' Bộ hồ sơ sau khi admin xác nhận.';
    topupFlowCard.appendChild(p1);

    var kv = document.createElement('div');
    kv.className = 'kv-grid';
    kv.style.marginTop = '10px';
    [
      ['Số tài khoản', data.bank.account_number],
      ['Tên chủ tài khoản', data.bank.account_name],
      ['Ngân hàng', data.bank.bank_name]
    ].forEach(function(pair){
      var div = document.createElement('div');
      var b = document.createElement('b');
      b.textContent = pair[0];
      div.appendChild(b);
      div.appendChild(document.createTextNode(pair[1]));
      kv.appendChild(div);
    });
    topupFlowCard.appendChild(kv);

    if(data.bank.qr_url){
      var img = document.createElement('img');
      img.src = data.bank.qr_url;
      img.alt = 'Mã QR chuyển khoản';
      img.style.maxWidth = '180px';
      img.style.marginTop = '12px';
      img.style.display = 'block';
      topupFlowCard.appendChild(img);
    }

    var confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.className = 'btn-main';
    confirmBtn.style.marginTop = '14px';
    confirmBtn.textContent = 'Tôi đã chuyển khoản';
    confirmBtn.addEventListener('click', function(){
      confirmBtn.disabled = true;
      fetch(BACKEND_BASE + '/api/topup/' + data.id + '/confirm-transfer', {
        method: 'POST',
        headers: {'Authorization': 'Bearer ' + getToken()}
      })
        .then(function(res){ return res.json().then(function(d){ return {status: res.status, data: d}; }); })
        .then(function(r){
          if(r.status >= 400){
            confirmBtn.disabled = false;
            showTopupMsg(r.data.error || 'Không gửi được xác nhận — vui lòng thử lại.', true);
            return;
          }
          renderTopupFlowPending(data.reference_code);
          showTopupMsg('Đã gửi yêu cầu — chờ admin xác nhận.', false);
        })
        .catch(function(){
          confirmBtn.disabled = false;
          showTopupMsg('Không kết nối được tới máy chủ — vui lòng thử lại.', true);
        });
    });
    topupFlowCard.appendChild(confirmBtn);
  }

  topupCreateBtn.addEventListener('click', function(){
    if(!currentUser){ window.openAuthModal(); return; }
    topupCreateBtn.disabled = true;
    showTopupMsg('', false);
    fetch(BACKEND_BASE + '/api/topup/request', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + getToken()}
    })
      .then(function(res){ return res.json().then(function(d){ return {status: res.status, data: d}; }); })
      .then(function(r){
        topupCreateBtn.disabled = false;
        if(r.status >= 400){
          showTopupMsg(r.data.error || 'Không tạo được yêu cầu nạp — vui lòng thử lại.', true);
          return;
        }
        renderTopupFlowCreated(r.data);
      })
      .catch(function(){
        topupCreateBtn.disabled = false;
        showTopupMsg('Không kết nối được tới máy chủ — vui lòng thử lại.', true);
      });
  });

  function renderTopupHistory(entries){
    topupHistoryTable.innerHTML = '';
    if(!entries.length){
      var trEmpty = document.createElement('tr');
      var tdEmpty = document.createElement('td');
      tdEmpty.style.color = 'var(--ink-soft)';
      tdEmpty.textContent = 'Chưa có giao dịch nào.';
      trEmpty.appendChild(tdEmpty);
      topupHistoryTable.appendChild(trEmpty);
      return;
    }
    var headerTr = document.createElement('tr');
    ['Thời gian', 'Loại', 'Thay đổi', 'Số dư sau', 'Ghi chú'].forEach(function(label){
      var th = document.createElement('th');
      th.textContent = label;
      headerTr.appendChild(th);
    });
    topupHistoryTable.appendChild(headerTr);

    entries.forEach(function(e){
      var tr = document.createElement('tr');

      var tdTime = document.createElement('td');
      tdTime.textContent = fmtTopupDate(e.created_at);
      tr.appendChild(tdTime);

      var tdReason = document.createElement('td');
      tdReason.textContent = LEDGER_REASON_LABELS[e.reason] || e.reason;
      tr.appendChild(tdReason);

      var tdDelta = document.createElement('td');
      tdDelta.textContent = (e.delta > 0 ? '+' : '') + e.delta;
      tdDelta.style.fontFamily = 'var(--mono)';
      tdDelta.style.color = e.delta > 0 ? 'var(--green)' : 'var(--red-deep)';
      tr.appendChild(tdDelta);

      var tdBalance = document.createElement('td');
      tdBalance.textContent = e.balance_after;
      tr.appendChild(tdBalance);

      var tdNote = document.createElement('td');
      tdNote.textContent = e.note || '—';
      tr.appendChild(tdNote);

      topupHistoryTable.appendChild(tr);
    });
  }

  topupHistoryToggle.addEventListener('click', function(){
    if(!currentUser){ window.openAuthModal(); return; }
    var willShow = topupHistoryWrap.hidden;
    if(willShow){
      fetch(BACKEND_BASE + '/api/topup/ledger', {headers: {'Authorization': 'Bearer ' + getToken()}})
        .then(function(res){ return res.json(); })
        .then(function(data){
          renderTopupHistory(data.ledger || []);
          if(data.bo_ho_so_con_lai !== undefined) updateBoHoSoDisplay({con_lai: data.bo_ho_so_con_lai});
        })
        .catch(function(){
          showTopupMsg('Không tải được lịch sử — vui lòng thử lại.', true);
        });
    }
    topupHistoryWrap.hidden = !willShow;
    topupHistoryToggle.textContent = willShow ? 'Ẩn lịch sử' : 'Xem lịch sử';
  });

  // Gioi han dung luong file, phan biet anh/PDF (khop dung gioi han that cua
  // Anthropic Messages API — xem giai thich chi tiet o routes/aiho.py
  // SINGLE_MAX_BYTES_IMAGE/SINGLE_MAX_BYTES_PDF). Dung CHUNG voi
  // MERGED_MAX_BYTES_IMAGE/MERGED_MAX_BYTES_PDF (khai bao rieng ben duoi cho
  // panel "Dinh 1 ban ve - AI tu nhan dien") vi cung 1 gioi han API goc.
  var SINGLE_MAX_BYTES_IMAGE = 7 * 1024 * 1024;
  var SINGLE_MAX_BYTES_PDF = 22 * 1024 * 1024;

  // Dung createElement/.textContent thay vi noi chuoi + innerHTML - ten file
  // nguoi dung tu chon (f.name) khong dang tin cay, co the chua ky tu HTML.
  function buildFileRow(text){
    var row = document.createElement('div');
    row.className = 'drop-file';
    var span = document.createElement('span');
    span.textContent = text;
    row.appendChild(span);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Gỡ file');
    btn.textContent = '✕';
    row.appendChild(btn);
    return row;
  }

  /* ===================================================================
     Các ô có AI thật — đính file thật, gọi API thật (khác các ô demo còn lại).
     Mỗi hạng mục chỉ cần thêm 1 mục vào đây + route backend tương ứng.
     =================================================================== */
  var REAL_CATEGORIES = {
    kientruc: {
      endpoint: '/api/aiho/read-quymo',
      label: 'Quy mô công trình',
      estimatedSeconds: 50, // 1 lan goi AI, tieu chi it hon bao chay/dien PCCC (chi 6 muc + 4 cau A.2/A.4)
      summarize: function(data){
        var qm = data.quy_mo || {};
        // OCCS la bien global khai bao o js/tuvan-so-bo.js (nap sau file nay,
        // nhung nam trong CUNG 1 khong gian ten script cua trang - ham nay chi
        // chay khi trang da nap xong het, sau khi nguoi dung tuong tac).
        var occDef = (typeof OCCS !== 'undefined' ? OCCS : []).filter(function(o){ return o.id === qm.occ; })[0];
        var occLabel = (occDef && occDef.label) || qm.occ || 'chưa xác định';
        var parts = ['Xác định công năng: ' + occLabel + '.'];
        if(qm.floors != null){
          parts.push(qm.floors + ' tầng nổi' + (qm.basements ? ' + ' + qm.basements + ' tầng hầm' : '') + '.');
        }
        if(qm.totalArea != null){
          parts.push('ΣF ≈ ' + Number(qm.totalArea).toLocaleString('vi-VN') + ' m².');
        }
        return {status: 'ok', note: parts.join(' ')};
      }
    },
    baochay: {
      endpoint: '/api/aiho/read-baochay',
      label: 'Báo cháy tự động',
      estimatedSeconds: 150, // theo thời gian thực đo được (~134s cho 47 tiêu chí), cộng thêm dự phòng
      summarize: function(data){
        var items = data.items || [];
        var status = 'ok';
        if(items.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(items.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        var loaiLabel = data.loai_he_thong === 'dia_chi' ? 'địa chỉ' : 'thường';
        return {status: status, note: 'AI nhận diện: báo cháy loại ' + loaiLabel + '. ' + (data.tong_ket || '')};
      }
    },
    dienpccc: {
      endpoint: '/api/aiho/read-dienpccc',
      label: 'Điện PCCC',
      estimatedSeconds: 60, // theo thời gian thực đo được (~45s cho 17 tiêu chí), cộng thêm dự phòng
      summarize: function(data){
        var items = data.items || [];
        var status = 'ok';
        if(items.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(items.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        return {status: status, note: data.tong_ket || ''};
      }
    },
    ccnuoc: {
      endpoint: '/api/aiho/read-ccnuoc',
      label: 'Chữa cháy bằng nước',
      estimatedSeconds: 150, // gộp 3 mẫu B3/B5/B6 chạy song song ở backend, giới hạn bởi B6 (48 tiêu chí) — ngang báo cháy
      summarize: function(data){
        var forms = data.forms || {};
        var allItems = [];
        Object.keys(forms).forEach(function(k){ allItems = allItems.concat(forms[k].items || []); });
        var status = 'ok';
        if(allItems.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(allItems.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        return {status: status, note: data.tong_ket || ''};
      }
    },
    densucco: {
      endpoint: '/api/aiho/read-densucco',
      label: 'Đèn sự cố / chỉ dẫn thoát nạn / Bình chữa cháy',
      estimatedSeconds: 110, // gộp 2 mẫu B12 (24 tiêu chí)/B13 (18 tiêu chí) song song ở backend — tạm ước lượng, đo lại sau lần chạy thật đầu tiên
      summarize: function(data){
        var forms = data.forms || {};
        var allItems = [];
        Object.keys(forms).forEach(function(k){ allItems = allItems.concat(forms[k].items || []); });
        var status = 'ok';
        if(allItems.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(allItems.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        return {status: status, note: data.tong_ket || ''};
      }
    },
    khibot: {
      endpoint: '/api/aiho/read-khibot',
      label: 'Chữa cháy bằng khí',
      estimatedSeconds: 90, // 1 lan goi AI, AI tu phan loai 1 trong 4 he (B8-B11) roi chi doi chieu dung nhanh do — it tieu chi hon bao chay/ccnuoc
      summarize: function(data){
        var items = data.items || [];
        var status = 'ok';
        if(items.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(items.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        var HE_THONG_LABEL = {
          khi_hoa_long: 'khí hóa lỏng',
          khi_nen: 'khí nén/khí trơ',
          khi_co2: 'CO₂',
          sol_khi: 'Sol-khí'
        };
        var heLabel = HE_THONG_LABEL[data.he_thong] || data.he_thong || 'chưa xác định';
        return {status: status, note: 'AI nhận diện: hệ ' + heLabel + '. ' + (data.tong_ket || '')};
      }
    },
    botcodinh: {
      endpoint: '/api/aiho/read-botcodinh',
      label: 'Chữa cháy bằng bọt cố định',
      estimatedSeconds: 60, // 1 mau duy nhat (B7, 15 tieu chi), khong co buoc AI phan loai — nhanh hon khibot
      summarize: function(data){
        var items = data.items || [];
        var status = 'ok';
        if(items.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(items.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        return {status: status, note: data.tong_ket || ''};
      }
    },
    giakehang: {
      endpoint: '/api/aiho/read-b15',
      label: 'Chữa cháy tự động giá kệ hàng',
      estimatedSeconds: 100, // 1 mau duy nhat nhung 74 tieu chi (ca 2 nhanh gop chung 1 bang) — nhieu hon khibot/botcodinh
      summarize: function(data){
        var items = data.items || [];
        var status = 'ok';
        if(items.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(items.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        var NHANH_LABEL = {mot_tang: 'hệ 1 tầng đầu phun', nhieu_tang: 'hệ nhiều tầng đầu phun'};
        var nhanhLabel = NHANH_LABEL[data.nhanh] || data.nhanh || 'chưa xác định';
        return {status: status, note: 'AI nhận diện: ' + nhanhLabel + '. ' + (data.tong_ket || '')};
      }
    },
    botchuachay: {
      endpoint: '/api/aiho/read-b16',
      label: 'Chữa cháy bằng bột',
      estimatedSeconds: 70, // 1 mau duy nhat, 33 tieu chi (ca 2 nhanh gop chung 1 bang) — it hon giakehang
      summarize: function(data){
        var items = data.items || [];
        var status = 'ok';
        if(items.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
        else if(items.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
        var NHANH_LABEL = {the_tich: 'hệ theo thể tích', be_mat: 'hệ bề mặt'};
        var nhanhLabel = NHANH_LABEL[data.nhanh] || data.nhanh || 'chưa xác định';
        return {status: status, note: 'AI nhận diện: ' + nhanhLabel + '. ' + (data.tong_ket || '')};
      }
    }
  };

  var realFiles = {};   // slot -> File[] (toi da MAX_FILES_PER_SLOT, Batch 5A Pha 1)
  var realResults = {}; // slot -> {status, note} (dùng cho dòng tóm tắt trong bảng kết quả)
  var realData = {};    // slot -> JSON đầy đủ AI trả về (gồm items/kien_nghi/mdc_docx_*)

  /* Phiên Bộ hồ sơ đang mở (session_id) — dùng CHUNG giữa 2 luồng: nút "Bắt
     đầu phân tích" chính (BƯỚC 1→2) VÀ nút "Lưu thông số" nhập tay Quy mô
     (có thể xảy ra TRƯỚC khi bấm phân tích). ensureSessionOpen() tái sử dụng
     phiên đã mở thay vì mở lần 2 (idempotent ở backend, nhưng tránh gọi thừa
     và giữ 2 luồng luôn cùng 1 phiên — để dữ liệu quy mô nhập tay trước đó
     được các hạng mục khác trong CÙNG lượt phân tích tái dùng). */
  var activeSessionId = null;

  /* Quy mô Giai đoạn 1 (Phần A/B/C/E) — trạng thái riêng cho phiên đang mở:
     - quyMoDataSavedInSession: true sau khi CÓ 1 bản ghi Quy mô được lưu
       trong phiên này (nhập tay "Lưu thông số" HOẶC Lượt 0 tự phát hiện) —
       dùng để KHÔNG hiện lại modal khuyến cáo (Phần B) nếu đã có rồi.
     - quyMoScanAttemptedInSession: true sau khi Lượt 0 đã chạy 1 lần (dù tìm
       thấy gì hay không) — tránh gọi lại Lượt 0 nhiều lần thừa nếu người
       dùng bấm "Bắt đầu phân tích" nhiều lần trong cùng phiên mà chưa từng
       đính file Quy mô riêng.
     - quyMoModalSkippedOnce: true sau khi người dùng bấm "Bỏ qua, vẫn chạy"
       1 lần — không hiện lại modal cho các lần bấm tiếp theo trong CÙNG
       phiên (tránh làm phiền lặp lại, đúng yêu cầu Phần B).
     - quyMoConflictWarningsPending: mảng conflict (Phần D.1) từ lần Lượt 0
       gần nhất, giữ tạm để hiển thị SAU khi Lượt 1 xong (cùng lúc với cảnh
       báo "thiếu hồ sơ" ở Phần E) — không hiện ngay lúc Lượt 0 xong vì lúc
       đó khu kết quả (#aihoResults) còn đang ẩn. */
  var quyMoDataSavedInSession = false;
  // Form A goc (A14/A15) - Phan 3: can biet occ hien tai de quyet dinh hien
  // nut "Xuat Form A goc" dung loai hinh - cap nhat o CA 3 nguon co the co
  // quy mo (AI doc kientruc / nhap tay / Luot 0 tu phat hien), vi khong co
  // 1 route rieng de GET lai occ hien tai tu server.
  var quyMoOccInSession = null;
  var quyMoScanAttemptedInSession = false;
  var quyMoModalSkippedOnce = false;
  var quyMoConflictWarningsPending = [];
  // Phan E — canh bao "thieu ho so he thong X" cua LUOT VUA CHAY XONG gan
  // nhat (khong tich luy qua nhieu luot, luon ghi de) - doc boi
  // outputPreviewHtml('loi') VA maybeExportKienNghiDocx() VA renderQuyMoWarningsBox().
  var quyMoMissingWarningsPending = [];

  function ensureSessionOpen(){
    if(activeSessionId){
      return Promise.resolve({status: 200, data: {session_id: activeSessionId}});
    }
    return fetch(BACKEND_BASE + '/api/aiho/session/open', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + getToken()}
    })
      .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
      .then(function(r){
        if(r.status < 400){
          activeSessionId = r.data.session_id;
        }
        if(r.data && r.data.bo_ho_so_con_lai !== undefined) updateBoHoSoDisplay({con_lai: r.data.bo_ho_so_con_lai});
        return r;
      });
  }

  // Kiem tra kich thuoc file - dung CHUNG cho ca 2 duong dinh file: tung the
  // rieng (setupRealFileCard) VA panel "Dung 1 file cho nhieu hang muc".
  // Tra ve chuoi loi neu vuot han muc, null neu hop le.
  function validateFileSize(f){
    var isPdf = f.type === 'application/pdf';
    var limitBytes = isPdf ? SINGLE_MAX_BYTES_PDF : SINGLE_MAX_BYTES_IMAGE;
    if(f.size > limitBytes){
      var overMb = (f.size / (1024 * 1024)).toFixed(1);
      var limitMb = limitBytes / (1024 * 1024);
      return 'File "' + f.name + '" (' + overMb + ' MB) vượt quá giới hạn ' + limitMb + 'MB cho ' + (isPdf ? 'PDF' : 'ảnh') + ' — vui lòng nén file hoặc chia nhỏ PDF rồi đính kèm lại.';
    }
    return null;
  }

  // Gioi han so file dinh CHO 1 SLOT/hang muc (Batch 5A Pha 1 - dinh nhieu file
  // vi noi dung 1 he thong doi khi nam tren file mang ten he thong khac) - khop
  // dung MAX_FILES_PER_CALL o backend routes/aiho.py.
  var MAX_FILES_PER_SLOT = 3;

  // THEM 1 file (da qua validateFileSize) vao 1 slot cu the - cap nhat realFiles
  // (gio la MANG, khong phai 1 File don) + ve THEM 1 dong .drop-file (khong xoa
  // dong cu). Dung CHUNG cho ca setupRealFileCard VA panel "Dung 1 file cho
  // nhieu hang muc" (khong viet lai).
  function addFileToSlot(slot, f){
    var card = document.getElementById(slot + 'Card');
    var status = document.getElementById(slot + 'Status');
    if(!card || !status) return;

    if(!realFiles[slot]) realFiles[slot] = [];
    realFiles[slot].push(f);
    realResults[slot] = null;
    realData[slot] = null;
    card.classList.add('filled');
    status.textContent = '● Đã đính kèm';
    status.classList.add('attached');
    var body = card.querySelector('.drop-body');
    var sizeMb = (f.size / (1024 * 1024)).toFixed(1);
    var fileRow = buildFileRow(f.name + ' · ' + sizeMb + ' MB');
    fileRow.querySelector('button').addEventListener('click', function(e){
      e.stopPropagation();
      var arr = realFiles[slot] || [];
      var idx = arr.indexOf(f);
      if(idx !== -1) arr.splice(idx, 1);
      realResults[slot] = null;
      realData[slot] = null;
      fileRow.remove();
      if(!arr.length){
        var fileInput = document.getElementById(slot + 'FileInput');
        if(fileInput) fileInput.value = '';
        card.classList.remove('filled');
        status.textContent = '○ Chưa đính kèm';
        status.classList.remove('attached');
      }
      updateCta();
      updateProgress();
    });
    body.appendChild(fileRow);
    updateCta();
    updateProgress();
  }

  function setupRealFileCard(slot){
    var card = document.getElementById(slot + 'Card');
    var fileInput = document.getElementById(slot + 'FileInput');
    var status = document.getElementById(slot + 'Status');
    if(!card || !fileInput || !status) return;
    fileInput.multiple = true;

    card.addEventListener('click', function(e){
      if(e.target.closest('.drop-file')) return;
      if(!currentUser){ window.openAuthModal(); return; }
      fileInput.click();
    });
    fileInput.addEventListener('click', function(e){ e.stopPropagation(); });
    fileInput.addEventListener('change', function(){
      var newFiles = Array.prototype.slice.call(fileInput.files);
      if(!newFiles.length) return;
      var current = realFiles[slot] || [];
      if(current.length + newFiles.length > MAX_FILES_PER_SLOT){
        msg.textContent = 'Chỉ được đính tối đa ' + MAX_FILES_PER_SLOT + ' file cho 1 hạng mục.';
        msg.classList.add('show');
        fileInput.value = '';
        return;
      }
      for(var i = 0; i < newFiles.length; i++){
        var err = validateFileSize(newFiles[i]);
        if(err){ msg.textContent = err; msg.classList.add('show'); fileInput.value = ''; return; }
      }
      msg.classList.remove('show');
      newFiles.forEach(function(f){ addFileToSlot(slot, f); });
      fileInput.value = ''; // cho phep chon lai file (kem them file 2/3 o lan click tiep theo)
    });
  }
  Object.keys(REAL_CATEGORIES).forEach(setupRealFileCard);

  /* ===================================================================
     Quy mô — nhập tay thông số (thay cho đính bản vẽ riêng), xổ ra NGAY
     TRONG thẻ "Quy mô". Gọi POST /api/aiho/quymo-manual — route này KHÔNG
     trừ Bộ hồ sơ nhưng VẪN cần 1 phiên đang mở (session_id) để lưu đúng
     phiên — dùng chung ensureSessionOpen() với nút "Bắt đầu phân tích"
     chính (idempotent ở backend, không mở/trừ 2 lần).
     Field lấy từ OCCS/EXTRA_FIELDS (js/tuvan-so-bo.js, đã nạp cùng trang) để
     đúng nhãn/enum với công cụ "Hướng dẫn sơ bộ" — không định nghĩa lại.
     =================================================================== */
  var QUYMO_BASE_FIELDS = [
    {key: 'floors', label: 'Số tầng nổi', ph: 'VD: 8'},
    {key: 'basements', label: 'Số tầng hầm', ph: 'VD: 1'},
    {key: 'semiBasements', label: 'Số tầng bán hầm', ph: 'VD: 0'},
    {key: 'areaFloor', label: 'Diện tích 1 tầng điển hình (m²)', ph: 'VD: 500'},
    {key: 'totalArea', label: 'Tổng diện tích sàn ΣF (m²)', ph: 'VD: 4200'},
    {key: 'volume', label: 'Khối tích V (m³)', ph: 'VD: 15000'},
    {key: 'hFire', label: 'Chiều cao phục vụ PCCC (m)', ph: 'VD: 22'},
    {key: 'chieuCaoKeHang', label: 'Chiều cao sắp xếp hàng hoá trên kệ (m) — nếu có', ph: 'VD: 6'}
  ];

  var quymoManualToggle = document.getElementById('kientrucManualToggle');
  var quymoManualForm = document.getElementById('kientrucManualForm');

  function buildQuymoManualForm(){
    var occs = (typeof OCCS !== 'undefined') ? OCCS : [];
    var extraDefs = (typeof EXTRA_FIELDS !== 'undefined') ? EXTRA_FIELDS : {};

    quymoManualForm.innerHTML = '';

    var introP = document.createElement('p');
    introP.className = 'hint';
    introP.style.marginBottom = '10px';
    introP.textContent = 'Điền thông số bạn biết — không bắt buộc điền hết. Dữ liệu này giúp các hạng mục khác (báo cháy, điện PCCC, nước, đèn/bình) trong CÙNG Bộ hồ sơ đối chiếu chính xác hơn.';
    quymoManualForm.appendChild(introP);

    var occField = document.createElement('div');
    occField.className = 'field';
    var occLabel = document.createElement('label');
    occLabel.textContent = 'Công năng chính';
    occField.appendChild(occLabel);
    var occSelect = document.createElement('select');
    var optDefault = document.createElement('option');
    optDefault.value = '';
    optDefault.textContent = '— Chọn công năng —';
    occSelect.appendChild(optDefault);
    occs.forEach(function(o){
      var opt = document.createElement('option');
      opt.value = o.id;
      opt.textContent = o.label;
      occSelect.appendChild(opt);
    });
    occField.appendChild(occSelect);
    quymoManualForm.appendChild(occField);

    var baseGrid = document.createElement('div');
    baseGrid.className = 'grid';
    baseGrid.style.marginTop = '10px';
    var baseInputs = {};
    QUYMO_BASE_FIELDS.forEach(function(f){
      var field = document.createElement('div');
      field.className = 'field';
      var label = document.createElement('label');
      label.textContent = f.label;
      field.appendChild(label);
      var input = document.createElement('input');
      input.type = 'number';
      input.min = '0';
      input.step = 'any';
      input.placeholder = f.ph;
      field.appendChild(input);
      baseGrid.appendChild(field);
      baseInputs[f.key] = input;
    });
    quymoManualForm.appendChild(baseGrid);

    // coBeXangDauNgoaiTroi (Phần D.2) — boolean, không fit khuôn input số
    // của QUYMO_BASE_FIELDS, dùng select riêng (3 trạng thái: chưa xác định
    // / có / không — KHÔNG mặc định "Không" để tránh hiểu nhầm là đã xác
    // nhận không có, xem evaluate_bot_co_dinh() phân biệt None vs False).
    var coBeField = document.createElement('div');
    coBeField.className = 'field';
    coBeField.style.marginTop = '10px';
    var coBeLabel = document.createElement('label');
    coBeLabel.textContent = 'Có bể chứa xăng dầu/dung môi dễ cháy đặt ngoài trời không?';
    coBeField.appendChild(coBeLabel);
    var coBeSelect = document.createElement('select');
    [['', '— Chưa xác định —'], ['true', 'Có'], ['false', 'Không']].forEach(function(pair){
      var opt = document.createElement('option');
      opt.value = pair[0];
      opt.textContent = pair[1];
      coBeSelect.appendChild(opt);
    });
    coBeField.appendChild(coBeSelect);
    quymoManualForm.appendChild(coBeField);

    var extraWrap = document.createElement('div');
    extraWrap.className = 'grid';
    extraWrap.style.marginTop = '10px';
    quymoManualForm.appendChild(extraWrap);

    var extraInputs = {};
    function renderExtraFields(){
      extraWrap.innerHTML = '';
      extraInputs = {};
      var occDef = occs.filter(function(o){ return o.id === occSelect.value; })[0];
      var extraKeys = (occDef && occDef.extra) || [];
      extraKeys.forEach(function(key){
        var def = extraDefs[key];
        if(!def) return;
        var field = document.createElement('div');
        field.className = 'field';
        var label = document.createElement('label');
        label.textContent = def.label;
        field.appendChild(label);
        var el;
        if(def.select){
          el = document.createElement('select');
          def.select.forEach(function(pair){
            var opt = document.createElement('option');
            opt.value = pair[0];
            opt.textContent = pair[1];
            el.appendChild(opt);
          });
        } else {
          el = document.createElement('input');
          el.type = 'number';
          el.min = '0';
          el.step = 'any';
          el.placeholder = def.ph || '';
        }
        field.appendChild(el);
        extraWrap.appendChild(field);
        extraInputs[key] = el;
      });
    }
    occSelect.addEventListener('change', renderExtraFields);
    renderExtraFields();

    var actions = document.createElement('div');
    actions.className = 'quymo-manual-actions';

    var saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn-main';
    saveBtn.textContent = 'Lưu thông số';
    actions.appendChild(saveBtn);

    var feedbackMsg = document.createElement('span');
    feedbackMsg.className = 'quymo-manual-msg';
    actions.appendChild(feedbackMsg);

    quymoManualForm.appendChild(actions);

    var downloadWrap = document.createElement('div');
    downloadWrap.style.marginTop = '10px';
    quymoManualForm.appendChild(downloadWrap);

    saveBtn.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var occVal = occSelect.value;
      if(!occVal){
        feedbackMsg.textContent = 'Vui lòng chọn công năng chính.';
        feedbackMsg.style.color = 'var(--red-deep)';
        return;
      }
      var quyMo = {occ: occVal};
      QUYMO_BASE_FIELDS.forEach(function(f){
        var v = baseInputs[f.key].value;
        if(v !== '') quyMo[f.key] = Number(v);
      });
      if(coBeSelect.value !== '') quyMo.coBeXangDauNgoaiTroi = (coBeSelect.value === 'true');
      Object.keys(extraInputs).forEach(function(key){
        var el = extraInputs[key];
        if(el.value === '') return;
        quyMo[key] = extraDefs[key].select ? el.value : Number(el.value);
      });

      saveBtn.disabled = true;
      feedbackMsg.textContent = 'Đang lưu…';
      feedbackMsg.style.color = '';
      downloadWrap.innerHTML = '';

      ensureSessionOpen().then(function(r){
        if(r.status >= 400){
          saveBtn.disabled = false;
          feedbackMsg.textContent = r.data.error || 'Không mở được phiên Bộ hồ sơ — vui lòng thử lại.';
          feedbackMsg.style.color = 'var(--red-deep)';
          return;
        }
        return fetch(BACKEND_BASE + '/api/aiho/quymo-manual', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
          body: JSON.stringify({session_id: r.data.session_id, quy_mo: quyMo})
        })
          .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
          .then(function(r2){
            saveBtn.disabled = false;
            if(r2.status >= 400){
              feedbackMsg.textContent = r2.data.error || 'Không lưu được thông số — vui lòng thử lại.';
              feedbackMsg.style.color = 'var(--red-deep)';
              return;
            }
            feedbackMsg.textContent = '✓ Đã lưu — các hạng mục khác trong Bộ hồ sơ này sẽ dùng thông số này để đối chiếu chính xác hơn.';
            feedbackMsg.style.color = 'var(--green)';
            quyMoDataSavedInSession = true;
            quyMoOccInSession = quyMo.occ;

            var f = (r2.data.mdc_docx_files || [])[0];
            if(f && f.base64){
              var a = document.createElement('a');
              a.className = 'btn-ghost';
              a.style.display = 'inline-block';
              a.style.textDecoration = 'none';
              a.download = f.filename;
              a.href = 'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,' + f.base64;
              a.textContent = 'Tải file Form A (.docx)';
              downloadWrap.appendChild(a);
            }
            updateCta();
          });
      }).catch(function(){
        saveBtn.disabled = false;
        feedbackMsg.textContent = 'Không kết nối được tới máy chủ — vui lòng thử lại.';
        feedbackMsg.style.color = 'var(--red-deep)';
      });
    });
  }

  if(quymoManualToggle && quymoManualForm){
    quymoManualToggle.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var willOpen = quymoManualForm.hidden;
      if(willOpen && !quymoManualForm.dataset.built){
        buildQuymoManualForm();
        quymoManualForm.dataset.built = '1';
      }
      quymoManualForm.hidden = !willOpen;
      quymoManualToggle.textContent = willOpen ? 'Ẩn form nhập tay' : 'Không có bản vẽ riêng? Nhập tay thông số';
    });
  }

  /* ===================================================================
     "Dùng 1 file cho nhiều hạng mục" — tiện ích UX THUẦN TUÝ: gán CÙNG 1
     File object vào nhiều slot (realFiles[slot]) cùng lúc, dùng lại ĐÚNG
     addFileToSlot() ở trên — mỗi hạng mục vẫn tự gọi AI đọc ĐỘC LẬP trên
     file này như đính riêng lẻ, KHÔNG tự nhận diện/gộp kết quả gì cả.
     Chặn tối đa 4 hạng mục/lần (rút kinh nghiệm sự cố OOM production khi
     nhiều hạng mục gọi AI đồng thời) - xem render.yaml (gunicorn --workers).
     =================================================================== */
  var MULTI_ATTACH_MAX = 4;
  var multiAttachToggle = document.getElementById('multiAttachToggle');
  var multiAttachPanel = document.getElementById('multiAttachPanel');

  function buildMultiAttachPanel(){
    multiAttachPanel.innerHTML = '';

    var introP = document.createElement('p');
    introP.className = 'hint';
    introP.textContent = 'Dùng khi bạn có 1 bản vẽ duy nhất áp dụng cho nhiều hạng mục (công trình nhỏ) — mỗi hạng mục vẫn tự đọc AI độc lập trên file này, không tự gộp kết quả.';
    multiAttachPanel.appendChild(introP);

    var fileField = document.createElement('div');
    fileField.className = 'field';
    fileField.style.marginTop = '10px';
    var fileLabel = document.createElement('label');
    fileLabel.textContent = 'Chọn file bản vẽ dùng chung';
    fileField.appendChild(fileLabel);
    var fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'application/pdf,image/png,image/jpeg,image/webp';
    fileField.appendChild(fileInput);
    multiAttachPanel.appendChild(fileField);

    var checklistLabel = document.createElement('p');
    checklistLabel.className = 'hint';
    checklistLabel.style.marginTop = '12px';
    checklistLabel.textContent = 'Áp dụng file này cho các hạng mục (tối đa ' + MULTI_ATTACH_MAX + '):';
    multiAttachPanel.appendChild(checklistLabel);

    var checklistWrap = document.createElement('div');
    checklistWrap.className = 'multi-attach-checklist';
    var checkboxes = [];
    Object.keys(REAL_CATEGORIES).forEach(function(slot){
      var card = document.getElementById(slot + 'Card');
      var label = (card && card.querySelector('h4')) ? card.querySelector('h4').childNodes[0].textContent.trim() : slot;
      var row = document.createElement('label');
      row.className = 'multi-attach-item';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = slot;
      row.appendChild(cb);
      var span = document.createElement('span');
      span.textContent = label;
      row.appendChild(span);
      checklistWrap.appendChild(row);
      checkboxes.push(cb);
    });
    multiAttachPanel.appendChild(checklistWrap);

    var warningP = document.createElement('p');
    warningP.className = 'multi-attach-warning';
    multiAttachPanel.appendChild(warningP);

    var errorP = document.createElement('p');
    errorP.className = 'multi-attach-error';
    errorP.hidden = true;
    multiAttachPanel.appendChild(errorP);

    var actions = document.createElement('div');
    actions.className = 'quymo-manual-actions';
    var applyBtn = document.createElement('button');
    applyBtn.type = 'button';
    applyBtn.className = 'btn-main';
    applyBtn.textContent = 'Áp dụng';
    applyBtn.disabled = true;
    actions.appendChild(applyBtn);
    var resultMsg = document.createElement('span');
    resultMsg.className = 'quymo-manual-msg';
    actions.appendChild(resultMsg);
    multiAttachPanel.appendChild(actions);

    function updateWarning(){
      var n = checkboxes.filter(function(cb){ return cb.checked; }).length;
      warningP.textContent = n > 0
        ? 'Việc này sẽ dùng ' + n + '/7 form trong Bộ hồ sơ hiện tại (1 form cho mỗi hạng mục đã chọn).'
        : '';
      applyBtn.disabled = !(n > 0 && fileInput.files[0]);
    }

    checkboxes.forEach(function(cb){
      cb.addEventListener('change', function(){
        var checkedCount = checkboxes.filter(function(c){ return c.checked; }).length;
        if(checkedCount > MULTI_ATTACH_MAX){
          cb.checked = false;
          errorP.textContent = 'Chỉ áp dụng tối đa ' + MULTI_ATTACH_MAX + ' hạng mục cùng lúc qua tính năng này.';
          errorP.hidden = false;
          updateWarning();
          return;
        }
        errorP.hidden = true;
        updateWarning();
      });
    });

    fileInput.addEventListener('change', function(){
      resultMsg.textContent = '';
      updateWarning();
    });

    applyBtn.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var f = fileInput.files[0];
      if(!f) return;
      var err = validateFileSize(f);
      if(err){
        resultMsg.textContent = err;
        resultMsg.style.color = 'var(--red-deep)';
        return;
      }
      var slots = checkboxes.filter(function(cb){ return cb.checked; }).map(function(cb){ return cb.value; });
      if(!slots.length) return;
      slots.forEach(function(slot){ addFileToSlot(slot, f); });
      resultMsg.textContent = '✓ Đã áp dụng file cho ' + slots.length + ' hạng mục — kiểm tra lại các thẻ bên dưới.';
      resultMsg.style.color = 'var(--green)';
    });

    updateWarning();
  }

  if(multiAttachToggle && multiAttachPanel){
    multiAttachToggle.addEventListener('click', function(){
      var willOpen = multiAttachPanel.hidden;
      if(willOpen && !multiAttachPanel.dataset.built){
        buildMultiAttachPanel();
        multiAttachPanel.dataset.built = '1';
      }
      multiAttachPanel.hidden = !willOpen;
      multiAttachToggle.textContent = willOpen ? 'Ẩn' : 'Dùng 1 file cho nhiều hạng mục';
    });
  }

  /* ===================================================================
     "Đính 1 bản vẽ — AI tự nhận diện nhiều hạng mục" (Batch 5A sub-bước 5).
     KHÁC hẳn "Dùng 1 file cho nhiều hạng mục" ở trên: đây là 1 LƯỢT GỌI AI DUY
     NHẤT (POST /api/aiho/read-merged) vừa tự xác định bản vẽ thuộc hạng mục
     nào trong 5 hạng mục AI thật, vừa điền luôn kết quả — không phải đính 1
     file vào nhiều thẻ để mỗi thẻ tự gọi AI riêng như tính năng kia.
     Cơ chế xác nhận 2 giai đoạn (đúng thiết kế đã duyệt): /read-merged chỉ giữ
     chỗ 1 FILE (files_used), CHƯA trừ form nào — người dùng xem kỹ kết quả,
     có thể bỏ bớt hạng mục không muốn giữ, rồi bấm "Xác nhận" mới gọi
     /read-merged/confirm để thực sự giữ chỗ form (forms_used) + xuất MDC.
     Tái dùng renderMdcReal()/renderKienNghiReal()/REAL_CATEGORIES[slot].summarize()
     đã có — không viết lại logic hiển thị/kết hợp kiến nghị.
     =================================================================== */
  var MERGED_MAX_BYTES_IMAGE = 7 * 1024 * 1024;
  var MERGED_MAX_BYTES_PDF = 22 * 1024 * 1024;
  var MERGED_FORMS_PER_CALL = {baochay: 1, ccnuoc: 3, densucco: 2, dienpccc: 1, quy_mo: 1};

  var autoDetectToggle = document.getElementById('autoDetectToggle');
  var autoDetectPanel = document.getElementById('autoDetectPanel');

  function validateMergedFileSize(f){
    var isPdf = f.type === 'application/pdf';
    var limitBytes = isPdf ? MERGED_MAX_BYTES_PDF : MERGED_MAX_BYTES_IMAGE;
    if(f.size > limitBytes){
      var overMb = (f.size / (1024 * 1024)).toFixed(1);
      var limitMb = limitBytes / (1024 * 1024);
      return 'File "' + f.name + '" (' + overMb + ' MB) vượt quá giới hạn ' + limitMb + 'MB cho ' + (isPdf ? 'PDF' : 'ảnh') + ' ở tính năng này.';
    }
    return null;
  }

  // Tom tat nhanh 1 hang muc de hien PREVIEW (TRUOC khi xac nhan) - doc THANG
  // du lieu tho tu response /read-merged (chua qua finalize_category_result()
  // ben server, vd ccnuoc/densucco chua gop tong_ket 3/2 mau con lai rieng
  // tung mau) - chi can du de hien dung trang thai (dat/can bo sung/thieu sot),
  // KHONG lam lai logic gop kien nghi/tong_ket cua server (se hien day du,
  // chinh xac o phan renderMdcReal/renderKienNghiReal SAU KHI xac nhan).
  function summarizeMergedPreview(cat, catData){
    if(cat === 'quy_mo'){
      var qm = (catData && catData.quy_mo) || {};
      var occDef = (typeof OCCS !== 'undefined' ? OCCS : []).filter(function(o){ return o.id === qm.occ; })[0];
      return {status: 'ok', note: 'Công năng: ' + ((occDef && occDef.label) || qm.occ || 'chưa xác định') + '.'};
    }
    var allItems = [];
    if(catData && catData.items){
      allItems = catData.items;
    } else if(catData && catData.forms){
      Object.keys(catData.forms).forEach(function(k){
        var f = catData.forms[k];
        if(!f || f.co_thiet_ke_tu_dong === false) return; // B6 khong thiet ke - khong tinh vao trang thai
        allItems = allItems.concat(f.items || []);
      });
    }
    var status = 'ok';
    if(allItems.some(function(it){ return it.ket_luan === 'chua_dat'; })) status = 'bad';
    else if(allItems.some(function(it){ return it.ket_luan === 'chua_the_hien'; })) status = 'warn';
    return {status: status, note: (catData && catData.tong_ket) || (allItems.length + ' mục đối chiếu.')};
  }

  function buildAutoDetectPanel(){
    autoDetectPanel.innerHTML = '';

    var introP = document.createElement('p');
    introP.className = 'hint';
    introP.textContent = 'AI đọc 1 bản vẽ, TỰ nhận diện bản vẽ thuộc (các) hạng mục nào trong 5 hạng mục AI thật, rồi điền luôn kết quả cho từng hạng mục phát hiện được — bạn xem kỹ và có thể bỏ bớt hạng mục trước khi xác nhận trừ. Giới hạn riêng cho tính năng này: ảnh tối đa 7MB, PDF tối đa 22MB.';
    autoDetectPanel.appendChild(introP);

    var fileField = document.createElement('div');
    fileField.className = 'field';
    fileField.style.marginTop = '10px';
    var fileLabel = document.createElement('label');
    fileLabel.textContent = 'Chọn 1 file bản vẽ';
    fileField.appendChild(fileLabel);
    var fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'application/pdf,image/png,image/jpeg,image/webp';
    fileField.appendChild(fileInput);
    autoDetectPanel.appendChild(fileField);

    var errorP = document.createElement('p');
    errorP.className = 'multi-attach-error';
    errorP.hidden = true;
    autoDetectPanel.appendChild(errorP);

    var actions = document.createElement('div');
    actions.className = 'quymo-manual-actions';
    var analyzeBtn = document.createElement('button');
    analyzeBtn.type = 'button';
    analyzeBtn.className = 'btn-main';
    analyzeBtn.textContent = 'Phân tích tự động';
    analyzeBtn.disabled = true;
    actions.appendChild(analyzeBtn);
    var statusMsg = document.createElement('span');
    statusMsg.className = 'quymo-manual-msg';
    actions.appendChild(statusMsg);
    autoDetectPanel.appendChild(actions);

    var previewWrap = document.createElement('div');
    previewWrap.hidden = true;
    autoDetectPanel.appendChild(previewWrap);

    var resultWrap = document.createElement('div');
    autoDetectPanel.appendChild(resultWrap);

    fileInput.addEventListener('click', function(e){ e.stopPropagation(); });
    fileInput.addEventListener('change', function(){
      errorP.hidden = true;
      previewWrap.hidden = true;
      previewWrap.innerHTML = '';
      resultWrap.innerHTML = '';
      statusMsg.textContent = '';
      analyzeBtn.disabled = !fileInput.files[0];
    });

    function renderConfirmedResults(data){
      resultWrap.innerHTML = '';
      var sections = Object.keys(data.results).map(function(cat){
        return {label: (data.category_labels && data.category_labels[cat]) || cat, data: data.results[cat]};
      });
      var wrap = document.createElement('div');
      wrap.innerHTML = renderMdcReal(sections) + SECTION_DIVIDER + renderKienNghiReal(sections);
      resultWrap.appendChild(wrap);
    }

    function renderPreview(sessionId, respData){
      previewWrap.innerHTML = '';
      previewWrap.hidden = false;
      var detection = respData.detection;
      var detected = detection.detected_categories || [];

      if(!detected.length){
        var noneP = document.createElement('p');
        noneP.textContent = 'AI không phát hiện bản vẽ này thuộc hạng mục nào trong 5 hạng mục đã hỗ trợ (báo cháy, chữa cháy bằng nước, đèn sự cố/bình chữa cháy, điện PCCC, quy mô) — vẫn có thể đính riêng vào từng thẻ ở trên nếu bạn chắc chắn.';
        noneP.style.color = 'var(--ink-soft)';
        previewWrap.appendChild(noneP);
        return;
      }

      var listLabel = document.createElement('p');
      listLabel.className = 'hint';
      listLabel.textContent = 'AI phát hiện ' + detected.length + ' hạng mục — bỏ chọn nếu không muốn giữ hạng mục nào trước khi xác nhận:';
      previewWrap.appendChild(listLabel);

      var checklistWrap = document.createElement('div');
      checklistWrap.className = 'multi-attach-checklist';
      var checkboxes = [];
      detected.forEach(function(cat){
        var summary = summarizeMergedPreview(cat, detection[cat]);

        var row = document.createElement('label');
        row.className = 'multi-attach-item';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = true;
        cb.value = cat;
        row.appendChild(cb);
        var span = document.createElement('span');
        span.textContent = ((respData.category_labels && respData.category_labels[cat]) || cat) + ' — ';
        row.appendChild(span);
        var pill = document.createElement('span');
        pill.className = 'status-pill status-' + summary.status;
        pill.textContent = STATUS_LABEL[summary.status];
        row.appendChild(pill);
        checklistWrap.appendChild(row);

        var noteP = document.createElement('p');
        noteP.style.margin = '2px 0 10px 26px';
        noteP.style.color = 'var(--ink-soft)';
        noteP.textContent = summary.note;
        checklistWrap.appendChild(noteP);

        checkboxes.push(cb);
        cb.addEventListener('change', updateWarn);
      });
      previewWrap.appendChild(checklistWrap);

      var warnP = document.createElement('p');
      warnP.className = 'multi-attach-warning';
      previewWrap.appendChild(warnP);

      var confirmActions = document.createElement('div');
      confirmActions.className = 'quymo-manual-actions';
      var confirmBtn = document.createElement('button');
      confirmBtn.type = 'button';
      confirmBtn.className = 'btn-main';
      confirmBtn.textContent = 'Xác nhận';
      confirmActions.appendChild(confirmBtn);
      var confirmMsg = document.createElement('span');
      confirmMsg.className = 'quymo-manual-msg';
      confirmActions.appendChild(confirmMsg);
      previewWrap.appendChild(confirmActions);

      function updateWarn(){
        var selected = checkboxes.filter(function(cb){ return cb.checked; }).map(function(cb){ return cb.value; });
        var forms = selected.reduce(function(sum, cat){ return sum + MERGED_FORMS_PER_CALL[cat]; }, 0);
        warnP.textContent = selected.length
          ? 'Số Bộ hồ sơ bị trừ sẽ theo đúng số hạng mục AI thực sự phát hiện và điền — xác nhận sẽ dùng ' + forms + '/7 form trong Bộ hồ sơ hiện tại cho ' + selected.length + ' hạng mục đã chọn. Xem kỹ kết quả ở trên trước khi xác nhận.'
          : 'Chưa chọn hạng mục nào để xác nhận.';
        confirmBtn.disabled = !selected.length;
      }
      updateWarn();

      confirmBtn.addEventListener('click', function(){
        var selected = checkboxes.filter(function(cb){ return cb.checked; }).map(function(cb){ return cb.value; });
        if(!selected.length) return;
        confirmBtn.disabled = true;
        checkboxes.forEach(function(cb){ cb.disabled = true; });
        confirmMsg.textContent = 'Đang xác nhận…';
        confirmMsg.style.color = '';
        fetch(BACKEND_BASE + '/api/aiho/read-merged/confirm', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
          body: JSON.stringify({session_id: sessionId, detection: detection, selected_categories: selected})
        })
          .then(function(res){ return res.json().then(function(d){ return {status: res.status, data: d}; }); })
          .then(function(r3){
            if(r3.status >= 400){
              confirmBtn.disabled = false;
              checkboxes.forEach(function(cb){ cb.disabled = false; });
              confirmMsg.textContent = r3.data.error || 'Không xác nhận được — vui lòng thử lại.';
              confirmMsg.style.color = 'var(--red-deep)';
              return;
            }
            confirmMsg.textContent = '✓ Đã xác nhận — xem kết quả bên dưới.';
            confirmMsg.style.color = 'var(--green)';
            renderConfirmedResults(r3.data);
          })
          .catch(function(){
            confirmBtn.disabled = false;
            checkboxes.forEach(function(cb){ cb.disabled = false; });
            confirmMsg.textContent = 'Không kết nối được tới máy chủ — vui lòng thử lại.';
            confirmMsg.style.color = 'var(--red-deep)';
          });
      });
    }

    analyzeBtn.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var f = fileInput.files[0];
      if(!f) return;
      var sizeErr = validateMergedFileSize(f);
      if(sizeErr){
        errorP.textContent = sizeErr;
        errorP.hidden = false;
        return;
      }
      errorP.hidden = true;
      previewWrap.hidden = true;
      previewWrap.innerHTML = '';
      resultWrap.innerHTML = '';
      analyzeBtn.disabled = true;
      statusMsg.textContent = 'Đang phân tích — có thể mất vài phút…';
      statusMsg.style.color = '';

      ensureSessionOpen().then(function(r){
        if(r.status === 401){
          A.logout();
          analyzeBtn.disabled = false;
          statusMsg.textContent = r.data.error || 'Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại.';
          statusMsg.style.color = 'var(--red-deep)';
          window.openAuthModal();
          return;
        }
        if(r.status >= 400){
          analyzeBtn.disabled = false;
          statusMsg.textContent = r.data.error || 'Không mở được phiên Bộ hồ sơ — vui lòng thử lại.';
          statusMsg.style.color = 'var(--red-deep)';
          return;
        }
        var sessionId = r.data.session_id;
        var form = new FormData();
        form.append('file', f);
        form.append('session_id', sessionId);
        return fetch(BACKEND_BASE + '/api/aiho/read-merged', {
          method: 'POST',
          headers: {'Authorization': 'Bearer ' + getToken()},
          body: form
        })
          .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
          .then(function(r2){
            analyzeBtn.disabled = false;
            if(r2.status === 401){
              A.logout();
              statusMsg.textContent = r2.data.error || 'Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại.';
              statusMsg.style.color = 'var(--red-deep)';
              window.openAuthModal();
              return;
            }
            if(r2.status >= 400){
              statusMsg.textContent = r2.data.error || 'AI đọc bản vẽ báo lỗi — vui lòng thử lại.';
              statusMsg.style.color = 'var(--red-deep)';
              return;
            }
            statusMsg.textContent = '';
            renderPreview(sessionId, r2.data);
          });
      }).catch(function(){
        analyzeBtn.disabled = false;
        statusMsg.textContent = 'Không kết nối được tới máy chủ — vui lòng thử lại.';
        statusMsg.style.color = 'var(--red-deep)';
      });
    });
  }

  if(autoDetectToggle && autoDetectPanel){
    autoDetectToggle.addEventListener('click', function(){
      var willOpen = autoDetectPanel.hidden;
      if(willOpen && !autoDetectPanel.dataset.built){
        buildAutoDetectPanel();
        autoDetectPanel.dataset.built = '1';
      }
      autoDetectPanel.hidden = !willOpen;
      autoDetectToggle.textContent = willOpen ? 'Ẩn' : 'Đính 1 bản vẽ — AI tự nhận diện nhiều hạng mục';
    });
  }

  /* ===================================================================
     Dự án nhiều công trình (Đợt 2a) — khai báo + xem trước quy mô TỪNG
     công trình/khối trong 1 dự án (vd Xưởng A, Kho B, Kho C dùng CHUNG bộ
     bản vẽ theo hệ thống). LƯU Ý: "hạng mục" trong biến/route (hang-muc,
     hangMuc...) nghĩa là 1 CÔNG TRÌNH — KHÁC "hạng mục" ở khu Bước 1 phía
     trên (1 loại hệ thống PCCC) — UI dùng chữ "công trình" để không nhầm.
     Đợt 2a CHỈ dừng ở khai báo + xem trước "thuộc diện hệ thống gì" —
     CHƯA nối vào luồng đọc bản vẽ hiện có (đó là Đợt 2b, làm sau).
     KHÔNG gọi AI, KHÔNG trừ quota/Bộ hồ sơ — giống hệt luồng Quy mô nhập
     tay (quymo-manual) ở trên, tái dùng ĐÚNG ensureSessionOpen().
     =================================================================== */
  var hangMucToggle = document.getElementById('hangMucToggle');
  var hangMucPanel = document.getElementById('hangMucPanel');

  // Nhan he thong hien thi cho 12 id cua build_thuoc_dien_preview_items()
  // (7,9,16,18,27,30,42,45,49,55,57,60 - dung THU TU/Y NGHIA da co san trong
  // quy_mo_store._TYPE1_ROWS, chi la nhan hien thi phia frontend, KHONG doi
  // du lieu/ket_luan backend tra ve).
  var HANG_MUC_SYSTEM_LABEL = {
    7: 'Báo cháy tự động (đối với nhà)',
    9: 'Báo cháy tự động (đối với gian phòng)',
    16: 'Chữa cháy Sprinkler (đối với nhà)',
    18: 'Chữa cháy Sprinkler (đối với gian phòng)',
    27: 'Họng nước chữa cháy trong nhà',
    30: 'Cấp nước chữa cháy ngoài nhà',
    42: 'Đèn sự cố / chỉ dẫn thoát nạn',
    45: 'Loa thông báo, hướng dẫn thoát nạn',
    49: 'Bình chữa cháy xách tay',
    55: 'Dụng cụ phá dỡ thô sơ',
    57: 'Mặt nạ lọc độc/phòng độc cách ly',
    60: 'Phương tiện chữa cháy cơ giới'
  };

  var hangMucEditingId = null; // null = dang them moi; khac null = dang sua dung id nay
  var hangMucListWrap; // gan trong buildHangMucPanel()

  function hangMucQuyMoFromForm(occSelect, baseInputs, coBeSelect, extraInputs, extraDefs){
    var quyMo = {occ: occSelect.value};
    QUYMO_BASE_FIELDS.forEach(function(f){
      var v = baseInputs[f.key].value;
      if(v !== '') quyMo[f.key] = Number(v);
    });
    if(coBeSelect.value !== '') quyMo.coBeXangDauNgoaiTroi = (coBeSelect.value === 'true');
    Object.keys(extraInputs).forEach(function(key){
      var el = extraInputs[key];
      if(el.value === '') return;
      quyMo[key] = extraDefs[key].select ? el.value : Number(el.value);
    });
    return quyMo;
  }

  function renderHangMucList(items){
    hangMucListWrap.innerHTML = '';
    if(!items.length){
      var emptyP = document.createElement('p');
      emptyP.className = 'hint';
      emptyP.textContent = 'Chưa có công trình nào trong dự án này.';
      hangMucListWrap.appendChild(emptyP);
      return;
    }

    var tblWrap = document.createElement('div');
    tblWrap.className = 'tbl-wrap';
    var table = document.createElement('table');
    var thead = document.createElement('thead');
    thead.innerHTML = ''; // dung textContent tung o thay vi noi chuoi HTML
    var headRow = document.createElement('tr');
    ['Tên công trình', 'Quy mô chính', 'Thuộc diện bắt buộc trang bị', 'Thao tác'].forEach(function(h){
      var th = document.createElement('th');
      th.textContent = h;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    items.forEach(function(hm){
      var tr = document.createElement('tr');

      var tdTen = document.createElement('td');
      tdTen.textContent = hm.ten_hang_muc;
      tr.appendChild(tdTen);

      var tdQuyMo = document.createElement('td');
      var f = hm.fields || {};
      var occDef = (typeof OCCS !== 'undefined' ? OCCS : []).filter(function(o){ return o.id === f.occ; })[0];
      var quyMoParts = [(occDef && occDef.label) || f.occ || 'chưa xác định công năng'];
      if(f.totalArea != null) quyMoParts.push('ΣF ' + Number(f.totalArea).toLocaleString('vi-VN') + ' m²');
      if(f.volume != null) quyMoParts.push('V ' + Number(f.volume).toLocaleString('vi-VN') + ' m³');
      if(f.floors != null) quyMoParts.push(f.floors + ' tầng nổi' + (f.basements ? ' + ' + f.basements + ' tầng hầm' : ''));
      if(f.pplFloor != null) quyMoParts.push(f.pplFloor + ' người/tầng');
      tdQuyMo.textContent = quyMoParts.join(' · ');
      tr.appendChild(tdQuyMo);

      var tdThuocDien = document.createElement('td');
      var thuocDien = (hm.thuoc_dien_items || []).filter(function(it){ return it.ket_luan === 'dat'; });
      if(thuocDien.length){
        var ul = document.createElement('ul');
        ul.style.margin = '0';
        ul.style.paddingLeft = '18px';
        thuocDien.forEach(function(it){
          var li = document.createElement('li');
          li.textContent = HANG_MUC_SYSTEM_LABEL[it.id] || ('Mục #' + it.id);
          ul.appendChild(li);
        });
        tdThuocDien.appendChild(ul);
      } else {
        var noneSpan = document.createElement('span');
        noneSpan.className = 'hint';
        noneSpan.textContent = 'Chưa xác định được — cần thêm thông số quy mô.';
        tdThuocDien.appendChild(noneSpan);
      }
      tr.appendChild(tdThuocDien);

      var tdActions = document.createElement('td');
      var editBtn = document.createElement('button');
      editBtn.type = 'button';
      editBtn.className = 'btn-ghost';
      editBtn.style.padding = '6px 12px';
      editBtn.style.marginRight = '6px';
      editBtn.textContent = 'Sửa';
      editBtn.addEventListener('click', function(){ hangMucStartEdit(hm); });
      tdActions.appendChild(editBtn);

      var delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'btn-ghost';
      delBtn.style.padding = '6px 12px';
      delBtn.addEventListener('click', function(){ hangMucDelete(hm.hang_muc_id); });
      delBtn.textContent = 'Xoá';
      tdActions.appendChild(delBtn);

      tr.appendChild(tdActions);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tblWrap.appendChild(table);
    hangMucListWrap.appendChild(tblWrap);
  }

  function fetchHangMucList(){
    if(!activeSessionId){
      renderHangMucList([]);
      return Promise.resolve();
    }
    return fetch(BACKEND_BASE + '/api/aiho/hang-muc?session_id=' + activeSessionId, {
      headers: {'Authorization': 'Bearer ' + getToken()}
    })
      .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
      .then(function(r){
        if(r.status < 400) renderHangMucList(r.data.items || []);
      })
      .catch(function(){ /* im lang - danh sach giu nguyen, khong chan luong nhap */ });
  }

  var hangMucStartEdit; // gan trong buildHangMucPanel() (can truy cap form)
  var hangMucDelete;    // gan trong buildHangMucPanel()

  function buildHangMucPanel(){
    hangMucPanel.innerHTML = '';
    var occs = (typeof OCCS !== 'undefined') ? OCCS : [];
    var extraDefs = (typeof EXTRA_FIELDS !== 'undefined') ? EXTRA_FIELDS : {};

    var introP = document.createElement('p');
    introP.className = 'hint';
    introP.textContent = 'Dùng khi dự án có NHIỀU công trình/khối (vd Xưởng A, Kho B, Kho C) dùng chung 1 bộ bản vẽ theo hệ thống — khai báo quy mô riêng từng công trình để xem trước công trình nào thuộc diện bắt buộc trang bị hệ thống gì.';
    hangMucPanel.appendChild(introP);

    var noteP = document.createElement('p');
    noteP.className = 'hint';
    noteP.style.color = 'var(--amber)';
    noteP.style.marginTop = '6px';
    noteP.textContent = 'Danh sách này hiện dùng để xem trước — chưa liên kết với việc đọc bản vẽ (sẽ bổ sung ở bản cập nhật sau).';
    hangMucPanel.appendChild(noteP);

    var tenField = document.createElement('div');
    tenField.className = 'field';
    tenField.style.marginTop = '12px';
    var tenLabel = document.createElement('label');
    tenLabel.textContent = 'Tên công trình';
    tenField.appendChild(tenLabel);
    var tenInput = document.createElement('input');
    tenInput.type = 'text';
    tenInput.placeholder = 'VD: Xưởng A';
    tenField.appendChild(tenInput);
    hangMucPanel.appendChild(tenField);

    var occField = document.createElement('div');
    occField.className = 'field';
    occField.style.marginTop = '10px';
    var occLabel = document.createElement('label');
    occLabel.textContent = 'Công năng chính';
    occField.appendChild(occLabel);
    var occSelect = document.createElement('select');
    var optDefault = document.createElement('option');
    optDefault.value = '';
    optDefault.textContent = '— Chọn công năng —';
    occSelect.appendChild(optDefault);
    occs.forEach(function(o){
      var opt = document.createElement('option');
      opt.value = o.id;
      opt.textContent = o.label;
      occSelect.appendChild(opt);
    });
    occField.appendChild(occSelect);
    hangMucPanel.appendChild(occField);

    var baseGrid = document.createElement('div');
    baseGrid.className = 'grid';
    baseGrid.style.marginTop = '10px';
    var baseInputs = {};
    QUYMO_BASE_FIELDS.forEach(function(f){
      var field = document.createElement('div');
      field.className = 'field';
      var label = document.createElement('label');
      label.textContent = f.label;
      field.appendChild(label);
      var input = document.createElement('input');
      input.type = 'number';
      input.min = '0';
      input.step = 'any';
      input.placeholder = f.ph;
      field.appendChild(input);
      baseGrid.appendChild(field);
      baseInputs[f.key] = input;
    });
    hangMucPanel.appendChild(baseGrid);

    var coBeField = document.createElement('div');
    coBeField.className = 'field';
    coBeField.style.marginTop = '10px';
    var coBeLabel = document.createElement('label');
    coBeLabel.textContent = 'Có bể chứa xăng dầu/dung môi dễ cháy đặt ngoài trời không?';
    coBeField.appendChild(coBeLabel);
    var coBeSelect = document.createElement('select');
    [['', '— Chưa xác định —'], ['true', 'Có'], ['false', 'Không']].forEach(function(pair){
      var opt = document.createElement('option');
      opt.value = pair[0];
      opt.textContent = pair[1];
      coBeSelect.appendChild(opt);
    });
    coBeField.appendChild(coBeSelect);
    hangMucPanel.appendChild(coBeField);

    var extraWrap = document.createElement('div');
    extraWrap.className = 'grid';
    extraWrap.style.marginTop = '10px';
    hangMucPanel.appendChild(extraWrap);

    var extraInputs = {};
    function renderExtraFields(){
      extraWrap.innerHTML = '';
      extraInputs = {};
      var occDef = occs.filter(function(o){ return o.id === occSelect.value; })[0];
      var extraKeys = (occDef && occDef.extra) || [];
      extraKeys.forEach(function(key){
        var def = extraDefs[key];
        if(!def) return;
        var field = document.createElement('div');
        field.className = 'field';
        var label = document.createElement('label');
        label.textContent = def.label;
        field.appendChild(label);
        var el;
        if(def.select){
          el = document.createElement('select');
          def.select.forEach(function(pair){
            var opt = document.createElement('option');
            opt.value = pair[0];
            opt.textContent = pair[1];
            el.appendChild(opt);
          });
        } else {
          el = document.createElement('input');
          el.type = 'number';
          el.min = '0';
          el.step = 'any';
          el.placeholder = def.ph || '';
        }
        field.appendChild(el);
        extraWrap.appendChild(field);
        extraInputs[key] = el;
      });
    }
    occSelect.addEventListener('change', renderExtraFields);
    renderExtraFields();

    function resetForm(){
      hangMucEditingId = null;
      tenInput.value = '';
      occSelect.value = '';
      renderExtraFields();
      QUYMO_BASE_FIELDS.forEach(function(f){ baseInputs[f.key].value = ''; });
      coBeSelect.value = '';
      submitBtn.textContent = 'Thêm công trình vào dự án';
      cancelEditBtn.hidden = true;
    }

    function fillFormForEdit(hm){
      hangMucEditingId = hm.hang_muc_id;
      tenInput.value = hm.ten_hang_muc;
      var f = hm.fields || {};
      occSelect.value = f.occ || '';
      renderExtraFields();
      QUYMO_BASE_FIELDS.forEach(function(fld){
        var v = f[fld.key];
        baseInputs[fld.key].value = (v == null) ? '' : v;
      });
      coBeSelect.value = f.coBeXangDauNgoaiTroi === true ? 'true' : (f.coBeXangDauNgoaiTroi === false ? 'false' : '');
      Object.keys(extraInputs).forEach(function(key){
        var v = f[key];
        extraInputs[key].value = (v == null) ? '' : v;
      });
      submitBtn.textContent = 'Lưu thay đổi công trình';
      cancelEditBtn.hidden = false;
      feedbackMsg.textContent = 'Đang sửa "' + hm.ten_hang_muc + '" — bấm "Lưu thay đổi công trình" để lưu.';
      feedbackMsg.style.color = '';
      hangMucPanel.scrollIntoView({behavior: 'smooth', block: 'start'});
    }

    var actions = document.createElement('div');
    actions.className = 'quymo-manual-actions';
    actions.style.marginTop = '12px';

    var submitBtn = document.createElement('button');
    submitBtn.type = 'button';
    submitBtn.className = 'btn-main';
    submitBtn.textContent = 'Thêm công trình vào dự án';
    actions.appendChild(submitBtn);

    var cancelEditBtn = document.createElement('button');
    cancelEditBtn.type = 'button';
    cancelEditBtn.className = 'btn-ghost';
    cancelEditBtn.style.marginLeft = '8px';
    cancelEditBtn.textContent = 'Huỷ sửa';
    cancelEditBtn.hidden = true;
    cancelEditBtn.addEventListener('click', resetForm);
    actions.appendChild(cancelEditBtn);

    var feedbackMsg = document.createElement('span');
    feedbackMsg.className = 'quymo-manual-msg';
    actions.appendChild(feedbackMsg);

    hangMucPanel.appendChild(actions);

    submitBtn.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var ten = tenInput.value.trim();
      if(!ten){
        feedbackMsg.textContent = 'Vui lòng nhập tên công trình.';
        feedbackMsg.style.color = 'var(--red-deep)';
        return;
      }
      if(!occSelect.value){
        feedbackMsg.textContent = 'Vui lòng chọn công năng chính.';
        feedbackMsg.style.color = 'var(--red-deep)';
        return;
      }
      var quyMo = hangMucQuyMoFromForm(occSelect, baseInputs, coBeSelect, extraInputs, extraDefs);

      submitBtn.disabled = true;
      feedbackMsg.textContent = 'Đang lưu…';
      feedbackMsg.style.color = '';

      ensureSessionOpen().then(function(r){
        if(r.status >= 400){
          submitBtn.disabled = false;
          feedbackMsg.textContent = r.data.error || 'Không mở được phiên Bộ hồ sơ — vui lòng thử lại.';
          feedbackMsg.style.color = 'var(--red-deep)';
          return;
        }
        var isEdit = hangMucEditingId != null;
        var url = BACKEND_BASE + '/api/aiho/hang-muc' + (isEdit ? '/' + hangMucEditingId : '');
        return fetch(url, {
          method: isEdit ? 'PUT' : 'POST',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
          body: JSON.stringify({session_id: r.data.session_id, ten_hang_muc: ten, quy_mo: quyMo})
        })
          .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
          .then(function(r2){
            submitBtn.disabled = false;
            if(r2.status >= 400){
              feedbackMsg.textContent = r2.data.error || 'Không lưu được công trình — vui lòng thử lại.';
              feedbackMsg.style.color = 'var(--red-deep)';
              return;
            }
            feedbackMsg.textContent = isEdit ? '✓ Đã lưu thay đổi.' : '✓ Đã thêm công trình — tiếp tục nhập công trình tiếp theo nếu có.';
            feedbackMsg.style.color = 'var(--green)';
            resetForm();
            fetchHangMucList();
          });
      }).catch(function(){
        submitBtn.disabled = false;
        feedbackMsg.textContent = 'Không kết nối được tới máy chủ — vui lòng thử lại.';
        feedbackMsg.style.color = 'var(--red-deep)';
      });
    });

    var listHeading = document.createElement('h4');
    listHeading.style.marginTop = '18px';
    listHeading.textContent = 'Danh sách công trình trong dự án';
    hangMucPanel.appendChild(listHeading);

    hangMucListWrap = document.createElement('div');
    hangMucListWrap.style.marginTop = '8px';
    hangMucPanel.appendChild(hangMucListWrap);

    hangMucStartEdit = fillFormForEdit;
    hangMucDelete = function(hangMucId){
      if(!activeSessionId) return;
      fetch(BACKEND_BASE + '/api/aiho/hang-muc/' + hangMucId, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
        body: JSON.stringify({session_id: activeSessionId})
      })
        .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
        .then(function(r){
          if(r.status < 400){
            if(hangMucEditingId === hangMucId) resetForm();
            fetchHangMucList();
          }
        });
    };

    renderHangMucList([]);
    fetchHangMucList();
  }

  if(hangMucToggle && hangMucPanel){
    hangMucToggle.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var willOpen = hangMucPanel.hidden;
      if(willOpen && !hangMucPanel.dataset.built){
        buildHangMucPanel();
        hangMucPanel.dataset.built = '1';
      }
      if(willOpen) fetchHangMucList();
      hangMucPanel.hidden = !willOpen;
      hangMucToggle.textContent = willOpen ? 'Ẩn' : 'Dự án nhiều công trình — khai báo quy mô từng công trình';
    });
  }

  /* ===================================================================
     Form A gốc (A14/A15) — Phần 0: "Phạm vi đề nghị thẩm định lần này" +
     "Hạ tầng hiện hữu". Tính năng TUỲ CHỌN (không khai báo gì = mặc định
     TẤT CẢ hệ thống đều trong phạm vi, dự án xây mới hoàn toàn) — combiner
     Form A backend tự đọc dữ liệu này qua session_id, KHÔNG cần frontend
     gửi lại khi xuất Form A (xem Phần 3, nút "Xuất Form A gốc").
     =================================================================== */
  var phamViToggle = document.getElementById('phamViToggle');
  var phamViPanel = document.getElementById('phamViPanel');

  var HE_THONG_LABELS = {
    baochay: 'Báo cháy tự động',
    dienpccc: 'Điện phục vụ PCCC',
    tram_bom: 'Trạm bơm cấp nước chữa cháy',
    hong_nuoc: 'Họng nước chữa cháy trong nhà',
    chua_chay_tu_dong: 'Chữa cháy tự động (sprinkler)',
    giakehang: 'Chữa cháy tự động giá kệ hàng',
    botcodinh: 'Chữa cháy bằng bọt cố định',
    botchuachay: 'Chữa cháy bằng bột',
    khibotsolkhi: 'Chữa cháy bằng khí/sol-khí',
    densucco: 'Đèn sự cố / Loa thông báo',
    binhchuachay: 'Bình chữa cháy'
  };
  var HE_THONG_KEYS_ORDER = ['baochay', 'tram_bom', 'hong_nuoc', 'chua_chay_tu_dong', 'giakehang',
    'khibotsolkhi', 'botcodinh', 'botchuachay', 'densucco', 'binhchuachay', 'dienpccc'];

  var haTangListWrap;

  function renderHaTangList(items){
    haTangListWrap.innerHTML = '';
    if(!items.length){
      var emptyP = document.createElement('p');
      emptyP.className = 'hint';
      emptyP.textContent = 'Chưa khai báo hạ tầng hiện hữu nào.';
      haTangListWrap.appendChild(emptyP);
      return;
    }
    var tblWrap = document.createElement('div');
    tblWrap.className = 'tbl-wrap';
    var table = document.createElement('table');
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    ['Hệ thống', 'Số GCN / ngày', 'Số nghiệm thu / ngày', 'Thao tác'].forEach(function(h){
      var th = document.createElement('th');
      th.textContent = h;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = document.createElement('tbody');
    items.forEach(function(ht){
      var tr = document.createElement('tr');
      var tdHe = document.createElement('td');
      tdHe.textContent = HE_THONG_LABELS[ht.ten_he_thong] || ht.ten_he_thong;
      tr.appendChild(tdHe);
      var tdGcn = document.createElement('td');
      tdGcn.textContent = ht.gcn_so + ' — ' + ht.gcn_ngay + (ht.gcn_bo_sung_so ? ' (bổ sung: ' + ht.gcn_bo_sung_so + ' — ' + ht.gcn_bo_sung_ngay + ')' : '');
      tr.appendChild(tdGcn);
      var tdNt = document.createElement('td');
      tdNt.textContent = ht.nghiem_thu_so + ' — ' + ht.nghiem_thu_ngay;
      tr.appendChild(tdNt);
      var tdActions = document.createElement('td');
      var delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'btn-ghost';
      delBtn.style.padding = '6px 12px';
      delBtn.textContent = 'Xoá';
      delBtn.addEventListener('click', function(){
        fetch(BACKEND_BASE + '/api/aiho/ha-tang-hien-huu/' + ht.id, {
          method: 'DELETE',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
          body: JSON.stringify({session_id: activeSessionId})
        })
          .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
          .then(function(r){ if(r.status < 400) fetchHaTangList(); });
      });
      tdActions.appendChild(delBtn);
      tr.appendChild(tdActions);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tblWrap.appendChild(table);
    haTangListWrap.appendChild(tblWrap);
  }

  function fetchHaTangList(){
    if(!activeSessionId){ renderHaTangList([]); return Promise.resolve(); }
    return fetch(BACKEND_BASE + '/api/aiho/ha-tang-hien-huu?session_id=' + activeSessionId, {
      headers: {'Authorization': 'Bearer ' + getToken()}
    })
      .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
      .then(function(r){ if(r.status < 400) renderHaTangList(r.data.items || []); })
      .catch(function(){ /* im lang - danh sach giu nguyen */ });
  }

  function buildPhamViPanel(){
    phamViPanel.innerHTML = '';

    var introP = document.createElement('p');
    introP.className = 'hint';
    introP.textContent = 'Mặc định (không khai báo gì) — coi như dự án XÂY MỚI HOÀN TOÀN, mọi hệ thống đều trong phạm vi đề nghị thẩm định lần này. Chỉ cần khai nếu đây là hồ sơ CẢI TẠO MỘT PHẦN (một số hệ thống đã có hồ sơ thẩm duyệt/nghiệm thu từ trước, không xin lại lần này).';
    phamViPanel.appendChild(introP);

    var checklistWrap = document.createElement('div');
    checklistWrap.className = 'multi-attach-checklist';
    var checkboxes = {};
    HE_THONG_KEYS_ORDER.forEach(function(key){
      var row = document.createElement('label');
      row.style.display = 'flex';
      row.style.alignItems = 'center';
      row.style.gap = '8px';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = true;
      cb.dataset.heThong = key;
      row.appendChild(cb);
      var span = document.createElement('span');
      span.textContent = HE_THONG_LABELS[key] + ' — trong phạm vi đề nghị lần này';
      row.appendChild(span);
      checklistWrap.appendChild(row);
      checkboxes[key] = cb;
    });
    phamViPanel.appendChild(checklistWrap);

    var saveScopeBtn = document.createElement('button');
    saveScopeBtn.type = 'button';
    saveScopeBtn.className = 'btn-main';
    saveScopeBtn.style.marginTop = '10px';
    saveScopeBtn.textContent = 'Lưu phạm vi đề nghị';
    phamViPanel.appendChild(saveScopeBtn);

    var scopeMsg = document.createElement('span');
    scopeMsg.className = 'quymo-manual-msg';
    scopeMsg.style.marginLeft = '10px';
    phamViPanel.appendChild(scopeMsg);

    saveScopeBtn.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var checkedKeys = HE_THONG_KEYS_ORDER.filter(function(key){ return checkboxes[key].checked; });
      saveScopeBtn.disabled = true;
      scopeMsg.textContent = 'Đang lưu…';
      scopeMsg.style.color = '';
      ensureSessionOpen().then(function(r){
        if(r.status >= 400){
          saveScopeBtn.disabled = false;
          scopeMsg.textContent = r.data.error || 'Không mở được phiên Bộ hồ sơ.';
          scopeMsg.style.color = 'var(--red-deep)';
          return;
        }
        return fetch(BACKEND_BASE + '/api/aiho/pham-vi-de-nghi', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
          body: JSON.stringify({session_id: r.data.session_id, pham_vi_de_nghi: checkedKeys})
        })
          .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
          .then(function(r2){
            saveScopeBtn.disabled = false;
            if(r2.status >= 400){
              scopeMsg.textContent = r2.data.error || 'Không lưu được.';
              scopeMsg.style.color = 'var(--red-deep)';
              return;
            }
            scopeMsg.textContent = '✓ Đã lưu.';
            scopeMsg.style.color = 'var(--green)';
          });
      }).catch(function(){
        saveScopeBtn.disabled = false;
        scopeMsg.textContent = 'Không kết nối được tới máy chủ.';
        scopeMsg.style.color = 'var(--red-deep)';
      });
    });

    var haTangHeading = document.createElement('h4');
    haTangHeading.style.marginTop = '18px';
    haTangHeading.textContent = 'Khai báo hạ tầng hiện hữu (hệ thống ĐÃ bỏ check ở trên vì đã có hồ sơ thẩm duyệt/nghiệm thu từ trước, không xin lại lần này)';
    phamViPanel.appendChild(haTangHeading);

    var heSelectField = document.createElement('div');
    heSelectField.className = 'field';
    heSelectField.style.marginTop = '8px';
    var heSelectLabel = document.createElement('label');
    heSelectLabel.textContent = 'Hệ thống hiện hữu';
    heSelectField.appendChild(heSelectLabel);
    var heSelect = document.createElement('select');
    HE_THONG_KEYS_ORDER.forEach(function(key){
      var opt = document.createElement('option');
      opt.value = key;
      opt.textContent = HE_THONG_LABELS[key];
      heSelect.appendChild(opt);
    });
    heSelectField.appendChild(heSelect);
    phamViPanel.appendChild(heSelectField);

    var haTangGrid = document.createElement('div');
    haTangGrid.className = 'grid';
    haTangGrid.style.marginTop = '10px';
    var haTangInputs = {};
    [
      {key: 'gcn_so', label: 'Số Giấy chứng nhận thẩm duyệt', ph: 'VD: 621/TD-PCCC-P2'},
      {key: 'gcn_ngay', label: 'Ngày GCN thẩm duyệt', ph: 'VD: 12/05/2016'},
      {key: 'gcn_bo_sung_so', label: 'Số GCN cải tạo bổ sung (nếu có)', ph: ''},
      {key: 'gcn_bo_sung_ngay', label: 'Ngày GCN cải tạo bổ sung (nếu có)', ph: ''},
      {key: 'nghiem_thu_so', label: 'Số văn bản nghiệm thu', ph: 'VD: 273/CSPCCC-P2'},
      {key: 'nghiem_thu_ngay', label: 'Ngày văn bản nghiệm thu', ph: 'VD: 20/09/2016'}
    ].forEach(function(f){
      var field = document.createElement('div');
      field.className = 'field';
      var label = document.createElement('label');
      label.textContent = f.label;
      field.appendChild(label);
      var input = document.createElement('input');
      input.type = 'text';
      input.placeholder = f.ph;
      field.appendChild(input);
      haTangGrid.appendChild(field);
      haTangInputs[f.key] = input;
    });
    phamViPanel.appendChild(haTangGrid);

    var ghiChuField = document.createElement('div');
    ghiChuField.className = 'field';
    ghiChuField.style.marginTop = '10px';
    var ghiChuLabel = document.createElement('label');
    ghiChuLabel.textContent = 'Ghi chú trên bản vẽ (nếu có, vd "SỬ DỤNG CHUNG CỤM BƠM HIỆN HỮU")';
    ghiChuField.appendChild(ghiChuLabel);
    var ghiChuInput = document.createElement('input');
    ghiChuInput.type = 'text';
    ghiChuField.appendChild(ghiChuInput);
    phamViPanel.appendChild(ghiChuField);

    var addHaTangBtn = document.createElement('button');
    addHaTangBtn.type = 'button';
    addHaTangBtn.className = 'btn-main';
    addHaTangBtn.style.marginTop = '10px';
    addHaTangBtn.textContent = 'Thêm hạ tầng hiện hữu';
    phamViPanel.appendChild(addHaTangBtn);

    var haTangMsg = document.createElement('span');
    haTangMsg.className = 'quymo-manual-msg';
    haTangMsg.style.marginLeft = '10px';
    phamViPanel.appendChild(haTangMsg);

    addHaTangBtn.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      if(!haTangInputs.gcn_so.value.trim() || !haTangInputs.gcn_ngay.value.trim() ||
         !haTangInputs.nghiem_thu_so.value.trim() || !haTangInputs.nghiem_thu_ngay.value.trim()){
        haTangMsg.textContent = 'Vui lòng nhập đủ số/ngày GCN thẩm duyệt và số/ngày nghiệm thu.';
        haTangMsg.style.color = 'var(--red-deep)';
        return;
      }
      addHaTangBtn.disabled = true;
      haTangMsg.textContent = 'Đang lưu…';
      haTangMsg.style.color = '';
      ensureSessionOpen().then(function(r){
        if(r.status >= 400){
          addHaTangBtn.disabled = false;
          haTangMsg.textContent = r.data.error || 'Không mở được phiên Bộ hồ sơ.';
          haTangMsg.style.color = 'var(--red-deep)';
          return;
        }
        return fetch(BACKEND_BASE + '/api/aiho/ha-tang-hien-huu', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
          body: JSON.stringify({
            session_id: r.data.session_id,
            ten_he_thong: heSelect.value,
            gcn_so: haTangInputs.gcn_so.value.trim(),
            gcn_ngay: haTangInputs.gcn_ngay.value.trim(),
            gcn_bo_sung_so: haTangInputs.gcn_bo_sung_so.value.trim() || null,
            gcn_bo_sung_ngay: haTangInputs.gcn_bo_sung_ngay.value.trim() || null,
            nghiem_thu_so: haTangInputs.nghiem_thu_so.value.trim(),
            nghiem_thu_ngay: haTangInputs.nghiem_thu_ngay.value.trim(),
            ghi_chu_ban_ve: ghiChuInput.value.trim() || null
          })
        })
          .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
          .then(function(r2){
            addHaTangBtn.disabled = false;
            if(r2.status >= 400){
              haTangMsg.textContent = r2.data.error || 'Không lưu được.';
              haTangMsg.style.color = 'var(--red-deep)';
              return;
            }
            haTangMsg.textContent = '✓ Đã thêm.';
            haTangMsg.style.color = 'var(--green)';
            Object.keys(haTangInputs).forEach(function(k){ haTangInputs[k].value = ''; });
            ghiChuInput.value = '';
            fetchHaTangList();
          });
      }).catch(function(){
        addHaTangBtn.disabled = false;
        haTangMsg.textContent = 'Không kết nối được tới máy chủ.';
        haTangMsg.style.color = 'var(--red-deep)';
      });
    });

    var haTangListHeading = document.createElement('h4');
    haTangListHeading.style.marginTop = '18px';
    haTangListHeading.textContent = 'Danh sách hạ tầng hiện hữu đã khai báo';
    phamViPanel.appendChild(haTangListHeading);

    haTangListWrap = document.createElement('div');
    haTangListWrap.style.marginTop = '8px';
    phamViPanel.appendChild(haTangListWrap);

    renderHaTangList([]);
    fetchHaTangList();
  }

  if(phamViToggle && phamViPanel){
    phamViToggle.addEventListener('click', function(){
      if(!currentUser){ window.openAuthModal(); return; }
      var willOpen = phamViPanel.hidden;
      if(willOpen && !phamViPanel.dataset.built){
        buildPhamViPanel();
        phamViPanel.dataset.built = '1';
      }
      if(willOpen) fetchHaTangList();
      phamViPanel.hidden = !willOpen;
      phamViToggle.textContent = willOpen ? 'Ẩn' : 'Phạm vi đề nghị thẩm định lần này (chỉ cần khai nếu là hồ sơ cải tạo một phần)';
    });
  }

  grid.addEventListener('click', function(e){
    var card = e.target.closest('.drop-card');
    if(!card) return;
    if(REAL_CATEGORIES[card.dataset.slot]) return; // ô này có xử lý file thật riêng, xem bên trên
    var willFill = !card.classList.contains('filled');
    if(willFill && !currentUser){ window.openAuthModal(); return; }
    var filled = card.classList.toggle('filled');
    var status = card.querySelector('.drop-status');
    var body = card.querySelector('.drop-body');
    var existing = body.querySelector('.drop-file');
    if(filled){
      status.textContent = '● Đã đính kèm';
      status.classList.add('attached');
      if(!existing){
        body.appendChild(buildFileRow(card.dataset.file));
      }
    } else {
      status.textContent = '○ Chưa đính kèm';
      status.classList.remove('attached');
      if(existing) existing.remove();
    }
    updateCta();
    updateProgress();
  });

  var uploadProgress = document.getElementById('aihoProgress');
  var totalSlots = grid.querySelectorAll('.drop-card').length;
  function updateProgress(){
    var filledCount = grid.querySelectorAll('.drop-card.filled').length;
    uploadProgress.textContent = filledCount + '/' + totalSlots + ' hạng mục đã đính kèm';
  }
  updateProgress();

  var trigger = document.getElementById('aihoTrigger');
  var panel = document.getElementById('aihoPanel');
  trigger.addEventListener('click', function(){
    var open = panel.classList.toggle('open');
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('click', function(e){
    if(!e.target.closest('.output-picker')){
      panel.classList.remove('open');
      trigger.setAttribute('aria-expanded','false');
    }
  });

  var roundStepper = document.getElementById('aihoRoundStepper');
  var roundVal = document.getElementById('aihoRoundVal');
  var phieuCheck = document.getElementById('aihoPhieuCheck');
  var round = 1;
  phieuCheck.addEventListener('change', function(){
    roundStepper.hidden = !phieuCheck.checked;
    updateRoundLabel();
  });
  roundStepper.addEventListener('click', function(e){
    var btn = e.target.closest('button');
    if(!btn) return;
    e.preventDefault();
    e.stopPropagation();
    round = Math.max(1, round + Number(btn.dataset.dir));
    roundVal.textContent = round;
    updateRoundLabel();
    panel.dispatchEvent(new Event('change'));
  });
  function updateRoundLabel(){
    phieuCheck.dataset.label = 'Phiếu kiểm tra tổng hợp (đợt ' + round + ')';
  }
  updateRoundLabel();

  var chipRow = document.getElementById('aihoChipRow');
  var placeholder = document.getElementById('aihoPlaceholder');
  panel.addEventListener('change', function(){
    var checked = Array.prototype.slice.call(panel.querySelectorAll('input:checked'));
    chipRow.innerHTML = '';
    checked.forEach(function(input){
      var chip = document.createElement('span');
      chip.className = 'chip';
      chip.innerHTML = '<span>' + input.dataset.label + '</span><button type="button">✕</button>';
      chip.querySelector('button').addEventListener('click', function(){
        input.checked = false;
        panel.dispatchEvent(new Event('change'));
      });
      chipRow.appendChild(chip);
    });
    placeholder.textContent = checked.length
      ? checked.length + ' kết quả đã chọn'
      : 'Chọn kết quả cần xuất…';
    updateCta();
  });

  var cta = document.getElementById('aihoCta');
  var ctaHint = document.getElementById('aihoCtaHint');
  var msg = document.getElementById('aihoMsg');
  var feedbackCta = document.getElementById('aihoFeedbackCta');
  var feedbackConfirm = document.getElementById('aihoFeedbackConfirm');
  var isProcessing = false;
  function updateCta(){
    if(isProcessing){
      // Đang chạy phân tích — khoá cứng nút này, không cho bất kỳ thao tác đính/gỡ file
      // nào ở các ô khác (gọi updateCta gián tiếp) mở khoá lại giữa chừng.
      cta.disabled = true;
      ctaHint.textContent = 'Đang phân tích — vui lòng chờ xong lượt này…';
      return;
    }
    // activeSessionId co the da mo tu truoc (vd chi nhap tay Quy mo, chua dinh
    // file nao) - van cho bam "Bắt đầu phân tích" de dong phien do gon gang
    // (hoan lai Bo ho so vi khong dung AI that nao), khong de nguoi dung ket
    // ket voi 1 phien da mo ma khong co cach nao dong qua giao dien.
    var hasFile = !!grid.querySelector('.drop-card.filled') || !!activeSessionId;
    var hasOutput = !!panel.querySelector('input:checked');
    cta.disabled = !(hasFile && hasOutput);
    if(cta.disabled){
      ctaHint.textContent = 'Đính ít nhất 1 bản vẽ và chọn 1 kết quả đầu ra để bật nút này';
    } else if(!currentUser){
      ctaHint.textContent = 'Cần đăng nhập trước khi phân tích — bấm nút sẽ mở màn đăng nhập';
    } else {
      ctaHint.textContent = 'Sẵn sàng — còn ' + currentUser.bo_ho_so.con_lai + ' Bộ hồ sơ (mỗi Bộ hồ sơ tối đa 5 file bản vẽ, 7 form MĐC).';
    }
  }

  /* ---- Dữ liệu minh hoạ cho màn kết quả (demo, chưa phải phân tích thật) ----
     CHỈ cho các slot "Sắp có" (không có trong REAL_CATEGORIES) — renderResultTable()
     ưu tiên tuyệt đối REAL_CATEGORIES trước, các key trùng tên ở đây (nếu có) sẽ
     không bao giờ được đọc tới, nên không khai báo demo cho baochay/ccnuoc/dienpccc. */
  var SLOT_MOCK = {
    cckhi: {status:'bad', note:'Chưa thấy tính toán nồng độ thiết kế d₁, f₂ cho phòng điện — cần bổ sung.'},
    capnuocngoai: {status:'ok', note:'Trụ nước ngoài nhà bố trí đủ theo bán kính bảo vệ.'}
  };
  var STATUS_LABEL = {ok:'Đạt', warn:'Cần bổ sung', bad:'Thiếu sót'};

  function renderResultTable(){
    var filledCards = Array.prototype.slice.call(grid.querySelectorAll('.drop-card.filled'));
    var container = document.getElementById('aihoResultTable');
    container.innerHTML = '';
    // mock.note co the la van ban AI sinh ra (data.tong_ket hoac loi co doan
    // trich tu phan hoi AI) - dung textContent, khong noi chuoi vao innerHTML.
    filledCards.forEach(function(card){
      var slot = card.dataset.slot;
      var label = card.querySelector('h4').childNodes[0].textContent.trim();
      // Hang la "AI thật" (co trong REAL_CATEGORIES) TUYET DOI khong duoc roi
      // vao noi dung demo (SLOT_MOCK) trong bat ky truong hop nao - tach han 2
      // nhanh thay vi 1 ternary dung chung 1 fallback, de du realResults[slot]
      // vi ly do gi do chua duoc ghi nhan thi hien ro "chua co ket qua that",
      // khong bao gio ngam lay tam du lieu minh hoa cua cac o "Sắp có".
      var mock;
      if(REAL_CATEGORIES[slot]){
        mock = realResults[slot] || {status: 'warn', note: 'Chưa có kết quả phân tích thật cho hạng mục này.'};
      } else {
        mock = SLOT_MOCK[slot] || {status: 'ok', note: 'Chưa phát hiện thiếu sót.'};
      }

      var row = document.createElement('div');
      row.className = 'result-row';

      var labelSpan = document.createElement('span');
      labelSpan.className = 'r-label';
      labelSpan.textContent = label;
      row.appendChild(labelSpan);

      var pill = document.createElement('span');
      pill.className = 'status-pill status-' + mock.status;
      pill.textContent = STATUS_LABEL[mock.status];
      row.appendChild(pill);

      var note = document.createElement('span');
      note.className = 'r-note';
      note.textContent = mock.note;
      row.appendChild(note);

      container.appendChild(row);
    });
  }

  var KIEN_NGHI_NHOM = [
    {key: 'I_chua_the_hien', label: 'I. Nội dung chưa thể hiện'},
    {key: 'II_chua_thong_nhat', label: 'II. Nội dung chưa thống nhất'},
    {key: 'III_chua_phu_hop', label: 'III. Nội dung chưa phù hợp QCVN, TCVN'},
    {key: 'IV_de_xuat_bo_sung', label: 'IV. Đề xuất bổ sung hồ sơ'}
  ];
  var SECTION_DIVIDER = '<hr style="margin:18px 0;border:none;border-top:1px solid var(--line)">';

  function collectRealSections(predicate){
    var sections = [];
    Object.keys(REAL_CATEGORIES).forEach(function(slot){
      var d = realData[slot];
      if(d && predicate(d)) sections.push({label: REAL_CATEGORIES[slot].label, data: d});
    });
    return sections;
  }

  function collectFailedRealSlots(){
    // Hạng mục AI thật đã thử phân tích (có gắn file) nhưng lỗi/hết lượt — không có dữ liệu thật (realData rỗng)
    // nhưng có ghi nhận lỗi (realResults) — phải báo rõ, không được lặng lẽ rơi về nội dung minh hoạ không liên quan.
    var failed = [];
    Object.keys(REAL_CATEGORIES).forEach(function(slot){
      if(!realData[slot] && realResults[slot] && realFiles[slot] && realFiles[slot].length){
        failed.push({label: REAL_CATEGORIES[slot].label, note: realResults[slot].note});
      }
    });
    return failed;
  }

  // Dung createElement/.textContent de dung noi dung AI sinh ra (khong dang tin
  // cay) an toan, roi doc lai .innerHTML de co chuoi HTML da duoc escape dung -
  // giu nguyen kien truc noi chuoi hien co cua outputPreviewHtml()/SECTION_DIVIDER
  // ma van chan duoc XSS o dung diem nguy hiem (danh sach kien nghi AI sinh ra).
  function renderKienNghiReal(sections){
    return sections.map(function(sec){
      var wrapper = document.createElement('div');
      var h4 = document.createElement('h4');
      h4.textContent = 'Danh sách kiến nghị (theo văn phong PC07) — ' + sec.label;
      wrapper.appendChild(h4);
      KIEN_NGHI_NHOM.forEach(function(nhom){
        var items = sec.data.kien_nghi[nhom.key] || [];
        var p = document.createElement('p');
        p.style.marginTop = '10px';
        var b = document.createElement('b');
        b.textContent = nhom.label;
        p.appendChild(b);
        wrapper.appendChild(p);
        if(items.length){
          var ol = document.createElement('ol');
          items.forEach(function(c){
            var li = document.createElement('li');
            li.textContent = c;
            ol.appendChild(li);
          });
          wrapper.appendChild(ol);
        } else {
          var empty = document.createElement('p');
          empty.style.color = 'var(--ink-soft)';
          empty.textContent = '(Không có)';
          wrapper.appendChild(empty);
        }
      });
      return wrapper.innerHTML;
    }).join(SECTION_DIVIDER);
  }

  function itemsForMdcFile(d, fileEntry){
    // ccnuoc gom nhiều mẫu (d.forms[loai].items); báo cháy/điện chỉ 1 mẫu (d.items).
    if(d.forms && d.forms[fileEntry.loai]) return d.forms[fileEntry.loai].items || [];
    return d.items || [];
  }

  function renderMdcReal(sections){
    return sections.map(function(sec){
      var d = sec.data;
      var wrapper = document.createElement('div');
      var h4 = document.createElement('h4');
      h4.textContent = 'Mẫu đối chiếu (MĐC) đã điền — ' + sec.label;
      wrapper.appendChild(h4);
      (d.mdc_docx_files || []).forEach(function(f){
        var fileDiv = document.createElement('div');
        fileDiv.style.marginTop = '12px';
        if(f.base64){
          var items = itemsForMdcFile(d, f);
          // "khong_ap_dung" (vd nhanh khong duoc AI chon o B7/B15/B16) khong
          // phai la 1 muc "can kien nghi" - tach rieng khoi knCount, khac voi
          // truoc day gop chung vao KN (dung sai voi cac form co nhieu id
          // khong_ap_dung nhu B15/B16 - xem mdc_filler._KET_LUAN_TO_DOCX cho
          // dung 3 nhom nay o phia backend).
          var naCount = items.filter(function(it){ return it.ket_luan === 'khong_ap_dung'; }).length;
          var knCount = items.filter(function(it){ return it.ket_luan !== 'dat' && it.ket_luan !== 'khong_ap_dung'; }).length;
          var datCount = items.length - knCount - naCount;
          var dataUrl = 'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,' + f.base64;

          var p = document.createElement('p');
          var b = document.createElement('b');
          b.textContent = f.label;
          p.appendChild(b);
          var summaryText = ' — đã điền ' + items.length + ' mục đối chiếu: ' + datCount + ' Đạt, ' + knCount + ' cần kiến nghị (KN)' + (naCount ? ', ' + naCount + ' không áp dụng' : '') + '.';
          p.appendChild(document.createTextNode(summaryText));
          fileDiv.appendChild(p);

          if(knCount === 0){
            var warnP = document.createElement('p');
            warnP.className = 'multi-attach-warning';
            warnP.textContent = 'Lưu ý: form này có 0 dòng cần kiến nghị (KN) — nên rà lại kỹ trước khi dùng, có khả năng đã bỏ sót nội dung trên bản vẽ.';
            fileDiv.appendChild(warnP);
          }

          var a = document.createElement('a');
          a.className = 'btn-main';
          a.style.display = 'inline-block';
          a.style.textDecoration = 'none';
          a.style.textAlign = 'center';
          a.download = f.filename;
          a.href = dataUrl;
          a.textContent = 'Tải file MĐC (.docx)';
          fileDiv.appendChild(a);
        } else {
          var p2 = document.createElement('p');
          var b2 = document.createElement('b');
          b2.textContent = f.label;
          p2.appendChild(b2);
          fileDiv.appendChild(p2);

          var errP = document.createElement('p');
          errP.style.color = 'var(--red-deep)';
          errP.textContent = f.error;
          fileDiv.appendChild(errP);
        }
        wrapper.appendChild(fileDiv);
      });
      return wrapper.innerHTML;
    }).join(SECTION_DIVIDER);
  }

  // Dung chung cho 2 nhanh "khong co du lieu that" cua outputPreviewHtml() -
  // f.note co the chua doan trich loi tu AI (khong dang tin cay), f.label la
  // nhan hang muc co dinh (an toan) nhung van di qua textContent cho dong bo.
  function buildFailedNoteHtml(heading, note){
    var wrapper = document.createElement('div');
    var h4 = document.createElement('h4');
    h4.textContent = heading;
    wrapper.appendChild(h4);
    var p = document.createElement('p');
    p.style.color = 'var(--red-deep)';
    p.textContent = note;
    wrapper.appendChild(p);
    return wrapper.innerHTML;
  }

  function outputPreviewHtml(key){
    switch(key){
      case 'mdc':
        var mdcSections = collectRealSections(function(d){ return d.mdc_docx_files && d.mdc_docx_files.length; });
        var mdcFailed = collectFailedRealSlots();
        if(mdcSections.length || mdcFailed.length){
          var mdcParts = [];
          if(mdcSections.length) mdcParts.push(renderMdcReal(mdcSections));
          mdcFailed.forEach(function(f){
            mdcParts.push(buildFailedNoteHtml('Mẫu đối chiếu (MĐC) đã điền — ' + f.label, f.note));
          });
          return mdcParts.join(SECTION_DIVIDER);
        }
        return '<h4>Mẫu đối chiếu (MĐC) đã điền — trích đoạn</h4>' +
          '<div class="tbl-wrap"><table><thead><tr><th>Mẫu</th><th>Kết luận</th><th>Ghi chú</th></tr></thead><tbody>' +
          '<tr><td>MĐC B1–B2 · Báo cháy tự động</td><td><span class="badge b-warn">Cần bổ sung</span></td><td>Bổ sung loại trung tâm, số zone</td></tr>' +
          '<tr><td>MĐC B3–B4 · Chữa cháy bằng nước</td><td><span class="badge b-no">Đạt</span></td><td>—</td></tr>' +
          '<tr><td>MĐC B5 · Chữa cháy bằng khí</td><td><span class="badge b-yes">Thiếu sót</span></td><td>Bổ sung tính toán d₁, f₂</td></tr>' +
          '</tbody></table></div>';
      case 'loi':
        var kienNghiSections = collectRealSections(function(d){ return !!d.kien_nghi; });
        var loiFailed = collectFailedRealSlots();
        // Phan E — canh bao quy mo (mau thuan/thieu ho so) cung phai kich hoat
        // hop #aihoKienNghiDocxBox du KHONG hang muc rieng le nao co kien_nghi
        // (vd moi hang muc deu "dat" nhung van thieu 1 he thong thuoc dien) -
        // khong thi maybeExportKienNghiDocx() se khong tim thay box de xuat file.
        var hasQuyMoWarnings = (quyMoConflictWarningsPending.length + quyMoMissingWarningsPending.length) > 0;
        if(kienNghiSections.length || loiFailed.length || hasQuyMoWarnings){
          var loiParts = [];
          if(kienNghiSections.length || hasQuyMoWarnings){
            if(kienNghiSections.length) loiParts.push(renderKienNghiReal(kienNghiSections));
            loiParts.push('<div id="aihoKienNghiDocxBox"><p>Đang tạo file kiến nghị thiết kế (.docx) tổng hợp…</p></div>');
          }
          loiFailed.forEach(function(f){
            loiParts.push(buildFailedNoteHtml('Danh sách kiến nghị (theo văn phong PC07) — ' + f.label, f.note));
          });
          return loiParts.join(SECTION_DIVIDER);
        }
        return '<h4>Danh sách lỗi / thiếu sót — trích đoạn</h4>' +
          '<ul>' +
          '<li>Thiếu loại trung tâm báo cháy và số zone (Báo cháy tự động).</li>' +
          '<li>Chưa có tính toán nồng độ thiết kế d₁, f₂ (Chữa cháy bằng khí).</li>' +
          '<li>Đèn chỉ dẫn thoát nạn bố trí cách nhau quá 20 m (Đèn sự cố).</li>' +
          '</ul>';
      case 'khoiluong':
        return '<h4>Bảng tổng hợp khối lượng thiết bị — trích đoạn</h4>' +
          '<div class="tbl-wrap"><table><thead><tr><th>Thiết bị</th><th>Số lượng</th></tr></thead><tbody>' +
          '<tr><td>Đầu báo khói</td><td>86 cái</td></tr>' +
          '<tr><td>Đầu phun sprinkler</td><td>142 cái</td></tr>' +
          '<tr><td>Bình chữa cháy xách tay</td><td>24 bình</td></tr>' +
          '</tbody></table></div>';
      case 'phieutonghop':
        return '<h4>Phiếu kiểm tra tổng hợp (đợt ' + round + ') — trích đoạn</h4>' +
          '<div class="kv-grid">' +
          '<div><b>Công trình / chủ đầu tư</b>Văn phòng hỗn hợp ABC</div>' +
          '<div><b>Quy mô / công năng</b>8 tầng nổi + 1 hầm, hỗn hợp</div>' +
          '<div><b>Báo cháy</b>Đang thiết kế trung tâm báo cháy loại… (chưa rõ số zone) — cần bổ sung</div>' +
          '<div><b>Chữa cháy nước</b>Họng nước + sprinkler — đạt</div>' +
          '</div>';
      default:
        return '';
    }
  }

  function renderOutputPreviews(){
    var checked = Array.prototype.slice.call(panel.querySelectorAll('input:checked'));
    document.getElementById('aihoOutputPreviews').innerHTML = checked.map(function(input){
      return '<div class="preview-card">' + outputPreviewHtml(input.dataset.key) + '</div>';
    }).join('');
  }

  // Goi sau renderOutputPreviews() - neu case 'loi' vua duoc render va co it nhat
  // 1 hang muc AI that co kien_nghi, gom lai va goi route moi (khong goi AI, chi
  // dung docx) de hien nut tai giong renderMdcReal thay vi chi hien HTML tinh.
  function maybeExportKienNghiDocx(){
    var box = document.getElementById('aihoKienNghiDocxBox');
    if(!box) return;
    var hangMuc = [];
    Object.keys(REAL_CATEGORIES).forEach(function(slot){
      var d = realData[slot];
      if(d && d.kien_nghi){
        hangMuc.push({
          ten_he_thong: REAL_CATEGORIES[slot].label,
          so_hieu_ban_ve: d.so_hieu_ban_ve || 'Không xác định được số hiệu bản vẽ',
          kien_nghi: d.kien_nghi
        });
      }
    });

    // Phan D.1/E.3 — 1 hang muc TONG HOP rieng cho canh bao quy mo (mau
    // thuan Luot 0 -> nhom II, thieu ho so theo doi chieu nguoc -> nhom IV),
    // KHONG gan voi 1 ban ve cu the nao nen dung dung ten trung lap voi cac
    // hang muc that o tren.
    if(quyMoConflictWarningsPending.length || quyMoMissingWarningsPending.length){
      hangMuc.push({
        ten_he_thong: 'Đối chiếu tổng thể theo quy mô công trình',
        so_hieu_ban_ve: 'Không xác định được số hiệu bản vẽ',
        kien_nghi: {
          I_chua_the_hien: [],
          II_chua_thong_nhat: quyMoConflictWarningsPending.map(quyMoConflictWarningText),
          III_chua_phu_hop: [],
          IV_de_xuat_bo_sung: quyMoMissingWarningsPending.map(quyMoMissingWarningText)
        }
      });
    }

    if(!hangMuc.length) return;

    function showError(text){
      box.innerHTML = '';
      var errP = document.createElement('p');
      errP.style.color = 'var(--red-deep)';
      errP.textContent = text;
      box.appendChild(errP);
    }

    fetch(BACKEND_BASE + '/api/aiho/export-kien-nghi', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
      body: JSON.stringify({hang_muc: hangMuc})
    })
      .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
      .then(function(r){
        if(r.status >= 400){
          showError(r.data.error || 'Không tạo được file kiến nghị tổng hợp — vui lòng thử lại sau.');
          return;
        }
        box.innerHTML = '';
        var a = document.createElement('a');
        a.className = 'btn-main';
        a.style.display = 'inline-block';
        a.style.textDecoration = 'none';
        a.style.textAlign = 'center';
        a.download = r.data.filename;
        a.href = 'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,' + r.data.base64;
        a.textContent = 'Tải file kiến nghị thiết kế (.docx)';
        box.appendChild(a);
      })
      .catch(function(){
        showError('Không kết nối được tới máy chủ — chưa tạo được file kiến nghị tổng hợp.');
      });
  }

  /* ===================================================================
     Form A gốc (A14/A15) — Phần 3: nút "Xuất Form A gốc". CHỈ hiện khi
     công năng (occ) đã khai ở Quy mô khớp "sanxuat" (→A14) hoặc "kho"
     (→A15) — tra đúng giá trị occ thật trong OCCS (js/tuvan-so-bo.js).
     Gom realData/realResults của mọi hạng mục ĐÃ đọc thành b_form_results
     theo ĐÚNG khoá loai của mdc_filler.TEMPLATE_PATHS (KHÔNG phải khoá
     slot REAL_CATEGORIES — 2 hạng mục ccnuoc/densucco gộp nhiều form con,
     phải tách phẳng ra đây) — backend tự lấy quy_mo/pham_vi/ha_tang_hien_huu
     theo session_id, KHÔNG cần gửi lại.
     =================================================================== */
  function buildBFormResults(){
    var out = {};
    if(realData.baochay){
      var loaiBaoChay = realData.baochay.loai_he_thong === 'dia_chi' ? 'dia_chi' : 'thuong';
      out[loaiBaoChay] = {items: realData.baochay.items || []};
    }
    if(realData.ccnuoc && realData.ccnuoc.forms){
      Object.keys(realData.ccnuoc.forms).forEach(function(k){
        out[k] = {items: realData.ccnuoc.forms[k].items || []};
      });
    }
    if(realData.densucco && realData.densucco.forms){
      Object.keys(realData.densucco.forms).forEach(function(k){
        out[k] = {items: realData.densucco.forms[k].items || []};
      });
    }
    if(realData.khibot && realData.khibot.he_thong){
      out[realData.khibot.he_thong] = {items: realData.khibot.items || []};
    }
    if(realData.botcodinh) out.bot_co_dinh = {items: realData.botcodinh.items || []};
    if(realData.giakehang) out.chua_chay_gia_ke_hang = {items: realData.giakehang.items || []};
    if(realData.botchuachay) out.bot_chua_chay = {items: realData.botchuachay.items || []};
    if(realData.dienpccc) out.dien_pccc = {items: realData.dienpccc.items || []};
    return out;
  }

  function maybeShowFormAButton(sessionId){
    var box = document.getElementById('aihoFormABox');
    if(!box) return;
    box.hidden = true;
    box.innerHTML = '';

    var loaiHinh = quyMoOccInSession === 'sanxuat' ? 'A14' : (quyMoOccInSession === 'kho' ? 'A15' : null);
    if(!loaiHinh) return;

    box.hidden = false;
    var nhanLoaiHinh = loaiHinh === 'A14' ? 'Nhà sản xuất' : 'Nhà kho';

    var introP = document.createElement('p');
    introP.className = 'hint';
    introP.textContent = 'Công năng công trình khớp loại hình "' + nhanLoaiHinh + '" — có thể xuất Form A gốc chính thức (' + loaiHinh + ') gộp từ dữ liệu quy mô + các hạng mục đã đọc trong Bộ hồ sơ này.';
    box.appendChild(introP);

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn-main';
    btn.style.marginTop = '8px';
    btn.textContent = 'Xuất Form A gốc (' + loaiHinh + ')';
    box.appendChild(btn);

    var msg = document.createElement('span');
    msg.className = 'quymo-manual-msg';
    msg.style.marginLeft = '10px';
    box.appendChild(msg);

    btn.addEventListener('click', function(){
      btn.disabled = true;
      msg.textContent = 'Đang tạo file…';
      msg.style.color = '';
      fetch(BACKEND_BASE + '/api/aiho/export-form-a', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
        body: JSON.stringify({session_id: sessionId, loai_hinh: loaiHinh, b_form_results: buildBFormResults()})
      })
        .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
        .then(function(r){
          btn.disabled = false;
          if(r.status >= 400){
            msg.textContent = r.data.error || 'Không tạo được file Form A — vui lòng thử lại sau.';
            msg.style.color = 'var(--red-deep)';
            return;
          }
          msg.textContent = '';
          var a = document.createElement('a');
          a.className = 'btn-ghost';
          a.style.display = 'inline-block';
          a.style.marginLeft = '10px';
          a.style.textDecoration = 'none';
          a.download = r.data.filename;
          a.href = 'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,' + r.data.base64;
          a.textContent = 'Tải file Form A (.docx)';
          box.appendChild(a);
        })
        .catch(function(){
          btn.disabled = false;
          msg.textContent = 'Không kết nối được tới máy chủ.';
          msg.style.color = 'var(--red-deep)';
        });
    });
  }

  var processing = document.getElementById('aihoProcessing');
  var processingFill = document.getElementById('aihoProcessingFill');
  var processingText = document.getElementById('aihoProcessingText');
  var resultsSection = document.getElementById('aihoResults');

  /* ---- Khoá/mở khu vực chọn kết quả đầu ra trong lúc đang phân tích ---- */
  function setOutputPickerLocked(locked){
    if(locked){
      panel.classList.remove('open');
      trigger.setAttribute('aria-expanded', 'false');
    }
    trigger.disabled = locked;
    Array.prototype.forEach.call(panel.querySelectorAll('input'), function(input){ input.disabled = locked; });
    Array.prototype.forEach.call(roundStepper.querySelectorAll('button'), function(btn){ btn.disabled = locked; });
  }

  function fmtElapsed(sec){
    if(sec < 60) return sec + ' giây';
    var m = Math.floor(sec / 60), s = sec % 60;
    return m + ' phút' + (s ? ' ' + s + ' giây' : '');
  }

  // Batch 5A sub-buoc 2: 1 lan bam "Bắt đầu phân tích" = 1 phien Bo ho so (tru
  // ngay 1 Bo ho so luc mo, giu hoac hoan luc dong tuy co lan doc nao thanh
  // cong hay khong) - mo phien TRUOC khi ban cac fetch hang muc song song,
  // dong phien NGAY SAU khi tat ca da settle (trong finishUp()).
  function abortProcessing(errorText){
    processing.hidden = true;
    isProcessing = false;
    setOutputPickerLocked(false);
    updateCta();
    msg.textContent = errorText;
    msg.classList.add('show');
  }

  function runAnalysis(sessionId){
    var activeSlots = Object.keys(REAL_CATEGORIES).filter(function(slot){ return realFiles[slot] && realFiles[slot].length > 0; });
    activeSlots.forEach(function(slot){ realResults[slot] = null; realData[slot] = null; });

    var interval;

    if(activeSlots.length){
      // Ước lượng theo hạng mục chậm nhất đang chạy (chạy song song, không cộng dồn thời gian).
      var estimatedSec = Math.max.apply(null, activeSlots.map(function(slot){ return REAL_CATEGORIES[slot].estimatedSeconds; }));
      // Tran toi da hien thi cho nguoi dung yen tam - khop dung gunicorn
      // --timeout 900 ben server (xem render.yaml), khong dung de tinh % thanh
      // tien trinh (van tinh theo estimatedSec nhu cu).
      var MAX_WAIT_SEC = 900;
      var startedAt = Date.now();
      function updateRealProgress(){
        var elapsedSec = Math.floor((Date.now() - startedAt) / 1000);
        var percent = Math.min(92, 5 + (elapsedSec / estimatedSec) * 87);
        processingFill.style.width = percent + '%';
        processingText.textContent = 'Đang đọc bản vẽ và đối chiếu — đã chờ ' + fmtElapsed(elapsedSec) + ' (dự kiến khoảng ' + fmtElapsed(estimatedSec) + ', tối đa ' + fmtElapsed(MAX_WAIT_SEC) + ')…';
      }
      updateRealProgress();
      interval = setInterval(updateRealProgress, 1000);
    } else {
      // Không có hạng mục AI thật nào được đính — chỉ mô phỏng nhanh cho mục đích xem giao diện.
      var steps = ['Đang đọc bản vẽ đã đính kèm…', 'Đang đối chiếu với mẫu MĐC B1–B14…', 'Đang tổng hợp kết quả đầu ra…'];
      var i = 0;
      processingText.textContent = steps[0];
      processingFill.style.width = '8%';
      interval = setInterval(function(){
        i++;
        if(i < steps.length){
          processingText.textContent = steps[i];
          processingFill.style.width = (8 + i * 42) + '%';
        }
      }, 700);
    }

    function closeSessionIfAny(){
      if(!sessionId) return Promise.resolve();
      return fetch(BACKEND_BASE + '/api/aiho/session/close', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
        body: JSON.stringify({session_id: sessionId})
      })
        .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
        .then(function(r){
          if(r.data && r.data.bo_ho_so_con_lai !== undefined) updateBoHoSoDisplay({con_lai: r.data.bo_ho_so_con_lai});
          if(activeSessionId === sessionId) activeSessionId = null;
        })
        .catch(function(){ /* dong phien la best-effort - khong chan hien ket qua neu loi mang luc dong */ });
    }

    function finishUp(){
      clearInterval(interval);
      processingFill.style.width = '100%';
      // Phan E — PHAI doi chieu nguoc TRUOC khi dong phien: route
      // /quymo-reverse-check doi hoi phien dang 'open' (ho_so_session.
      // get_open_session_for_user) - goi SAU closeSessionIfAny() se luon
      // that bai vi phien da chuyen 'closed_used'/'closed_refunded'.
      fetchQuyMoReverseCheck(activeSlots, sessionId).then(function(){
        return closeSessionIfAny();
      }).then(function(){
        setTimeout(function(){
          processing.hidden = true;
          processingFill.style.width = '0%';
          isProcessing = false;
          setOutputPickerLocked(false);
          renderResultTable();
          renderOutputPreviews();
          renderQuyMoWarningsBox();
          maybeExportKienNghiDocx();
          maybeShowFormAButton(sessionId);
          resultsSection.hidden = false;
          resultsSection.scrollIntoView({behavior: 'smooth', block: 'start'});
          updateCta();
        }, 300);
      });
    }

    function fireLuot1(){
      if(activeSlots.length){
        var checkedKeys = Array.prototype.map.call(panel.querySelectorAll('input:checked'), function(input){ return input.dataset.key; });
        var outputsValue = checkedKeys.join(',');
        var pending = activeSlots.length;
        var sawAuthError = false;

        activeSlots.forEach(function(slot){
          var cfg = REAL_CATEGORIES[slot];
          var form = new FormData();
          (realFiles[slot] || []).forEach(function(f){ form.append('files', f); });
          form.append('outputs', outputsValue);
          form.append('session_id', sessionId);
          fetch(BACKEND_BASE + cfg.endpoint, {
            method: 'POST',
            headers: {'Authorization': 'Bearer ' + getToken()},
            body: form
          })
            .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
            .then(function(r){
              if(r.status === 401){
                if(sawAuthError) return;
                sawAuthError = true;
                A.logout();
                clearInterval(interval);
                processing.hidden = true;
                isProcessing = false;
                setOutputPickerLocked(false);
                updateCta();
                msg.textContent = r.data.error || 'Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại.';
                msg.classList.add('show');
                window.openAuthModal();
                return;
              }
              if(r.status >= 400){
                realResults[slot] = {status: 'warn', note: cfg.label + ': AI đọc bản vẽ báo lỗi: ' + (r.data.error || 'không rõ nguyên nhân') + '.'};
                return;
              }
              realResults[slot] = cfg.summarize(r.data);
              realData[slot] = r.data;
              if(slot === 'kientruc' && r.data.quy_mo && r.data.quy_mo.occ) quyMoOccInSession = r.data.quy_mo.occ;
            })
            .catch(function(){
              realResults[slot] = {status: 'warn', note: cfg.label + ': Không kết nối được tới máy chủ AI — thử lại sau.'};
            })
            .then(function(){
              pending--;
              if(pending === 0 && !sawAuthError) finishUp();
            });
        });
      } else {
        setTimeout(finishUp, 2200);
      }
    }

    // Quy mô Giai đoạn 1, Phần A.2 — Lượt 0: quét nhẹ quy mô từ báo cháy/ccnuoc
    // TRƯỚC khi bắn Lượt 1, CHỈ khi Quy mô CHƯA đính file riêng, CÓ ít nhất 1
    // trong 2 file báo cháy/ccnuoc, VÀ chưa từng chạy Lượt 0 trong phiên này
    // (tránh gọi lại thừa nếu bấm "Bắt đầu phân tích" nhiều lần). Lượt 0 lỗi
    // (mạng/AI) KHÔNG được chặn Lượt 1 — luôn resolve rồi mới gọi fireLuot1().
    var needQuyMoScan = sessionId && !realFiles.kientruc && !quyMoScanAttemptedInSession &&
      (activeSlots.indexOf('baochay') !== -1 || activeSlots.indexOf('ccnuoc') !== -1);
    if(needQuyMoScan){
      runQuyMoScanLuot0(sessionId, activeSlots).then(fireLuot1);
    } else {
      fireLuot1();
    }
  }

  /* ---- Quy mô Giai đoạn 1, Phần E — đối chiếu ngược sau Lượt 1 ---- */
  function fetchQuyMoReverseCheck(activeSlots, sessionId){
    quyMoMissingWarningsPending = [];
    if(!sessionId) return Promise.resolve();
    var slotsWithData = activeSlots.filter(function(slot){ return !!realData[slot]; });
    return fetch(BACKEND_BASE + '/api/aiho/quymo-reverse-check', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
      body: JSON.stringify({session_id: sessionId, slots_with_data: slotsWithData})
    })
      .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
      .then(function(r){
        if(r.status < 400 && r.data.warnings) quyMoMissingWarningsPending = r.data.warnings;
      })
      .catch(function(){ /* doi chieu nguoc la best-effort - khong chan hien ket qua neu loi mang */ });
  }

  function quyMoConflictWarningText(c){
    return 'Phát hiện số liệu quy mô KHÔNG THỐNG NHẤT giữa bản vẽ ' +
      c.values.map(function(v){ return v.label; }).join(' và ') + ' — trường ' + c.label + ': ' +
      c.values.map(function(v){ return (v.value === true ? 'Có' : v.value === false ? 'Không' : v.value) + ' (theo ' + v.label + ')'; }).join(' vs ') +
      '. Đã tạm dùng ' + (c.chosen === true ? 'Có' : c.chosen === false ? 'Không' : c.chosen) + ', cần xác nhận lại.';
  }

  function quyMoMissingWarningText(w){
    var label = (REAL_CATEGORIES[w.slot] && REAL_CATEGORIES[w.slot].label) || w.slot;
    return 'Bổ sung hồ sơ thiết kế hệ thống ' + label + ' cho hạng mục này; theo ' + w.can_cu +
      ', hạng mục này thuộc diện bắt buộc trang bị nhưng chưa thấy bản vẽ/hồ sơ thiết kế hệ thống này trong bộ hồ sơ hiện có.';
  }

  function renderQuyMoWarningsBox(){
    var box = document.getElementById('aihoQuyMoWarnings');
    if(!box) return;
    box.innerHTML = '';
    quyMoConflictWarningsPending.forEach(function(c){
      var div = document.createElement('div');
      div.className = 'quymo-warning qw-red';
      div.textContent = quyMoConflictWarningText(c);
      box.appendChild(div);
    });
    quyMoMissingWarningsPending.forEach(function(w){
      var div = document.createElement('div');
      div.className = 'quymo-warning qw-amber';
      div.textContent = quyMoMissingWarningText(w);
      box.appendChild(div);
    });
    box.hidden = !(quyMoConflictWarningsPending.length || quyMoMissingWarningsPending.length);
  }

  /* ---- Quy mô Giai đoạn 1, Phần A.1-A.3 — "Lượt 0" quét nhẹ quy mô ---- */
  function runQuyMoScanLuot0(sessionId, activeSlots){
    quyMoScanAttemptedInSession = true;
    var scanSlots = ['baochay', 'ccnuoc'].filter(function(s){ return activeSlots.indexOf(s) !== -1; });

    var calls = scanSlots.map(function(slot){
      var form = new FormData();
      form.append('file', (realFiles[slot] || [])[0]);
      form.append('session_id', sessionId);
      return fetch(BACKEND_BASE + '/api/aiho/scan-quymo', {
        method: 'POST',
        headers: {'Authorization': 'Bearer ' + getToken()},
        body: form
      })
        .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
        .then(function(r){
          if(r.status >= 400) return null; // loi Luot 0 (vd het quota AI/ngay) - bo qua ket qua nay, KHONG chan Luot 1
          return {slot: slot, label: REAL_CATEGORIES[slot].label, tim_thay: !!r.data.tim_thay, quy_mo: r.data.quy_mo || null};
        })
        .catch(function(){ return null; });
    });

    return Promise.all(calls).then(function(results){
      var valid = results.filter(function(r){ return !!r; });
      if(!valid.length) return Promise.resolve();
      return fetch(BACKEND_BASE + '/api/aiho/scan-quymo/finish', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken()},
        body: JSON.stringify({session_id: sessionId, results: valid})
      })
        .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
        .then(function(r){
          if(r.status >= 400) return;
          if(r.data.saved){
            quyMoDataSavedInSession = true;
            quyMoOccInSession = r.data.saved.occ;
          }
          if(r.data.conflicts && r.data.conflicts.length) quyMoConflictWarningsPending = r.data.conflicts;
        })
        .catch(function(){});
    });
  }

  /* ---- Quy mô Giai đoạn 1, Phần B — modal khuyến cáo trước khi chạy ---- */
  var quyMoNoticeModal = document.getElementById('quyMoNoticeModal');
  var quyMoNoticeClose = document.getElementById('quyMoNoticeClose');
  var quyMoNoticeAttachBtn = document.getElementById('quyMoNoticeAttachBtn');
  var quyMoNoticeSkipBtn = document.getElementById('quyMoNoticeSkipBtn');

  function startAnalysisFlow(){
    msg.classList.remove('show');
    feedbackConfirm.hidden = true;
    resultsSection.hidden = true;
    processing.hidden = false;
    isProcessing = true;
    updateCta();
    setOutputPickerLocked(true);

    var hasRealSlot = Object.keys(REAL_CATEGORIES).some(function(slot){ return realFiles[slot] && realFiles[slot].length > 0; });
    // Khong co file that nao dinh KEM, VA cung khong co phien nao dang mo tu
    // truoc (vd chua tung "Luu thong so" Quy mo) -> chi mo phong demo, khong
    // dung gi toi backend. Neu DA co activeSessionId (chi nhap tay Quy mo,
    // chua dinh file), van phai di qua ensureSessionOpen()/runAnalysis() de
    // dong phien do dung cach (xem ghi chu o hasFile trong updateCta()).
    if(!hasRealSlot && !activeSessionId){
      runAnalysis(null);
      return;
    }

    ensureSessionOpen()
      .then(function(r){
        if(r.status === 401){
          A.logout();
          abortProcessing(r.data.error || 'Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại.');
          window.openAuthModal();
          return;
        }
        if(r.status >= 400){
          abortProcessing(r.data.error || 'Không mở được phiên Bộ hồ sơ — vui lòng thử lại sau.');
          return;
        }
        runAnalysis(r.data.session_id);
      })
      .catch(function(){
        abortProcessing('Không kết nối được tới máy chủ — vui lòng thử lại sau.');
      });
  }

  cta.addEventListener('click', function(){
    if(!currentUser){
      window.openAuthModal();
      return;
    }

    // Phan B: chi hien modal khi CHUA dinh file Quy mo VA CHUA co ban ghi
    // Quy mo nao da luu trong phien (nhap tay truoc do) VA nguoi dung CHUA
    // tung bam "Bo qua" 1 lan trong phien nay.
    if(!realFiles.kientruc && !quyMoDataSavedInSession && !quyMoModalSkippedOnce && quyMoNoticeModal){
      quyMoNoticeModal.hidden = false;
      return;
    }

    startAnalysisFlow();
  });

  if(quyMoNoticeModal){
    if(quyMoNoticeClose) quyMoNoticeClose.addEventListener('click', function(){ quyMoNoticeModal.hidden = true; });
    if(quyMoNoticeAttachBtn) quyMoNoticeAttachBtn.addEventListener('click', function(){
      quyMoNoticeModal.hidden = true;
      var kientrucCard = document.getElementById('kientrucCard');
      if(kientrucCard) kientrucCard.scrollIntoView({behavior: 'smooth', block: 'center'});
      // KHONG chay phan tich - nguoi dung tu dinh file/nhap tay Quy mo roi tu bam lai "Bắt đầu phân tích".
    });
    if(quyMoNoticeSkipBtn) quyMoNoticeSkipBtn.addEventListener('click', function(){
      quyMoModalSkippedOnce = true;
      quyMoNoticeModal.hidden = true;
      startAnalysisFlow();
    });
  }

  /* ===================================================================
     Modal Góp ý — góp ý chung cho cả Bộ hồ sơ (không phải riêng 1 kết quả).
     Chỉ mở khi người dùng chủ động bấm nút "GÓP Ý" (không tự bật sau khi AI
     chạy xong); nút đó chỉ bật sau khi có ít nhất 1 lượt chạy hoàn tất.
     "Loại góp ý" bắt buộc chọn 1 (gate nút Gửi góp ý); sao đánh giá và nội
     dung chi tiết vẫn tuỳ chọn.
     =================================================================== */
  var feedbackModal = document.getElementById('feedbackModal');
  var feedbackModalClose = document.getElementById('feedbackModalClose');
  var feedbackStars = document.getElementById('feedbackStars');
  var feedbackType = document.getElementById('feedbackType');
  var feedbackComment = document.getElementById('feedbackComment');
  var feedbackSubmitBtn = document.getElementById('feedbackSubmitBtn');
  var feedbackSkipBtn = document.getElementById('feedbackSkipBtn');
  var selectedRating = 0;
  var feedbackConfirmTimer = null;

  function updateStars(){
    Array.prototype.forEach.call(feedbackStars.querySelectorAll('button'), function(btn){
      var val = Number(btn.dataset.star);
      btn.textContent = val <= selectedRating ? '★' : '☆';
      btn.classList.toggle('filled', val <= selectedRating);
    });
  }

  function openFeedbackModal(){
    selectedRating = 0;
    updateStars();
    feedbackType.value = '';
    feedbackComment.value = '';
    feedbackSubmitBtn.disabled = true;
    feedbackModal.hidden = false;
  }
  function closeFeedbackModal(){ feedbackModal.hidden = true; }

  feedbackStars.addEventListener('click', function(e){
    var btn = e.target.closest('button');
    if(!btn) return;
    selectedRating = Number(btn.dataset.star);
    updateStars();
  });

  feedbackType.addEventListener('change', function(){
    feedbackSubmitBtn.disabled = !feedbackType.value;
  });

  feedbackModalClose.addEventListener('click', closeFeedbackModal);
  feedbackSkipBtn.addEventListener('click', closeFeedbackModal);
  feedbackModal.addEventListener('click', function(e){ if(e.target === feedbackModal) closeFeedbackModal(); });

  function showFeedbackConfirm(text){
    clearTimeout(feedbackConfirmTimer);
    feedbackConfirm.textContent = text;
    feedbackConfirm.hidden = false;
    feedbackConfirmTimer = setTimeout(function(){ feedbackConfirm.hidden = true; }, 5000);
  }

  feedbackSubmitBtn.addEventListener('click', function(){
    var headers = {'Content-Type': 'application/json'};
    var token = getToken();
    if(token) headers['Authorization'] = 'Bearer ' + token;
    var typeLabel = feedbackType.value;
    var rawComment = feedbackComment.value.trim();
    var comment = typeLabel ? ('[' + typeLabel + '] ' + rawComment).trim() : rawComment;
    feedbackSubmitBtn.disabled = true;
    fetch(BACKEND_BASE + '/api/feedback', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        feature: 'aiho_bo_ho_so',
        rating: selectedRating || null,
        comment: comment || null
      })
    })
      .then(function(res){
        feedbackSubmitBtn.disabled = false;
        closeFeedbackModal();
        if(res.ok){
          res.json().then(function(data){
            if(data && data.bonus_granted){
              showFeedbackConfirm('Anh/chị đã hoàn thành 05 góp ý. Hệ thống đã cộng thêm 01 lượt hướng dẫn cho 01 Bộ hồ sơ vào tài khoản của anh/chị.');
              A.refreshMe();
            } else {
              showFeedbackConfirm('Cảm ơn góp ý của anh/chị!');
            }
          }).catch(function(){
            showFeedbackConfirm('Cảm ơn góp ý của anh/chị!');
          });
        } else {
          msg.textContent = 'Không gửi được góp ý — vui lòng thử lại sau.';
          msg.classList.add('show');
        }
      })
      .catch(function(){
        feedbackSubmitBtn.disabled = false;
        closeFeedbackModal();
        msg.textContent = 'Không kết nối được tới máy chủ — góp ý chưa được gửi.';
        msg.classList.add('show');
      });
  });

  feedbackCta.addEventListener('click', openFeedbackModal);
})();
