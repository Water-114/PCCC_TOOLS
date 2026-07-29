import { useEffect, useState } from "react";
import { getThamDinhOccupancies, evaluateThamDinh } from "../api/client";

export default function ThamDinhForm({ onResult }) {
  const [meta, setMeta] = useState(null);
  const [occId, setOccId] = useState("");
  const [values, setValues] = useState({});
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getThamDinhOccupancies()
      .then(setMeta)
      .catch((err) => setError(err.message));
  }, []);

  const occ = meta?.occupations.find((o) => o.id === occId);
  const fieldKeys = occ ? [...(occ.fields || []), ...(occ.extra || [])] : [];

  function update(key, value) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function fieldMeta(key) {
    return meta.baseFields[key] || meta.extraFields[key];
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    onResult(null);
    try {
      const result = await evaluateThamDinh({ occ: occId, ...values });
      onResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!meta) return <p>Đang tải danh mục công năng...</p>;

  return (
    <form className="card" onSubmit={handleSubmit}>
      <fieldset>
        <legend>Diện thẩm định (Phụ lục III, NĐ 105/2025)</legend>
        <div className="grid">
          <label>
            Công năng công trình
            <select
              value={occId}
              onChange={(e) => {
                setOccId(e.target.value);
                setValues({});
                onResult(null);
              }}
            >
              <option value="">— Chọn công năng —</option>
              {meta.occupations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          {fieldKeys.map((key) => {
            const f = fieldMeta(key);
            return (
              <label key={key}>
                {f.label}
                {f.select ? (
                  <select value={values[key] ?? ""} onChange={(e) => update(key, e.target.value)}>
                    {f.select.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="number"
                    min="0"
                    placeholder={f.ph || ""}
                    value={values[key] ?? ""}
                    onChange={(e) => update(key, e.target.value)}
                  />
                )}
              </label>
            );
          })}
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}

      <div className="actions">
        <button type="submit" disabled={!occId || loading}>
          {loading ? "Đang kiểm tra..." : "Kiểm tra diện thẩm định"}
        </button>
      </div>
    </form>
  );
}
