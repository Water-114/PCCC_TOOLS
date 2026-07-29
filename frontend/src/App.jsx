import { useState } from "react";
import WaterCalcForm from "./components/WaterCalcForm";
import ResultPanel from "./components/ResultPanel";
import AiCommentBox from "./components/AiCommentBox";
import ThamDinhForm from "./components/ThamDinhForm";
import ThamDinhResult from "./components/ThamDinhResult";
import "./App.css";

const TABS = [
  { id: "nuoc", label: "Tính nước chữa cháy" },
  { id: "thamdinh", label: "Diện thẩm định (Phụ lục III)" },
];

function App() {
  const [tab, setTab] = useState("nuoc");
  const [waterResult, setWaterResult] = useState(null);
  const [thamDinhResult, setThamDinhResult] = useState(null);

  return (
    <main className="wrap">
      <header>
        <h1>Tư vấn PCCC — Demo MVP</h1>
        <p>React + Vite (UI) + Flask (API) + AI gateway (Claude/Gemini).</p>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "nuoc" && (
        <>
          <p className="tab-desc">
            V = Q × t (QCVN 06, TCVN 7336) — tính deterministic, có thể nhờ AI diễn giải kết quả.
          </p>
          <WaterCalcForm onResult={setWaterResult} />
          <ResultPanel result={waterResult} />
          <AiCommentBox result={waterResult} />
        </>
      )}

      {tab === "thamdinh" && (
        <>
          <p className="tab-desc">
            Xác định công trình có thuộc diện thẩm định thiết kế PCCC theo Phụ lục III, NĐ 105/2025/NĐ-CP hay không — rule-based, không dùng AI.
          </p>
          <ThamDinhForm onResult={setThamDinhResult} />
          <ThamDinhResult result={thamDinhResult} />
        </>
      )}
    </main>
  );
}

export default App;
