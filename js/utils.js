"use strict";
const fmt = n => Number(n).toLocaleString("vi-VN");
const nf1 = n => Number(n).toLocaleString("vi-VN",{minimumFractionDigits:1,maximumFractionDigits:1});
const nf2 = n => Number(n).toLocaleString("vi-VN",{minimumFractionDigits:2,maximumFractionDigits:2});
const R = (v, detail, canCu, notes) => ({ v, detail, canCu, notes: notes || [] });

const $ = id => document.getElementById(id);

const BADGE = { yes:'<span class="badge b-yes">BẮT BUỘC</span>', no:'<span class="badge b-no">KHÔNG BẮT BUỘC</span>', warn:'<span class="badge b-warn">⚠️ CẦN ĐỐI CHIẾU</span>', na:'<span class="badge b-na">KHÔNG NÊU</span>' };
const BADGE_TD = { yes:'<span class="badge b-yes">THUỘC DIỆN</span>', no:'<span class="badge b-no">KHÔNG THUỘC</span>', warn:'<span class="badge b-warn">⚠️ CẦN ĐỐI CHIẾU</span>', na:'<span class="badge b-na">CHƯA KẾT LUẬN</span>' };
const noteHtml = arr => arr && arr.length ? arr.map(n=>`<div class="note">${n}</div>`).join("") : "";

// Canh bao trach nhiem chuyen mon thong nhat (Batch 3) - dung chung cho moi
// khu vuc hien ket qua thẩm dinh (tuvan-so-bo.js) va ket qua AI doc ban ve
// (ai-doc-ho-so.js). Cong cu la tro ly/ho tro tham khao, khong co quyen
// thẩm dinh/phe duyet - trach nhiem chuyen mon cuoi cung thuoc ky su PCCC.
const PCCC_DISCLAIMER = "Kết quả từ công cụ chỉ mang tính hỗ trợ tham khảo trong quá trình rà soát hồ sơ. Kết luận, thẩm định và trách nhiệm chuyên môn cuối cùng thuộc về kỹ sư PCCC.";
