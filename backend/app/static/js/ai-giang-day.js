"use strict";
(function(){
  /* =====================================================================
     Tab con 1 — "Thư viện bài giảng PCCC"
     Dữ liệu THẬT từ data/ai-giang-day-tiktok.json (xuất từ
     AI_GIANG_DAY/DANH_SACH_LINK_TIKTOK.xlsx, sheet BAI_GIANG_TIKTOK, xem
     scripts/prepare_ai_giang_day_tiktok.py) — pill lọc chuyên đề SINH ĐỘNG
     theo đúng giá trị chuyen_de phân biệt thực tế xuất hiện trong dữ liệu
     (không hardcode danh sách chuyên đề), cộng 1 pill "Chưa phân loại" cho
     các dòng chuyen_de rỗng.
     ===================================================================== */
  var TIKTOK_DATA_URL = "data/ai-giang-day-tiktok.json";
  var UNCLASSIFIED_CD = "__chua_phan_loai__";
  var filterTabsWrap = document.querySelector(".bg-filter-tabs");
  var baigiangGrid = document.getElementById("baigiangGrid");
  var baigiangEmpty = document.getElementById("baigiangEmpty");

  function renderBaigiangCard(item){
    var videoHtml;
    if(item.video_id){
      videoHtml =
        '<div class="baigiang-video-ph">' +
          '<iframe src="https://www.tiktok.com/player/v1/' + item.video_id + '?music_info=0&description=0&controls=1" ' +
            'height="580" width="325" allow="fullscreen" style="border:none;max-width:100%"></iframe>' +
        '</div>';
    }else{
      videoHtml =
        '<div class="baigiang-video-ph">' +
          '<span class="ph-play">▶</span>' +
          '<span class="ph-label">Không nhúng được video này<br>(liên kết không đúng định dạng)</span>' +
          '<a href="' + item.tiktok_url + '" target="_blank" rel="noopener noreferrer" class="btn-ghost">Xem trên TikTok</a>' +
        '</div>';
    }
    var descHtml = item.ghi_chu ? '<p class="baigiang-desc">' + item.ghi_chu + '</p>' : '';
    var cd = item.chuyen_de || UNCLASSIFIED_CD;
    return (
      '<div class="baigiang-card" data-cd="' + cd + '">' +
        '<h3 class="baigiang-title">' + item.tieu_de + '</h3>' +
        videoHtml +
        descHtml +
      '</div>'
    );
  }

  function renderFilterPills(items){
    var distinctChuyenDe = [];
    var hasUnclassified = false;
    items.forEach(function(it){
      if(it.chuyen_de){
        if(distinctChuyenDe.indexOf(it.chuyen_de) === -1) distinctChuyenDe.push(it.chuyen_de);
      }else{
        hasUnclassified = true;
      }
    });
    var html = '<button class="active" data-cd="all" type="button">Tất cả</button>';
    distinctChuyenDe.forEach(function(cd){
      html += '<button data-cd="' + cd + '" type="button">' + cd + '</button>';
    });
    if(hasUnclassified){
      html += '<button data-cd="' + UNCLASSIFIED_CD + '" type="button">Chưa phân loại</button>';
    }
    filterTabsWrap.innerHTML = html;
  }

  function loadBaigiangLibrary(){
    if(!filterTabsWrap || !baigiangGrid || !baigiangEmpty) return;
    baigiangGrid.innerHTML = '<p style="color:var(--ink-soft);padding:24px 0;text-align:center;grid-column:1/-1">Đang tải dữ liệu…</p>';
    fetch(TIKTOK_DATA_URL)
      .then(function(res){ if(!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
      .then(function(items){
        renderFilterPills(items);
        baigiangGrid.innerHTML = items.map(renderBaigiangCard).join('');
        baigiangEmpty.hidden = true;
      })
      .catch(function(err){
        baigiangGrid.innerHTML = '';
        baigiangEmpty.hidden = false;
        baigiangEmpty.textContent = 'Không tải được dữ liệu bài giảng (' + err.message + ').';
      });

    // Event delegation vì pill được sinh động (không gắn listener trực tiếp
    // lên từng nút cứng trong HTML như trước).
    filterTabsWrap.addEventListener("click", function(e){
      var btn = e.target.closest("button");
      if(!btn) return;
      filterTabsWrap.querySelectorAll("button").forEach(function(x){ x.classList.remove("active"); });
      btn.classList.add("active");
      var cd = btn.dataset.cd;
      var shown = 0;
      baigiangGrid.querySelectorAll(".baigiang-card").forEach(function(c){
        var match = (cd === "all" || c.dataset.cd === cd);
        c.hidden = !match;
        if(match) shown++;
      });
      baigiangEmpty.hidden = shown !== 0;
    });
  }

  loadBaigiangLibrary();

  /* ---- 3 tab con chính: Thư viện bài giảng / Hướng dẫn bố cục / Hỗ trợ kiểm tra ---- */
  var agdTabs = document.querySelectorAll(".agd-subnav .subtab");
  var agdPanels = document.querySelectorAll(".agd-panel");
  agdTabs.forEach(function(t){
    t.addEventListener("click", function(){
      agdTabs.forEach(function(x){ x.classList.remove("active"); });
      t.classList.add("active");
      var target = "agd-" + t.dataset.agdtab;
      agdPanels.forEach(function(p){ p.classList.toggle("active", p.id === target); });
    });
  });

  /* ---- Tab con 3: nút "Không đồng ý" (demo — chỉ đổi trạng thái nút, chưa lưu CSDL) ---- */
  document.querySelectorAll(".hk-disagree-btn").forEach(function(btn){
    btn.addEventListener("click", function(){
      if(btn.classList.contains("done")) return;
      btn.classList.add("done");
      btn.textContent = "Đã ghi nhận (demo)";
    });
  });

  /* =====================================================================
     Tab con 2 — "Hướng dẫn bố cục bản vẽ thẩm định"
     - Mục "2. Báo cháy": đọc DỮ LIỆU THẬT từ data/ai-giang-day-baochay.json
       (xuất sẵn từ sheet NOI_DUNG_BAN_VE, lọc he_thong = B1 hoặc B2 — xem
       cách xuất trong lịch sử trò chuyện, KHÔNG lọc kiểu "chứa B1" vì sẽ
       dính nhầm B12), hiển thị dạng master/detail (cột trái danh sách gom
       nhóm theo loai_ban_ve, cột phải chi tiết + ảnh thật).
     - 6 mục còn lại: accordion 3 tầng với dữ liệu placeholder "Đang cập
       nhật…" (chưa có nguồn thật).
     ===================================================================== */
  var bvSidebar = document.getElementById("bvSidebar");
  var bvPageList = document.getElementById("bvPageList");
  if(!bvSidebar || !bvPageList) return;

  var IMG_BASE = "img/ai-giang-day/bao-chay/";
  var BAOCHAY_DATA_URL = "data/ai-giang-day-baochay.json";
  var baochayRowsCache = null;
  var baochaySelectedIdx = 0;

  function placeholderTrang(title){
    return { title: title, placeholder: true };
  }

  var BV_DATA = {
    thongtincongtrinh: {
      pages: [placeholderTrang("Mặt bằng tổng thể công trình"), placeholderTrang("Bảng thống kê diện tích, số tầng"), placeholderTrang("Mặt cắt kiến trúc tổng thể")]
    },
    ccnuoc: {
      pages: [placeholderTrang("Mặt bằng họng nước trong nhà"), placeholderTrang("Mặt bằng trạm bơm"), placeholderTrang("Sơ đồ nguyên lý chữa cháy nước")]
    },
    ccbot: {
      pages: [placeholderTrang("Mặt bằng bọt cố định"), placeholderTrang("Chi tiết lăng phun bọt")]
    },
    cckhi: {
      pages: [placeholderTrang("Mặt bằng phòng bảo vệ"), placeholderTrang("Sơ đồ nguyên lý xả khí")]
    },
    densucco: {
      pages: [placeholderTrang("Mặt bằng đèn sự cố, đèn Exit"), placeholderTrang("Sơ đồ chỉ dẫn thoát nạn"), placeholderTrang("Mặt bằng bình chữa cháy")]
    },
    dienpccc: {
      pages: [placeholderTrang("Sơ đồ nguyên lý cấp nguồn ưu tiên"), placeholderTrang("Mặt bằng tuyến cáp chống cháy")]
    }
  };

  // ---- Accordion 3 tầng (6 mục còn placeholder) ----
  function renderPage(page, idx){
    return (
      '<div class="bv-page-item" data-page-idx="' + idx + '">' +
        '<button type="button" class="bv-page-header">' +
          '<span class="bv-toggle-icon">▸</span>' +
          '<span class="bv-page-num">' + (idx + 1) + '.</span> ' + page.title +
        '</button>' +
        '<div class="bv-page-body"><div class="bv-placeholder">Đang cập nhật…</div></div>' +
      '</div>'
    );
  }

  function renderAccordionSection(key){
    var section = BV_DATA[key];
    if(!section){ bvPageList.innerHTML = '<div class="bv-placeholder">Đang cập nhật…</div>'; return; }
    bvPageList.innerHTML = section.pages.map(renderPage).join('');
  }

  // ---- Master/detail (mục "2. Báo cháy", dữ liệu thật) ----
  function groupByLoaiBanVe(rows){
    var order = [];
    var groups = {};
    rows.forEach(function(r){
      var key = r.loai_ban_ve || "Khác";
      if(!groups[key]){ groups[key] = []; order.push(key); }
      groups[key].push(r);
    });
    return order.map(function(key){ return { label: key, rows: groups[key] }; });
  }

  function renderBaochayDetail(row){
    var statusClass = row.trang_thai === "Đã rà soát" ? "b-green" : "b-warn";
    var imageHtml;
    if(row.ten_file_anh){
      imageHtml =
        '<div class="bv2-image-wrap">' +
          '<img src="' + IMG_BASE + row.ten_file_anh + '" alt="' + row.noi_dung + '">' +
          (row.nguon_anh ? '<div class="bv2-image-caption">Nguồn ảnh: ' + row.nguon_anh + '</div>' : '') +
        '</div>';
    }else{
      imageHtml = '<div class="bv2-image-wrap"><div class="bv2-image-ph">Chưa có ảnh minh hoạ cho mục này</div></div>';
    }
    var canCuHtml = row.can_cu_phap_ly
      ? '<div class="bv2-block"><div class="bv2-block-label">Căn cứ</div><div class="bv2-block-text">' + row.can_cu_phap_ly + '</div></div>'
      : '';
    var loiHtml = row.loi_thuong_gap
      ? '<div class="bv2-block warn"><div class="bv2-block-label">Lỗi thường gặp</div><div class="bv2-block-text">' + row.loi_thuong_gap + '</div></div>'
      : '';
    return (
      '<div class="bv2-detail-title">' + row.noi_dung + '</div>' +
      '<div class="bv2-detail-meta">' +
        '<span class="bv2-item-ma">' + row.ma_muc + '</span>' +
        '<span class="badge ' + statusClass + '">' + row.trang_thai + '</span>' +
      '</div>' +
      imageHtml +
      '<div class="bv2-block"><div class="bv2-block-label">Yêu cầu chi tiết</div><div class="bv2-block-text">' + (row.yeu_cau_chi_tiet || '—') + '</div></div>' +
      canCuHtml + loiHtml
    );
  }

  function renderBaochayMasterDetail(rows){
    var groups = groupByLoaiBanVe(rows);
    var listHtml = groups.map(function(g){
      return (
        '<div class="bv2-group-label">' + g.label + '</div>' +
        g.rows.map(function(r){
          var globalIdx = rows.indexOf(r);
          var hasImg = !!r.ten_file_anh;
          return (
            '<button type="button" class="bv2-item' + (globalIdx === baochaySelectedIdx ? ' active' : '') + '" data-idx="' + globalIdx + '">' +
              '<span class="bv2-item-icon ' + (hasImg ? 'has-img' : 'no-img') + '">' + (hasImg ? '●' : '○') + '</span>' +
              '<span><span class="bv2-item-ma">' + r.ma_muc + '</span> — ' + r.noi_dung + '</span>' +
            '</button>'
          );
        }).join('')
      );
    }).join('');

    bvPageList.innerHTML =
      '<div class="bv2-layout">' +
        '<div class="bv2-list">' + listHtml + '</div>' +
        '<div class="bv2-detail" id="bv2Detail">' + renderBaochayDetail(rows[baochaySelectedIdx]) + '</div>' +
      '</div>';
  }

  function loadBaochaySection(){
    if(baochayRowsCache){ renderBaochayMasterDetail(baochayRowsCache); return; }
    bvPageList.innerHTML = '<div class="bv-placeholder">Đang tải dữ liệu…</div>';
    fetch(BAOCHAY_DATA_URL)
      .then(function(res){ if(!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
      .then(function(rows){
        baochayRowsCache = rows;
        renderBaochayMasterDetail(rows);
      })
      .catch(function(err){
        bvPageList.innerHTML = '<div class="bv-placeholder">Không tải được dữ liệu mục Báo cháy (' + err.message + ').</div>';
      });
  }

  function renderSection(key){
    if(key === "baochay"){ loadBaochaySection(); return; }
    renderAccordionSection(key);
  }

  bvSidebar.querySelectorAll(".bv-side-item").forEach(function(item){
    item.addEventListener("click", function(){
      bvSidebar.querySelectorAll(".bv-side-item").forEach(function(x){ x.classList.remove("active"); });
      item.classList.add("active");
      renderSection(item.dataset.bv);
    });
  });

  // Event delegation dùng chung cho cả 2 kiểu nội dung (accordion / master-detail)
  // vì nội dung được render lại động mỗi khi đổi mục sidebar.
  bvPageList.addEventListener("click", function(e){
    var bv2Item = e.target.closest(".bv2-item");
    if(bv2Item){
      baochaySelectedIdx = parseInt(bv2Item.dataset.idx, 10);
      bvPageList.querySelectorAll(".bv2-item").forEach(function(x){ x.classList.remove("active"); });
      bv2Item.classList.add("active");
      document.getElementById("bv2Detail").innerHTML = renderBaochayDetail(baochayRowsCache[baochaySelectedIdx]);
      return;
    }
    var pageHeader = e.target.closest(".bv-page-header");
    if(pageHeader){
      var pageItem = pageHeader.closest(".bv-page-item");
      var wasOpen = pageItem.classList.contains("open");
      pageItem.classList.toggle("open", !wasOpen);
      if(wasOpen){
        pageItem.querySelectorAll(".bv-sub.open").forEach(function(s){ s.classList.remove("open"); });
      }
      return;
    }
    var subHeader = e.target.closest(".bv-sub-header");
    if(subHeader){
      subHeader.closest(".bv-sub").classList.toggle("open");
    }
  });

  // Hiện sẵn mục 2 (báo cháy) — khớp trạng thái "active" mặc định trên sidebar.
  renderSection("baochay");
})();
