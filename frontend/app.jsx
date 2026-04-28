/**
 * 前端界面 - Hong Kong Ninja Park
 * 整合 AI Agent 对话 + 课程推荐系统
 *
 * 部署说明：
 * - 开发环境：确保 Flask 后端运行在 localhost:5000
 * - 生产环境：修改 API_BASE 为实际后端地址
 * - 也可以独立运行（不连接后端），使用内置的 Claude API 和本地 Excel 解析
 */

import { useState, useRef, useEffect, useCallback } from "react";

// ─── 配置 ───
// 如果有后端运行，前端会调用后端 API
// 如果没有后端，前端会直接调用 Claude API + 本地解析 Excel
const API_BASE = "http://localhost:5000/api";

// ─── 内置知识库（后端不可用时的 fallback） ───
const FALLBACK_KNOWLEDGE = `
【Hong Kong Ninja Park 香港障礙競技學園】
地址：香港鰂魚涌華蘭路20號華蘭中心2204室
電話：9832 2052 | 電郵：cs@hongkongninjapark.com
預約系統：https://sasukeninjaparkauau.auau.io/zh-HK/

訓練班類別：忍者班、Lache班、體操技巧班、體適能班、Muscle Up班
小朋友班費用：體驗班 $325/堂, 恆常班 $1188/4堂, $2860/10堂, $5500/20堂
成人班費用：$375/堂, $1390/4堂, $3325/10堂, $6500/20堂

Open Gym: 星期一至五 10:30-17:30, 18:00-21:45 | 週末 10:15-14:00, 14:15-18:00, 18:15-22:00
`;

const DEFAULT_CLASS_DATA = {
  dimensions: ["上肢力量", "协调", "柔韧性", "放松", "技巧"],
  classes: [
    { name: "忍者班", scores: [7, 9, 6, 10, 9], color: "#e63946", emoji: "🥷" },
    { name: "体适能班", scores: [7, 3, 4, 2, 3], color: "#2a9d8f", emoji: "💪" },
    { name: "体操班", scores: [5, 9, 9, 5, 9], color: "#e9c46a", emoji: "🤸" },
  ],
};

// ─── Radar Chart ───
function RadarChart({ dimensions, classes, selectedDims, size = 280 }) {
  const cx = size / 2, cy = size / 2, r = size * 0.38;
  const n = dimensions.length;
  const angleStep = (2 * Math.PI) / n;
  const levels = 5;

  const getPoint = (i, val, max = 10) => {
    const angle = angleStep * i - Math.PI / 2;
    const dist = (val / max) * r;
    return [cx + dist * Math.cos(angle), cy + dist * Math.sin(angle)];
  };

  return (
    <svg viewBox={`0 0 ${size} ${size}`} style={{ width: "100%", maxWidth: size }}>
      {Array.from({ length: levels }, (_, lv) => {
        const lr = ((lv + 1) / levels) * r;
        const pts = Array.from({ length: n }, (_, i) => {
          const a = angleStep * i - Math.PI / 2;
          return `${cx + lr * Math.cos(a)},${cy + lr * Math.sin(a)}`;
        }).join(" ");
        return <polygon key={lv} points={pts} fill="none" stroke="var(--grid)" strokeWidth={0.5} opacity={0.4} />;
      })}
      {dimensions.map((d, i) => {
        const [ex, ey] = getPoint(i, 10);
        const [lx, ly] = getPoint(i, 12.5);
        const sel = selectedDims.includes(i);
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={ex} y2={ey} stroke="var(--grid)" strokeWidth={0.5} opacity={0.3} />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="central"
              fontSize={11} fontWeight={sel ? 700 : 400}
              fill={sel ? "var(--accent)" : "var(--text-dim)"}>{d}</text>
          </g>
        );
      })}
      {classes.map((cls, ci) => {
        const pts = dimensions.map((_, i) => getPoint(i, cls.scores[i]).join(",")).join(" ");
        return (
          <g key={ci}>
            <polygon points={pts} fill={cls.color} fillOpacity={0.12} stroke={cls.color} strokeWidth={2} />
            {cls.scores.map((s, i) => {
              const [px, py] = getPoint(i, s);
              return <circle key={i} cx={px} cy={py} r={3} fill={cls.color} />;
            })}
          </g>
        );
      })}
    </svg>
  );
}

