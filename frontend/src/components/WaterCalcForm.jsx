import { useState } from "react";
import { calculateWaterTank } from "../api/client";

const initialForm = {
  htn_n: "",
  htn_q: "",
  htn_t: "",
  sp_q: "",
  sp_t: "",
  nn_q: "",
  nn_t: "180",
};

export default function WaterCalcForm({ onResult }) {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await calculateWaterTank(form);
      onResult(result);
    } catch (err) {
      setError(err.message);
      onResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <fieldset>
        <legend>Họng nước chữa cháy trong nhà</legend>
        <div className="grid">
          <label>
            Số tia phun đồng thời (tia)
            <input
              type="number"
              min="0"
              step="1"
              placeholder="VD: 2"
              value={form.htn_n}
              onChange={(e) => update("htn_n", e.target.value)}
            />
          </label>
          <label>
            Lưu lượng mỗi tia (L/s)
            <input
              type="number"
              min="0"
              step="0.1"
              placeholder="VD: 2.5"
              value={form.htn_q}
              onChange={(e) => update("htn_q", e.target.value)}
            />
          </label>
          <label>
            Thời gian duy trì (phút)
            <input
              type="number"
              min="0"
              step="1"
              placeholder="VD: 60"
              value={form.htn_t}
              onChange={(e) => update("htn_t", e.target.value)}
            />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Chữa cháy tự động (sprinkler / drencher)</legend>
        <div className="grid">
          <label>
            Lưu lượng Q (L/s)
            <input
              type="number"
              min="0"
              step="0.1"
              placeholder="VD: 30"
              value={form.sp_q}
              onChange={(e) => update("sp_q", e.target.value)}
            />
          </label>
          <label>
            Thời gian phun (phút)
            <input
              type="number"
              min="0"
              step="1"
              placeholder="VD: 60"
              value={form.sp_t}
              onChange={(e) => update("sp_t", e.target.value)}
            />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Cấp nước chữa cháy ngoài nhà</legend>
        <div className="grid">
          <label>
            Lưu lượng Q (L/s)
            <input
              type="number"
              min="0"
              step="0.1"
              placeholder="VD: 20"
              value={form.nn_q}
              onChange={(e) => update("nn_q", e.target.value)}
            />
          </label>
          <label>
            Thời gian duy trì (phút)
            <input
              type="number"
              min="0"
              step="1"
              value={form.nn_t}
              onChange={(e) => update("nn_t", e.target.value)}
            />
          </label>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}

      <div className="actions">
        <button type="submit" disabled={loading}>
          {loading ? "Đang tính..." : "Tính dung tích bể"}
        </button>
        <button type="button" onClick={() => { setForm(initialForm); onResult(null); }}>
          Nhập lại
        </button>
      </div>
    </form>
  );
}
