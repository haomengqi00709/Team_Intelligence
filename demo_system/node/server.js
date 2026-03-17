const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const path = require("path");

const app = express();
const PORT     = process.env.PORT     || 3000;
const API_BASE = process.env.API_BASE || "http://localhost:8000";

// Proxy all /api/* to FastAPI (mount at root to preserve the /api prefix)
app.use(
  createProxyMiddleware({
    target: API_BASE,
    changeOrigin: true,
    pathFilter: "/api/**",
    on: {
      error: (err, req, res) => {
        console.error("Proxy error:", err.message);
        res.status(502).json({ error: "Backend unavailable", detail: err.message });
      },
    },
  })
);

// Explicit routes
app.get("/login",     (req, res) => res.sendFile(path.join(__dirname, "public", "login.html")));
app.get("/dashboard", (req, res) => res.sendFile(path.join(__dirname, "public", "dashboard.html")));
app.get("/",          (req, res) => res.sendFile(path.join(__dirname, "public", "index.html")));

// Static assets (js, css, etc.)
app.use(express.static(path.join(__dirname, "public")));

app.listen(PORT, () => {
  console.log(`Team Intelligence running at http://localhost:${PORT}`);
  console.log(`Proxying /api/* → ${API_BASE}`);
});
