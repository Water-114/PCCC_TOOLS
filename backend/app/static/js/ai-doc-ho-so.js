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
    }
  };

  var realFiles = {};   // slot -> File
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

  // Gan 1 file (da qua validateFileSize) vao 1 slot cu the - cap nhat realFiles
  // + giao dien the (giong het duong dinh tung the rieng le). Dung CHUNG cho ca
  // setupRealFileCard VA panel "Dung 1 file cho nhieu hang muc" (khong viet lai).
  function attachFileToSlot(slot, f){
    var card = document.getElementById(slot + 'Card');
    var status = document.getElementById(slot + 'Status');
    if(!card || !status) return;

    realFiles[slot] = f;
    realResults[slot] = null;
    realData[slot] = null;
    card.classList.add('filled');
    status.textContent = '● Đã đính kèm';
    status.classList.add('attached');
    var body = card.querySelector('.drop-body');
    var existing = body.querySelector('.drop-file');
    if(existing) existing.remove();
    var sizeMb = (f.size / (1024 * 1024)).toFixed(1);
    var fileRow = buildFileRow(f.name + ' · ' + sizeMb + ' MB');
    fileRow.querySelector('button').addEventListener('click', function(e){
      e.stopPropagation();
      realFiles[slot] = null;
      realResults[slot] = null;
      realData[slot] = null;
      var fileInput = document.getElementById(slot + 'FileInput');
      if(fileInput) fileInput.value = '';
      card.classList.remove('filled');
      status.textContent = '○ Chưa đính kèm';
      status.classList.remove('attached');
      fileRow.remove();
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

    card.addEventListener('click', function(e){
      if(e.target.closest('.drop-file')) return;
      if(!currentUser){ window.openAuthModal(); return; }
      fileInput.click();
    });
    fileInput.addEventListener('click', function(e){ e.stopPropagation(); });
    fileInput.addEventListener('change', function(){
      var f = fileInput.files[0];
      if(!f) return;
      var err = validateFileSize(f);
      if(err){
        msg.textContent = err;
        msg.classList.add('show');
        fileInput.value = '';
        return;
      }
      msg.classList.remove('show');
      attachFileToSlot(slot, f);
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
     attachFileToSlot() ở trên — mỗi hạng mục vẫn tự gọi AI đọc ĐỘC LẬP trên
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
      slots.forEach(function(slot){ attachFileToSlot(slot, f); });
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
      if(!realData[slot] && realResults[slot] && realFiles[slot]){
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
          var knCount = items.filter(function(it){ return it.ket_luan !== 'dat'; }).length;
          var datCount = items.length - knCount;
          var dataUrl = 'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,' + f.base64;

          var p = document.createElement('p');
          var b = document.createElement('b');
          b.textContent = f.label;
          p.appendChild(b);
          p.appendChild(document.createTextNode(' — đã điền ' + items.length + ' mục đối chiếu: ' + datCount + ' Đạt, ' + knCount + ' cần kiến nghị (KN).'));
          fileDiv.appendChild(p);

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
    var activeSlots = Object.keys(REAL_CATEGORIES).filter(function(slot){ return !!realFiles[slot]; });
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
          form.append('file', realFiles[slot]);
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
      form.append('file', realFiles[slot]);
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
          if(r.data.saved) quyMoDataSavedInSession = true;
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

    var hasRealSlot = Object.keys(REAL_CATEGORIES).some(function(slot){ return !!realFiles[slot]; });
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
