"use strict";
/* =====================================================================
   TƯ VẤN SƠ BỘ PCCC — rule engine
   Nguồn ngưỡng: NĐ 105/2025 PL III; QCVN 10:2025/BCA PL A–G;
   TCVN 7435-1:2004; TCVN 13456:2022 (bảng dựng từ bản OCR — ô ⚠️ cần đối chiếu)
   Trạng thái kết luận: yes = THUỘC DIỆN | no = KHÔNG THUỘC | warn = CẦN ĐỐI CHIẾU ⚠️ | na = KHÔNG NÊU TRONG PHỤ LỤC
   ===================================================================== */


/* ---------- Danh mục công năng ---------- */
const OCCS = [
  { id:"chungcu",  label:"Chung cư / nhà ở tập thể / ký túc xá", binh:"tb" },
  { id:"nhatre",   label:"Nhà trẻ, mẫu giáo, mầm non", binh:"tb", extra:["kids"] },
  { id:"truonghoc",label:"Trường học (tiểu học → đại học, dạy nghề)", binh:"thap" },
  { id:"yte",      label:"Y tế (bệnh viện, phòng khám, điều dưỡng…)", binh:"tb", extra:["pplFloor"] },
  { id:"khachsan", label:"Khách sạn / nhà nghỉ / cơ sở lưu trú", binh:"tb" },
  { id:"truso",    label:"Trụ sở / văn phòng làm việc", binh:"thap" },
  { id:"honhop",   label:"Nhà hỗn hợp (đa công năng)", binh:"tb" },
  { id:"tttm",     label:"Chợ / trung tâm thương mại / siêu thị", binh:"tb" },
  { id:"cuahang",  label:"Cửa hàng điện máy / bách hóa / KD hàng dễ cháy", binh:"tb" },
  { id:"nhahang",  label:"Nhà hàng / cửa hàng ăn uống", binh:"tb" },
  { id:"karaoke",  label:"Karaoke / vũ trường", binh:"tb", extra:["pplFloor"] },
  { id:"vanhoa",   label:"Nhà văn hóa / trung tâm hội nghị / nhà đa năng", binh:"tb" },
  { id:"nhahat",   label:"Nhà hát / rạp chiếu phim / rạp xiếc", binh:"tb", extra:["seats","pplFloor"] },
  { id:"baotang",  label:"Bảo tàng / triển lãm / thư viện", binh:"tb" },
  { id:"thethao",  label:"Nhà thi đấu / nhà tập luyện thể thao", binh:"tb", extra:["seats"] },
  { id:"sanxuat",  label:"Nhà sản xuất (xưởng)", binh:"cao", extra:["hazard","pplFloor"] },
  { id:"kho",      label:"Nhà kho", binh:"cao", extra:["hazard"] },
  { id:"congnghiep_dacthu", label:"Công nghiệp đặc thù (lọc/hóa dầu, kho xăng dầu/khí hóa lỏng, nhà máy điện, trạm biến áp ≥110kV, vật liệu nổ/vũ khí)", binh:"cao" },
  { id:"garakin",  label:"Nhà để xe (gara) ô tô/xe máy", binh:"cao", extra:["garaKin"] },
  { id:"buudien",  label:"Bưu điện / viễn thông", binh:"thap" },
  { id:"nhaga",    label:"Nhà ga / bến xe / trạm dừng nghỉ", binh:"tb" },
  { id:"sanvandong",   label:"Sân vận động", binh:"thap", extra:["seats"] },
  { id:"hatangkt",     label:"Hạ tầng kỹ thuật đô thị / KCN / khu du lịch, đào tạo, thể dục thể thao", binh:"tb" },
  { id:"hamgiaothong", label:"Hầm đường ô tô / đường sắt / tàu điện ngầm", binh:"cao", extra:["tunnelLength"] },
  { id:"csohatnhan",   label:"Công trình thuộc cơ sở hạt nhân", binh:"cao" },
  { id:"phuongtiengt", label:"Phương tiện giao thông (thủy nội địa/tàu biển) chở khách/xăng dầu/chất dễ cháy/vật liệu nổ", binh:"cao", extra:["pplTransport","vesselGT","enginePower"] }
];

const EXTRA_FIELDS = {
  kids:    { label:"Số trẻ (cháu)", req:true,  ph:"VD: 120", hint:"Dữ liệu phân nhánh — bắt buộc với nhà trẻ" },
  seats:   { label:"Số chỗ ngồi / khán đài (chỗ)", req:true, ph:"VD: 350", hint:"Dữ liệu phân nhánh — bắt buộc với nhà hát / thể thao" },
  hazard:  { label:"Hạng nguy hiểm cháy nổ", req:true, select:[["","— Chọn hạng —"],["A","Hạng A"],["B","Hạng B"],["C","Hạng C"],["D","Hạng D"],["E","Hạng E"]], hint:"Dữ liệu phân nhánh — bắt buộc với nhà SX / kho" },
  pplFloor:{ label:"Số người lớn nhất trên 1 tầng (người)", req:false, ph:"VD: 60", hint:"Dùng xét loa thông báo (PL G) — bỏ trống nếu chưa rõ" },
  garaKin: { label:"Dạng nhà để xe", req:true, select:[["","— Chọn dạng —"],["kin","Dạng kín"],["ho","Dạng hở (không tường bao che ngoài)"]], hint:"Dữ liệu phân nhánh — quyết định ngưỡng theo Bảng A.1 mục 25 và Phụ lục B mục 3" },
  tunnelLength: { label:"Chiều dài hầm (m)", req:true, ph:"VD: 1200", hint:"Dữ liệu phân nhánh — bắt buộc với hầm giao thông (Phụ lục III, mục 14)" },
  pplTransport: { label:"Sức chở người (người)", req:false, ph:"VD: 60", hint:"Phương tiện đường thủy nội địa — điền nếu có, bỏ trống nếu không áp dụng" },
  vesselGT: { label:"Dung tích phương tiện (GT)", req:false, ph:"VD: 600", hint:"Tổng dung tích đăng ký theo pháp luật hàng hải — điền nếu có" },
  enginePower: { label:"Công suất máy chính (sức ngựa)", req:false, ph:"VD: 350", hint:"Điền nếu có, bỏ trống nếu không áp dụng" }
};

/* =====================================================================
   BƯỚC 1 — Diện thẩm định (Phụ lục III NĐ 105/2025)
   ===================================================================== */
