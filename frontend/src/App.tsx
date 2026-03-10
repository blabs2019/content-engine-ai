import { Routes, Route } from "react-router-dom";
import Verticals from "./pages/Verticals";
import DataViewer from "./pages/DataViewer";

export default function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Verticals />} />
        <Route path="/data/:verticalId" element={<DataViewer />} />
      </Routes>
    </div>
  );
}
