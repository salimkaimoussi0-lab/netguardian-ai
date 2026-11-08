import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App.jsx";
import "./index.css";
import CyberRangeLive from "./components/CyberRangeLive.jsx";
import CyberLabControls from "./components/CyberLabControls.jsx";

ReactDOM.createRoot(
  document.getElementById("root")
).render(
  <React.StrictMode>
    <>
        <App />
        <CyberRangeLive />
        <CyberLabControls />
      </>
  </React.StrictMode>
);
