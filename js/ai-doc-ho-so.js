(function(){
  var grid = document.getElementById('aihoGrid');
  if(!grid) return;

  /* Đăng nhập/phiên làm việc dùng chung toàn trang qua window.PcccAuth (xem script ngay sau <nav>) */
  var A = window.PcccAuth;
  var BACKEND_BASE = A.BACKEND_BASE;
  var currentUser = A.getUser();
  function getToken(){ return A.getToken(); }
  function updateQuotaDisplay(quota){ A.setUserQuota(quota); }
  A.onChange(function(user){ currentUser = user; updateCta(); });

  var MAX_FILE_MB = 15;
  var MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024;

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
      var fileRow = document.createElement('div');
      fileRow.className = 'drop-file';
      fileRow.innerHTML = '<span>' + f.name + ' · ' + sizeMb + ' MB</span><button type="button" aria-label="Gỡ file">✕</button>';
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
        var fileRow = document.createElement('div');
        fileRow.className = 'drop-file';
        fileRow.innerHTML = '<span>' + card.dataset.file + '</span><button type="button" aria-label="Gỡ file">✕</button>';
        body.appendChild(fileRow);
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
      ctaHint.textContent = 'Sẵn sàng — còn ' + currentUser.quota.remaining_today + '/' + currentUser.quota.limit + ' lượt đọc bản vẽ hôm nay';
    }
  }

  /* ---- Dữ liệu minh hoạ cho màn kết quả (demo, chưa phải phân tích thật) ---- */
  var SLOT_MOCK = {
    kientruc: {status:'ok', note:'Xác định công năng: văn phòng hỗn hợp, 8 tầng nổi + 1 tầng hầm, ΣF ≈ 4.200 m².'},
    baochay: {status:'warn', note:'Thiếu thông tin loại trung tâm báo cháy và số zone trên sơ đồ nguyên lý.'},
    ccnuoc: {status:'warn', note:'Chưa rõ bơm bù áp có khởi động độc lập với bơm chính hay không; họng nước trong nhà và sprinkler khớp với Bảng A.1.'},
    cckhi: {status:'bad', note:'Chưa thấy tính toán nồng độ thiết kế d₁, f₂ cho phòng điện — cần bổ sung.'},
    capnuocngoai: {status:'ok', note:'Trụ nước ngoài nhà bố trí đủ theo bán kính bảo vệ.'},
    binhcc: {status:'ok', note:'Số lượng và khoảng cách bình xách tay phù hợp TCVN 7435-1.'},
    densucco: {status:'warn', note:'Một số vị trí đèn chỉ dẫn thoát nạn cách nhau quá 20 m.'},
    dienpccc: {status:'ok', note:'Có cấp nguồn ưu tiên riêng, dây dẫn ghi chú chống cháy 70 phút.'}
  };
  var STATUS_LABEL = {ok:'Đạt', warn:'Cần bổ sung', bad:'Thiếu sót'};

  function renderResultTable(){
    var filledCards = Array.prototype.slice.call(grid.querySelectorAll('.drop-card.filled'));
    var rows = filledCards.map(function(card){
      var slot = card.dataset.slot;
      var label = card.querySelector('h4').childNodes[0].textContent.trim();
      var mock = (REAL_CATEGORIES[slot] && realResults[slot]) ? realResults[slot] : (SLOT_MOCK[slot] || {status:'ok', note:'Chưa phát hiện thiếu sót.'});
      return '<div class="result-row"><span class="r-label">' + label + '</span>' +
        '<span class="status-pill status-' + mock.status + '">' + STATUS_LABEL[mock.status] + '</span>' +
        '<span class="r-note">' + mock.note + '</span></div>';
    });
    document.getElementById('aihoResultTable').innerHTML = rows.join('');
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

  function renderKienNghiReal(sections){
    return sections.map(function(sec){
      var groups = KIEN_NGHI_NHOM.map(function(nhom){
        var items = sec.data.kien_nghi[nhom.key] || [];
        var body = items.length
          ? '<ol>' + items.map(function(c){ return '<li>' + c + '</li>'; }).join('') + '</ol>'
          : '<p style="color:var(--ink-soft)">(Không có)</p>';
        return '<p style="margin-top:10px"><b>' + nhom.label + '</b></p>' + body;
      }).join('');
      return '<h4>Danh sách kiến nghị (theo văn phong PC07) — ' + sec.label + '</h4>' + groups;
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
      var filesHtml = (d.mdc_docx_files || []).map(function(f){
        if(f.base64){
          var items = itemsForMdcFile(d, f);
          var knCount = items.filter(function(it){ return it.ket_luan !== 'dat'; }).length;
          var datCount = items.length - knCount;
          var dataUrl = 'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,' + f.base64;
          return '<div style="margin-top:12px">' +
            '<p><b>' + f.label + '</b> — đã điền ' + items.length + ' mục đối chiếu: ' + datCount + ' Đạt, ' + knCount + ' cần kiến nghị (KN).</p>' +
            '<a class="btn-main" style="display:inline-block;text-decoration:none;text-align:center" download="' + f.filename + '" href="' + dataUrl + '">Tải file MĐC (.docx)</a>' +
            '</div>';
        }
        return '<div style="margin-top:12px"><p><b>' + f.label + '</b></p><p style="color:var(--red-deep)">' + f.error + '</p></div>';
      }).join('');
      return '<h4>Mẫu đối chiếu (MĐC) đã điền — ' + sec.label + '</h4>' + filesHtml;
    }).join(SECTION_DIVIDER);
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
            mdcParts.push('<h4>Mẫu đối chiếu (MĐC) đã điền — ' + f.label + '</h4><p style="color:var(--red-deep)">' + f.note + '</p>');
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
          if(kienNghiSections.length) loiParts.push(renderKienNghiReal(kienNghiSections));
          loiFailed.forEach(function(f){
            loiParts.push('<h4>Danh sách kiến nghị (theo văn phong PC07) — ' + f.label + '</h4><p style="color:var(--red-deep)">' + f.note + '</p>');
          });
          return loiParts.join(SECTION_DIVIDER);
        }
        return '<h4>Danh sách lỗi / thiếu sót — trích đoạn</h4>' +
          '<ul>' +
          '<li>Thiếu loại trung tâm báo cháy và số zone (Báo cháy tự động).</li>' +
          '<li>Chưa có tính toán nồng độ thiết kế d₁, f₂ (Chữa cháy bằng khí).</li>' +
          '<li>Đèn chỉ dẫn thoát nạn bố trí cách nhau quá 20 m (Đèn sự cố).</li>' +
          '</ul>';
      case 'thuyetminh':
        return '<h4>Thuyết minh PCCC (bản thảo) — trích đoạn</h4>' +
          '<p>1. Thông tin công trình: văn phòng hỗn hợp, 8 tầng nổi + 1 tầng hầm, ΣF ≈ 4.200 m².<br>' +
          '2. Giải pháp báo cháy: hệ thống báo cháy tự động theo địa chỉ (chưa rõ loại trung tâm, cần bổ sung).<br>' +
          '3. Giải pháp chữa cháy: họng nước trong nhà và sprinkler theo Bảng A.1…<br>' +
          '<i>(bản thảo — cần kỹ sư hoàn thiện và rà lại trước khi ký)</i></p>';
      case 'pc12':
        return '<h4>Đơn đề nghị thẩm duyệt (PC12) — điền sẵn</h4>' +
          '<div class="kv-grid">' +
          '<div><b>Tên công trình</b>Văn phòng hỗn hợp ABC</div>' +
          '<div><b>Chủ đầu tư</b>— (nhận diện từ kiến trúc)</div>' +
          '<div><b>Địa điểm xây dựng</b>— (nhận diện từ kiến trúc)</div>' +
          '<div><b>Quy mô</b>8 tầng nổi + 1 hầm, ΣF ≈ 4.200 m²</div>' +
          '</div>';
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
      case 'thugopy':
        return '<h4>Thư góp ý gửi đơn vị thiết kế — trích đoạn</h4>' +
          '<p>Kính gửi đơn vị thiết kế,<br>Qua rà soát bản vẽ PCCC, đề nghị bổ sung: (1) loại trung tâm báo cháy và số zone; ' +
          '(2) tính toán nồng độ thiết kế d₁, f₂ cho hệ chữa cháy khí; (3) điều chỉnh khoảng cách đèn chỉ dẫn thoát nạn ≤ 20 m…</p>';
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

  cta.addEventListener('click', function(){
    if(!currentUser){
      window.openAuthModal();
      return;
    }

    msg.classList.remove('show');
    resultsSection.hidden = true;
    processing.hidden = false;
    isProcessing = true;
    updateCta();
    setOutputPickerLocked(true);

    var activeSlots = Object.keys(REAL_CATEGORIES).filter(function(slot){ return !!realFiles[slot]; });
    activeSlots.forEach(function(slot){ realResults[slot] = null; realData[slot] = null; });

    var interval;

    if(activeSlots.length){
      // Ước lượng theo hạng mục chậm nhất đang chạy (chạy song song, không cộng dồn thời gian).
      var estimatedSec = Math.max.apply(null, activeSlots.map(function(slot){ return REAL_CATEGORIES[slot].estimatedSeconds; }));
      var startedAt = Date.now();
      function updateRealProgress(){
        var elapsedSec = Math.floor((Date.now() - startedAt) / 1000);
        var percent = Math.min(92, 5 + (elapsedSec / estimatedSec) * 87);
        processingFill.style.width = percent + '%';
        processingText.textContent = 'Đang đọc bản vẽ và đối chiếu — đã chờ ' + fmtElapsed(elapsedSec) + ' (dự kiến khoảng ' + fmtElapsed(estimatedSec) + ')…';
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

    function finishUp(){
      clearInterval(interval);
      processingFill.style.width = '100%';
      setTimeout(function(){
        processing.hidden = true;
        processingFill.style.width = '0%';
        isProcessing = false;
        setOutputPickerLocked(false);
        renderResultTable();
        renderOutputPreviews();
        resultsSection.hidden = false;
        resultsSection.scrollIntoView({behavior: 'smooth', block: 'start'});
        updateCta();
        setTimeout(openFeedbackModal, 800);
      }, 300);
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
            if(r.status === 429){
              msg.textContent = r.data.error;
              msg.classList.add('show');
              if(r.data.quota) updateQuotaDisplay(r.data.quota);
              realResults[slot] = {status: 'bad', note: cfg.label + ': ' + (r.data.error || 'Đã hết lượt đọc bản vẽ hôm nay.')};
              return;
            }
            if(r.status >= 400){
              realResults[slot] = {status: 'warn', note: cfg.label + ': AI đọc bản vẽ báo lỗi: ' + (r.data.error || 'không rõ nguyên nhân') + '.'};
              return;
            }
            realResults[slot] = cfg.summarize(r.data);
            realData[slot] = r.data;
            if(r.data.quota) updateQuotaDisplay(r.data.quota);
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
  });

  /* ===================================================================
     Modal Góp ý — tự bật sau khi phân tích xong, hoặc bấm nút ở footer
     =================================================================== */
  var feedbackModal = document.getElementById('feedbackModal');
  var feedbackModalClose = document.getElementById('feedbackModalClose');
  var feedbackStars = document.getElementById('feedbackStars');
  var feedbackComment = document.getElementById('feedbackComment');
  var feedbackSubmitBtn = document.getElementById('feedbackSubmitBtn');
  var feedbackSkipBtn = document.getElementById('feedbackSkipBtn');
  var selectedRating = 0;

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
    feedbackComment.value = '';
    feedbackModal.hidden = false;
  }
  function closeFeedbackModal(){ feedbackModal.hidden = true; }

  feedbackStars.addEventListener('click', function(e){
    var btn = e.target.closest('button');
    if(!btn) return;
    selectedRating = Number(btn.dataset.star);
    updateStars();
  });

  feedbackModalClose.addEventListener('click', closeFeedbackModal);
  feedbackSkipBtn.addEventListener('click', closeFeedbackModal);
  feedbackModal.addEventListener('click', function(e){ if(e.target === feedbackModal) closeFeedbackModal(); });

  feedbackSubmitBtn.addEventListener('click', function(){
    var headers = {'Content-Type': 'application/json'};
    var token = getToken();
    if(token) headers['Authorization'] = 'Bearer ' + token;
    feedbackSubmitBtn.disabled = true;
    fetch(BACKEND_BASE + '/api/feedback', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        feature: 'aiho_baochay',
        rating: selectedRating || null,
        comment: feedbackComment.value.trim() || null
      })
    })
      .then(function(){ feedbackSubmitBtn.disabled = false; closeFeedbackModal(); })
      .catch(function(){ feedbackSubmitBtn.disabled = false; closeFeedbackModal(); });
  });

  var feedbackBtn = document.getElementById('aihoFeedbackBtn');
  feedbackBtn.addEventListener('click', openFeedbackModal);
})();