// ─── Main App ───
export default function NinjaParkApp() {
  const [tab, setTab] = useState("recommend");
  const [classData, setClassData] = useState(DEFAULT_CLASS_DATA);
  const [backendAvailable, setBackendAvailable] = useState(null); // null=checking, true/false
  const [selectedDims, setSelectedDims] = useState([]);
  const [showResult, setShowResult] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "你好！我是 Hong Kong Ninja Park 的智能助手 🥷\n歡迎查詢任何關於訓練班、自由練習、包場活動的問題！" }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // ── Check backend availability ──
  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json())
      .then(d => {
        setBackendAvailable(true);
        // Load class data from backend
        fetch(`${API_BASE}/recommend/data`).then(r => r.json()).then(setClassData);
      })
      .catch(() => setBackendAvailable(false));
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // ── Recommend ──
  const toggleDim = (i) => { setShowResult(false); setSelectedDims(p => p.includes(i) ? p.filter(x => x !== i) : [...p, i]); };

  const getResults = () => {
    if (selectedDims.length === 0) return [];
    return classData.classes.map(cls => {
      const total = selectedDims.reduce((s, di) => s + cls.scores[di], 0);
      const max = selectedDims.length * 10;
      return { ...cls, total, pct: Math.round((total / max) * 100) };
    }).sort((a, b) => b.total - a.total);
  };

  // ── Chat: try backend first, fallback to direct Claude API ──
  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages(p => [...p, { role: "user", text: userMsg }]);
    setLoading(true);

    try {
      let reply;

      if (backendAvailable) {
        // 调用 Flask 后端
        const history = messages.filter((_, i) => i > 0).map(m => ({ role: m.role === "assistant" ? "assistant" : "user", content: m.text }));
        const res = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userMsg, history }),
        });
        const data = await res.json();
        reply = data.reply || data.error || "无法获取回复";
      } else {
        // 直接调用 Claude API（前端 fallback）
        const res = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: "claude-sonnet-4-20250514",
            max_tokens: 1000,
            system: `你是 Hong Kong Ninja Park 的客服助手。根据以下知识库回答问题。用繁體中文或英文回答。如果用户想预约，引导到：https://sasukeninjaparkauau.auau.io/zh-HK/\n${FALLBACK_KNOWLEDGE}`,
            messages: [{ role: "user", content: userMsg }],
          }),
        });
        const data = await res.json();
        reply = data.content?.map(b => b.text || "").join("") || "暂时无法回应";
      }

      setMessages(p => [...p, { role: "assistant", text: reply }]);
    } catch {
      setMessages(p => [...p, { role: "assistant", text: "网络错误，请稍后再试。如有急事可致电 9832 2052。" }]);
    }
    setLoading(false);
  };

  // ── Excel upload ──
  const handleFileUpload = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (backendAvailable) {
      // 上传到后端
      const fd = new FormData();
      fd.append("file", file);
      try {
        const res = await fetch(`${API_BASE}/recommend/upload`, { method: "POST", body: fd });
        const data = await res.json();
        if (data.success) {
          setClassData(data.data);
          setSelectedDims([]);
          setShowResult(false);
          alert(`✅ ${data.message}`);
        } else {
          alert(`❌ ${data.error}`);
        }
      } catch { alert("上传失败，请检查后端是否运行"); }
    } else {
      // 本地解析
      try {
        const XLSX = await import("https://cdn.sheetjs.com/xlsx-0.20.0/package/xlsx.mjs");
        const buf = await file.arrayBuffer();
        const wb = XLSX.read(buf);
        const ws = wb.Sheets[wb.SheetNames[0]];
        const raw = XLSX.utils.sheet_to_json(ws, { header: 1 });
        if (raw.length < 2) { alert("Excel 格式不正确"); return; }

        const classNames = raw[0].slice(1).filter(Boolean);
        const dims = [];
        const scoreArrays = classNames.map(() => []);
        for (let r = 1; r < raw.length; r++) {
          if (!raw[r][0]) continue;
          dims.push(String(raw[r][0]));
          classNames.forEach((_, ci) => { scoreArrays[ci].push(Number(raw[r][ci + 1]) || 0); });
        }
        const colors = ["#e63946", "#2a9d8f", "#e9c46a", "#457b9d", "#f4a261", "#6a4c93"];
        const emojis = ["🥷", "💪", "🤸", "⚡", "🔥", "🌟"];
        setClassData({
          dimensions: dims,
          classes: classNames.map((name, i) => ({ name: String(name), scores: scoreArrays[i], color: colors[i % colors.length], emoji: emojis[i % emojis.length] })),
        });
        setSelectedDims([]);
        setShowResult(false);
        alert(`✅ 已载入 ${classNames.length} 个班型，${dims.length} 个维度`);
      } catch (err) { alert("读取失败: " + err.message); }
    }
    e.target.value = "";
  }, [backendAvailable]);

  const results = getResults();

  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg)",
      fontFamily: "'Noto Sans TC', 'Noto Sans SC', sans-serif",
      "--bg": "#0a0a0f", "--surface": "#141420", "--surface2": "#1c1c2e",
      "--border": "#2a2a40", "--grid": "#444466", "--text": "#e8e8f0",
      "--text-dim": "#8888aa", "--accent": "#ff4757", "--accent2": "#ffa502",
      color: "var(--text)",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700;900&family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ background: "linear-gradient(135deg, #0a0a0f 0%, #1a0a1e 50%, #0a0a0f 100%)", borderBottom: "1px solid var(--border)", padding: "20px 16px 12px", textAlign: "center" }}>
        <div style={{ fontSize: 28, fontWeight: 900, letterSpacing: 2, marginBottom: 4 }}>
          <span style={{ color: "var(--accent)" }}>NINJA</span>
          <span style={{ color: "var(--text)", opacity: 0.6 }}> PARK</span>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-dim)", letterSpacing: 4, textTransform: "uppercase" }}>Hong Kong Obstacle Training</div>

        {/* Backend status */}
        <div style={{ fontSize: 10, marginTop: 6, color: backendAvailable === null ? "var(--text-dim)" : backendAvailable ? "#2ed573" : "var(--accent2)" }}>
          {backendAvailable === null ? "⏳ 检测后端..." : backendAvailable ? "● 后端已连接" : "○ 独立模式（无后端）"}
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, marginTop: 12, background: "var(--surface)", borderRadius: 10, padding: 3 }}>
          {[{ key: "recommend", label: "🎯 课程推荐" }, { key: "agent", label: "🥷 智能助手" }].map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} style={{
              flex: 1, padding: "10px 8px", border: "none", borderRadius: 8, cursor: "pointer",
              background: tab === t.key ? "var(--accent)" : "transparent",
              color: tab === t.key ? "#fff" : "var(--text-dim)",
              fontFamily: "inherit", fontSize: 14, fontWeight: 600, transition: "all 0.2s",
            }}>{t.label}</button>
          ))}
        </div>
      </div>

      {/* ═══ RECOMMEND TAB ═══ */}
      {tab === "recommend" && (
        <div style={{ padding: "20px 16px", maxWidth: 500, margin: "0 auto" }}>
          {/* Upload */}
          <div style={{ background: "var(--surface)", borderRadius: 12, padding: "14px 16px", border: "1px dashed var(--border)", marginBottom: 20, textAlign: "center" }}>
            <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv" onChange={handleFileUpload} style={{ display: "none" }} />
            <button onClick={() => fileInputRef.current?.click()} style={{
              background: "var(--surface2)", color: "var(--text-dim)", border: "1px solid var(--border)",
              padding: "8px 20px", borderRadius: 8, cursor: "pointer", fontFamily: "inherit", fontSize: 13,
            }}>📁 上传评分表 Upload Excel</button>
            <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 6 }}>
              已载入 {classData.classes.length} 个班型 · {classData.dimensions.length} 个维度
            </div>
          </div>

          {/* Dimension selection */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>你想提升什么？</div>
            <div style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 14 }}>选择你最想改善的方面（可多选）</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {classData.dimensions.map((dim, i) => {
                const active = selectedDims.includes(i);
                return (
                  <button key={i} onClick={() => toggleDim(i)} style={{
                    padding: "10px 18px", borderRadius: 20, cursor: "pointer",
                    border: active ? "2px solid var(--accent)" : "2px solid var(--border)",
                    background: active ? "rgba(255,71,87,0.15)" : "var(--surface)",
                    color: active ? "var(--accent)" : "var(--text)",
                    fontFamily: "inherit", fontSize: 14, fontWeight: active ? 600 : 400, transition: "all 0.2s",
                  }}>{dim}</button>
                );
              })}
            </div>
          </div>

          {selectedDims.length > 0 && (
            <button onClick={() => setShowResult(true)} style={{
              width: "100%", padding: "14px", border: "none", borderRadius: 12, cursor: "pointer",
              background: "linear-gradient(135deg, var(--accent), #ff6b81)", color: "#fff",
              fontFamily: "inherit", fontSize: 16, fontWeight: 700, marginBottom: 20,
              boxShadow: "0 4px 20px rgba(255,71,87,0.3)",
            }}>查看推荐结果 →</button>
          )}

          {showResult && results.length > 0 && (
            <div>
              <div style={{ background: "var(--surface)", borderRadius: 16, padding: 16, border: "1px solid var(--border)", marginBottom: 16, textAlign: "center" }}>
                <RadarChart dimensions={classData.dimensions} classes={classData.classes} selectedDims={selectedDims} />
                <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 8 }}>
                  {classData.classes.map((cls, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                      <div style={{ width: 10, height: 10, borderRadius: 2, background: cls.color }} />{cls.name}
                    </div>
                  ))}
                </div>
              </div>

              {results.map((cls, i) => (
                <div key={i} style={{
                  background: i === 0 ? `linear-gradient(135deg, ${cls.color}18, ${cls.color}08)` : "var(--surface)",
                  borderRadius: 14, padding: "16px 18px", marginBottom: 10,
                  border: i === 0 ? `2px solid ${cls.color}` : "1px solid var(--border)", position: "relative", overflow: "hidden",
                }}>
                  {i === 0 && <div style={{ position: "absolute", top: 0, right: 0, background: cls.color, color: "#fff", fontSize: 10, fontWeight: 700, padding: "4px 12px", borderRadius: "0 0 0 10px" }}>最佳推荐 BEST</div>}
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ fontSize: 32 }}>{cls.emoji}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 17, fontWeight: 700 }}>{cls.name}</div>
                      <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 2 }}>匹配度 Match</div>
                    </div>
                    <div style={{ fontSize: 28, fontWeight: 900, color: cls.color }}>{cls.pct}%</div>
                  </div>
                  <div style={{ marginTop: 10, background: "var(--surface2)", borderRadius: 6, height: 6, overflow: "hidden" }}>
                    <div style={{ width: `${cls.pct}%`, height: "100%", borderRadius: 6, background: `linear-gradient(90deg, ${cls.color}, ${cls.color}aa)`, transition: "width 0.6s ease" }} />
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                    {selectedDims.map(di => (
                      <div key={di} style={{ fontSize: 11, background: "var(--surface2)", borderRadius: 6, padding: "3px 8px", color: "var(--text-dim)" }}>
                        {classData.dimensions[di]}: <span style={{ color: cls.color, fontWeight: 600 }}>{cls.scores[di]}</span>/10
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              <a href="https://sasukeninjaparkauau.auau.io/zh-HK/" target="_blank" rel="noopener noreferrer" style={{
                display: "block", textAlign: "center", padding: "14px",
                background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12,
                color: "var(--accent)", fontWeight: 600, fontSize: 14, textDecoration: "none", marginTop: 12,
              }}>立即预约 → Book Now</a>
            </div>
          )}
        </div>
      )}

      {/* ═══ AGENT TAB ═══ */}
      {tab === "agent" && (
        <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 150px)" }}>
          <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
            <div style={{ maxWidth: 500, margin: "0 auto" }}>
              {messages.map((m, i) => (
                <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: 12 }}>
                  <div style={{
                    maxWidth: "85%", padding: "12px 16px", borderRadius: 16, fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap",
                    background: m.role === "user" ? "linear-gradient(135deg, var(--accent), #ff6b81)" : "var(--surface)",
                    color: m.role === "user" ? "#fff" : "var(--text)",
                    border: m.role === "user" ? "none" : "1px solid var(--border)",
                    borderBottomRightRadius: m.role === "user" ? 4 : 16,
                    borderBottomLeftRadius: m.role === "user" ? 16 : 4,
                  }}>{m.text}</div>
                </div>
              ))}
              {loading && (
                <div style={{ display: "flex", marginBottom: 12 }}>
                  <div style={{ padding: "12px 20px", borderRadius: 16, borderBottomLeftRadius: 4, background: "var(--surface)", border: "1px solid var(--border)", fontSize: 14, color: "var(--text-dim)" }}>
                    <span style={{ animation: "pulse 1.2s infinite" }}>思考中...</span>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          </div>

          {/* Quick questions */}
          <div style={{ padding: "0 16px", maxWidth: 500, margin: "0 auto", width: "100%" }}>
            <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8 }}>
              {["有什么课程？", "收费多少？", "Open Gym时间？", "如何预约？"].map(q => (
                <button key={q} onClick={() => setInput(q)} style={{
                  whiteSpace: "nowrap", padding: "6px 14px", borderRadius: 16,
                  border: "1px solid var(--border)", background: "var(--surface)",
                  color: "var(--text-dim)", fontFamily: "inherit", fontSize: 12, cursor: "pointer", flexShrink: 0,
                }}>{q}</button>
              ))}
            </div>
          </div>

          <div style={{ padding: "8px 16px 16px", maxWidth: 500, margin: "0 auto", width: "100%" }}>
            <div style={{ display: "flex", gap: 8, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 14, padding: "6px 8px 6px 16px" }}>
              <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendMessage()}
                placeholder="输入你的问题..." style={{ flex: 1, border: "none", outline: "none", background: "transparent", color: "var(--text)", fontFamily: "inherit", fontSize: 14 }} />
              <button onClick={sendMessage} disabled={loading || !input.trim()} style={{
                width: 40, height: 40, borderRadius: 10, border: "none", cursor: "pointer",
                background: input.trim() ? "var(--accent)" : "var(--surface2)",
                color: "#fff", fontSize: 18, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s",
              }}>↑</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
        input::placeholder { color: var(--text-dim); }
      `}</style>
    </div>
  );
}
