"use strict";
const fmt = n => Number(n).toLocaleString("vi-VN");
const nf1 = n => Number(n).toLocaleString("vi-VN",{minimumFractionDigits:1,maximumFractionDigits:1});
const nf2 = n => Number(n).toLocaleString("vi-VN",{minimumFractionDigits:2,maximumFractionDigits:2});
const R = (v, detail, canCu, notes) => ({ v, detail, canCu, notes: notes || [] });

const $ = id => document.getElementById(id);

const BADGE = { yes:'<span class="badge b-yes">BẮT BUỘC</span>', no:'<span class="badge b-no">KHÔNG BẮT BUỘC</span>', warn:'<span class="badge b-warn">⚠️ CẦN ĐỐI CHIẾU</span>', na:'<span class="badge b-na">KHÔNG NÊU</span>' };
const BADGE_TD = { yes:'<span class="badge b-yes">THUỘC DIỆN</span>', no:'<span class="badge b-no">KHÔNG THUỘC</span>', warn:'<span class="badge b-warn">⚠️ CẦN ĐỐI CHIẾU</span>', na:'<span class="badge b-na">CHƯA KẾT LUẬN</span>' };
const noteHtml = arr => arr && arr.length ? arr.map(n=>`<div class="note">${n}</div>`).join("") : "";