function evalThamDinh(d){
  const F = d.totalArea, T = d.floors, V = d.volume;
  const cc = m => `Phụ lục III NĐ 105/2025, mục ${m}`;
  switch(d.occ){
    case "chungcu":
      return T>=7||F>=3000 ? R("yes",`Đạt ngưỡng: cao ≥ 7 tầng hoặc ΣF ≥ 3.000 m² (công trình: ${T} tầng, ΣF ${fmt(F)} m²).`,cc(1))
                           : R("no",`Chưa đạt ngưỡng cao ≥ 7 tầng và ΣF ≥ 3.000 m² (công trình: ${T} tầng, ΣF ${fmt(F)} m²).`,cc(1));
    case "nhatre":
      return d.kids>=150||F>=2000 ? R("yes",`Đạt ngưỡng: ≥ 150 cháu hoặc ΣF ≥ 2.000 m² (công trình: ${fmt(d.kids)} cháu, ΣF ${fmt(F)} m²).`,cc(2))
                                  : R("no",`Chưa đạt ngưỡng ≥ 150 cháu và ΣF ≥ 2.000 m² (công trình: ${fmt(d.kids)} cháu, ΣF ${fmt(F)} m²).`,cc(2));
    case "truonghoc":
      return T>=5||F>=3000 ? R("yes",`Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 3.000 m².`,cc(2)) : R("no",`Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 3.000 m².`,cc(2));
    case "yte":
      return T>=5||F>=2000 ? R("yes",`Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 2.000 m².`,cc(3)) : R("no",`Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 2.000 m².`,cc(3));
    case "thethao":
      return d.seats>=5000||F>=5000 ? R("yes",`Đạt ngưỡng: khán đài ≥ 5.000 chỗ hoặc ΣF ≥ 5.000 m².`,cc(4)) : R("no",`Chưa đạt ngưỡng khán đài ≥ 5.000 chỗ và ΣF ≥ 5.000 m².`,cc(4));
    case "nhahat":
      return d.seats>=300 ? R("yes",`Đạt ngưỡng: ≥ 300 chỗ ngồi (công trình: ${fmt(d.seats)} chỗ).`,cc(5)) : R("no",`Chưa đạt ngưỡng ≥ 300 chỗ ngồi (công trình: ${fmt(d.seats)} chỗ).`,cc(5));
    case "vanhoa": case "baotang":
      return T>=5||F>=3000 ? R("yes",`Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 3.000 m².`,cc(5)) : R("no",`Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 3.000 m².`,cc(5));
    case "karaoke":
      return T>=4||F>=1000 ? R("yes",`Đạt ngưỡng: cao ≥ 4 tầng hoặc ΣF ≥ 1.000 m².`,cc(5)) : R("no",`Chưa đạt ngưỡng cao ≥ 4 tầng và ΣF ≥ 1.000 m².`,cc(5));
    case "tttm": case "cuahang":
      return F>=2000 ? R("yes",`Đạt ngưỡng: ΣF ≥ 2.000 m² (công trình: ${fmt(F)} m²).`,cc(6)) : R("no",`Chưa đạt ngưỡng ΣF ≥ 2.000 m² (công trình: ${fmt(F)} m²).`,cc(6));
    case "nhahang":
      return F>=3000 ? R("yes",`Đạt ngưỡng: ΣF ≥ 3.000 m² (công trình: ${fmt(F)} m²).`,cc(6))
                     : R("no",`Chưa đạt ngưỡng ΣF ≥ 3.000 m² (công trình: ${fmt(F)} m²).`,cc(6));
    case "khachsan": case "buudien": case "truso":
      return T>=7||F>=3000 ? R("yes",`Đạt ngưỡng: cao ≥ 7 tầng hoặc ΣF ≥ 3.000 m².`,cc(7)) : R("no",`Chưa đạt ngưỡng cao ≥ 7 tầng và ΣF ≥ 3.000 m².`,cc(7));
    case "honhop":
      return T>=7||F>=3000 ? R("yes",`Đạt ngưỡng: cao ≥ 7 tầng hoặc ΣF ≥ 3.000 m².`,cc(8),["Nhà hỗn hợp: nếu có phần công năng thuộc mục 1–7 PL III thì cũng thuộc diện — cần kỹ sư xét riêng từng phần công năng."])
                           : R("warn",`Chưa đạt ngưỡng cao ≥ 7 tầng / ΣF ≥ 3.000 m² xét theo tổng thể — NHƯNG nếu có phần công năng thuộc mục 1–7 PL III thì vẫn thuộc diện. Cần kỹ sư xét riêng từng phần công năng.`,cc(8));
    case "congnghiep_dacthu":
      return R("yes","Thuộc mục 9a/9b/9c Phụ lục III NĐ 105/2025 (nhà máy lọc dầu/hóa dầu/lọc-hóa dầu/chế biến khí/nhiên liệu sinh học, kho dầu mỏ-sản phẩm dầu mỏ, kho khí hóa lỏng, trạm chiết khí hóa lỏng, trạm phân phối khí, cửa hàng/trạm cấp xăng dầu ≥ 1 cột bơm; HOẶC nhà máy điện, trạm biến áp ≥ 110 kV; HOẶC nhà máy/kho vật liệu nổ, tiền chất thuốc nổ công nghiệp, vũ khí, công cụ hỗ trợ): bắt buộc thẩm định, KHÔNG phụ thuộc quy mô.",cc("9a/9b/9c"));
    case "sanxuat":
      if(d.hazard==="A"||d.hazard==="B")
        return V>=7000||F>=1000 ? R("yes",`Đạt ngưỡng hạng A, B: V ≥ 7.000 m³ hoặc ΣF ≥ 1.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc("9d"))
                                : R("no",`Chưa đạt ngưỡng hạng A, B: V ≥ 7.000 m³ và ΣF ≥ 1.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc("9d"));
      if(d.hazard==="C")
        return V>=15000||F>=2000 ? R("yes",`Đạt ngưỡng hạng C: V ≥ 15.000 m³ hoặc ΣF ≥ 2.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc("9d"))
                                 : R("no",`Chưa đạt ngưỡng hạng C: V ≥ 15.000 m³ và ΣF ≥ 2.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc("9d"));
      return V>=30000||F>=10000 ? R("yes",`Đạt ngưỡng hạng D, E: V ≥ 30.000 m³ hoặc ΣF ≥ 10.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc("9d"))
                                : R("no",`Chưa đạt ngưỡng hạng D, E: V ≥ 30.000 m³ và ΣF ≥ 10.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc("9d"));
    case "kho":
      if(["A","B","C"].includes(d.hazard))
        return V>=15000||F>=2000 ? R("yes",`Kho hạng ${d.hazard}: đạt ngưỡng V ≥ 15.000 m³ hoặc ΣF ≥ 2.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc(10))
                                 : R("no",`Kho hạng ${d.hazard}: chưa đạt ngưỡng V ≥ 15.000 m³ và ΣF ≥ 2.000 m² (công trình: V ${fmt(V)} m³, ΣF ${fmt(F)} m²).`,cc(10));
      return R("no",`Kho hạng ${d.hazard}: mục 10 PL III chỉ áp dụng kho hạng A, B, C.`,cc(10));
    case "garakin":
      return F>=2000 ? R("yes",`Đạt ngưỡng: ΣF ≥ 2.000 m².`,cc(12)) : R("no",`Chưa đạt ngưỡng ΣF ≥ 2.000 m².`,cc(12));
    case "nhaga":
      return F>=3000 ? R("yes",`Đạt ngưỡng: ΣF ≥ 3.000 m² (một số loại xét theo cấp công trình — kiểm tra thêm).`,cc(13)) : R("no",`Chưa đạt ngưỡng ΣF ≥ 3.000 m² (một số loại xét theo cấp công trình — kiểm tra thêm).`,cc(13));
    case "sanvandong":
      return d.seats>=5000 ? R("yes",`Đạt ngưỡng: khán đài ≥ 5.000 chỗ (công trình: ${fmt(d.seats)} chỗ).`,cc(4)) : R("no",`Chưa đạt ngưỡng khán đài ≥ 5.000 chỗ (công trình: ${fmt(d.seats)} chỗ).`,cc(4));
    case "hatangkt":
      return R("yes","Hạ tầng kỹ thuật của khu đô thị, khu nhà ở, khu công nghiệp, cụm công nghiệp, khu du lịch, khu nghiên cứu, đào tạo, khu thể dục, thể thao: bắt buộc thẩm định, không phụ thuộc quy mô.",cc(11),
        ["Các bước tính toán hệ thống PCCC (BƯỚC 2 trở đi) của công cụ này được xây dựng cho công trình xây dựng thông thường — hạ tầng kỹ thuật đô thị/KCN cần tra cứu riêng theo quy chuẩn/tiêu chuẩn hạ tầng chuyên ngành tương ứng."]);
    case "hamgiaothong":
      return d.tunnelLength>=1000 ? R("yes",`Đạt ngưỡng: chiều dài ≥ 1.000 m (công trình: ${fmt(d.tunnelLength)} m).`,cc(14),
          ["Các bước tính toán hệ thống PCCC (BƯỚC 2 trở đi) của công cụ này được xây dựng cho công trình xây dựng thông thường — hầm giao thông cần tra cứu riêng theo quy chuẩn/tiêu chuẩn hầm chuyên ngành."])
        : R("no",`Chưa đạt ngưỡng chiều dài ≥ 1.000 m (công trình: ${fmt(d.tunnelLength)} m).`,cc(14));
    case "csohatnhan":
      return R("yes","Công trình thuộc cơ sở hạt nhân: bắt buộc thẩm định, không phụ thuộc quy mô.",cc(15),
        ["Công trình hạt nhân chịu quản lý chuyên ngành riêng — các bước tính toán hệ thống PCCC (BƯỚC 2 trở đi) của công cụ này không thay thế được quy chuẩn/tiêu chuẩn chuyên ngành hạt nhân."]);
    case "phuongtiengt":
      return (d.pplTransport>=50 || d.vesselGT>=500 || d.enginePower>=300)
        ? R("yes",`Đạt ngưỡng: sức chở ≥ 50 người, hoặc ≥ 500 GT, hoặc công suất máy chính ≥ 300 sức ngựa (phương tiện: ${fmt(d.pplTransport||0)} người, ${fmt(d.vesselGT||0)} GT, ${fmt(d.enginePower||0)} sức ngựa).`,cc(16),
            ["Phương tiện giao thông không phải công trình xây dựng — các bước tính toán hệ thống PCCC (BƯỚC 2 trở đi) của công cụ này không áp dụng, cần tra cứu riêng theo quy định PCCC phương tiện giao thông."])
        : R("no",`Chưa đạt ngưỡng sức chở ≥ 50 người, ≥ 500 GT, và công suất máy chính ≥ 300 sức ngựa (phương tiện: ${fmt(d.pplTransport||0)} người, ${fmt(d.vesselGT||0)} GT, ${fmt(d.enginePower||0)} sức ngựa).`,cc(16));
  }
  return R("na","Không xác định được nhóm công năng.","—");
}

/* =====================================================================
   BƯỚC 2 — Hệ thống bắt buộc theo QCVN 10:2025/BCA
   ===================================================================== */
function evalBaoChay(d){
  const F=d.totalArea,T=d.floors,H=d.hFire,B=(d.basements>0||d.semiBasements>0);
  const cc = s => `QCVN 10:2025/BCA, Bảng A.1, STT ${s}`;
  switch(d.occ){
    case "chungcu": return T>=5||F>=700 ? R("yes","Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 700 m².",cc(3),[T<5&&F<1500?"Cho phép dùng thiết bị báo cháy độc lập khi < 5 tầng và < 1.500 m².":""].filter(Boolean)) : R("no","Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 700 m².",cc(3));
    case "nhatre":  return d.kids>=100||F>=300 ? R("yes","Đạt ngưỡng: ≥ 100 cháu hoặc ΣF ≥ 300 m².",cc(4),[F<500?"Cho phép thiết bị báo cháy độc lập khi ΣF < 500 m².":""].filter(Boolean)) : R("no","Chưa đạt ngưỡng ≥ 100 cháu và ΣF ≥ 300 m².",cc(4));
    case "truonghoc": return T>=5||F>=1500 ? R("yes","Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 1.500 m².",cc(5)) : R("no","Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 1.500 m².",cc(5));
    case "yte":     return T>=3||F>=300 ? R("yes","Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 300 m².",cc(6)) : R("no","Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 300 m².",cc(6));
    case "thethao": return F>=500||d.seats>=200 ? R("yes","Đạt ngưỡng: ΣF ≥ 500 m² hoặc khán đài ≥ 200 chỗ.",cc(8)) : R("no","Chưa đạt ngưỡng ΣF ≥ 500 m² và khán đài ≥ 200 chỗ.",cc(8));
    case "nhahat":  return F>=500 ? R("yes","Đạt ngưỡng: ΣF ≥ 500 m².",cc(9)) : R("no","Chưa đạt ngưỡng ΣF ≥ 500 m².",cc(9));
    case "baotang":
      if(B) return R("yes","Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.",cc("11.1"));
      return T>=3 ? R("yes","Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.",cc("11.2.2"))
                  : (F>=500 ? R("yes","1–2 tầng: đạt ngưỡng ΣF ≥ 500 m².",cc("11.2.1")) : R("no","1–2 tầng: chưa đạt ngưỡng ΣF ≥ 500 m².",cc("11.2.1")));
    case "vanhoa":  return T>=5||F>=500 ? R("yes","Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 500 m².",cc(12)) : R("no","Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 500 m².",cc(12));
    case "karaoke": return R("yes","Bắt buộc, không phụ thuộc diện tích (mọi trường hợp karaoke/vũ trường).",cc(13));
    case "tttm":    return R("yes","Bắt buộc, không phụ thuộc diện tích.",cc(15));
    case "nhahang": return F>=500 ? R("yes","Đạt ngưỡng: ΣF ≥ 500 m².",cc(16),[T<3&&F<1500?"Cho phép thiết bị báo cháy độc lập khi < 3 tầng và < 1.500 m².":""].filter(Boolean)) : R("no","Chưa đạt ngưỡng ΣF ≥ 500 m².",cc(16));
    case "cuahang":
      if(B) return R("yes","Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.",cc("17.1"));
      return T>=3||F>=300 ? R("yes","Trên mặt đất: đạt ngưỡng cao ≥ 3 tầng hoặc ΣF ≥ 300 m².",cc("17.2"),["Nhà KD chất lỏng cháy/dễ cháy (trừ can, bình ≤ 20 lít): bắt buộc không phụ thuộc diện tích (STT 17.3)."]) : R("no","Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 300 m².",cc("17.2"),["Nhà KD chất lỏng cháy/dễ cháy (trừ can, bình ≤ 20 lít): bắt buộc không phụ thuộc diện tích (STT 17.3)."]);
    case "khachsan":return T>=3||F>=700 ? R("yes","Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 700 m².",cc(18),[T<5&&F<1500?"Cho phép thiết bị báo cháy độc lập khi < 5 tầng và < 1.500 m².":""].filter(Boolean)) : R("no","Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 700 m².",cc(18));
    case "buudien": return T>=3||F>=500 ? R("yes","Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 500 m².",cc(19)) : R("no","Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 500 m².",cc(19));
    case "truso":   return T>=5||F>=500 ? R("yes","Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 500 m².",cc(20),[T<5&&F<1500?"Cho phép thiết bị báo cháy độc lập khi < 5 tầng và < 1.500 m².":""].filter(Boolean)) : R("no","Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 500 m².",cc(20));
    case "honhop":  return T>=3||F>=500 ? R("yes","Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 500 m².",cc(21)) : R("no","Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 500 m².",cc(21));
    case "nhaga":   return F>=500 ? R("yes","Đạt ngưỡng: ΣF ≥ 500 m².",cc(22)) : R("no","Chưa đạt ngưỡng ΣF ≥ 500 m².",cc(22));
    case "garakin":
      if(B||T>=2) return R("yes","Dạng kín có tầng hầm/bán hầm hoặc trên mặt đất ≥ 2 tầng: bắt buộc, không phụ thuộc diện tích.",cc("25.1"));
      if(d.garaKinVal==="ho"){
        return d.garaKC12==="le12" ? (F>=4000||T>=4 ? R("yes","Dạng hở, khoảng cách đến cạnh để hở ≤ 12 m: đạt ngưỡng ΣF ≥ 4.000 m² hoặc cao ≥ 4 tầng.",cc("25.3.1")) : R("no","Dạng hở, khoảng cách ≤ 12 m: chưa đạt ngưỡng ΣF ≥ 4.000 m² và cao ≥ 4 tầng.",cc("25.3.1")))
          : R("yes","Dạng hở, khoảng cách đến cạnh để hở > 12 m: bắt buộc, không phụ thuộc diện tích.",cc("25.3.2"));
      }
      /* Dạng kín, 1 tầng nổi trên mặt đất — theo bậc chịu lửa & cấp kết cấu S */
      const b=d.garaBcl, s=d.garaCapS;
      if((b==="I"||b==="II"||b==="III")&&s==="S0") return F>=2000 ? R("yes","Bậc I/II/III, cấp S0: đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.1")) : R("no","Bậc I/II/III, cấp S0: chưa đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.1"));
      if((b==="I"||b==="II"||b==="III")&&s==="S1") return F>=2000 ? R("yes","Bậc I/II/III, cấp S1: đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.2")) : R("no","Bậc I/II/III, cấp S1: chưa đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.2"));
      if((b==="IV"||b==="V")&&s==="S0") return F>=1000 ? R("yes","Bậc IV/V, cấp S0: đạt ngưỡng ΣF ≥ 1.000 m².",cc("25.2.3")) : R("no","Bậc IV/V, cấp S0: chưa đạt ngưỡng ΣF ≥ 1.000 m².",cc("25.2.3"));
      if((b==="IV"||b==="V")&&s==="S1") return F>=2000 ? R("yes","Bậc IV/V, cấp S1: đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.4")) : R("no","Bậc IV/V, cấp S1: chưa đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.4"));
      if((b==="IV"||b==="V")&&(s==="S2"||s==="S3")) return F>=1000 ? R("yes","Bậc IV/V, cấp S2/S3: đạt ngưỡng ΣF ≥ 1.000 m².",cc("25.2.5")) : R("no","Bậc IV/V, cấp S2/S3: chưa đạt ngưỡng ΣF ≥ 1.000 m².",cc("25.2.5"));
      return R("warn","Dạng kín 1 tầng nổi: cần bổ sung bậc chịu lửa, cấp kết cấu S (hoặc dạng hở/khoảng cách cạnh hở) để tra đúng mục 25.2/25.3.",cc("25.2/25.3"));
    case "sanxuat": case "kho":
      return evalA3(d);
  }
  return R("na","—","—");
}

/* Bảng A.3 QCVN 10 — gian phòng SX/kho theo hạng nguy hiểm cháy nổ & vị trí (dùng chung cho báo cháy & chữa cháy, IS_CHUACHAY phân biệt cột) */
function evalA3(d, forSprinkler){
  const hz=d.hazard, F=d.areaFloor, B=(d.basements>0||d.semiBasements>0);
  const isKho = d.occ==="kho";
  const cc = s => `QCVN 10:2025/BCA, Bảng A.3, mục ${s}`;
  if(isKho){
    if(hz==="A"||hz==="B") return forSprinkler
      ? (F>=300?R("yes","Kho hạng A, B: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("1.1")):R("no","Kho hạng A, B: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("1.1")))
      : R("yes","Kho hạng A, B: bắt buộc báo cháy tự động, không phụ thuộc diện tích.",cc("1.1"));
    if(hz==="C"){
      if(B) return R("yes","Kho hạng C tại tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.",cc("1.4.1"));
      return forSprinkler
        ? (F>=300?R("yes","Kho hạng C trên mặt đất: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("1.4.2")):R("no","Kho hạng C trên mặt đất: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("1.4.2")))
        : (F>=500?R("yes","Kho hạng C trên mặt đất: đạt ngưỡng diện tích gian phòng ≥ 500 m² (báo cháy tự động).",cc("1.4.2")):R("no","Kho hạng C trên mặt đất: chưa đạt ngưỡng diện tích gian phòng ≥ 500 m² (báo cháy tự động).",cc("1.4.2")));
    }
    return R("na","Kho hạng D, E: Bảng A.3 chỉ quy định cụ thể cho hạng A, B, C (mục 1.1–1.5) — hạng D, E đối chiếu thêm mục 1.5/1.6 hoặc xin ý kiến kỹ sư.",cc("1"));
  }
  /* Nhà sản xuất — gian phòng theo hạng nguy hiểm cháy nổ */
  if(hz==="A"||hz==="B") return forSprinkler
    ? (F>=300?R("yes","Xưởng SX hạng A, B: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("2.1")):R("no","Xưởng SX hạng A, B: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("2.1")))
    : R("yes","Xưởng SX hạng A, B: bắt buộc báo cháy tự động, không phụ thuộc diện tích.",cc("2.1"));
  if(hz==="C"){
    if(B) return R("yes","Xưởng SX hạng C tại tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích (báo cháy và chữa cháy tự động).",cc("2.2.1/2.3.1"));
    return forSprinkler
      ? (F>=300?R("yes","Xưởng SX hạng C trên mặt đất: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("2.2.2")):R("no","Xưởng SX hạng C trên mặt đất: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).",cc("2.2.2")))
      : R("yes","Xưởng SX hạng C trên mặt đất: bắt buộc báo cháy tự động, không phụ thuộc diện tích.",cc("2.2.2"));
  }
  return R("na","Xưởng SX hạng D, E: Bảng A.3 mục 2 chủ yếu quy định cho hạng C1–C3 (mục 2.2–2.4) — hạng D, E cần đối chiếu thêm hoặc xin ý kiến kỹ sư.",cc("2"));
}

function evalSprinkler(d){
  const F=d.totalArea,T=d.floors,H=d.hFire,B=(d.basements>0||d.semiBasements>0);
  const cc = s => `QCVN 10:2025/BCA, Bảng A.1, STT ${s}`;
  const hf = th => `chiều cao PCCC ${H} m so ngưỡng ≥ ${th} m`;
  switch(d.occ){
    case "chungcu": return H>=30 ? R("yes",`Đạt ngưỡng: ${hf(30)}.`,cc(3)) : R("no",`Chưa đạt ngưỡng chiều cao PCCC ≥ 30 m (công trình: ${H} m).`,cc(3));
    case "nhatre":  return (T>=4&&F>=5000) ? R("yes","Đạt ngưỡng: cao ≥ 4 tầng VÀ ΣF ≥ 5.000 m² (điều kiện đồng thời).",cc(4)) : R("no","Chưa đạt điều kiện đồng thời cao ≥ 4 tầng VÀ ΣF ≥ 5.000 m².",cc(4));
    case "truonghoc": return H>=25 ? R("yes",`Đạt ngưỡng: ${hf(25)}.`,cc(5)) : R("no",`Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m (công trình: ${H} m).`,cc(5));
    case "yte":     return H>=25||F>=2000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 2.000 m².",cc(6)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 2.000 m².",cc(6));
    case "thethao": return H>=25 ? R("yes",`Đạt ngưỡng: ${hf(25)}.`,cc(8)) : R("no",`Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m.`,cc(8));
    case "nhahat":  return H>=25 ? R("yes",`Đạt ngưỡng: ${hf(25)}.`,cc(9)) : R("no",`Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m.`,cc(9));
    case "baotang":
      if(B) return F>=200 ? R("yes","Tầng hầm/bán hầm: đạt ngưỡng ΣF ≥ 200 m².",cc("11.1")) : R("no","Tầng hầm/bán hầm: chưa đạt ngưỡng ΣF ≥ 200 m².",cc("11.1"));
      return T>=3 ? (F>=500 ? R("yes","≥ 3 tầng: đạt ngưỡng ΣF ≥ 500 m².",cc("11.2.2")) : R("no","≥ 3 tầng: chưa đạt ngưỡng ΣF ≥ 500 m².",cc("11.2.2")))
                  : (F>=4000 ? R("yes","1–2 tầng: đạt ngưỡng ΣF ≥ 4.000 m².",cc("11.2.1")) : R("no","1–2 tầng: chưa đạt ngưỡng ΣF ≥ 4.000 m².",cc("11.2.1")));
    case "vanhoa":  return H>=25||F>=5000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².",cc(12)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².",cc(12));
    case "karaoke":
      if(B) return R("yes","Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.",cc("13.1"));
      return T>=3 ? R("yes","Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.",cc("13.2.2"))
                  : (F>=500 ? R("yes","1–2 tầng: đạt ngưỡng ΣF ≥ 500 m².",cc("13.2.1")) : R("no","1–2 tầng: chưa đạt ngưỡng ΣF ≥ 500 m².",cc("13.2.1")));
    case "tttm":
      if(B) return F>=200 ? R("yes","Tầng hầm/bán hầm: đạt ngưỡng ΣF ≥ 200 m².",cc("15.1")) : R("no","Tầng hầm/bán hầm: chưa đạt ngưỡng ΣF ≥ 200 m².",cc("15.1"));
      return T>=3 ? R("yes","Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.",cc("15.2.2"))
                  : (F>=3500 ? R("yes","1–2 tầng: đạt ngưỡng ΣF ≥ 3.500 m².",cc("15.2.1")) : R("no","1–2 tầng: chưa đạt ngưỡng ΣF ≥ 3.500 m².",cc("15.2.1")));
    case "nhahang": return H>=25||F>=5000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².",cc(16)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².",cc(16));
    case "cuahang":
      if(B) return F>=200 ? R("yes","Tầng hầm/bán hầm: đạt ngưỡng ΣF ≥ 200 m².",cc("17.1")) : R("no","Tầng hầm/bán hầm: chưa đạt ngưỡng ΣF ≥ 200 m².",cc("17.1"));
      return H>=25||F>=3500 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 3.500 m².",cc("17.2"),["Nhà KD chất lỏng cháy/dễ cháy (trừ can, bình ≤ 20 lít): bắt buộc không phụ thuộc diện tích (STT 17.3)."]) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 3.500 m².",cc("17.2"),["Nhà KD chất lỏng cháy/dễ cháy (trừ can, bình ≤ 20 lít): bắt buộc không phụ thuộc diện tích (STT 17.3)."]);
    case "khachsan":return H>=25||F>=5000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².",cc(18)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².",cc(18));
    case "buudien": return H>=25||F>=5000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².",cc(19)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².",cc(19));
    case "truso":   return H>=25||F>=5000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².",cc(20)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².",cc(20));
    case "honhop":  return H>=25||F>=5000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².",cc(21)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².",cc(21));
    case "nhaga":   return H>=25||F>=10000 ? R("yes","Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 10.000 m².",cc(22)) : R("no","Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 10.000 m².",cc(22));
    case "garakin":
      if(B||T>=2) return R("yes","Dạng kín có tầng hầm/bán hầm hoặc trên mặt đất ≥ 2 tầng: bắt buộc, không phụ thuộc diện tích.",cc("25.1"));
      if(d.garaKinVal==="ho"){
        return d.garaKC12==="le12" ? R("yes","Dạng hở, khoảng cách đến cạnh để hở ≤ 12 m: đạt ngưỡng ΣF ≥ 4.000 m² hoặc cao ≥ 4 tầng — kiểm tra lại quy mô.",cc("25.3.1"))
          : (F>=4000||T>=4 ? R("yes","Dạng hở, khoảng cách > 12 m: đạt ngưỡng ΣF ≥ 4.000 m² hoặc cao ≥ 4 tầng.",cc("25.3.2")) : R("no","Dạng hở, khoảng cách > 12 m: chưa đạt ngưỡng ΣF ≥ 4.000 m² và cao ≥ 4 tầng.",cc("25.3.2")));
      }
      const b2=d.garaBcl, s2=d.garaCapS;
      if((b2==="I"||b2==="II"||b2==="III")&&(s2==="S0"||s2==="S1")) return F>=2000 ? R("yes","Bậc I/II/III, cấp S0/S1: đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.1/25.2.2")) : R("no","Bậc I/II/III, cấp S0/S1: chưa đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.1/25.2.2"));
      if(b2==="IV"||b2==="V") return F>=2000 ? R("yes","Bậc IV/V: đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.3/25.2.4/25.2.5")) : R("no","Bậc IV/V: chưa đạt ngưỡng ΣF ≥ 2.000 m².",cc("25.2.3/25.2.4/25.2.5"));
      return R("warn","Dạng kín 1 tầng nổi: cần bổ sung bậc chịu lửa, cấp kết cấu S (hoặc dạng hở/khoảng cách cạnh hở) để tra đúng mục 25.2/25.3.",cc("25.2/25.3"));
    case "sanxuat": case "kho":
      return evalA3(d, true);
  }
  return R("na","—","—");
}

function evalHongNuoc(d){
  const F=d.totalArea,T=d.floors,B=(d.basements>0||d.semiBasements>0);
  const cc = "QCVN 10:2025/BCA, Phụ lục B";
  switch(d.occ){
    case "chungcu": return T>=7 ? R("yes","Đạt ngưỡng: nhà ở/công trình công cộng cao ≥ 7 tầng.",cc) : R("no","Chưa đạt ngưỡng cao ≥ 7 tầng (nhóm nhà ở, công trình công cộng chung).",cc);
    case "honhop": case "khachsan":
      return T>=5||F>=1500 ? R("yes","Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 1.500 m².",cc) : R("no","Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 1.500 m².",cc);
    case "nhatre":  return d.kids>=100||T>=3||F>=1000 ? R("yes","Đạt ngưỡng: ≥ 100 cháu hoặc cao ≥ 3 tầng hoặc ΣF ≥ 1.000 m².",cc) : R("no","Chưa đạt ngưỡng ≥ 100 cháu, cao ≥ 3 tầng và ΣF ≥ 1.000 m².",cc);
    case "truonghoc": case "yte":
      return T>=3||F>=600 ? R("yes","Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 600 m².",cc) : R("no","Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 600 m².",cc);
    case "thethao": return T>=6||F>=1500 ? R("yes","Đạt ngưỡng: cao ≥ 6 tầng hoặc ΣF ≥ 1.500 m² (nhóm văn hóa/thể thao).",cc) : R("no","Chưa đạt ngưỡng cao ≥ 6 tầng và ΣF ≥ 1.500 m².",cc);
    case "nhahat":  return d.seats>=300||F>=1000 ? R("yes","Đạt ngưỡng: ≥ 300 chỗ ngồi hoặc ΣF ≥ 1.000 m².",cc) : R("no","Chưa đạt ngưỡng ≥ 300 chỗ và ΣF ≥ 1.000 m².",cc);
    case "vanhoa": case "baotang": case "cuahang":
      return F>=1500 ? R("yes","Đạt ngưỡng: ΣF ≥ 1.500 m² (nhóm thư viện/nhà văn hóa/TT hội nghị/cửa hàng).",cc) : R("no","Chưa đạt ngưỡng ΣF ≥ 1.500 m².",cc);
    case "truso": case "buudien":
      return T>=6||F>=1500 ? R("yes","Đạt ngưỡng: cao ≥ 6 tầng hoặc ΣF ≥ 1.500 m².",cc) : R("no","Chưa đạt ngưỡng cao ≥ 6 tầng và ΣF ≥ 1.500 m².",cc);
    case "karaoke":
      if(B) return R("yes","Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.",cc);
      return T>=3 ? R("yes","Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.",cc)
                  : (F>=300 ? R("yes","1–2 tầng: đạt ngưỡng ΣF ≥ 300 m².",cc) : R("no","1–2 tầng: chưa đạt ngưỡng ΣF ≥ 300 m².",cc));
    case "tttm":    return R("yes","Chợ hạng 1, hạng 2, TTTM, siêu thị: bắt buộc, không phụ thuộc diện tích.",cc);
    case "nhahang": return T>=6||F>=1500 ? R("yes","Đạt ngưỡng: cao ≥ 6 tầng hoặc ΣF ≥ 1.500 m².",cc) : R("no","Chưa đạt ngưỡng cao ≥ 6 tầng và ΣF ≥ 1.500 m².",cc);
    case "nhaga":   return F>=1500 ? R("yes","Đạt ngưỡng: ΣF ≥ 1.500 m².",cc) : R("no","Chưa đạt ngưỡng ΣF ≥ 1.500 m².",cc);
    case "sanxuat": case "kho":
      if(["A","B","C","D"].includes(d.hazard))
        return d.totalArea>=500 ? R("yes",`Nhà SX/kho hạng ${d.hazard}: đạt ngưỡng ΣF ≥ 500 m² (công trình: ΣF ${fmt(d.totalArea)} m²).`,cc) : R("no",`Nhà SX/kho hạng ${d.hazard}: chưa đạt ngưỡng ΣF ≥ 500 m² (công trình: ΣF ${fmt(d.totalArea)} m²).`,cc);
      return R("no",`Nhà SX/kho hạng E: mục 2 Phụ lục B chỉ áp dụng hạng A, B, C, D.`,cc,["Chú thích 3 Phụ lục B: không trang bị họng nước trong nhà đối với nhà SX/kho có chất khi tiếp xúc nước có thể sinh cháy, nổ."]);
    case "garakin":
      if(d.garaKin==="kin"){
        if(B) return R("yes","Nhà để xe dạng kín tại tầng hầm/bán hầm: đạt ngưỡng, không phụ thuộc diện tích (mục 3.1).",cc);
        return F>=150 ? R("yes","Nhà để xe dạng kín: đạt ngưỡng ΣF ≥ 150 m².",cc) : R("no","Nhà để xe dạng kín: chưa đạt ngưỡng ΣF ≥ 150 m².",cc);
      }
      return F>=1000 ? R("yes","Nhà để xe dạng hở (trừ gara cơ khí): đạt ngưỡng ΣF ≥ 1.000 m².",cc) : R("no","Nhà để xe dạng hở: chưa đạt ngưỡng ΣF ≥ 1.000 m².",cc);
  }
  return R("na","—",cc);
}

function evalNgoaiNha(d){
  const F=d.totalArea,T=d.floors;
  const cc = "QCVN 10:2025/BCA, Phụ lục C";
  switch(d.occ){
    case "yte":  return T>=5||F>=3000 ? R("yes","Nhà khám, chữa bệnh: đạt ngưỡng cao ≥ 5 tầng hoặc ΣF ≥ 3.000 m² (TT 1).",cc) : R("no","Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 3.000 m² (TT 1).",cc);
    case "tttm": return R("yes","Chợ hạng 1, hạng 2, TTTM: bắt buộc, không phụ thuộc quy mô (TT 2).",cc);
    case "nhaga":return R("yes","Nhà ga/cảng/bến: bắt buộc, không phụ thuộc quy mô (TT 3). Lưu ý: trạm dừng nghỉ chỉ áp dụng trên đường cao tốc.",cc);
    default:
      return R("na","Loại nhà không nêu trực tiếp trong Phụ lục C. Lưu ý: nếu công trình nằm trong khu đô thị, khu nhà ở, KCN/cụm CN, khu du lịch… thì hạ tầng khu vực thuộc diện cấp nước ngoài nhà (TT 10) — thường do hạ tầng chung đảm nhận; nhu cầu nước ngoài nhà của bản thân công trình xét theo QCVN 06.",cc);
  }
}

/* =====================================================================
   BƯỚC 5 — Phương tiện & hạng mục khác
   ===================================================================== */
/* Phụ lục E QCVN 10:2025/BCA — 7 mục, đối chiếu bản gốc ngày 13/7/2026: TẤT CẢ đều "Không phụ thuộc quy mô" */
const PHADO_MAP = {
  sanxuat:  "1",                                    // Nhà sản xuất
  kho:      "2",                                    // Nhà kho (độc lập)
  chungcu:  "3", khachsan: "3",                      // Chung cư/nhà ở tập thể/khách sạn/nhà khách/nhà nghỉ/lưu trú
  truso:    "4", truonghoc: "4", yte: "4",           // Trụ sở/VP, cơ sở nghiên cứu, trường học, bệnh viện
  nhaga:    "5",                                     // Nhà ga, bến xe, trạm dừng nghỉ, bến thủy/cảng biển, cáp treo
  karaoke:  "6", nhahat: "6",                        // Karaoke/vũ trường, nhà hát/rạp chiếu phim
  tttm:     "7"                                      // Chợ hạng 1, hạng 2, TTTM
};
const DUNG_CU = "01 bộ dụng cụ phá dỡ thô sơ: rìu (thép cacbon cao, ≥ 2 kg); xà beng (một đầu nhọn một đầu dẹt, dài ≥ 100 cm); búa (thép cacbon cao, ≥ 5 kg); kìm cộng lực (tải cắt ≥ 60 kg).";
function evalPhaDo(d){
  const stt = PHADO_MAP[d.occ];
  if(stt)
    return R("yes",`Thuộc đối tượng trang bị theo Bảng E.1, mục ${stt} — không phụ thuộc quy mô. Định mức: ${DUNG_CU}`,`QCVN 10:2025/BCA, Phụ lục E, Bảng E.1, mục ${stt}`);
  return R("no","Loại nhà không nêu trong 7 mục của Bảng E.1 Phụ lục E — không thuộc đối tượng bắt buộc trang bị dụng cụ phá dỡ thô sơ theo phụ lục này.","QCVN 10:2025/BCA, Phụ lục E, Bảng E.1");
}

function evalMatNa(d){
  const cc = "QCVN 10:2025/BCA, Phụ lục F";
  if(d.occ==="khachsan")
    return d.floors>=3 ? R("yes","Khách sạn/nhà nghỉ/lưu trú cao ≥ 3 tầng: trang bị mặt nạ LỌC ĐỘC tại mọi tầng, định mức 01 chiếc/người (gồm khách lưu trú + nhân viên thường xuyên) (TT 1).",cc)
                       : R("no","Khách sạn/lưu trú dưới 3 tầng: chưa thuộc diện theo TT 1.",cc);
  if(d.occ==="karaoke")
    return R("yes","Karaoke/vũ trường: bắt buộc không phụ thuộc quy mô — mặt nạ LỌC ĐỘC mọi tầng, tính theo số người trong phòng lớn nhất của tầng, 01 chiếc/người (TT 2).",cc);
  return R("na","Loại nhà không nêu trong Phụ lục F (các mục còn lại áp dụng công nghiệp/năng lượng quy mô lớn: lọc hóa dầu, kho dầu ≥ 100.000 m³, nhiệt điện ≥ 600 MW, KCN ≥ 75 ha…).",cc);
}

/* Nhóm công năng thuộc "chung cư, nhà và công trình công cộng thuộc diện quản lý PCCC" — TT1 Phụ lục G */
const TT1_CONGCONG = ["chungcu","truonghoc","nhatre","yte","thethao","nhahat","baotang","vanhoa","khachsan","cuahang","nhahang","truso","buudien","honhop","nhaga"];
function evalLoa(d){
  const cc = "QCVN 10:2025/BCA, Phụ lục G";
  const notes = [];
  const P = d.pplFloor;
  const ttHits = [];

  /* TT1: chung cư, nhà và công trình công cộng — cao > 10 tầng HOẶC ≥ 2 tầng hầm */
  if(TT1_CONGCONG.includes(d.occ)){
    const qualTT1 = d.floors>10 || d.basements>=2;
    if(qualTT1) ttHits.push({stt:1, detail:`Đạt ngưỡng TT 1: cao trên 10 tầng (công trình: ${d.floors} tầng tính toán) hoặc có từ 2 tầng hầm trở lên (công trình: ${d.basements} tầng hầm).`});
  }
  /* TT2: karaoke/vũ trường, nhà hát, rạp chiếu phim, bệnh viện, nhà dưỡng lão — ≥ 50 người/tầng */
  if(["karaoke","nhahat","yte"].includes(d.occ)){
    if(P===null) notes.push("TT 2 (karaoke/vũ trường, nhà hát/rạp, bệnh viện, nhà dưỡng lão): ngưỡng ≥ 50 người trên 1 tầng — chưa khai báo số người/tầng nên chưa kiểm tra được mục này.");
    else if(P>=50) ttHits.push({stt:2, detail:`Đạt ngưỡng TT 2: ≥ 50 người trên 1 tầng (khai báo: ${fmt(P)} người).`});
  }
  /* TT3: nhà để xe dạng kín — ΣF ≥ 18.000 m² */
  if(d.occ==="garakin" && d.garaKin==="kin"){
    if(d.totalArea>=18000) ttHits.push({stt:3, detail:`Đạt ngưỡng TT 3: nhà để xe dạng kín ΣF ≥ 18.000 m² (công trình: ${fmt(d.totalArea)} m²).`});
  }
  /* TT4: nhà sản xuất — ΣF ≥ 18.000 m² VÀ ≥ 300 người/tầng (đồng thời) */
  if(d.occ==="sanxuat"){
    if(P===null) notes.push("TT 4 (nhà sản xuất): ngưỡng ΣF ≥ 18.000 m² VÀ ≥ 300 người/tầng (đồng thời) — chưa khai báo số người/tầng nên chưa kiểm tra được mục này.");
    else if(d.totalArea>=18000 && P>=300) ttHits.push({stt:4, detail:`Đạt điều kiện đồng thời TT 4: ΣF ≥ 18.000 m² (${fmt(d.totalArea)} m²) VÀ ≥ 300 người/tầng (${fmt(P)} người).`});
  }
  /* TT6: nhà ga hành khách hàng không/đường sắt/đường sắt đô thị — không phụ thuộc quy mô */
  if(d.occ==="nhaga") ttHits.push({stt:6, detail:"Đạt ngưỡng TT 6: nhà ga hành khách — không phụ thuộc quy mô."});

  if(ttHits.length){
    const sttList = ttHits.map(h=>h.stt).join(", ");
    return R("yes", ttHits.map(h=>h.detail).join(" ") , `${cc}, Bảng G.1, mục ${sttList}`, notes);
  }
  const naNote = notes.length ? notes : ["Không đạt ngưỡng của bất kỳ mục nào (TT 1–6) trong Bảng G.1 với dữ liệu hiện tại."];
  return R("no", "Chưa thuộc đối tượng trang bị loa thông báo & hướng dẫn thoát nạn theo Bảng G.1 với dữ liệu hiện tại.", cc, naNote);
}

function evalCoGioi(d){
  const cc = "QCVN 10:2025/BCA, Phụ lục D";
  if(["sanxuat","kho"].includes(d.occ))
    return R("na","Phụ lục D áp dụng chủ yếu cho kho dầu mỏ, cảng, nhà máy điện, lọc hóa dầu, KCN/cụm CN. Nhà SX/kho đơn lẻ thường không thuộc diện; nếu nằm trong KCN/cụm CN thì phương tiện cơ giới xét theo hạ tầng KCN (định mức ⚠️ — đọc bản gốc khi rơi vào diện).",cc);
  return R("na","Công trình dân dụng thông thường không thuộc diện trang bị phương tiện chữa cháy cơ giới (Phụ lục D áp dụng công nghiệp/hạ tầng quy mô lớn).",cc);
}

const BINH_TBL = { thap:{cs:"2-A",kc:20,dt:300,ten:"Thấp"}, tb:{cs:"3-A",kc:20,dt:150,ten:"Trung bình"}, cao:{cs:"4-A",kc:15,dt:100,ten:"Cao"} };
function evalBinh(d){
  const auto = d.extLevel==="auto";
  const lv = auto ? (OCCS.find(o=>o.id===d.occ).binh) : d.extLevel;
  const t = BINH_TBL[lv];
  const n1 = Math.ceil(d.areaFloor/t.dt);
  const min = d.areaFloor<100 ? 1 : 2;
  const n = Math.max(n1,min);
  return {
    v:"yes",
    lv, ten:t.ten + (auto?" (giả thiết theo công năng — cần xác nhận)":""),
    detail:`Tầng điển hình ${fmt(d.areaFloor)} m², mức nguy hiểm ${t.ten}${auto?" (giả thiết)":""}: dự kiến ≥ ${n} bình/tầng loại A, công suất tối thiểu ${t.cs}, khoảng cách di chuyển ≤ ${t.kc} m, diện tích bảo vệ tối đa ${fmt(t.dt)} m²/bình. Sàn tối thiểu: ${min} bình/tầng.`,
    canCu:"TCVN 7435-1:2004, Bảng 1, mục 7.2.2 / 7.1.8",
    notes:[
      "Số bình là DỰ KIẾN theo diện tích; bố trí thực tế theo mặt bằng để đảm bảo khoảng cách di chuyển — mặt bằng dài/ngóc ngách có thể cần nhiều hơn.",
      "Nếu có mối nguy hiểm loại B/C (chất lỏng cháy, khí): bổ sung bình theo Bảng 2 (55B/144B/233B, KC ≤ 15 m); vẫn phải đủ bình loại A (mục 7.1.6).",
      "Bố trí: dễ thấy, dễ lấy, trên lối đi/lối ra; bình ≤ 18 kg đặt đỉnh ≤ 1,5 m; > 18 kg ≤ 1,0 m; đáy cách sàn ≥ 3 cm (điều 5).",
      "TCVN 7435-1 là bản 2004 — kiểm tra bản thay thế mới hơn nếu có."
    ]
  };
}

function evalDen(d){
  const pos = [
    "Cầu thang bộ thoát nạn",
    "Đường thoát nạn, vị trí chuyển hướng, nút giao hành lang",
    "Vị trí thay đổi cao độ",
    "Cửa / lối ra thoát nạn",
    "Phòng trạm biến áp, máy phát, kỹ thuật thang máy, gian lánh nạn (nếu có)",
    "Phòng trực điều khiển chống cháy, phòng bơm chữa cháy, vị trí đặt phương tiện PCCC",
    "Gian phòng có người làm việc mà điểm xa nhất → lối ra > 13 m"
  ];
  if(d.occ==="garakin"||d.basements>0||d.semiBasements>0) pos.splice(4,0,"Gara / tầng hầm, bán hầm để xe");
  const notes = [
    "Nguồn dự phòng duy trì ≥ 120 phút (mục 4.5); độ rọi đường thoát nạn ≥ 1 lux tại tim đường, gian phòng ≥ 0,5 lux (5.1.2–5.1.3).",
    "Biển báo \"LỐI RA/EXIT\" nền xanh lá chữ trắng; khoảng cách giữa các biển ≤ 25 m (5.2.6); biển chỉ hướng tại vị trí tầm nhìn che khuất.",
    "Số lượng đèn/biển chính xác phụ thuộc mặt bằng bố trí — cần bản vẽ để định vị."
  ];
  if(d.occ==="khachsan"&&d.floors>=7) notes.unshift("Khách sạn ≥ 7 tầng: bổ sung BIỂN TẦM THẤP tại tầng có phòng nghỉ (đáy biển 150–200 mm so sàn, khoảng cách ≤ 10 m) (5.2.3) và sơ đồ thoát nạn tại mọi phòng nghỉ (5.2.9).");
  else if(d.occ==="khachsan") notes.unshift("Cơ sở lưu trú: sơ đồ thoát nạn tại mọi phòng nghỉ (5.2.9).");
  if(d.volume>=5000) notes.push("Khối tích ≥ 5.000 m³: nếu có hành lang thoát nạn > 10 m thì thuộc diện biển tầm thấp (5.2.3) — cần xác nhận chiều dài hành lang.");
  if(d.areaFloor>1000) notes.push(`Tầng > 1.000 m² (tầng điển hình ${fmt(d.areaFloor)} m²): bắt buộc SƠ ĐỒ CHỈ DẪN THOÁT NẠN tại tầng, kích thước ≥ 600×400 mm, mép dưới cao 1,5 ± 0,2 m (5.2.9).`);
  else notes.push("Tầng có ≥ 2 lối ra thoát nạn: bắt buộc sơ đồ chỉ dẫn thoát nạn tại tầng (5.2.9) — xác nhận theo mặt bằng.");
  return { v:"yes", pos, notes, canCu:"TCVN 13456:2022, mục 4.5, 5.1.1–5.1.6, 5.2" };
}

/* =====================================================================
   MODULE TÍNH NƯỚC CHỮA CHÁY SƠ BỘ
   Nguồn: QCVN 06 (Bảng 8, 11, 12); TCVN 7336:2021 (Bảng 1, 2, 3, Phụ lục A);
   QCVN 10:2025/BCA Phụ lục C. Quy đổi 1 m³ = 1.000 L.
   ===================================================================== */

/* Gợi ý nhóm nguy cơ theo công năng (Phụ lục A TCVN 7336) */
const NHOM_SUGGEST = {
  truso:"1", chungcu:"1", truonghoc:"1", nhatre:"1", yte:"1", khachsan:"1",
  nhahang:"1", baotang:"1", thethao:"1", nhaga:"1",
  karaoke:"2", nhahat:"2", vanhoa:"2", tttm:"2", cuahang:"2", buudien:"2",
  garakin:"2", sanxuat:"2", honhop:"2", kho:"5"
};

/* Bảng 11 QCVN 06 — họng nước trong nhà (nhà ở & công cộng): trả {n,q,muc} */
function traBang11(d){
  if(d.occ==="chungcu"){
    const gt10 = d.corridor==="gt10";
    if(d.floors<=16) return { n: gt10?2:1, q:2.5, muc:"Bảng 11 QCVN 06, mục 1 (nhà ở ≤ 16 tầng, hành lang "+(gt10?"> 10 m":"≤ 10 m")+")" };
    if(d.floors<=25) return { n: gt10?3:2, q:2.5, muc:"Bảng 11 QCVN 06, mục 1 (nhà ở > 16 đến ≤ 25 tầng, hành lang "+(gt10?"> 10 m":"≤ 10 m")+")" };
    return { err:"Nhà ở > 25 tầng: ngoài phạm vi Bảng 11 — tính riêng theo quy định nhà siêu cao tầng." };
  }
  if(d.occ==="nhahat"){
    return d.seats>300 ? { n:2, q:5.0, muc:"Bảng 11 QCVN 06, mục 3 (> 300 chỗ ngồi)" }
                       : { n:2, q:2.5, muc:"Bảng 11 QCVN 06, mục 3 (≤ 300 chỗ ngồi)" };
  }
  const muc = (d.occ==="truso"||d.occ==="buudien") ? {so:"2",ten:"nhà hành chính"} : {so:"4",ten:"nhà công cộng"};
  const big = d.volume>25000;
  let n;
  if(d.floors<=10) n = big?2:1; else n = big?3:2;
  return { n, q:2.5, muc:`Bảng 11 QCVN 06, mục ${muc.so} (${muc.ten} ${d.floors<=10?"≤ 10":"> 10"} tầng, V ${big?"> 25.000":"≤ 25.000"} m³)` };
}

/* Bảng 12 QCVN 06 — họng nước trong nhà (nhà SX/kho): trả {n,q,muc} theo bậc chịu lửa, hạng, cấp S, V */
function traBang12(d){
  const big = d.volume>150000; // 150 (nghìn m³)
  const hz = d.hazard, b = d.bcl, s = d.capS;
  const tag = (n,q)=>({ n, q, muc:`Bảng 12 QCVN 06 (bậc ${b}, hạng ${hz}, cấp ${s}, V ${big?"> 150.000":"≤ 150.000"} m³)` });
  if(b==="I"||b==="II"){
    if(["A","B","C"].includes(hz)&&["S0","S1"].includes(s)) return big?tag(3,2.5):tag(2,2.5);
    if(["D","E"].includes(hz)) return tag(1,2.5);
  }
  if(b==="III"){
    if(["A","B","C"].includes(hz)&&s==="S0") return big?tag(3,2.5):tag(2,2.5);
    if(["D","E"].includes(hz)&&["S0","S1"].includes(s)) return big?tag(2,2.5):tag(1,2.5);
  }
  if(b==="IV"){
    if(["A","B"].includes(hz)&&s==="S0") return big?tag(3,2.5):tag(2,2.5);
    if(hz==="C"&&["S0","S1"].includes(s)) return big?tag(2,5):tag(2,2.5);
    if(hz==="C"&&["S2","S3"].includes(s)) return big?tag(4,2.5):tag(3,2.5);
    if(["D","E"].includes(hz)) return big?tag(2,2.5):tag(1,2.5);
  }
  if(b==="V"){
    if(hz==="C") return big?tag(2,5):tag(2,2.5);
    if(["D","E"].includes(hz)) return big?tag(2,2.5):tag(1,2.5);
  }
  return { err:`Tổ hợp bậc ${b} / hạng ${hz} / cấp ${s} không có trong Bảng 12 QCVN 06 — kiểm tra lại dữ liệu (VD bậc IV hạng A,B chỉ quy định cấp S0).` };
}

/* Bảng 8 QCVN 06 mục 2 (F1.1, F2, F3, F4) — nước ngoài nhà: trả {Q,muc} theo số tầng & V */
function traBang8(d){
  const Vk = d.volume/1000; // nghìn m³
  const row = d.floors<=3 ? [10,10,15,20,25]
            : d.floors<=12 ? [10,15,20,25,30]
            : d.floors<=16 ? [null,20,25,30,35]
            : [null,25,30,30,35];
  const idx = Vk<=1?0 : Vk<=5?1 : Vk<=25?2 : Vk<=50?3 : 4;
  const Q = row[idx];
  if(Q===null) return { err:"Tổ hợp số tầng/khối tích không quy định trong Bảng 8 (dấu \u2014) — kiểm tra lại dữ liệu." };
  return { Q, muc:`Bảng 8 QCVN 06, mục 2 (nhóm F1.1/F2/F3/F4; ${d.floors<=3?"≤ 3":d.floors<=12?"> 3 đến ≤ 12":d.floors<=16?"> 12 đến ≤ 16":"> 16"} tầng; V ${fmt(d.volume)} m³)` };
}

/* Bảng 1/2/3 TCVN 7336 — chữa cháy tự động: trả {Q,t,muc} hoặc {err}/{kekcao} */
const B1_7336 = { "1":{Q:10,t:30}, "2":{Q:30,t:60}, "3":{Q:60,t:60}, "4.1":{Q:110,t:60} };
const B2_7336 = { "5":{"1":15,"2":30,"3":45,"4":60,"5.5":75}, "6":{"1":30,"2":60,"3":75,"4":75,"5.5":90} };
const B3_7336 = [ // [Hmax, {nhóm: Q}]
  [12,{"1":12,"2":35,"3":70,"4.1":130}],
  [14,{"1":14,"2":40,"3":85,"4.1":155}],
  [16,{"1":17,"2":50,"3":95,"4.1":180}],
  [18,{"1":20,"2":57,"3":115,"4.1":215}],
  [20,{"1":24,"2":65,"3":130,"4.1":240}]
];
/* =====================================================================
   MODULE TCVN 14496:2025 — Chữa cháy tự động bằng nước cho kho kệ cao
   (chiều cao xếp hàng trên giá đỡ > 5,5 m đến 25 m)
   Chế độ A: 1 tầng đầu phun (Điều 5) — nhóm 5/6, H≤14m, h≤12,5m
   Chế độ B: nhiều tầng đầu phun (Điều 6) — h đến 25m
   ===================================================================== */

/* Bảng 2 TCVN 14496 — hệ số thay đổi chiều cao gian phòng ψ */
function heSoPsi14496(H){
  return H<=6.4 ? 0 : 0.06; // Trên 6,4 đến 14,0 m → 0,06 (Điều 5.7, Bảng 2)
}

/* Chế độ A — Điều 5: 1 tầng đầu phun. Trả {err} hoặc {qcd, psi, Qs, ghichu[]} */
function tinh14496_1tang(d){
  const g=d.nhomNC14496, h=d.hXepM, H=d.hGianPhong, N=d.soDauPhun90;
  if(!["5","6"].includes(g)) return { err:"Chế độ 1 tầng đầu phun (Điều 5) chỉ áp dụng cho nhóm nguy cơ cháy 5 hoặc 6 (Phụ lục B TCVN 7336)." };
  if(H>14) return { err:"Chiều cao gian phòng H = "+fmt(H)+" m > 14 m — vượt phạm vi Điều 5 (áp dụng H ≤ 14 m). Dùng chế độ nhiều tầng đầu phun (Điều 6)." };
  if(h>12.5) return { err:"Chiều cao xếp hàng h = "+fmt(h)+" m > 12,5 m — vượt phạm vi Điều 5 (áp dụng h ≤ 12,5 m). Dùng chế độ nhiều tầng đầu phun (Điều 6)." };
  if(h<5.5) return { err:"Chiều cao xếp hàng h = "+fmt(h)+" m ≤ 5,5 m — thuộc phạm vi TCVN 7336 (kho thường), không thuộc TCVN 14496." };
  const q55 = g==="5" ? 5.3 : 6.5;
  const psi = heSoPsi14496(H);
  const qcd = (q55 + 0.19*(h-5.5)) * (1 + psi*(H-10));
  const ghichu = [];
  if(N===null){
    ghichu.push("Chưa nhập số đầu phun trong diện tích tính toán 90 m² — Qs chỉ dừng ở lưu lượng 1 đầu phun chủ đạo.");
    return { qcd, psi, Qs:null, ghichu, q55 };
  }
  const Qs = qcd*N;
  return { qcd, psi, Qs, N, ghichu, q55 };
}

/* Bảng 5 TCVN 14496 — chiều dài tính toán A theo loại pallet */
const A_PALLET_14496 = { phang:9, hop:12, hopkimloai:8 };
/* Bảng 6 TCVN 14496 — cường độ phun trong không gian kệ hàng i (L/s·m²) theo loại hàng & dải cao độ tấm chắn */
const I_KEHANG_14496 = {
  ranco: { le2:0.24, tu2den3:0.36, tu3den45:0.5 },   // vật liệu dễ cháy thể rắn
  khongchay: { le2:0.20, tu2den3:0.30, tu3den45:0.4 }, // vật liệu không cháy trong bao bì dễ cháy
  caosu: { le2:0.40, tu2den3:0.60, tu3den45:0.8 }     // sản phẩm cao su
};

/* Chế độ B — Điều 6: nhiều tầng đầu phun. Trả {err} hoặc {Qi, Qd, Qs, chiTiet} */
function tinh14496_nhieutang(d){
  const h=d.hXepM;
  if(h<5.5) return { err:"Chiều cao xếp hàng h ≤ 5,5 m — thuộc phạm vi TCVN 7336, không thuộc TCVN 14496." };
  if(h>25) return { err:"Chiều cao xếp hàng h = "+fmt(h)+" m > 25 m — vượt phạm vi áp dụng TCVN 14496 (tối đa 25 m)." };
  const A = A_PALLET_14496[d.loaiPallet14496];
  const B = d.chieuRongKeB, n = d.soTamChan;
  const iBang = I_KEHANG_14496[d.loaiHang14496];
  const dai = d.daiCaoDo14496; // "le2" | "tu2den3" | "tu3den45"
  const i = iBang ? iBang[dai] : null;
  const errs=[];
  if(A===undefined) errs.push("Loại pallet");
  if(B===null||B===undefined||B<=0) errs.push("Chiều rộng tối đa kệ hàng B");
  if(n===null||n===undefined||n<=0) errs.push("Số tấm chắn n");
  if(!i) errs.push("Loại hàng lưu trữ / dải cao độ");
  if(errs.length) return { err:"Thiếu dữ liệu để tính Qi (không gian kệ hàng): "+errs.join(", ")+"." };
  const Qi = A*B*n*i;

  // Qd — đầu phun dưới mái: cường độ theo h, diện tích tối thiểu 90 m²
  const iD = h<=16 ? 0.12 : 0.18;
  const Sd = d.dienTichMai90 ?? 90;
  const Qd = iD*Sd;

  const Qs = Qi+Qd;
  return { Qi, Qd, Qs, A, B, n, i, iD, Sd, muc_i:`Bảng 6 TCVN 14496 (${({ranco:"vật liệu dễ cháy thể rắn",khongchay:"không cháy trong bao bì dễ cháy",caosu:"sản phẩm cao su"})[d.loaiHang14496]}, dải ${({le2:"≤ 2,0 m",tu2den3:"> 2,0–3,0 m",tu3den45:"> 3,0–4,5 m"})[dai]})` };
}

/* Bảng 1 TCVN 14496 — họng nước trong nhà cho kho kệ cao: trả {n,q,muc} hoặc {err} */
function traBang1_14496(d){
  const big = d.volume>150000; // > 150.000 m³ (đồng nhất đơn vị với Bảng 12 QCVN 06 — "nghìn m3" theo bản gốc, dùng absolute cho nhất quán UI)
  const b=d.bcl, hz=d.hazard, s=d.capS;
  const tag=(n,q)=>({n,q,muc:`Bảng 1 TCVN 14496 (bậc ${b}, hạng ${hz}, cấp ${s}, V ${big?"> 150.000":"≤ 150.000"} m³)`});
  if(b==="I"||b==="II"){
    if(["A","B","C"].includes(hz)&&["S0","S1"].includes(s)) return big?tag(3,2.5):tag(2,2.5);
    if(["D","E"].includes(hz)) return tag(1,2.5);
  }
  if(b==="III"){
    if(["A","B"].includes(hz)&&s==="S0") return big?tag(3,2.5):tag(2,2.5);
    if(hz==="C"&&["S0","S1"].includes(s)) return big?tag(2,5):tag(2,2.5);
    if(hz==="C"&&["S2","S3"].includes(s)) return big?tag(4,2.5):tag(3,2.5);
    if(["D","E"].includes(hz)&&["S0","S1"].includes(s)) return big?tag(2,2.5):tag(1,2.5);
  }
  if(b==="IV"){
    if(["A","B"].includes(hz)&&s==="S0") return big?tag(3,2.5):tag(2,2.5);
    if(hz==="C"&&["S0","S1"].includes(s)) return big?tag(2,5):tag(2,2.5);
    if(hz==="C"&&["S2","S3"].includes(s)) return big?tag(4,2.5):tag(3,2.5);
    if(["D","E"].includes(hz)) return big?tag(2,2):tag(1,2.5);
  }
  if(b==="V"){
    if(hz==="C") return big?tag(2,5):tag(2,2.5);
    if(["D","E"].includes(hz)) return big?tag(2,2.5):tag(1,2.5);
  }
  return { err:`Tổ hợp bậc ${b} / hạng ${hz} / cấp ${s} không có trong Bảng 1 TCVN 14496 — kiểm tra lại dữ liệu.` };
}

function traSprinkler(d){
  const g = d.nhomNC;
  if(g==="4.2"||g==="7"){
    // Hệ chữa cháy bằng bọt: Q_ct = S·J ; W_dd = K·Q_ct·t·60
    const S=d.botS, J=d.botJ, t=d.botT, K=d.botK, CB=d.botCB;
    const Qct = S*J;
    const Wdd = K*Qct*t*60;            // lít dung dịch
    const Wctb = Wdd*CB/100;           // lít chất tạo bọt đậm đặc
    const Wnuoc = Wdd*(100-CB)/100;    // lít nước
    const mucNhom = g==="4.2" ? "Bảng 1 TCVN 7336 (nhóm 4.2 — khí cháy/xăng/cồn)" : "Bảng 2 TCVN 7336 (nhóm 7 — kho vecni, sơn, chất lỏng cháy)";
    return { foam:true, S, J, t, K, CB, Qct, Wdd, Wctb, Wnuoc, muc:`${mucNhom}; công thức bọt theo TCVN 5307` };
  }
  if(g==="5"||g==="6"){
    if(d.hXep==="cao"){
      const res = d.phuongAn14496==="1tang" ? tinh14496_1tang(d) : tinh14496_nhieutang(d);
      if(res.err) return { err: res.err };
      return { kecao:true, phuongAn:d.phuongAn14496, res };
    }
    const Q = B2_7336[g][d.hXep];
    return { Q, t:60, muc:`Bảng 2 TCVN 7336 (nhóm ${g}, chiều cao xếp hàng ${({"1":"đến 1 m","2":"1–2 m","3":"2–3 m","4":"3–4 m","5.5":"4–5,5 m"})[d.hXep]}); t = 60 phút (Bảng 1)` };
  }
  const hb = d.hBaoVe;
  if(hb!==null && hb>=10){
    if(hb>20) return { err:"Chiều cao khu vực bảo vệ > 20 m: ngoài phạm vi Bảng 3 TCVN 7336 — tính riêng." };
    const row = B3_7336.find(([mx])=>hb<=mx);
    const Q = row[1][g];
    return { Q, t:B1_7336[g].t, muc:`Bảng 3 TCVN 7336 (nhóm ${g}, chiều cao khu vực bảo vệ ${hb} m thuộc dải ≤ ${row[0]} m); t theo Bảng 1` };
  }
  const b = B1_7336[g];
  return { Q:b.Q, t:b.t, muc:`Bảng 1 TCVN 7336 (nhóm ${g}: lưu lượng tối thiểu ${b.Q} L/s, thời gian ${b.t} phút)`,
    note: g==="2" ? "Chú thích 4 Bảng 1: nhóm 2 có tải trọng cháy > 1.400 MJ/m² phải tăng ≥ 1,5 lần; > 2.200 MJ/m² tăng ≥ 2,5 lần — xác nhận tải trọng cháy khi thiết kế." : null };
}

/* Tổng hợp tính nước: trả {trich[], freeze[], kq{}, notes[], errs[]} */
function evalNuoc(d, sp, hn, nn){
  const trich=[], freeze=[], notes=[], errs=[];
  const kq = { Vtn:null, Vnn:null, Vtd:null, Qtn:null, Qnn:null, Qtd:null, tTn:null, tTd:null };

  const isBotGroup = ["4.2","7"].includes(d.nhomNC);
  const isKeCaoGroup = ["5","6"].includes(d.nhomNC) && d.hXep==="cao";
  const coSpr = sp.v==="yes" || d.tangCuong || isBotGroup || isKeCaoGroup;
  const kqBot = { Wdd:null, Wctb:null, Wnuoc:null, Qct:null };

  /* --- Chữa cháy tự động (tính trước để biết t họng) --- */
  let sprRes = null;
  if(coSpr){
    sprRes = traSprinkler(d);
    if(sprRes.err){ errs.push(sprRes.err); }
    else if(sprRes.foam){
      kqBot.Qct=sprRes.Qct; kqBot.Wdd=sprRes.Wdd; kqBot.Wctb=sprRes.Wctb; kqBot.Wnuoc=sprRes.Wnuoc;
      kq.tTd = sprRes.t;
      trich.push(["Lưu lượng dung dịch bọt Q_ct = S × J", `${nf1(sprRes.Qct)} L/s (S=${fmt(sprRes.S)} m² × J=${nf2(sprRes.J)})`, sprRes.muc]);
      trich.push(["Thời gian phun bọt t", `${sprRes.t} phút`, sprRes.muc]);
      trich.push(["Lượng dung dịch bọt W_dd = K·Q_ct·t·60", `${nf2(sprRes.Wdd/1000)} m³ (K=${nf1(sprRes.K)})`, "TCVN 5307, Phụ lục B"]);
      trich.push(["→ Chất tạo bọt đậm đặc (C_B=" + fmt(sprRes.CB) + "%)", `${fmt(Math.round(sprRes.Wctb))} L`, "TCVN 7278-3"]);
      trich.push(["→ Nước pha bọt (" + fmt(100-sprRes.CB) + "%)", `${nf2(sprRes.Wnuoc/1000)} m³`, "—"]);
      notes.push("Nhóm nguy cơ " + d.nhomNC + " dùng hệ chữa cháy bằng BỌT (không phải sprinkler nước). Cường độ J, thời gian t tra Bảng 1/2 TCVN 7336 theo loại chất cháy cụ thể — giá trị đang dùng là mặc định/người dùng nhập, cần đối chiếu khi thiết kế.");
    }
    else if(sprRes.kecao){
      const r = sprRes.res;
      if(sprRes.phuongAn==="1tang"){
        kq.Qtd = r.Qs; kq.tTd = 60; // Điều 4.8: tối thiểu 1h
        trich.push(["Lưu lượng đầu phun chủ đạo qcđ = [q5,5+0,19(h−5,5)]×[1+ψ(H−10)]", `${nf2(r.qcd)} L/s (q5,5=${r.q55}, ψ=${r.psi})`, "TCVN 14496, Điều 5.6–5.7"]);
        if(r.Qs!==null) trich.push(["Lưu lượng Qs = qcđ × N đầu phun (90 m²)", `${nf2(r.Qs)} L/s (N=${r.N})`, "TCVN 14496, Điều 5.10"]);
        trich.push(["Thời gian cấp nước tối thiểu", "60 phút", "TCVN 14496, Điều 4.8"]);
        r.ghichu.forEach(x=>notes.push(x));
        notes.push("Chế độ 1 tầng đầu phun (Điều 5): chỉ áp dụng nhóm nguy cơ 5/6, chiều cao gian phòng ≤ 14 m, chiều cao xếp hàng ≤ 12,5 m.");
      } else {
        kq.Qtd = r.Qs; kq.tTd = 60;
        trich.push(["Lưu lượng trong không gian kệ hàng Qi = A×B×n×i", `${nf2(r.Qi)} L/s (A=${r.A}, B=${fmt(r.B)}, n=${r.n}, i=${nf2(r.i)})`, r.muc_i]);
        trich.push(["Lưu lượng đầu phun dưới mái Qd = i_D×S_d", `${nf2(r.Qd)} L/s (i_D=${nf2(r.iD)}, S_d=${fmt(r.Sd)} m²)`, "TCVN 14496, Điều 6.6"]);
        trich.push(["Lưu lượng Qs = Qi + Qd", `${nf2(r.Qs)} L/s`, "TCVN 14496, Điều 6.13"]);
        trich.push(["Thời gian cấp nước tối thiểu", "60 phút", "TCVN 14496, Điều 4.8"]);
        notes.push("Chế độ nhiều tầng đầu phun (Điều 6): áp dụng chiều cao xếp hàng đến 25 m. Kiểm tra thêm bố trí tấm chắn, khoảng cách đầu phun theo Điều 6.7–6.17.");
      }
      notes.push("Kho kệ cao TCVN 14496: Vtd trong bảng dưới là dung tích cho hệ sprinkler kệ cao (Qs), CHƯA gồm màn nước Qd (Điều 4.19–4.22, nếu có) — cộng thêm thủ công nếu công trình có màn nước.");
    }
    else if(sprRes.kekcao){
      notes.push("Kho kệ cao (h > 5,5 m đến 25 m): tính QS/QD/QTN theo TCVN 14496:2025 — module riêng, KHÔNG tính trong phiếu sơ bộ. Vtd để trống.");
    } else {
      kq.Qtd = sprRes.Q; kq.tTd = sprRes.t;
      trich.push(["Lưu lượng chữa cháy tự động Qtđ", `${sprRes.Q} L/s`, sprRes.muc]);
      trich.push(["Thời gian phun ttđ", `${sprRes.t} phút`, sprRes.muc]);
      if(sprRes.note) notes.push(sprRes.note);
      if(sp.v!=="yes" && d.tangCuong) notes.push("Sprinkler được tính theo yêu cầu người dùng (tick \"Có tính toán hệ thống sprinkler\") dù công trình không thuộc diện bắt buộc chữa cháy tự động theo Bảng A.1.");
    }
  }

  /* --- Họng nước trong nhà --- */
  const tinhHong = hn.v==="yes" || ["sanxuat","kho"].includes(d.occ);
  if(tinhHong){
    const b = isKeCaoGroup ? traBang1_14496(d) : (["sanxuat","kho"].includes(d.occ) ? traBang12(d) : traBang11(d));
    if(b.err){ errs.push(b.err); }
    else {
      kq.Qtn = b.n*b.q;
      kq.tTn = isKeCaoGroup ? 60 : (!coSpr ? 60 : (d.nhomNC==="1" ? 30 : 60)); // Điều 4.8: kệ cao luôn tối thiểu 1h
      trich.push(["Họng nước trong nhà", `${b.n} tia × ${b.q} L/s = ${kq.Qtn} L/s`, b.muc]);
      trich.push(["Thời gian họng trong nhà t", `${kq.tTn} phút`, isKeCaoGroup?"Kho kệ cao TCVN 14496, Điều 4.8: tối thiểu 1 giờ, không phụ thuộc có/không có màn nước và họng nước":(!coSpr?"Không có sprinkler → t = 60 phút":(d.nhomNC==="1"?"Có sprinkler, nhóm nguy cơ 1 → t = 30 phút":"Có sprinkler, nhóm ≠ 1 → t = 60 phút"))]);
      if(isKeCaoGroup) notes.push("Kho kệ cao: lưu lượng họng nước trong nhà tra Bảng 1 TCVN 14496:2025 (không dùng Bảng 12 QCVN 06) theo Điều 4.11.");
      else if(["sanxuat","kho"].includes(d.occ)) notes.push("Nhà SX/kho: lưu lượng họng trong nhà tra Bảng 12 QCVN 06 — áp dụng khi công trình thuộc diện trang bị họng nước theo QCVN 06 (kỹ sư xác nhận diện).");
    }
  } else {
    notes.push("Không thuộc diện họng nước trong nhà theo sàng lọc BƯỚC 2 → Vtn: Không áp dụng / Không tính.");
  }

  /* --- Ngoài nhà --- */
  if(nn.v==="yes"){
    const b8 = traBang8(d);
    if(b8.err){ errs.push(b8.err); }
    else {
      kq.Qnn = b8.Q;
      trich.push(["Lưu lượng ngoài nhà Qnn", `${b8.Q} L/s`, b8.muc]);
      trich.push(["Thời gian ngoài nhà", "180 phút (3 giờ)", "Chú thích 1, 2 Bảng 8 QCVN 06"]);
      notes.push("Nếu mạng cấp nước đô thị/hạ tầng khu vực đã đảm bảo lưu lượng ngoài nhà thì bể của công trình có thể không phải dự trữ phần Vnn — kỹ sư xác nhận theo điều kiện hạ tầng thực tế.");
    }
  } else {
    notes.push("Không thuộc đối tượng cấp nước ngoài nhà theo Phụ lục C (Bảng C.1) QCVN 10 → Vnn: Không áp dụng / Không tính.");
  }

  /* --- FREEZE INPUT --- */
  freeze.push(["Công năng", OCCS.find(o=>o.id===d.occ).label]);
  freeze.push(["Số tầng / khối tích", `${d.floorsNoi} tầng nổi${d.semiBasements>0?" + "+d.semiBasements+" bán hầm (tính toán: "+d.floors+" tầng)":""}${d.basements>0?" + "+d.basements+" hầm":""} / ${fmt(d.volume)} m³`]);
  freeze.push(["Có sprinkler", coSpr ? (sp.v==="yes"?"Có (bắt buộc theo Bảng A.1)":"Có (tính theo yêu cầu người dùng)") : "Không"]);
  if(d.nhomNC) freeze.push(["Nhóm nguy cơ cháy", "Nhóm "+d.nhomNC+" (Phụ lục A TCVN 7336)"]);
  if(isBotGroup) freeze.push(["Thông số bọt (S / J / t / K / C_B)", `${fmt(d.botS)} m² / ${nf2(d.botJ)} L/s·m² / ${fmt(d.botT)}′ / K=${nf1(d.botK)} / ${fmt(d.botCB)}%`]);
  if(d.occ==="chungcu"&&d.corridor) freeze.push(["Hành lang chung", d.corridor==="gt10"?"> 10 m":"≤ 10 m"]);
  if(["sanxuat","kho"].includes(d.occ)) freeze.push(["Bậc chịu lửa / cấp S / hạng", `${d.bcl} / ${d.capS} / ${d.hazard}`]);
  if(["5","6","7"].includes(d.nhomNC)&&d.hXep) freeze.push(["Chiều cao xếp hàng h", ({"1":"đến 1 m","2":"1–2 m","3":"2–3 m","4":"3–4 m","5.5":"4–5,5 m",cao:"> 5,5 m (kệ cao)"})[d.hXep]]);
  if(d.hBaoVe!==null) freeze.push(["Chiều cao khu vực bảo vệ", d.hBaoVe+" m"]);

  /* --- TÍNH --- */
  if(kq.Qtn!==null) kq.Vtn = kq.Qtn*kq.tTn*60;
  if(kq.Qnn!==null) kq.Vnn = kq.Qnn*180*60;
  if(kq.Qtd!==null) kq.Vtd = kq.Qtd*kq.tTd*60;
  kq.Vbot = kqBot.Wdd;  // dung dịch bọt (lít)
  kq.Vtong = (kq.Vtn||0)+(kq.Vnn||0)+(kq.Vtd||0)+(kq.Vbot||0);

  return { trich, freeze, kq, kqBot, notes, errs, coSpr };
}

/* =====================================================================
   FORM — dựng select, trường bổ sung, kiểm tra đầu vào (BƯỚC 0)
   ===================================================================== */

const occSel = $("occ");
occSel.innerHTML = '<option value="">— Chọn công năng —</option>' + OCCS.map(o=>`<option value="${o.id}">${o.label}</option>`).join("");

/* Ẩn/hiện các trường tính nước theo trạng thái */
function updateGaraUI(){
  const isGara = occSel.value==="garakin";
  $("fsGara").style.display = isGara ? "" : "none";
  if(!isGara) return;
  const kinSel = $("x_garaKin");
  const val = kinSel ? kinSel.value : "";
  const floorsNoi = num("floors"), basements = num("basements")??0, semiBasements = num("semiBasements")??0;
  const B = (basements>0||semiBasements>0);
  const oneFloorGround = !B && (floorsNoi??0)<2;
  $("fGaraKC12").style.display = (val==="ho" && oneFloorGround) ? "" : "none";
  $("fGaraBCL").style.display = (val==="kin" && oneFloorGround) ? "" : "none";
  $("fGaraCapS").style.display = (val==="kin" && oneFloorGround) ? "" : "none";
}
function updateWaterUI(){
  const on = $("chkNuoc").checked;
  $("nuocGrid").style.display = on ? "" : "none";
  if(!on) return;
  const occId = occSel.value;
  const g = $("nhomNC").value;
  $("fHXep").style.display = ["5","6"].includes(g) ? "" : "none";
  $("fHBaoVe").style.display = (["5","6","7","4.2"].includes(g)) ? "none" : "";
  $("fCorridor").style.display = occId==="chungcu" ? "" : "none";
  const sxKho = ["sanxuat","kho"].includes(occId);
  $("fBCL").style.display = sxKho ? "" : "none";
  $("fCapS").style.display = sxKho ? "" : "none";
  const isBot = ["4.2","7"].includes(g);
  ["fBotNote","fBotS","fBotJ","fBotT","fBotK","fBotCB"].forEach(id=>$(id).style.display = isBot ? "" : "none");

  const isKeCao = ["5","6"].includes(g) && $("hXep").value==="cao";
  $("fKeCao").style.display = isKeCao ? "" : "none";
  $("fPhuongAn14496").style.display = isKeCao ? "" : "none";
  if(isKeCao){
    const pa = $("phuongAn14496").value;
    const isA = pa==="1tang";
    ["fNhomNC14496A","fHXepM","fHGianPhong","fSoDauPhun90"].forEach(id=>$(id).style.display = isA ? "" : "none");
    ["fLoaiPallet14496","fChieuRongKeB","fSoTamChan","fLoaiHang14496","fDaiCaoDo14496","fHXepM2","fDienTichMai90"].forEach(id=>$(id).style.display = isA ? "none" : "");
  } else {
    ["fNhomNC14496A","fHXepM","fHGianPhong","fSoDauPhun90","fLoaiPallet14496","fChieuRongKeB","fSoTamChan","fLoaiHang14496","fDaiCaoDo14496","fHXepM2","fDienTichMai90"].forEach(id=>$(id).style.display = "none");
  }
  $("fTangCuong").style.display = (isBot||isKeCao) ? "none" : "";
}
$("chkNuoc").addEventListener("change", updateWaterUI);
$("floors").addEventListener("input", updateGaraUI);
$("basements").addEventListener("input", updateGaraUI);
$("semiBasements").addEventListener("input", updateGaraUI);
$("nhomNC").addEventListener("change", updateWaterUI);
$("hXep").addEventListener("change", updateWaterUI);
$("phuongAn14496").addEventListener("change", updateWaterUI);

occSel.addEventListener("change", () => {
  const occ = OCCS.find(o=>o.id===occSel.value);
  const fs = $("fsExtra"), grid = $("extraGrid");
  grid.innerHTML = "";
  /* Gợi ý nhóm nguy cơ theo công năng */
  if(occ){
    $("nhomNC").value = NHOM_SUGGEST[occ.id] || "";
    $("nhomHint").textContent = $("nhomNC").value
      ? `Gợi ý theo Phụ lục A TCVN 7336 cho "${occ.label}": Nhóm ${$("nhomNC").value} — xác nhận hoặc chọn lại`
      : "App gợi ý theo công năng — xác nhận hoặc chọn lại";
  }
  updateWaterUI();
  if(occ && occ.extra && occ.extra.length){
    occ.extra.forEach(k=>{
      const f = EXTRA_FIELDS[k];
      const wrap = document.createElement("div");
      wrap.className = "field";
      const req = f.req ? ' <span class="req">*</span>' : "";
      let ctrl;
      if(f.select){
        ctrl = `<select id="x_${k}">${f.select.map(([v,l])=>`<option value="${v}">${l}</option>`).join("")}</select>`;
      } else {
        ctrl = `<input id="x_${k}" type="number" min="0" inputmode="numeric" placeholder="${f.ph||""}">`;
      }
      wrap.innerHTML = `<label for="x_${k}">${f.label}${req}<span class="hint">${f.hint}</span></label>${ctrl}`;
      grid.appendChild(wrap);
    });
    fs.style.display = "";
  } else fs.style.display = "none";
  updateGaraUI();
  const gk = $("x_garaKin");
  if(gk) gk.addEventListener("change", updateGaraUI);
});

function num(id){ const v = $(id) ? $(id).value.trim() : ""; return v==="" ? null : Number(v); }

function gather(){
  const errs = [];
  const mark = (id,bad)=>{ const el=$(id); if(el) el.classList.toggle("err",bad); };
  const occId = occSel.value;
  if(!occId) errs.push("Công năng chính");
  const floorsNoi = num("floors");
  const semiBasements = num("semiBasements") ?? 0;
  const d = {
    occ: occId,
    floorsNoi, semiBasements,
    floors: (floorsNoi ?? 0) + semiBasements, /* bán hầm tính như 1 tầng nổi khi so ngưỡng */
    basements: num("basements") ?? 0,
    areaFloor: num("areaFloor"), totalArea: num("totalArea"),
    volume: num("volume"), hFire: num("hFire"),
    extLevel: $("extLevel").value,
    kids: num("x_kids"), seats: num("x_seats"), pplFloor: num("x_pplFloor"),
    tunnelLength: num("x_tunnelLength"), pplTransport: num("x_pplTransport"),
    vesselGT: num("x_vesselGT"), enginePower: num("x_enginePower"),
    hazard: $("x_hazard") ? $("x_hazard").value : "",
    garaKin: $("x_garaKin") ? $("x_garaKin").value : "",
    garaKinVal: $("x_garaKin") ? $("x_garaKin").value : "",
    garaKC12: $("garaKC12").value, garaBcl: $("garaBcl").value, garaCapS: $("garaCapS").value,
    tinhNuoc: $("chkNuoc").checked,
    nhomNC: $("nhomNC").value, hXep: $("hXep").value, hBaoVe: num("hBaoVe"),
    corridor: $("corridor").value, bcl: $("bcl").value, capS: $("capS").value,
    tangCuong: $("chkTangCuong").checked,
    botS: num("botS"), botJ: num("botJ"), botT: num("botT"), botK: num("botK"), botCB: Number($("botCB").value),
    phuongAn14496: $("phuongAn14496").value,
    nhomNC14496: $("phuongAn14496").value==="1tang" ? $("nhomNC14496A").value : $("nhomNC").value,
    hXepM: num("hXepM"), hGianPhong: num("hGianPhong"), soDauPhun90: num("soDauPhun90"),
    loaiPallet14496: $("loaiPallet14496").value, chieuRongKeB: num("chieuRongKeB"), soTamChan: num("soTamChan"),
    loaiHang14496: $("loaiHang14496").value, daiCaoDo14496: $("daiCaoDo14496").value,
    hXepM2: num("hXepM2"), dienTichMai90: num("dienTichMai90")
  };
  [["floorsNoi","floors","Số tầng nổi"],["areaFloor","areaFloor","Diện tích 1 tầng"],["totalArea","totalArea","Tổng diện tích sàn ΣF"],["volume","volume","Tổng khối tích V"],["hFire","hFire","Chiều cao PCCC"]].forEach(([key,id,lb])=>{
    const bad = d[key]===null || isNaN(d[key]) || d[key]<0 || (id!=="hFire" && d[key]<=0);
    mark(id,bad); if(bad) errs.push(lb);
  });
  const occ = OCCS.find(o=>o.id===occId);
  if(occ && occ.extra){
    occ.extra.forEach(k=>{
      const f = EXTRA_FIELDS[k];
      if(f.req){
        const bad = f.select ? !d[k] : (d[k]===null||isNaN(d[k]));
        mark("x_"+k,bad); if(bad) errs.push(f.label+" (dữ liệu phân nhánh)");
      }
    });
  }
  /* Kiểm tra dữ liệu gara (chỉ khi công năng là garakin) */
  if(d.occ==="garakin" && !errs.length){
    if(!d.garaKin){ mark("x_garaKin",true); errs.push("Dạng nhà để xe (kín/hở)"); }
    else {
      const B = (d.basements>0||d.semiBasements>0);
      const oneFloorGround = !B && d.floors<2;
      if(oneFloorGround){
        if(d.garaKin==="ho" && !d.garaKC12){ mark("garaKC12",true); errs.push("Khoảng cách đến cạnh để hở (gara dạng hở)"); }
        if(d.garaKin==="kin"){
          if(!d.garaBcl){ mark("garaBcl",true); errs.push("Bậc chịu lửa (gara dạng kín, 1 tầng nổi)"); }
          if(!d.garaCapS){ mark("garaCapS",true); errs.push("Cấp nguy hiểm cháy kết cấu (gara dạng kín, 1 tầng nổi)"); }
        }
      }
    }
  }
  /* Kiểm tra dữ liệu tính nước (chỉ khi bật) */
  if(d.tinhNuoc && !errs.length){
    if(!d.nhomNC){ mark("nhomNC",true); errs.push("Nhóm nguy cơ cháy (Phụ lục A TCVN 7336)"); } else mark("nhomNC",false);
    if(["5","6"].includes(d.nhomNC) && !d.hXep){ mark("hXep",true); errs.push("Chiều cao xếp hàng h (kho nhóm 5–6)"); }
    if(["4.2","7"].includes(d.nhomNC)){
      if(d.botS===null||d.botS<=0){ mark("botS",true); errs.push("Diện tích tính toán chữa cháy bọt S"); } else mark("botS",false);
      if(d.botJ===null||d.botJ<=0){ mark("botJ",true); errs.push("Cường độ phun bọt J"); } else mark("botJ",false);
      if(d.botT===null||d.botT<=0){ mark("botT",true); errs.push("Thời gian phun bọt t"); } else mark("botT",false);
      if(d.botK===null||d.botK<1){ mark("botK",true); errs.push("Hệ số dự trữ K"); } else mark("botK",false);
    }
    const isKeCaoV = ["5","6"].includes(d.nhomNC) && d.hXep==="cao";
    if(isKeCaoV){
      if(d.phuongAn14496==="1tang"){
        if(d.hXepM===null||d.hXepM<=0){ mark("hXepM",true); errs.push("Chiều cao xếp hàng h (kệ cao, 1 tầng đầu phun)"); } else mark("hXepM",false);
        if(d.hGianPhong===null||d.hGianPhong<=0){ mark("hGianPhong",true); errs.push("Chiều cao gian phòng H (kệ cao, 1 tầng đầu phun)"); } else mark("hGianPhong",false);
      } else {
        if(!d.loaiPallet14496){ errs.push("Loại pallet (kệ cao, nhiều tầng đầu phun)"); }
        if(d.chieuRongKeB===null||d.chieuRongKeB<=0){ mark("chieuRongKeB",true); errs.push("Chiều rộng tối đa kệ hàng B"); } else mark("chieuRongKeB",false);
        if(d.soTamChan===null||d.soTamChan<=0){ mark("soTamChan",true); errs.push("Số tấm chắn n"); } else mark("soTamChan",false);
        if(!d.loaiHang14496){ errs.push("Loại hàng lưu trữ (kệ cao)"); }
        if(!d.daiCaoDo14496){ errs.push("Dải chiều cao giữa các tấm chắn"); }
        if(d.hXepM2===null||d.hXepM2<=0){ mark("hXepM2",true); errs.push("Chiều cao xếp hàng h (kệ cao, nhiều tầng đầu phun)"); } else mark("hXepM2",false);
      }
    }
    if(d.occ==="chungcu" && !d.corridor){ mark("corridor",true); errs.push("Chiều dài hành lang chung (nhà ở)"); }
    if(["sanxuat","kho"].includes(d.occ)){
      if(!d.bcl){ mark("bcl",true); errs.push("Bậc chịu lửa (tra Bảng 12)"); }
      if(!d.capS){ mark("capS",true); errs.push("Cấp nguy hiểm cháy kết cấu (tra Bảng 12)"); }
    }
  }
  const soft = [];
  if(d.totalArea!==null && d.areaFloor!==null && d.totalArea < d.areaFloor)
    soft.push("ΣF nhỏ hơn diện tích 1 tầng — kiểm tra lại số liệu.");
  return { d, errs, soft };
}

/* =====================================================================
   KẾT XUẤT PHIẾU
   ===================================================================== */


function render(d){
  const occ = OCCS.find(o=>o.id===d.occ);
  const td = evalThamDinh(d);
  const bc = evalBaoChay(d), sp = evalSprinkler(d), hn = evalHongNuoc(d), nn = evalNgoaiNha(d);
  const pd = evalPhaDo(d), mn = evalMatNa(d), loa = evalLoa(d), cg = evalCoGioi(d);
  const binh = evalBinh(d), den = evalDen(d);

  const now = new Date();
  const soPhieu = "TVSB-" + now.getFullYear() + String(now.getMonth()+1).padStart(2,"0") + String(now.getDate()).padStart(2,"0") + "-" + String(now.getHours()).padStart(2,"0") + String(now.getMinutes()).padStart(2,"0");
  const ngay = `ngày ${now.getDate()} tháng ${now.getMonth()+1} năm ${now.getFullYear()}`;

  const stampCls = td.v==="yes" ? "" : (td.v==="no" ? "khong" : "warn");
  const stampTxt = td.v==="yes" ? "Thuộc diện thẩm định" : (td.v==="no" ? "Không thuộc diện thẩm định" : "Cần đối chiếu thêm");

  const row = (ten,r) => `<tr><td><b>${ten}</b></td><td>${r.detail}<span class="cc">Căn cứ: ${r.canCu}</span></td><td>${BADGE[r.v]}</td></tr>`;

  /* BƯỚC 3/4 — phân nhánh nước */
  let nuoc = "";
  let nc = null;
  if(d.tinhNuoc){
    nc = evalNuoc(d, sp, hn, nn);
    const L2m3 = v => `${fmt(v)} L (= ${fmt(v/1000)} m³)`;
    const kqLine = (ten,v,q,t) => v!==null
      ? `<tr><td><b>${ten}</b></td><td>${q} L/s × ${t} phút × 60</td><td><b>${L2m3(v)}</b></td></tr>`
      : `<tr><td><b>${ten}</b></td><td colspan="2">Không áp dụng / Không tính</td></tr>`;
    nuoc = `
      ${sp.v==="warn" ? '<div class="note">Diện chữa cháy tự động đang ở trạng thái ⚠️ CẦN ĐỐI CHIẾU — kết quả dưới đây tính theo dữ liệu người dùng chọn; đối chiếu bản gốc trước khi dùng chính thức.</div>' : ''}
      <div class="card" style="margin-bottom:14px">
        <h4 style="font-family:var(--mono);font-size:12.5px;letter-spacing:.1em;color:var(--red);margin-bottom:8px">MỤC 3 — DỮ LIỆU TRÍCH</h4>
        ${nc.trich.length ? `<div class="tbl-wrap"><table>
          <tr><th>Nội dung trích</th><th style="width:22%">Giá trị</th><th style="width:40%">Nguồn tiêu chuẩn</th></tr>
          ${nc.trich.map(([a,b,c])=>`<tr><td>${a}</td><td><b>${b}</b></td><td><span style="font-family:var(--mono);font-size:11.5px">${c}</span></td></tr>`).join("")}
        </table></div>` : '<p style="font-size:14px">Không có nhánh nào áp dụng để trích dữ liệu.</p>'}
      </div>
      <div class="card" style="margin-bottom:14px">
        <h4 style="font-family:var(--mono);font-size:12.5px;letter-spacing:.1em;color:var(--red);margin-bottom:8px">MỤC 4 — FREEZE INPUT</h4>
        <div class="tbl-wrap"><table>
          ${nc.freeze.map(([a,b])=>`<tr><td style="width:40%">${a}</td><td><b>${b}</b></td></tr>`).join("")}
        </table></div>
      </div>
      <div class="card">
        <h4 style="font-family:var(--mono);font-size:12.5px;letter-spacing:.1em;color:var(--red);margin-bottom:8px">MỤC 5 — KẾT QUẢ</h4>
        <div class="tbl-wrap"><table>
          <tr><th>Thành phần</th><th>Công thức</th><th style="width:34%">Dung tích</th></tr>
          ${kqLine("Vtn — họng nước trong nhà",nc.kq.Vtn,nc.kq.Qtn,nc.kq.tTn)}
          ${kqLine("Vnn — cấp nước ngoài nhà",nc.kq.Vnn,nc.kq.Qnn,180)}
          ${kqLine("Vtd — chữa cháy tự động",nc.kq.Vtd,nc.kq.Qtd,nc.kq.tTd)}
          ${nc.kq.Vbot!==null ? `<tr><td><b>Vbọt — dung dịch bọt chữa cháy</b><br><span style="font-size:12px;color:var(--ink-soft)">gồm ${fmt(Math.round(nc.kqBot.Wctb))} L chất tạo bọt + ${nf2(nc.kqBot.Wnuoc/1000)} m³ nước</span></td><td>K × Q_ct × t × 60</td><td><b>${L2m3(nc.kq.Vbot)}</b></td></tr>` : ""}
          <tr><td colspan="2"><b>V_total = Vtn + Vnn + Vtd${nc.kq.Vbot!==null?" + Vbọt":""}</b></td><td><b style="color:var(--red-deep);font-size:16px">${L2m3(nc.kq.Vtong)}</b></td></tr>
        </table></div>
        <p style="font-size:13.5px;margin-top:10px">Lưu lượng bơm chữa cháy sơ bộ: ≥ Qtn + Qtđ khi các hệ trong nhà dùng chung trạm bơm${nc.kq.Qtn!==null&&nc.kq.Qtd!==null?` (≥ ${nc.kq.Qtn+nc.kq.Qtd} L/s)`:""}; cột áp bơm xác định theo tính toán thủy lực mạng ống — ngoài phạm vi phiếu sơ bộ.</p>
        ${nc.errs.length ? nc.errs.map(e=>`<div class="note" style="border-left-color:var(--red);background:var(--red-wash);border-color:#E3B9BA">${e}</div>`).join("") : ""}
        ${noteHtml(nc.notes)}
      </div>`;
  }
  else if(sp.v==="yes"){
    nuoc = `<div class="note blue"><b>Công trình thuộc diện chữa cháy tự động (sprinkler).</b> Bước tiếp theo: tính lưu lượng – thời gian – dung tích bể và thông số bơm theo TCVN 7336:2021 (kho kệ cao h &gt; 5,5 m: TCVN 14496:2025). Đầu vào cần gom: số tầng, ΣF, V, nhóm nguy cơ cháy theo công năng${d.occ==="chungcu"?", chiều dài hành lang":""}${["kho","sanxuat"].includes(d.occ)?", loại chất cháy và chiều cao xếp hàng/kệ h":""}. Phần tính toán này thực hiện bằng công cụ/skill <b>tinh-nuoc-chua-chay</b> riêng — ngoài phạm vi phiếu sơ bộ.</div>`;
  } else if(hn.v==="yes"){
    nuoc = `<div class="note blue"><b>Công trình chỉ thuộc diện hệ thống họng nước chữa cháy trong nhà</b>, không thuộc diện lắp đặt chữa cháy tự động sprinkler theo Bảng A.1. Nếu muốn, có thể tick <b>"Có tính toán hệ thống sprinkler"</b> ở mục IV để tính thêm; khi đó cần bổ sung: loại chất cháy/hàng hóa, nhóm nguy cơ cháy${["kho","sanxuat"].includes(d.occ)?", chiều cao xếp hàng/kệ h, loại pallet":""} — rồi tính theo TCVN 7336:2021 bằng công cụ/skill <b>tinh-nuoc-chua-chay</b>.</div>`;
  } else if(sp.v==="warn"){
    nuoc = `<div class="note"><b>Chưa kết luận được diện chữa cháy tự động</b> (ô ⚠️ hoặc thuộc Bảng A.2/A.3) — đối chiếu bản gốc trước khi quyết định bước tính nước.</div>`;
  } else {
    nuoc = `<div class="note blue">Công trình không thuộc diện sprinkler và họng nước trong nhà theo kết quả sàng lọc — chưa phát sinh yêu cầu tính bể/bơm chữa cháy trong nhà ở bước sơ bộ (vẫn kiểm tra cấp nước ngoài nhà theo hạ tầng khu vực).</div>`;
  }

  /* BƯỚC 6 — tổng hợp */
  const sumRow = (hm,r,badge) => `<tr><td>${hm}</td><td>${(badge||BADGE)[r.v]}</td><td><span style="font-family:var(--mono);font-size:11.5px">${r.canCu}</span></td></tr>`;
  const nx = [];
  nx.push(td.v==="yes" ? "Công trình <b>thuộc diện thẩm định thiết kế PCCC</b> theo Phụ lục III NĐ 105/2025 — hồ sơ thiết kế phải trình thẩm định trước khi thi công."
        : td.v==="no" ? "Công trình <b>không thuộc diện thẩm định</b> thiết kế PCCC theo Phụ lục III NĐ 105/2025 (vẫn phải tuân thủ quy chuẩn khi thiết kế, thi công)."
        : "Diện thẩm định <b>chưa kết luận cứng được</b> — vướng ô ⚠️/điều kiện cần xét thêm, đối chiếu bản gốc NĐ 105.");
  const sysY = [["báo cháy tự động",bc],["chữa cháy tự động (sprinkler)",sp],["họng nước trong nhà",hn],["cấp nước ngoài nhà",nn]].filter(x=>x[1].v==="yes").map(x=>x[0]);
  nx.push(sysY.length ? `Hệ thống bắt buộc theo QCVN 10: <b>${sysY.join("; ")}</b>.` : "Theo sàng lọc, chưa có hệ thống chính nào bắt buộc theo QCVN 10 — kiểm tra lại khi hồ sơ chi tiết hơn.");
  const ptY = [["dụng cụ phá dỡ",pd],["mặt nạ lọc độc",mn],["loa thông báo",loa]].filter(x=>x[1].v==="yes").map(x=>x[0]);
  const ptW = [["dụng cụ phá dỡ",pd],["mặt nạ lọc độc",mn],["loa thông báo",loa]].filter(x=>x[1].v==="warn").map(x=>x[0]);
  if(ptY.length) nx.push(`Phương tiện phải trang bị: <b>${ptY.join("; ")}</b>; cùng bình chữa cháy xách tay và đèn sự cố/chỉ dẫn thoát nạn theo TCVN.`);
  else nx.push("Bình chữa cháy xách tay và đèn sự cố/chỉ dẫn thoát nạn trang bị theo TCVN 7435-1 và TCVN 13456 như mục 5.");
  if(ptW.length) nx.push(`Hạng mục còn treo do ô ⚠️/thiếu dữ liệu: <b>${ptW.join("; ")}</b> — xác nhận trước khi chốt phiếu.`);
  const anyWarn = [td,bc,sp,hn,nn,pd,mn,loa].some(r=>r.v==="warn");
  if(anyWarn) nx.push("Phiếu có kết luận dựa trên bảng dựng từ bản OCR (ô ⚠️) — <b>bắt buộc đối chiếu bản gốc văn bản</b> trước khi sử dụng chính thức.");

  window.__phieuSnapshot = {
    goiY: `${occ.label} - ${d.floors} tầng - ${fmt(d.totalArea)}m²`,
    congNang: occ.label,
    soTang: d.floorsNoi + (d.semiBasements>0?` +${d.semiBasements}BH`:'') + (d.basements>0?` +${d.basements}H`:''),
    dtTang: d.areaFloor,
    tongDT: d.totalArea,
    khoiTich: d.volume,
    tham: td.v,
    baoChay: bc.v,
    sprinkler: sp.v,
    hongNuoc: hn.v,
    capNuocNgoai: nn.v,
    beNuoc: nc ? nc.kq.Vtong/1000 : null,
  };

  $("phieu").dataset.soPhieu = soPhieu;
  $("phieu").innerHTML = `
    <div class="phieu-head">
      <div>
        <div class="eyebrow">Phiếu tư vấn sơ bộ</div>
        <h2>${occ.label}</h2>
        <div class="sub">${d.floorsNoi} tầng nổi${d.semiBasements>0?` + ${d.semiBasements} bán hầm (số tầng tính toán: ${d.floors})`:""}${d.basements>0?` + ${d.basements} tầng hầm`:""} · DT tầng ${fmt(d.areaFloor)} m² · ΣF ${fmt(d.totalArea)} m² · V ${fmt(d.volume)} m³ · Chiều cao PCCC ${d.hFire} m${d.hazard?` · Hạng ${d.hazard}`:""}${d.kids!==null?` · ${fmt(d.kids)} cháu`:""}${d.seats!==null?` · ${fmt(d.seats)} chỗ`:""}</div>
      </div>
      <div class="phieu-meta">Số: <b>${soPhieu}</b><br>TP. Hồ Chí Minh, ${ngay}</div>
    </div>

    <section class="buoc">
      <div class="buoc-tag"><span class="num">BƯỚC 1</span><h3>Diện thẩm định thiết kế PCCC</h3></div>
      <div class="card">
        <div class="stamp-row">
          <div class="stamp ${stampCls}">${stampTxt}</div>
          <div class="stamp-note">${td.detail}<span class="cc" style="font-family:var(--mono);font-size:11.5px;color:var(--ink-soft);display:block;margin-top:4px">Căn cứ: ${td.canCu}</span></div>
        </div>
        ${noteHtml(td.notes)}
        ${d.semiBasements>0 ? '<div class="note blue">Tầng bán hầm được tính như 1 tầng nổi khi so các ngưỡng "cao ≥ X tầng" (số tầng tính toán = '+d.floors+' tầng). Đồng thời, các nhánh "tầng hầm/bán hầm" của Bảng A.1 và Phụ lục B QCVN 10 vẫn được xét vì bảng nêu rõ cả bán hầm.</div>' : ''}
      </div>
    </section>

    <section class="buoc">
      <div class="buoc-tag"><span class="num">BƯỚC 2</span><h3>Hệ thống PCCC bắt buộc (QCVN 10:2025/BCA)</h3></div>
      <div class="tbl-wrap"><table>
        <tr><th style="width:22%">Hệ thống</th><th>Đối chiếu ngưỡng</th><th style="width:16%">Kết luận</th></tr>
        ${row("Báo cháy tự động",bc)}
        ${row("Chữa cháy tự động (sprinkler)",sp)}
        ${row("Họng nước trong nhà",hn)}
        ${row("Cấp nước ngoài nhà",nn)}
      </table></div>
      ${noteHtml([...(bc.notes||[]),...(sp.notes||[])])}
    </section>

    <section class="buoc">
      <div class="buoc-tag"><span class="num">BƯỚC 3–4</span><h3>Nước chữa cháy</h3></div>
      ${nuoc}
    </section>

    <section class="buoc">
      <div class="buoc-tag"><span class="num">BƯỚC 5</span><h3>Phương tiện & hạng mục khác phải trang bị</h3></div>
      <div class="card">
        <div class="item"><h4>Dụng cụ phá dỡ thô sơ ${BADGE[pd.v]}</h4><p>${pd.detail}</p><span class="cc">Căn cứ: ${pd.canCu}</span></div>
        <div class="item"><h4>Mặt nạ lọc độc / phòng độc cách ly ${BADGE[mn.v]}</h4><p>${mn.detail}</p><span class="cc">Căn cứ: ${mn.canCu}</span></div>
        <div class="item"><h4>Loa thông báo & hướng dẫn thoát nạn ${BADGE[loa.v]}</h4><p>${loa.detail}</p><span class="cc">Căn cứ: ${loa.canCu}</span>${noteHtml(loa.notes)}</div>
        <div class="item"><h4>Phương tiện chữa cháy cơ giới ${BADGE[cg.v]}</h4><p>${cg.detail}</p><span class="cc">Căn cứ: ${cg.canCu}</span></div>
        <div class="item"><h4>Bình chữa cháy xách tay <span class="badge b-yes">TRANG BỊ</span></h4><p>${binh.detail}</p><span class="cc">Căn cứ: ${binh.canCu}</span>${noteHtml(binh.notes)}</div>
        <div class="item"><h4>Đèn chiếu sáng sự cố & chỉ dẫn thoát nạn <span class="badge b-yes">TRANG BỊ</span></h4>
          <p>Vị trí bắt buộc lắp đèn chiếu sáng sự cố:</p>
          <ul class="pos">${den.pos.map(p=>`<li>${p}</li>`).join("")}</ul>
          <span class="cc">Căn cứ: ${den.canCu}</span>${noteHtml(den.notes)}
        </div>
      </div>
    </section>

    <section class="buoc">
      <div class="buoc-tag"><span class="num">BƯỚC 6</span><h3>Bảng tổng hợp & nhận xét</h3></div>
      <div class="tbl-wrap"><table>
        <tr><th>Hạng mục</th><th style="width:20%">Kết luận</th><th style="width:34%">Căn cứ</th></tr>
        ${sumRow("Thẩm định thiết kế PCCC",td,BADGE_TD)}
        ${sumRow("Báo cháy tự động",bc)}
        ${sumRow("Chữa cháy tự động (sprinkler)",sp)}
        ${sumRow("Họng nước trong nhà",hn)}
        ${sumRow("Cấp nước ngoài nhà",nn)}
        ${sumRow("Dụng cụ phá dỡ thô sơ",pd)}
        ${sumRow("Mặt nạ lọc độc",mn)}
        ${sumRow("Loa thông báo thoát nạn",loa)}
        ${sumRow("Chữa cháy cơ giới",cg)}
        <tr><td>Bình chữa cháy xách tay</td><td><span class="badge b-yes">TRANG BỊ</span></td><td><span style="font-family:var(--mono);font-size:11.5px">TCVN 7435-1:2004</span></td></tr>
        <tr><td>Đèn sự cố / chỉ dẫn thoát nạn</td><td><span class="badge b-yes">TRANG BỊ</span></td><td><span style="font-family:var(--mono);font-size:11.5px">TCVN 13456:2022</span></td></tr>
        ${nc ? `<tr><td><b>Bể nước chữa cháy sơ bộ V_total</b></td><td><b style="color:var(--red-deep)">${fmt(nc.kq.Vtong/1000)} m³</b></td><td><span style="font-family:var(--mono);font-size:11.5px">QCVN 06 + TCVN 7336:2021 (chi tiết tại BƯỚC 3–4)</span></td></tr>` : ""}
      </table></div>
      <div class="nhanxet" style="margin-top:14px"><b>Nhận xét:</b><ul>${nx.map(x=>`<li>${x}</li>`).join("")}</ul></div>
      <div class="actions no-print" style="margin-top:16px">
        <button type="button" class="btn-main" id="btnInPhieu">In / xuất PDF phiếu</button>
        <button type="button" class="btn-ghost" id="btnXuatWord">Xuất Word (.doc)</button>
        <button type="button" class="btn-ghost" id="btnThemSoSanh">Thêm vào bảng so sánh</button>
      </div>
      <div class="disclaimer">
        <b>Lưu ý sử dụng:</b> Phiếu này là kết quả <b>sàng lọc sơ bộ</b> theo logic cố định, dùng tham khảo nội bộ — không thay thế thẩm định chính thức của cơ quan Cảnh sát PCCC&amp;CNCH và không thay thế đánh giá của kỹ sư đối với trường hợp đặc thù (công năng hỗn hợp phức tạp; khu vực/gian phòng/thiết bị theo Bảng A.2/A.3/A.4; chống khói theo QCVN 06 Phụ lục D — xử lý ở bước riêng). Các ô đánh dấu ⚠️ dựng từ bản OCR, <b>bắt buộc đối chiếu bản gốc văn bản</b> trước khi sử dụng chính thức. TCVN 3890 đã hết hiệu lực — không dùng.
      </div>
    </section>`;
  // Gan lai bang addEventListener (thay vi onclick="..." inline trong template
  // string o tren) de CSP script-src 'self' khong can 'unsafe-inline'.
  document.getElementById("btnInPhieu").addEventListener("click", () => window.print());
  document.getElementById("btnXuatWord").addEventListener("click", xuatWord);
  document.getElementById("btnThemSoSanh").addEventListener("click", themVaoSoSanh);
  $("phieu").classList.add("show");
  $("phieu").scrollIntoView({behavior:"smooth",block:"start"});
}

/* ---------- Xuất Word (.doc) ---------- */
function xuatWord(){
  const noiDung = $("phieu").innerHTML;
  const soPhieu = $("phieu").dataset.soPhieu || "phieu-tu-van-so-bo";
  const html = `<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
<head><meta charset="utf-8"><title>${soPhieu}</title>
<style>
  body{font-family:'Times New Roman',serif;font-size:13pt;color:#000}
  table{border-collapse:collapse;width:100%}
  td,th{border:1px solid #666;padding:6px;vertical-align:top}
  .no-print{display:none}
  .badge{border:1px solid #999;padding:1px 5px}
</style></head>
<body>${noiDung}</body></html>`;
  const blob = new Blob(["﻿", html], {type:"application/msword"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${soPhieu}.doc`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/* ---------- So sánh phương án (lưu tại trình duyệt, chưa cần database) ---------- */
const SOSANH_KEY = "pcccSoSanhPhuongAn";
function layDSSoSanh(){
  try { return JSON.parse(localStorage.getItem(SOSANH_KEY) || "[]"); } catch(e){ return []; }
}
function luuDSSoSanh(list){ localStorage.setItem(SOSANH_KEY, JSON.stringify(list)); }

function themVaoSoSanh(){
  if(!window.__phieuSnapshot) return;
  const nhan = prompt("Đặt tên ngắn cho phương án này:", window.__phieuSnapshot.goiY);
  if(nhan === null) return;
  const list = layDSSoSanh();
  list.push({ id: Date.now(), nhan: nhan.trim() || window.__phieuSnapshot.goiY, ...window.__phieuSnapshot });
  luuDSSoSanh(list);
  renderBangSoSanh();
}

function xoaSoSanh(id){
  luuDSSoSanh(layDSSoSanh().filter(x => x.id !== id));
  renderBangSoSanh();
}

function renderBangSoSanh(){
  const list = layDSSoSanh();
  const wrap = $("soSanhWrap");
  if(!list.length){ wrap.style.display = "none"; return; }
  wrap.style.display = "";
  const rows = [
    ["Công năng", x => x.congNang],
    ["Số tầng", x => x.soTang],
    ["DT tầng điển hình", x => fmt(x.dtTang) + " m²"],
    ["Tổng DT sàn ΣF", x => fmt(x.tongDT) + " m²"],
    ["Khối tích V", x => fmt(x.khoiTich) + " m³"],
    ["Diện thẩm định", x => BADGE_TD[x.tham]],
    ["Báo cháy tự động", x => BADGE[x.baoChay]],
    ["Chữa cháy tự động", x => BADGE[x.sprinkler]],
    ["Họng nước trong nhà", x => BADGE[x.hongNuoc]],
    ["Cấp nước ngoài nhà", x => BADGE[x.capNuocNgoai]],
    ["Bể nước sơ bộ", x => x.beNuoc != null ? fmt(Math.round(x.beNuoc)) + " m³" : "—"],
  ];
  let bodyHtml = "";
  rows.forEach(([label, f]) => {
    bodyHtml += `<tr><td><b>${label}</b></td>` + list.map(x => `<td>${f(x)}</td>`).join("") + "</tr>";
  });
  $("tblSoSanh").innerHTML = bodyHtml;

  // Dong dau: ten phuong an (x.nhan) do nguoi dung go qua prompt() trong
  // themVaoSoSanh(), luu vao localStorage - khong dang tin cay. Dung
  // createElement/textContent/addEventListener thay vi noi chuoi + onclick
  // inline de tranh XSS luu qua localStorage va phu hop CSP script-src 'self'.
  const headerRow = document.createElement("tr");
  const thCrit = document.createElement("th");
  thCrit.textContent = "Tiêu chí";
  headerRow.appendChild(thCrit);
  list.forEach(x => {
    const th = document.createElement("th");
    th.appendChild(document.createTextNode(x.nhan + " "));
    const btn = document.createElement("button");
    btn.type = "button";
    btn.title = "Xoá phương án này";
    btn.style.cssText = "border:none;background:none;color:var(--ink-soft);cursor:pointer;font-weight:700;font-size:13px";
    btn.textContent = "✕";
    btn.addEventListener("click", () => xoaSoSanh(x.id));
    th.appendChild(btn);
    headerRow.appendChild(th);
  });
  $("tblSoSanh").insertBefore(headerRow, $("tblSoSanh").firstChild);
}

/* ---------- Sự kiện ---------- */
$("btnXoaHetSoSanh").addEventListener("click", () => {
  if(confirm("Xoá toàn bộ bảng so sánh phương án?")){ luuDSSoSanh([]); renderBangSoSanh(); }
});
renderBangSoSanh();

$("frm").addEventListener("submit", e => {
  e.preventDefault();
  const { d, errs, soft } = gather();
  const msg = $("formMsg");
  if(errs.length){
    msg.innerHTML = "<b>DỪNG — thiếu dữ liệu bắt buộc</b> (Luật cứng số 1: không giả thiết dữ liệu phân nhánh): " + errs.join("; ") + ".";
    msg.classList.add("show");
    $("phieu").classList.remove("show");
    return;
  }
  msg.classList.remove("show");
  if(soft.length){
    msg.innerHTML = "Cảnh báo số liệu: " + soft.join(" ");
    msg.classList.add("show");
  }
  render(d);
});
$("btnReset").addEventListener("click", () => {
  $("frm").reset(); $("fsExtra").style.display="none"; $("extraGrid").innerHTML="";
  $("formMsg").classList.remove("show");
  document.querySelectorAll("input.err").forEach(el=>el.classList.remove("err"));
  $("phieu").classList.remove("show"); $("phieu").innerHTML="";
  updateWaterUI();
  window.scrollTo({top:0,behavior:"smooth"});
});
