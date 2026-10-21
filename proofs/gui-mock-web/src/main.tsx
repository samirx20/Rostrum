import { createRoot } from "react-dom/client";
import "./store";
import "./app.css";
import "./inspector.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(<App />);
