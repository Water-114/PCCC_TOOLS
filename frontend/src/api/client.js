const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function postJSON(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Lỗi ${res.status}`);
  }
  return data;
}

export function calculateWaterTank(payload) {
  return postJSON("/api/water/calculate", payload);
}

export function requestAiComment(provider, result) {
  return postJSON("/api/ai/comment", { provider, result });
}
