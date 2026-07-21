import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import KatipDashboard from "./pages/KatipDashboard";
import DraftEditor from "./pages/DraftEditor";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<KatipDashboard />} />
        <Route path="/drafts/:draftId" element={<DraftEditor />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
