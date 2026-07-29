export default function ResultPanel({ result }) {
  if (!result) return null;

  const rows = [
    ["Họng nước trong nhà", result.hong_nuoc_trong_nha],
    ["Chữa cháy tự động", result.chua_chay_tu_dong],
    ["Cấp nước ngoài nhà", result.cap_nuoc_ngoai_nha],
  ].filter(([, v]) => v.the_tich_m3 > 0);

  return (
    <div className="card result-panel">
      <h3>Kết quả</h3>
      <table>
        <tbody>
          {rows.map(([label, v]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{v.the_tich_m3} m³</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="total">
        Tổng dung tích bể nước: <strong>{result.tong.the_tich_m3} m³</strong>
      </p>
    </div>
  );
}
