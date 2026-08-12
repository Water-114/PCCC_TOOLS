"use strict";
(function(){
  const q = id => document.getElementById(id);

  /* ---- Điều hướng: tab chính + 2 cấp subnav ---- */
  const subCongcu = q("subnav-congcu");
  const subKhi = q("subnav-khi");
  function syncKhiSubnav(){
    // subnav-khi chỉ hiện khi đang ở view congcu VÀ chọn loại "khi"
    const congcuActive = q("view-congcu").classList.contains("active");
    const khiCalcActive = q("calc-khi").classList.contains("active");
    subKhi.hidden = !(congcuActive && khiCalcActive);
  }
  document.querySelectorAll(".tab").forEach(t=>{
    t.addEventListener("click", ()=>{
      document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
      t.classList.add("active");
      const v=t.dataset.view;
      document.querySelectorAll(".view").forEach(x=>x.classList.remove("active"));
      q("view-"+v).classList.add("active");
      subCongcu.hidden = (v!=="congcu");
      syncKhiSubnav();
      window.scrollTo({top:0,behavior:"smooth"});
    });
  });
  /* ---- Chọn loại hình tính (nước / khí / bọt) ---- */
  subCongcu.querySelectorAll(".subtab").forEach(t=>{
    t.addEventListener("click", ()=>{
      subCongcu.querySelectorAll(".subtab").forEach(x=>x.classList.remove("active"));
      t.classList.add("active");
      const c=t.dataset.calc;
      document.querySelectorAll(".calc-panel").forEach(x=>x.classList.remove("active"));
      q("calc-"+c).classList.add("active");
      syncKhiSubnav();
      window.scrollTo({top:0,behavior:"smooth"});
    });
  });
  /* ---- Chọn loại khí (Sol-khí / CO₂ / FM200 / IG) ---- */
  subKhi.querySelectorAll(".subtab").forEach(t=>{
    t.addEventListener("click", ()=>{
      if(t.disabled) return;
      subKhi.querySelectorAll(".subtab").forEach(x=>x.classList.remove("active"));
      t.classList.add("active");
      const g=t.dataset.gas;
      document.querySelectorAll(".gas-panel").forEach(x=>x.classList.remove("active"));
      q("gas-"+g).classList.add("active");
      window.scrollTo({top:0,behavior:"smooth"});
    });
  });
})();
