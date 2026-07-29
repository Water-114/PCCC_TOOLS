const LABELS = {
  yes: "Thuộc diện thẩm định",
  no: "Không thuộc diện thẩm định",
  warn: "Cần kỹ sư xem xét thêm",
  na: "Không xác định",
};

export default function ThamDinhResult({ result }) {
  if (!result) return null;

  return (
    <div className={`card result-panel tham-dinh-${result.result}`}>
      <h3>{LABELS[result.result] || result.result}</h3>
      <p>{result.detail}</p>
      <p className="can-cu">Căn cứ: {result.can_cu}</p>
      {result.notes && result.notes.length > 0 && (
        <ul className="notes">
          {result.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
