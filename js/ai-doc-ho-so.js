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

  var MAX_FILE_MB = 15;
  var MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024;

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
    }
  };

  var realFiles = {};   // slot -> File
  var realResults = {}; // slot -> {status, note} (dùng cho dòng tóm tắt trong bảng kết quả)
  var realData = {};    // slot -> JSON đầy đủ AI trả về (gồm items/kien_nghi/mdc_docx_*)

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
      if(f.size > MAX_FILE_BYTES){
        var overMb = (f.size / (1024 * 1024)).toFixed(1);
        msg.textContent = 'File "' + f.name + '" (' + overMb + ' MB) vượt quá giới hạn ' + MAX_FILE_MB + 'MB — vui lòng nén file hoặc chia nhỏ PDF rồi đính kèm lại.';
        msg.classList.add('show');
        fileInput.value = '';
        return;
      }
      msg.classList.remove('show');
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
        fileInput.value = '';
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
    });
  }
  Object.keys(REAL_CATEGORIES).forEach(setupRealFileCard);

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
    var hasFile = !!grid.querySelector('.drop-card.filled');
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
    kientruc: {status:'ok', note:'Xác định công năng: văn phòng hỗn hợp, 8 tầng nổi + 1 tầng hầm, ΣF ≈ 4.200 m².'},
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
        if(kienNghiSections.length || loiFailed.length){
          var loiParts = [];
          if(kienNghiSections.length){
            loiParts.push(renderKienNghiReal(kienNghiSections));
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
        })
        .catch(function(){ /* dong phien la best-effort - khong chan hien ket qua neu loi mang luc dong */ });
    }

    function finishUp(){
      clearInterval(interval);
      processingFill.style.width = '100%';
      closeSessionIfAny().then(function(){
        setTimeout(function(){
          processing.hidden = true;
          processingFill.style.width = '0%';
          isProcessing = false;
          setOutputPickerLocked(false);
          renderResultTable();
          renderOutputPreviews();
          maybeExportKienNghiDocx();
          resultsSection.hidden = false;
          resultsSection.scrollIntoView({behavior: 'smooth', block: 'start'});
          updateCta();
          // Khong tu bat popup gop y - chi kich hoat nut, nguoi dung tu bam khi san sang.
          feedbackCta.disabled = false;
        }, 300);
      });
    }

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

  cta.addEventListener('click', function(){
    if(!currentUser){
      window.openAuthModal();
      return;
    }

    msg.classList.remove('show');
    feedbackConfirm.hidden = true;
    feedbackCta.disabled = true;
    resultsSection.hidden = true;
    processing.hidden = false;
    isProcessing = true;
    updateCta();
    setOutputPickerLocked(true);

    var hasRealSlot = Object.keys(REAL_CATEGORIES).some(function(slot){ return !!realFiles[slot]; });
    if(!hasRealSlot){
      runAnalysis(null);
      return;
    }

    fetch(BACKEND_BASE + '/api/aiho/session/open', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + getToken()}
    })
      .then(function(res){ return res.json().then(function(data){ return {status: res.status, data: data}; }); })
      .then(function(r){
        if(r.status === 401){
          A.logout();
          abortProcessing(r.data.error || 'Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại.');
          window.openAuthModal();
          return;
        }
        if(r.status >= 400){
          if(r.data.bo_ho_so_con_lai !== undefined) updateBoHoSoDisplay({con_lai: r.data.bo_ho_so_con_lai});
          abortProcessing(r.data.error || 'Không mở được phiên Bộ hồ sơ — vui lòng thử lại sau.');
          return;
        }
        if(r.data.bo_ho_so_con_lai !== undefined) updateBoHoSoDisplay({con_lai: r.data.bo_ho_so_con_lai});
        runAnalysis(r.data.session_id);
      })
      .catch(function(){
        abortProcessing('Không kết nối được tới máy chủ — vui lòng thử lại sau.');
      });
  });

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
