import { BrowserRouter, Route, Routes } from "react-router";
import { PaperPage } from "./paper/PaperPage";
import { Styleguide } from "./styleguide/Styleguide";

export function App() {
  return (
    <BrowserRouter basename="/paper">
      <Routes>
        <Route path="styleguide" element={<Styleguide />} />
        <Route path=":agentId" element={<PaperPage />} />
        <Route path=":agentId/:runId" element={<PaperPage />} />
      </Routes>
    </BrowserRouter>
  );
}
