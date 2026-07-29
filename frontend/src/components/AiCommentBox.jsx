import { useState } from "react";
import { requestAiComment } from "../api/client";

export default function AiCommentBox({ result }) {
  const [provider, setProvider] = useState("claude");
  const [comment, setComment] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!result) return null;

  async function handleClick() {
    setLoading(true);
    setError(null);
    setComment(null);
    try {
      const res = await requestAiComment(provider, result);
      setComment(res.comment);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card ai-box">
      <h3>Nhận xét từ AI</h3>
      <div className="actions">
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="claude">Claude</option>
          <option value="gemini">Gemini</option>
        </select>
        <button type="button" onClick={handleClick} disabled={loading}>
          {loading ? "Đang hỏi AI..." : "Nhận xét từ AI"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {comment && <p className="ai-comment">{comment}</p>}
    </div>
  );
}
