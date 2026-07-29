import { useState } from "react";
import WaterCalcForm from "./components/WaterCalcForm";
import ResultPanel from "./components/ResultPanel";
import AiCommentBox from "./components/AiCommentBox";
import "./App.css";

function App() {
  const [result, setResult] = useState(null);

  return (
    <main className="wrap">
      <header>
        <h1>Tính dung tích bể nước chữa cháy</h1>
        <p>
          V = Q × t (QCVN 06, TCVN 7336) — bản demo MVP: React + Vite (UI) +
          Flask (API) + AI gateway (Claude/Gemini).
        </p>
      </header>

      <WaterCalcForm onResult={setResult} />
      <ResultPanel result={result} />
      <AiCommentBox result={result} />
    </main>
  );
}

export default App;
