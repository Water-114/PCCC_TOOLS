"use strict";
/* =====================================================================
   MODULE TÍNH KHÍ CHỮA CHÁY
   Công thức: Sol-khí m=d₁·f₂·V (TCVN 13333) · CO₂ m=K_B(0,2A+0,7V) (TCVN 6101)
   · FM200/Novec m=V·(1/S)·c/(100−c), S=k₁+k₂T (TCVN 7161-9/6)
   ===================================================================== */
(function(){
  const q = id => document.getElementById(id);
  function nf(x, dec){ return (x===null||x===undefined||isNaN(x)) ? "—" : x.toLocaleString("vi-VN",{minimumFractionDigits:dec,maximumFractionDigits:dec}); }
  function val(id){ const el=q(id); if(!el) return null; const v=el.value.trim(); if(v==="") return null; const n=Number(v.replace(",",".")); return isNaN(n)?null:n; }
  function showMsg(id,html){ const m=q(id); m.innerHTML=html; m.classList.add("show"); }
  function hideMsg(id){ q(id).classList.remove("show"); }
  const row = (l,v)=>`<div class="res-row"><span class="lbl">${l}</span><span class="val">${v}</span></div>`;
  function renderResult(id, rowsHtml, finalLbl, finalVal){
    q(id).innerHTML = `<div class="rhead">Kết quả tính toán</div><div class="rbody">${rowsHtml}</div>`
      + (finalLbl?`<div class="res-final"><span class="lbl">${finalLbl}</span><span class="val">${finalVal}</span></div>`:"");
    q(id).classList.add("show");
    q(id).scrollIntoView({behavior:"smooth",block:"nearest"});
  }

  /* ---- Kho kệ cao (TCVN 14496) trong tab Công cụ tính toán > Chữa cháy bằng nước ---- */
  q("chkKeCaoNuoc").addEventListener("change", ()=>{
    q("keCaoNuocBox").style.display = q("chkKeCaoNuoc").checked ? "" : "none";
  });
  q("kc-phuongAn").addEventListener("change", ()=>{
    const isA = q("kc-phuongAn").value==="1tang";
    q("kc-modeA").style.display = isA ? "" : "none";
    q("kc-modeB").style.display = isA ? "none" : "";
  });
  q("kc-tinh").addEventListener("click", ()=>{
    const pa = q("kc-phuongAn").value;
    let res, muc, chiTiet="";
    if(pa==="1tang"){
      const g=q("kc-nhom").value, h=val("kc-h"), H=val("kc-H"), N=val("kc-N");
      if(h===null||H===null){ showMsg("kc-msg","Nhập đủ chiều cao xếp hàng h và chiều cao gian phòng H."); q("kc-ketqua").style.display="none"; return; }
      const q55 = g==="5"?5.3:6.5;
      if(H>14){ showMsg("kc-msg","H = "+nf(H,1)+" m > 14 m — vượt phạm vi Điều 5. Chuyển sang phương án nhiều tầng đầu phun."); q("kc-ketqua").style.display="none"; return; }
      if(h>12.5){ showMsg("kc-msg","h = "+nf(h,1)+" m > 12,5 m — vượt phạm vi Điều 5. Chuyển sang phương án nhiều tầng đầu phun."); q("kc-ketqua").style.display="none"; return; }
      if(h<5.5){ showMsg("kc-msg","h = "+nf(h,1)+" m ≤ 5,5 m — không thuộc TCVN 14496, dùng TCVN 7336 thông thường."); q("kc-ketqua").style.display="none"; return; }
      hideMsg("kc-msg");
      const psi = H<=6.4?0:0.06;
      const qcd = (q55+0.19*(h-5.5))*(1+psi*(H-10));
      if(N===null){
        res = { Q:qcd, t:60 };
        chiTiet = "qcđ = ["+nf(q55,1)+" + 0,19×("+nf(h,1)+"−5,5)] × [1 + "+psi+"×("+nf(H,1)+"−10)] = <b>"+nf(qcd,2)+" L/s</b> (1 đầu phun chủ đạo — chưa nhân số đầu phun N)";
      } else {
        const Qs = qcd*N;
        res = { Q:Qs, t:60 };
        chiTiet = "qcđ = "+nf(qcd,2)+" L/s × N = "+nf(N,0)+" đầu phun → Qs = <b>"+nf(Qs,2)+" L/s</b>";
      }
      muc = "TCVN 14496:2025, Điều 5.6–5.10 (1 tầng đầu phun)";
    } else {
      const A_MAP={phang:9,hop:12,hopkimloai:8};
      const I_MAP={ranco:{le2:0.24,tu2den3:0.36,tu3den45:0.5},khongchay:{le2:0.20,tu2den3:0.30,tu3den45:0.4},caosu:{le2:0.40,tu2den3:0.60,tu3den45:0.8}};
      const A=A_MAP[q("kc-pallet").value], B=val("kc-B"), n=val("kc-n"), i=I_MAP[q("kc-hang").value][q("kc-dai").value];
      const h2=val("kc-h2"), Smai=val("kc-Smai")??90;
      if(B===null||n===null||h2===null){ showMsg("kc-msg","Nhập đủ chiều rộng kệ B, số tấm chắn n và chiều cao xếp hàng h."); q("kc-ketqua").style.display="none"; return; }
      if(h2<5.5||h2>25){ showMsg("kc-msg","h = "+nf(h2,1)+" m ngoài phạm vi 5,5–25 m của TCVN 14496."); q("kc-ketqua").style.display="none"; return; }
      hideMsg("kc-msg");
      const Qi = A*B*n*i;
      const iD = h2<=16?0.12:0.18;
      const Qd = iD*Smai;
      const Qs = Qi+Qd;
      res = { Q:Qs, t:60 };
      chiTiet = "Qi = A×B×n×i = "+A+"×"+nf(B,1)+"×"+nf(n,0)+"×"+nf(i,2)+" = "+nf(Qi,2)+" L/s<br>Qd = i_D×S_d = "+nf(iD,2)+"×"+nf(Smai,0)+" = "+nf(Qd,2)+" L/s<br>Qs = Qi + Qd = <b>"+nf(Qs,2)+" L/s</b>";
      muc = "TCVN 14496:2025, Điều 6.10–6.13 (nhiều tầng đầu phun)";
    }
    q("kc-ketqua").innerHTML = chiTiet + `<div style="font-family:var(--mono);font-size:11.5px;color:var(--ink-soft);margin-top:6px">Nguồn: ${muc} · Thời gian cấp nước tối thiểu 60 phút (Điều 4.8)</div>`;
    q("kc-ketqua").style.display = "";
    q("n-sp-q").value = res.Q.toFixed(2);
    q("n-sp-t").value = res.t;
  });

  /* ---- TÍNH NƯỚC: V = Q × t × 60 ---- */
  q("frm-nuoc").addEventListener("submit", e=>{
    e.preventDefault();
    const htnN=val("n-htn-n")??0, htnQ=val("n-htn-q")??0, htnT=val("n-htn-t")??0;
    const spQ=val("n-sp-q")??0, spT=val("n-sp-t")??0;
    const nnQ=val("n-nn-q")??0, nnT=val("n-nn-t")??0;
    const Qtn=htnN*htnQ, Vtn=Qtn*htnT*60;
    const Vsp=spQ*spT*60;
    const Vnn=nnQ*nnT*60;
    const Vtong=Vtn+Vsp+Vnn;
    if(Vtong<=0){ showMsg("n-msg","Chưa nhập đủ dữ liệu cho hệ thống nào — nhập ít nhất 1 hệ thống có lưu lượng và thời gian > 0."); q("n-res").classList.remove("show"); return; }
    hideMsg("n-msg");
    const m3 = v => nf(v/1000,2)+" m³";
    let rows="";
    if(Vtn>0) rows+=row("Họng trong nhà: "+nf(htnN,0)+" tia × "+nf(htnQ,1)+" L/s = "+nf(Qtn,1)+" L/s × "+nf(htnT,0)+"′", m3(Vtn));
    if(Vsp>0) rows+=row("Chữa cháy tự động: "+nf(spQ,1)+" L/s × "+nf(spT,0)+"′", m3(Vsp));
    if(Vnn>0) rows+=row("Ngoài nhà: "+nf(nnQ,1)+" L/s × "+nf(nnT,0)+"′", m3(Vnn));
    renderResult("n-res", rows, "Tổng dung tích bể nước", nf(Vtong/1000,2)+" m³");
  });

  /* ---- TÍNH BỌT: Q_ct = S_c·J_ct ; W_dd = K·Q_ct·t·60 ---- */
  const BOT_DEFAULT = { thap:{J:0.2,t:20,K:2}, tb:{J:0.25,t:10,K:3} };
  q("b-noden").addEventListener("change", ()=>{
    const d=BOT_DEFAULT[q("b-noden").value];
    q("b-j").value=d.J; q("b-t").value=d.t; q("b-k").value=d.K;
  });
  q("frm-bot").addEventListener("submit", e=>{
    e.preventDefault();
    const Sc=val("b-sc"), J=val("b-j"), t=val("b-t"), K=val("b-k"), CB=Number(q("b-cb").value);
    const errs=[];
    if(Sc===null||Sc<=0) errs.push("S_c (> 0)");
    if(J===null||J<=0) errs.push("J_ct (> 0)");
    if(t===null||t<=0) errs.push("t (> 0)");
    if(K===null||K<1) errs.push("K (≥ 1)");
    if(errs.length){ showMsg("b-msg","<b>Thiếu/sai dữ liệu:</b> "+errs.join("; ")+"."); q("b-res").classList.remove("show"); return; }
    hideMsg("b-msg");
    const Qct = Sc*J;                    // L/s — lưu lượng dung dịch
    const Wdd = K*Qct*t*60;              // lít — lượng dung dịch dự trữ (đã gồm hệ số K)
    const Wctb = Wdd*CB/100;             // lít — chất tạo bọt đậm đặc
    const Wnuoc = Wdd*(100-CB)/100;      // lít — nước
    const m3 = v => nf(v/1000,2)+" m³";
    renderResult("b-res",
      row("Lưu lượng dung dịch Q_ct = S_c × J_ct", nf(Qct,2)+" L/s")+
      row("Cường độ phun J_ct", nf(J,2)+" L/s·m²")+
      row("Thời gian phun t", nf(t,0)+" phút")+
      row("Hệ số dự trữ K", nf(K,1))+
      row("Lượng dung dịch W_dd = K·Q_ct·t·60", m3(Wdd)+" ("+nf(Wdd,0)+" L)")+
      row("→ Chất tạo bọt đậm đặc (C_B = "+nf(CB,0)+"%)", nf(Wctb,0)+" L")+
      row("→ Nước pha ("+nf(100-CB,0)+"%)", m3(Wnuoc)),
      "Tổng dung dịch bọt cần dự trữ", m3(Wdd));
  });

  /* ---- SOL-KHÍ: m = d₁ × f₂ × V ---- */
  q("frm-solkhi").addEventListener("submit", e=>{
    e.preventDefault();
    const d1=val("sk-d1"), f2=val("sk-f2"), V=val("sk-v");
    const errs=[];
    if(d1===null||d1<=0) errs.push("d₁ (> 0)");
    if(f2===null||f2<1) errs.push("f₂ (≥ 1)");
    if(V===null||V<=0) errs.push("V (> 0)");
    if(errs.length){ showMsg("sk-msg","<b>Thiếu/sai dữ liệu:</b> "+errs.join("; ")+"."); q("sk-res").classList.remove("show"); return; }
    hideMsg("sk-msg");
    const m=d1*f2*V;
    renderResult("sk-res",
      row("Nồng độ thiết kế d₁", nf(d1,2)+" g/m³")+
      row("Yếu tố thiết kế bổ sung f₂", nf(f2,2))+
      row("Thể tích bảo vệ V", nf(V,2)+" m³")+
      row("Khối lượng m = d₁ × f₂ × V", nf(m,1)+" g"),
      "Khối lượng chất Sol-khí", nf(m/1000,3)+" kg");
  });

  /* ---- CO₂: m = K_B(0,2A + 0,7V) ---- */
  q("frm-co2").addEventListener("submit", e=>{
    e.preventDefault();
    const KB=val("co2-kb"), AV=val("co2-av"), AOV=val("co2-aov")??0, VV=val("co2-vv"), VZ=val("co2-vz")??0, VG=val("co2-vg")??0;
    const errs=[];
    if(KB===null||KB<1) errs.push("K_B (≥ 1)");
    if(AV===null||AV<=0) errs.push("A_V (> 0)");
    if(VV===null||VV<=0) errs.push("V_V (> 0)");
    if(errs.length){ showMsg("co2-msg","<b>Thiếu/sai dữ liệu:</b> "+errs.join("; ")+"."); q("co2-res").classList.remove("show"); return; }
    const A=AV+30*AOV, V=VV+VZ-VG;
    if(V<=0){ showMsg("co2-msg","Thể tích tính toán V = V_V + V_Z − V_G ≤ 0 — kiểm tra lại V_G."); q("co2-res").classList.remove("show"); return; }
    hideMsg("co2-msg");
    const m=KB*(0.2*A+0.7*V);
    renderResult("co2-res",
      row("A = A_V + 30·A_OV", nf(A,2)+" m²")+
      row("V = V_V + V_Z − V_G", nf(V,2)+" m³")+
      row("Hệ số vật liệu K_B", nf(KB,2))+
      row("Khối lượng tính toán m = K_B·(0,2A + 0,7V)", nf(m,2)+" kg")+
      row("Lượng dự trữ bắt buộc (100%)", nf(m,2)+" kg"),
      "Tổng lượng CO₂ (gồm dự trữ)", nf(2*m,2)+" kg");
  });

  /* ---- FM200 / Novec: m = V·(1/S)·c/(100−c), S = k₁ + k₂·T ---- */
  const KGAS = { hfc:{k1:0.1269,k2:0.000513,ten:"HFC-227ea (FM200)"}, fk:{k1:0.0664,k2:0.000274,ten:"FK-5-1-12 (Novec 1230)"} };
  q("frm-fm200").addEventListener("submit", e=>{
    e.preventDefault();
    const gas=q("fm-gas").value, T=val("fm-t"), c=val("fm-c"), V=val("fm-v");
    const errs=[];
    if(T===null) errs.push("T");
    if(c===null||c<=0||c>=100) errs.push("c (0 < c < 100)");
    if(V===null||V<=0) errs.push("V (> 0)");
    if(errs.length){ showMsg("fm-msg","<b>Thiếu/sai dữ liệu:</b> "+errs.join("; ")+"."); q("fm-res").classList.remove("show"); return; }
    hideMsg("fm-msg");
    const k=KGAS[gas], S=k.k1+k.k2*T, mv=(1/S)*(c/(100-c)), m=mv*V;
    renderResult("fm-res",
      row("Loại khí", k.ten)+
      row("Thể tích riêng S = k₁ + k₂·T", nf(S,4)+" m³/kg")+
      row("Nồng độ thiết kế c", nf(c,1)+" %")+
      row("Lượng khí trên 1 m³ (m/V)", nf(mv,4)+" kg/m³")+
      row("Thể tích bảo vệ V", nf(V,2)+" m³"),
      "Khối lượng khí "+(gas==="hfc"?"FM200":"Novec 1230"), nf(m,2)+" kg");
  });

  /* ---- Reset ---- */
  document.querySelectorAll("[data-reset]").forEach(b=>{
    b.addEventListener("click", ()=>{
      const g=b.dataset.reset;
      if(g==="nuoc"){ q("frm-nuoc").reset(); q("n-nn-t").value="180"; hideMsg("n-msg"); q("n-res").classList.remove("show"); q("keCaoNuocBox").style.display="none"; q("kc-ketqua").style.display="none"; hideMsg("kc-msg"); q("kc-modeA").style.display=""; q("kc-modeB").style.display="none"; q("kc-Smai").value="90"; }
      if(g==="bot"){ q("frm-bot").reset(); q("b-noden").value="thap"; q("b-j").value="0.2"; q("b-t").value="20"; q("b-k").value="2"; q("b-cb").value="3"; hideMsg("b-msg"); q("b-res").classList.remove("show"); }
      if(g==="solkhi"){ q("frm-solkhi").reset(); q("sk-f2").value="1.0"; hideMsg("sk-msg"); q("sk-res").classList.remove("show"); }
      if(g==="co2"){ q("frm-co2").reset(); q("co2-kb").value="1.0"; ["co2-aov","co2-vz","co2-vg"].forEach(id=>q(id).value="0"); hideMsg("co2-msg"); q("co2-res").classList.remove("show"); }
      if(g==="fm200"){ q("frm-fm200").reset(); q("fm-t").value="20"; hideMsg("fm-msg"); q("fm-res").classList.remove("show"); }
      if(g==="ig"){ q("frm-ig").reset(); q("ig-t").value="20"; hideMsg("ig-msg"); q("ig-res").classList.remove("show"); }
    });
  });

  /* ---- Khí IG (trơ): m = V × (1/S) × ln(100/(100−c)), S = k₁ + k₂T ---- */
  /* Hằng số từ ISO 14520 — đối chiếu lại TCVN 7161 khi có bản VN */
  const KIG = {
    ig541:{ k1:0.6598, k2:0.002011, ten:"IG-541 (Inergen)" },
    ig100:{ k1:0.7997, k2:0.002741, ten:"IG-100 (Nitơ)" },
    ig55: { k1:0.6816, k2:0.002280, ten:"IG-55 (Argonite)" },
    ig01: { k1:0.5685, k2:0.001902, ten:"IG-01 (Argon)" }
  };
  q("frm-ig").addEventListener("submit", e=>{
    e.preventDefault();
    const gas=q("ig-gas").value, T=val("ig-t"), c=val("ig-c"), V=val("ig-v");
    const errs=[];
    if(T===null) errs.push("T");
    if(c===null||c<=0||c>=100) errs.push("c (0 < c < 100)");
    if(V===null||V<=0) errs.push("V (> 0)");
    if(errs.length){ showMsg("ig-msg","<b>Thiếu/sai dữ liệu:</b> "+errs.join("; ")+"."); q("ig-res").classList.remove("show"); return; }
    hideMsg("ig-msg");
    const k=KIG[gas], S=k.k1+k.k2*T, lnVal=Math.log(100/(100-c)), mv=(1/S)*lnVal, m=mv*V;
    renderResult("ig-res",
      row("Loại khí", k.ten)+
      row("Thể tích riêng S = k₁ + k₂·T", nf(S,5)+" m³/kg")+
      row("Nồng độ thiết kế c", nf(c,1)+" %")+
      row("ln[100/(100−c)]", nf(lnVal,5))+
      row("Lượng khí trên 1 m³ (m/V)", nf(mv,4)+" kg/m³")+
      row("Thể tích bảo vệ V", nf(V,2)+" m³")+
      row("⚠️ Hằng số k₁,k₂ từ ISO 14520 — đối chiếu TCVN 7161", ""),
      "Khối lượng khí "+k.ten, nf(m,2)+" kg");
  });
})();
