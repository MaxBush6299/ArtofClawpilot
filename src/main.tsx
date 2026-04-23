import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App";
import Home from "./pages/Home";
import Room from "./pages/Room";
import Critic from "./pages/Critic";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Home />} />
          <Route path="rooms/:roomId" element={<Room />} />
          <Route path="critic" element={<Critic />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
