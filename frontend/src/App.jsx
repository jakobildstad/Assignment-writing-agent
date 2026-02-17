import { useState, useRef, useEffect, useCallback } from "react";
import Markdown from "react-markdown";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  Play,
  FileText,
  Search,
  PenTool,
  MessageSquare,
  CheckCircle2,
  Download,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertTriangle,
  X,
  Copy,
  Check,
  Settings,
  Globe,
  DollarSign,
  FileDown,
  History,
  ArrowRight,
  Sparkles,
  Plus,
  RotateCcw,
  Eye,
  Edit3,
  RefreshCw,
} from "lucide-react";

const API = "";

// ─── Constants ───────────────────────────────────────────────
const MODELS = [
  // Anthropic — current                        input/output per MTok
  { value: "claude-opus-4-6", label: "Claude Opus 4.6", price: "$5 / $25" },
  { value: "claude-sonnet-4-5-20250929", label: "Claude Sonnet 4.5", price: "$3 / $15" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5", price: "$1 / $5" },
  // Anthropic — legacy
  { value: "claude-opus-4-5-20251101", label: "Claude Opus 4.5", price: "$5 / $25" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4", price: "$3 / $15" },
  { value: "claude-opus-4-20250514", label: "Claude Opus 4", price: "$15 / $75" },
  // OpenAI — GPT-5 series
  { value: "gpt-5-2", label: "GPT-5.2", price: "$1.75 / $14" },
  { value: "gpt-5-1", label: "GPT-5.1", price: "$1.25 / $10" },
  { value: "gpt-5-2025-08-07", label: "GPT-5", price: "$1.25 / $10" },
  { value: "gpt-5-mini-2025-08-07", label: "GPT-5 Mini", price: "$0.25 / $2" },
  // OpenAI — reasoning (o-series)
  { value: "o3", label: "o3", price: "$2 / $8" },
  { value: "o3-pro", label: "o3-pro", price: "$20 / $80" },
  { value: "o3-mini", label: "o3-mini", price: "$1.10 / $4.40" },
  { value: "o4-mini", label: "o4-mini", price: "$1.10 / $4.40" },
  // OpenAI — GPT-4.1 series
  { value: "gpt-4.1-2025-04-14", label: "GPT-4.1", price: "$2 / $8" },
  { value: "gpt-4.1-mini-2025-04-14", label: "GPT-4.1 Mini", price: "$0.40 / $1.60" },
  { value: "gpt-4.1-nano-2025-04-14", label: "GPT-4.1 Nano", price: "$0.10 / $0.40" },
  // OpenAI — legacy
  { value: "gpt-4o", label: "GPT-4o", price: "$2.50 / $10" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini", price: "$0.15 / $0.60" },
];

const STEPS = [
  { id: "searcher", label: "Søk", icon: Search },
  { id: "writer", label: "Skriv", icon: PenTool },
  { id: "critic", label: "Kritikk", icon: MessageSquare },
  { id: "evaluator", label: "Vurdering", icon: CheckCircle2 },
];

const AGENTS = [
  { id: "searcher", label: "Søker", defaultTemp: 0.0, defaultMaxTokens: 4096 },
  { id: "writer", label: "Skriver", defaultTemp: 0.7, defaultMaxTokens: 8192 },
  { id: "critic", label: "Kritiker", defaultTemp: 0.2, defaultMaxTokens: 4096 },
];

const DEFAULT_SETTINGS = {
  agents: {
    searcher: { model: "claude-sonnet-4-5-20250929", temperature: 0.0, maxTokens: 4096 },
    writer: { model: "claude-sonnet-4-5-20250929", temperature: 0.7, maxTokens: 8192 },
    critic: { model: "claude-sonnet-4-5-20250929", temperature: 0.2, maxTokens: 4096 },
  },
  pipeline: {
    maxIterations: 3,
    scoreThreshold: 7.5,
    maxWords: 1500,
    language: "norsk",
  },
};

function loadSettings() {
  try {
    const saved = localStorage.getItem("exphil-settings");
    if (saved) return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
  } catch {}
  return DEFAULT_SETTINGS;
}

function saveSettings(s) {
  localStorage.setItem("exphil-settings", JSON.stringify(s));
}

// ═══════════════════════════════════════════════════════════════
// GRADIENT BACKGROUND — intense orbs on pure black
// ═══════════════════════════════════════════════════════════════
function GradientBackground() {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
      <div className="absolute inset-0 bg-black" />
      {/* Indigo — top center, massive */}
      <div
        className="absolute top-[-15%] left-[20%] w-[70vw] h-[70vw] max-w-[900px] max-h-[900px] rounded-full animate-orb1"
        style={{ background: "radial-gradient(circle, #4f46e5 0%, transparent 70%)", opacity: 0.3 }}
      />
      {/* Fuchsia — bottom left */}
      <div
        className="absolute bottom-[-10%] left-[-10%] w-[60vw] h-[60vw] max-w-[800px] max-h-[800px] rounded-full animate-orb2"
        style={{ background: "radial-gradient(circle, #d946ef 0%, transparent 70%)", opacity: 0.25 }}
      />
      {/* Orange — right center */}
      <div
        className="absolute top-[35%] right-[-15%] w-[55vw] h-[55vw] max-w-[700px] max-h-[700px] rounded-full animate-orb3"
        style={{ background: "radial-gradient(circle, #f97316 0%, transparent 70%)", opacity: 0.18 }}
      />
      {/* Cyan — bottom right, subtle */}
      <div
        className="absolute bottom-[10%] right-[10%] w-[50vw] h-[50vw] max-w-[650px] max-h-[650px] rounded-full animate-orb4"
        style={{ background: "radial-gradient(circle, #06b6d4 0%, transparent 70%)", opacity: 0.15 }}
      />
      {/* Noise grain */}
      <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")" }} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// GLASS CARD
// ═══════════════════════════════════════════════════════════════
function Glass({ children, className = "", active = false, ...props }) {
  return (
    <div
      className={`
        bg-white/[0.03] backdrop-blur-2xl border border-white/[0.06] rounded-2xl
        ${active ? "glass-glow-active" : "glass-glow"}
        transition-all duration-500
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// SCORE RING (SVG)
// ═══════════════════════════════════════════════════════════════
function ScoreRing({ score, size = 120 }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 10) * circumference;

  let color1 = "#ef4444";
  let color2 = "#f87171";
  if (score >= 8) { color1 = "#10b981"; color2 = "#34d399"; }
  else if (score >= 6) { color1 = "#eab308"; color2 = "#fbbf24"; }

  const gradId = `score-grad-${score}`;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color1} />
            <stop offset="100%" stopColor={color2} />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="5" />
        <motion.circle
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={`url(#${gradId})`} strokeWidth="5" strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - progress }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-light text-white/90">{score}</span>
        <span className="text-[10px] text-white/30 tracking-widest">/10</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// HEADER STEPPER — compact inline progress in the fixed header
// ═══════════════════════════════════════════════════════════════
function HeaderStepper({ activeAgent, completedSteps, pipelineStatus }) {
  return (
    <div className="flex items-center gap-1.5">
      {STEPS.map((step, i) => {
        const done = completedSteps.has(step.id);
        const active = activeAgent === step.id;
        const Icon = step.icon;

        return (
          <div key={step.id} className="flex items-center gap-1.5">
            <div className={`
              w-6 h-6 rounded-full flex items-center justify-center transition-all duration-500
              ${active ? "bg-violet-500/30 animate-step-pulse" : done ? "bg-emerald-500/15" : "bg-white/[0.04]"}
            `}>
              {active && pipelineStatus === "running" ? (
                <Loader2 className="w-3 h-3 text-violet-400 animate-spin" />
              ) : done ? (
                <Check className="w-3 h-3 text-emerald-400" />
              ) : (
                <Icon className={`w-3 h-3 ${active ? "text-violet-400" : "text-white/20"}`} />
              )}
            </div>
            <span className={`text-[10px] hidden sm:inline transition-colors duration-300 ${
              active ? "text-violet-400" : done ? "text-emerald-400/60" : "text-white/20"
            }`}>
              {step.label}
            </span>
            {i < STEPS.length - 1 && (
              <div className={`w-4 h-px transition-colors duration-500 ${done ? "bg-emerald-500/25" : "bg-white/[0.06]"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// FILE CHIP
// ═══════════════════════════════════════════════════════════════
function FileChip({ file, onRemove }) {
  const sizeKb = (file.size / 1024).toFixed(0);
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 bg-white/[0.04] border border-white/[0.06] rounded-full text-[11px]"
    >
      <FileText className="w-3 h-3 text-fuchsia-400/50" />
      <span className="text-white/60 truncate max-w-[100px]">{file.name}</span>
      <span className="text-white/20">{sizeKb}K</span>
      <button onClick={onRemove} className="p-0.5 text-white/15 hover:text-white/40 transition rounded-full hover:bg-white/[0.04]">
        <X className="w-3 h-3" />
      </button>
    </motion.div>
  );
}

// ═══════════════════════════════════════════════════════════════
// TOAST NOTIFICATION
// ═══════════════════════════════════════════════════════════════
function Toast({ toast, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 3500);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <motion.div
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex items-center gap-2.5 px-4 py-2.5 bg-black/80 backdrop-blur-2xl border border-white/[0.06] rounded-xl shadow-2xl shadow-black/40"
    >
      {toast.icon && <toast.icon className={`w-3.5 h-3.5 ${toast.color || "text-violet-400/70"}`} />}
      <span className="text-[12px] text-white/65 font-light">{toast.message}</span>
    </motion.div>
  );
}

function ToastContainer({ toasts, onDismiss }) {
  return (
    <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[80] flex flex-col items-center gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <Toast toast={t} onDismiss={onDismiss} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// INLINE MARKDOWN EDITOR (for final tab)
// ═══════════════════════════════════════════════════════════════
function InlineEditor({ draft, onSave, onReCritique, reCritiquing, sessionId }) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const originalRef = useRef("");

  function startEditing() {
    const text = draft?.body || "";
    setEditText(text);
    originalRef.current = text;
    setEditing(true);
  }

  function cancelEditing() {
    setEditText(originalRef.current);
    setEditing(false);
  }

  function resetToOriginal() {
    setEditText(originalRef.current);
  }

  const wordCount = editText.trim() ? editText.trim().split(/\s+/).length : 0;
  const hasChanges = editText !== originalRef.current;

  if (!draft?.body) return null;

  return (
    <div>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          {!editing ? (
            <button
              onClick={startEditing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg transition text-white/45 hover:text-white/65"
            >
              <Edit3 className="w-3 h-3" /> Rediger
            </button>
          ) : (
            <>
              <button
                onClick={() => { onSave(editText); setEditing(false); }}
                disabled={!hasChanges}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/20 rounded-lg transition text-violet-300/80 disabled:opacity-30"
              >
                <Check className="w-3 h-3" /> Lagre
              </button>
              <button
                onClick={cancelEditing}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg transition text-white/40"
              >
                <X className="w-3 h-3" /> Avbryt
              </button>
              <button
                onClick={resetToOriginal}
                disabled={!hasChanges}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg transition text-white/35 disabled:opacity-30"
              >
                <RotateCcw className="w-3 h-3" /> Tilbakestill
              </button>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {editing && (
            <span className="text-[10px] text-white/25 font-mono">{wordCount} ord</span>
          )}
          {editing && (
            <button
              onClick={() => onReCritique(editText)}
              disabled={reCritiquing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-amber-500/8 hover:bg-amber-500/15 border border-amber-500/15 rounded-lg transition text-amber-300/70 disabled:opacity-40"
            >
              {reCritiquing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Kjør kritikk på nytt
            </button>
          )}
        </div>
      </div>

      {/* Editor / Preview */}
      {editing ? (
        <textarea
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          className="w-full min-h-[50vh] px-5 py-4 bg-white/[0.02] border border-white/[0.04] rounded-xl text-[14px] text-white/75 leading-relaxed font-mono resize-y focus:outline-none focus:border-violet-500/20 transition"
        />
      ) : (
        <div className="prose prose-sm prose-glass max-w-none">
          <Markdown>{draft.body}</Markdown>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// PARAGRAPH DIFF VIEW (for draft tab)
// ═══════════════════════════════════════════════════════════════
function ParagraphDiff({ prevBody, currBody }) {
  if (!prevBody || !currBody) return null;

  const prevParas = prevBody.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
  const currParas = currBody.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);

  // Simple paragraph-level diff: match by similarity
  const used = new Set();
  const diffItems = [];

  for (const cp of currParas) {
    let bestIdx = -1;
    let bestRatio = 0;
    for (let i = 0; i < prevParas.length; i++) {
      if (used.has(i)) continue;
      // Quick similarity: shared words ratio
      const pw = new Set(prevParas[i].toLowerCase().split(/\s+/));
      const cw = new Set(cp.toLowerCase().split(/\s+/));
      const shared = [...cw].filter((w) => pw.has(w)).length;
      const ratio = shared / Math.max(pw.size, cw.size);
      if (ratio > bestRatio) {
        bestRatio = ratio;
        bestIdx = i;
      }
    }
    if (bestRatio > 0.4 && bestIdx >= 0) {
      used.add(bestIdx);
      const changed = bestRatio < 0.9;
      diffItems.push({ type: changed ? "modified" : "unchanged", text: cp });
    } else {
      diffItems.push({ type: "added", text: cp });
    }
  }

  // Find removed paragraphs
  for (let i = 0; i < prevParas.length; i++) {
    if (!used.has(i)) {
      diffItems.push({ type: "removed", text: prevParas[i] });
    }
  }

  const styles = {
    added: "bg-emerald-500/[0.06] border-l-2 border-emerald-500/30 pl-4",
    removed: "bg-red-500/[0.06] border-l-2 border-red-500/30 pl-4 line-through opacity-50",
    modified: "bg-amber-500/[0.04] border-l-2 border-amber-500/25 pl-4",
    unchanged: "",
  };

  const labels = {
    added: { text: "Nytt", color: "text-emerald-400/60 bg-emerald-500/10" },
    removed: { text: "Fjernet", color: "text-red-400/60 bg-red-500/10" },
    modified: { text: "Endret", color: "text-amber-400/60 bg-amber-500/10" },
  };

  return (
    <div className="space-y-3">
      {diffItems.map((item, i) => (
        <div key={i} className={`py-2 pr-3 rounded-lg text-sm text-white/60 leading-relaxed ${styles[item.type]}`}>
          {labels[item.type] && (
            <span className={`inline-block text-[9px] px-1.5 py-0.5 rounded-full mb-1 ${labels[item.type].color}`}>
              {labels[item.type].text}
            </span>
          )}
          <p className="whitespace-pre-wrap">{item.text}</p>
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// AGENT CONFIG (inside settings slide-over)
// ═══════════════════════════════════════════════════════════════
function AgentConfigSection({ agent, config, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-white/[0.04] last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-xs font-medium text-white/50 hover:text-white/70 transition"
      >
        {agent.label}
        <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3">
              <div>
                <label className="text-[10px] text-white/25 uppercase tracking-wider">Modell</label>
                <select
                  value={config.model}
                  onChange={(e) => onChange({ ...config, model: e.target.value })}
                  className="mt-1 w-full px-2.5 py-1.5 bg-white/[0.03] border border-white/[0.06] rounded-lg text-xs text-white/60 focus:outline-none focus:border-violet-500/30 transition appearance-none"
                >
                  {MODELS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}{m.price ? ` — ${m.price}` : ""}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[10px] text-white/25 uppercase tracking-wider">Temperatur</label>
                  <span className="text-[10px] text-violet-400/70 font-mono">{config.temperature.toFixed(1)}</span>
                </div>
                <input
                  type="range" min="0" max="1" step="0.1"
                  value={config.temperature}
                  onChange={(e) => onChange({ ...config, temperature: parseFloat(e.target.value) })}
                  className="w-full mt-1.5"
                />
              </div>
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[10px] text-white/25 uppercase tracking-wider">Maks tokens</label>
                  <span className="text-[10px] text-violet-400/70 font-mono">{(config.maxTokens || agent.defaultMaxTokens).toLocaleString()}</span>
                </div>
                <input
                  type="range" min="1024" max="16384" step="1024"
                  value={config.maxTokens || agent.defaultMaxTokens}
                  onChange={(e) => onChange({ ...config, maxTokens: parseInt(e.target.value) })}
                  className="w-full mt-1.5"
                />
                <div className="flex justify-between mt-0.5">
                  <span className="text-[9px] text-white/15">1K</span>
                  <span className="text-[9px] text-white/15">16K</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// CRITIQUE VIEW
// ═══════════════════════════════════════════════════════════════
function CritiqueView({ critique }) {
  if (!critique) return null;
  return (
    <div className="space-y-6">
      <div className="flex justify-center py-4">
        <ScoreRing score={critique.score} />
      </div>
      {critique.overall_assessment && (
        <p className="text-sm text-white/50 leading-relaxed text-center max-w-xl mx-auto">
          {critique.overall_assessment}
        </p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {critique.strengths?.length > 0 && (
          <Glass className="p-4">
            <h4 className="text-[10px] font-medium text-emerald-400/80 uppercase tracking-wider mb-2">Styrker</h4>
            <ul className="space-y-1.5">
              {critique.strengths.map((s, i) => (
                <li key={i} className="text-xs text-white/50 flex gap-2">
                  <span className="text-emerald-400/40 mt-px shrink-0">+</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </Glass>
        )}
        {critique.weaknesses?.length > 0 && (
          <Glass className="p-4">
            <h4 className="text-[10px] font-medium text-red-400/80 uppercase tracking-wider mb-2">Svakheter</h4>
            <ul className="space-y-1.5">
              {critique.weaknesses.map((w, i) => (
                <li key={i} className="text-xs text-white/50 flex gap-2">
                  <span className="text-red-400/40 mt-px shrink-0">-</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </Glass>
        )}
      </div>
      {critique.specific_feedback?.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-medium text-white/30 uppercase tracking-wider">Detaljert feedback</h4>
          {critique.specific_feedback.map((fb, i) => (
            <Glass key={i} className="p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-medium text-violet-400/70">{fb.section || `Punkt ${i + 1}`}</span>
                {fb.severity && (
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                    fb.severity === "high" ? "bg-red-500/8 text-red-400/80" :
                    fb.severity === "medium" ? "bg-yellow-500/8 text-yellow-400/80" :
                    "bg-white/4 text-white/35"
                  }`}>{fb.severity}</span>
                )}
              </div>
              <p className="text-xs text-white/45">{fb.comment || fb.feedback || JSON.stringify(fb)}</p>
            </Glass>
          ))}
        </div>
      )}
      {critique.revision_priority?.length > 0 && (
        <div>
          <h4 className="text-[10px] font-medium text-yellow-400/60 uppercase tracking-wider mb-2">Revisjonsprioritet</h4>
          <ol className="space-y-1">
            {critique.revision_priority.map((r, i) => (
              <li key={i} className="text-xs text-white/45 flex gap-2">
                <span className="text-yellow-400/40 font-mono shrink-0">{i + 1}.</span>
                <span>{r}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// EXPORT BUTTONS
// ═══════════════════════════════════════════════════════════════
function ExportButtons({ draft, sessionId }) {
  const [copied, setCopied] = useState(false);
  if (!draft?.body) return null;

  function buildMd() {
    const refs = (draft.references || [])
      .map((r) => `- ${r.author} (${r.year}). *${r.title}*.${r.page ? ` s. ${r.page}.` : ""}${r.url ? ` ${r.url}` : ""}`)
      .join("\n");
    return `# ${draft.title || "Essay"}\n\n${draft.body}\n\n## Referanser\n\n${refs}`;
  }
  function downloadMd() {
    const blob = new Blob([buildMd()], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(draft.title || "essay").replace(/\s+/g, "_")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }
  function downloadDocx() {
    if (!sessionId) return;
    const a = document.createElement("a");
    a.href = `${API}/api/export/docx/${sessionId}`;
    a.download = `${(draft.title || "essay").replace(/\s+/g, "_")}.docx`;
    a.click();
  }
  function handleCopy() {
    navigator.clipboard.writeText(buildMd()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="flex gap-2">
      <button onClick={downloadMd} className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg transition text-white/50">
        <Download className="w-3 h-3" /> .md
      </button>
      {sessionId && (
        <button onClick={downloadDocx} className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg transition text-white/50">
          <FileDown className="w-3 h-3" /> .docx
        </button>
      )}
      <button onClick={handleCopy} className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg transition text-white/50">
        {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
        {copied ? "Kopiert" : "Kopier"}
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// LOG FOOTER
// ═══════════════════════════════════════════════════════════════
function LogFooter({ logs }) {
  const [open, setOpen] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, open]);

  return (
    <div className="border-t border-white/[0.04]">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-2 text-[10px] text-white/20 hover:text-white/35 transition"
      >
        <span>Logg ({logs.length})</span>
        <ChevronUp className={`w-3 h-3 transition-transform ${open ? "" : "rotate-180"}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 160 }} exit={{ height: 0 }} className="overflow-hidden">
            <div className="px-5 pb-3 h-40 overflow-y-auto font-mono text-[10px]">
              {logs.map((line, i) => (
                <div key={i} className="py-px text-white/20">
                  <span className="text-white/8 mr-2">{String(i + 1).padStart(3, "0")}</span>
                  {line}
                </div>
              ))}
              <div ref={endRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// ─── MAIN APP ─────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════
export default function App() {
  // ── Settings ──
  const [settings, setSettings] = useState(loadSettings);

  function updateAgent(id, cfg) {
    setSettings((s) => {
      const next = { ...s, agents: { ...s.agents, [id]: cfg } };
      saveSettings(next);
      return next;
    });
  }
  function updatePipeline(key, val) {
    setSettings((s) => {
      const next = { ...s, pipeline: { ...s.pipeline, [key]: val } };
      saveSettings(next);
      return next;
    });
  }

  // ── Files & Session ──
  const [files, setFiles] = useState([]);
  const [task, setTask] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [connected, setConnected] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [running, setRunning] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  // ── Pipeline State ──
  const [activeAgent, setActiveAgent] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState("idle");
  const [iteration, setIteration] = useState(1);
  const [currentDraft, setCurrentDraft] = useState(null);
  const [draftHistory, setDraftHistory] = useState([]);
  const [finalDraft, setFinalDraft] = useState(null);
  const [critiques, setCritiques] = useState([]);
  const [logs, setLogs] = useState([]);
  const [errorMsg, setErrorMsg] = useState(null);
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [tokenUsage, setTokenUsage] = useState([]);
  const [totalCost, setTotalCost] = useState(0);

  // ── UI State ──
  const [activeTab, setActiveTab] = useState("draft");
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyList, setHistoryList] = useState([]);
  const [rehydrating, setRehydrating] = useState(false);
  const [showDiff, setShowDiff] = useState(false);

  // ── Auto-tab navigation ──
  const [autoTabEnabled, setAutoTabEnabled] = useState(true);
  const autoTabRef = useRef(true); // synchronous mirror for use inside callbacks
  const [toasts, setToasts] = useState([]);
  const [lastAutoTab, setLastAutoTab] = useState(null);

  // ── Inline editor ──
  const [reCritiquing, setReCritiquing] = useState(false);

  const wsRef = useRef(null);
  const toastIdRef = useRef(0);

  // ── Derived ──
  const latestCritique = critiques.length > 0 ? critiques[critiques.length - 1] : null;
  const isInputMode = pipelineStatus === "idle";
  const isPipelineMode = !isInputMode;

  // ── Close panels on click outside ──
  useEffect(() => {
    if (!showHistory && !showSettings) return;
    const handler = (e) => {
      if (showHistory && !e.target.closest("[data-history-dropdown]")) setShowHistory(false);
      if (showSettings && !e.target.closest("[data-settings-panel]") && !e.target.closest("[data-settings-trigger]")) setShowSettings(false);
    };
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, [showHistory, showSettings]);

  // ── WebSocket ──
  useEffect(() => {
    if (!sessionId) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/${sessionId}`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
    return () => { ws.close(); setConnected(false); };
  }, [sessionId]);

  // ── Persist active session_id to localStorage ──
  useEffect(() => {
    if (sessionId) localStorage.setItem("exphil-active-session", sessionId);
  }, [sessionId]);

  // ── Rehydrate from localStorage on mount ──
  useEffect(() => {
    const savedId = localStorage.getItem("exphil-active-session");
    if (!savedId) return;
    setRehydrating(true);
    fetch(`${API}/api/session/${savedId}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) { localStorage.removeItem("exphil-active-session"); return; }
        setSessionId(data.session_id);
        setTask(data.task_text || "");
        if (data.status === "completed") {
          setPipelineStatus("completed");
          setCompletedSteps(new Set(["searcher", "writer", "critic", "evaluator"]));
          setFinalDraft(data.final_draft || null);
          setCurrentDraft(data.drafts?.[data.drafts.length - 1] || null);
          setCritiques((data.critiques || []).map((c, i) => ({ ...c, _iteration: i + 1 })));
          setIteration(data.iteration || 1);
          setTokenUsage(data.token_usage || []);
          setTotalCost(data.total_cost_usd || 0);
          setActiveTab("final");
          setLogs((data.progress_log || []).map((e) => e.message || e));
        } else if (data.status === "error") {
          setPipelineStatus("error");
          setErrorMsg(data.error || "Unknown error");
          setCurrentDraft(data.drafts?.[data.drafts.length - 1] || null);
          setCritiques((data.critiques || []).map((c, i) => ({ ...c, _iteration: i + 1 })));
          setTokenUsage(data.token_usage || []);
          setTotalCost(data.total_cost_usd || 0);
          setLogs((data.progress_log || []).map((e) => e.message || e));
        } else if (data.status === "running") {
          setPipelineStatus("running");
          setRunning(true);
          setIteration(data.iteration || 1);
          setCurrentDraft(data.drafts?.[data.drafts.length - 1] || null);
          setCritiques((data.critiques || []).map((c, i) => ({ ...c, _iteration: i + 1 })));
          setTokenUsage(data.token_usage || []);
          setTotalCost(data.total_cost_usd || 0);
          setLogs((data.progress_log || []).map((e) => e.message || e));
          const phase = data.current_phase || "";
          const steps = new Set();
          if (["writing", "critiquing", "evaluating", "done"].includes(phase) || data.sources) steps.add("searcher");
          if (["critiquing", "evaluating", "done"].includes(phase) || data.drafts?.length > 0) steps.add("writer");
          if (["evaluating", "done"].includes(phase) || data.critiques?.length > 0) steps.add("critic");
          setCompletedSteps(steps);
        }
      })
      .catch(() => { localStorage.removeItem("exphil-active-session"); })
      .finally(() => setRehydrating(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Fetch history ──
  function fetchHistory() {
    fetch(`${API}/api/sessions`)
      .then((r) => r.json())
      .then((list) => { if (Array.isArray(list)) setHistoryList(list); })
      .catch(() => {});
  }

  function loadSession(id) {
    setShowHistory(false);
    setRehydrating(true);
    fetch(`${API}/api/session/${id}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) return;
        setRunning(false); setActiveAgent(null); setErrorMsg(null);
        setSessionId(data.session_id);
        setTask(data.task_text || "");
        setIteration(data.iteration || 1);
        setCurrentDraft(data.drafts?.[data.drafts.length - 1] || null);
        setFinalDraft(data.final_draft || null);
        setCritiques((data.critiques || []).map((c, i) => ({ ...c, _iteration: i + 1 })));
        setTokenUsage(data.token_usage || []);
        setTotalCost(data.total_cost_usd || 0);
        setLogs((data.progress_log || []).map((e) => e.message || e));
        if (data.status === "completed") {
          setPipelineStatus("completed");
          setCompletedSteps(new Set(["searcher", "writer", "critic", "evaluator"]));
          setActiveTab("final");
        } else if (data.status === "error") {
          setPipelineStatus("error");
          setErrorMsg(data.error || "Unknown error");
        } else {
          setPipelineStatus("running");
          setRunning(true);
        }
        localStorage.setItem("exphil-active-session", data.session_id);
      })
      .catch(() => {})
      .finally(() => setRehydrating(false));
  }

  const handleEvent = useCallback((ev) => {
    const { event, agent, message } = ev;
    if (message) setLogs((p) => [...p, `[${ev.timestamp || ""}] ${message}`]);

    // Helper: emit a toast notification
    const emitToast = (toastMsg, icon, color) => {
      const id = ++toastIdRef.current;
      setToasts((p) => [...p.slice(-3), { id, message: toastMsg, icon, color }]);
    };

    // Helper: switch tab only if auto-tab is enabled (read synchronously via ref)
    const autoSwitch = (tab, toastMsg, icon, color) => {
      if (autoTabRef.current) {
        setActiveTab(tab);
        setLastAutoTab(tab);
      }
      if (toastMsg) emitToast(toastMsg, icon, color);
    };

    // Re-enable auto-tab on new phase boundaries
    const reEnableAutoTab = () => {
      autoTabRef.current = true;
      setAutoTabEnabled(true);
    };

    switch (event) {
      case "agent_start":
        setActiveAgent(agent);
        reEnableAutoTab();
        if (agent === "searcher") autoSwitch("draft", "Søker etter kilder...", Search, "text-cyan-400/70");
        else if (agent === "writer") autoSwitch("draft", "Skriver utkast...", PenTool, "text-violet-400/70");
        else if (agent === "critic") autoSwitch("critique", "Evaluerer utkast...", MessageSquare, "text-amber-400/70");
        else if (agent === "evaluator") autoSwitch("critique", "Vurderer kvalitet...", CheckCircle2, "text-emerald-400/70");
        break;
      case "agent_complete": setCompletedSteps((p) => new Set([...p, agent])); break;
      case "revision_start":
        setActiveAgent("writer"); setIteration(ev.iteration || 2);
        setCompletedSteps(new Set(["searcher"]));
        reEnableAutoTab();
        autoSwitch("draft", `Revisjon ${ev.iteration || 2} startet`, ArrowRight, "text-violet-400/70");
        break;
      case "draft_ready":
        setCompletedSteps((p) => new Set([...p, "writer"]));
        setCurrentDraft(ev.draft); setIteration(ev.iteration || 1);
        if (ev.draft) setDraftHistory((p) => [...p, ev.draft]);
        autoSwitch("draft", `Utkast v${ev.draft?.revision_number || 1} klart`, PenTool, "text-emerald-400/70");
        break;
      case "stagnation":
        emitToast(ev.message || "Score-stagnasjon — restrukturerer...", AlertTriangle, "text-amber-400/70");
        break;
      case "critique_ready":
        setCompletedSteps((p) => new Set([...p, "critic"]));
        if (ev.critique) {
          setCritiques((p) => [...p, { ...ev.critique, _iteration: ev.iteration }]);
          autoSwitch("critique", `Kritikk: ${ev.critique.score}/10`, MessageSquare, "text-amber-400/70");
        }
        break;
      case "tokens":
        setTokenUsage((p) => [...p, { agent: ev.agent, input_tokens: ev.input_tokens, output_tokens: ev.output_tokens, cost_usd: ev.cost_usd, duration_s: ev.duration_s }]);
        setTotalCost(ev.total_cost_usd || 0); break;
      case "complete":
        setActiveAgent(null); setCompletedSteps(new Set(["searcher", "writer", "critic", "evaluator"]));
        setPipelineStatus("completed"); setRunning(false); setFinalDraft(ev.final_draft || null);
        if (ev.total_cost_usd) setTotalCost(ev.total_cost_usd);
        if (ev.token_usage) setTokenUsage(ev.token_usage);
        reEnableAutoTab();
        autoSwitch("final", "Essay ferdig!", CheckCircle2, "text-emerald-400/70");
        break;
      case "warning":
        emitToast(message || "Advarsel fra agent", AlertTriangle, "text-amber-400/70");
        break;
      case "error":
        setPipelineStatus("error"); setRunning(false); setErrorMsg(message);
        if (ev.total_cost_usd) setTotalCost(ev.total_cost_usd); break;
      default: break;
    }
  }, []);

  // ── File Handling ──
  function addFiles(newFiles) {
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...[...newFiles].filter((f) => !names.has(f.name))];
    });
  }
  function removeFile(idx) { setFiles((p) => p.filter((_, i) => i !== idx)); }
  function handleDrop(e) { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files); }

  // ── Upload ──
  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    const form = new FormData();
    for (const f of files) form.append("files", f);
    try {
      const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
      const data = await res.json();
      setSessionId(data.session_id);
      setLogs([`Lastet opp ${data.files.length} fil(er)`]);
    } catch (err) {
      setLogs((p) => [...p, `Opplastingsfeil: ${err.message}`]);
    } finally {
      setUploading(false);
    }
  }

  // ── Start Pipeline ──
  async function handleStart() {
    if (!sessionId || !task.trim()) return;
    try {
      await fetch(`${API}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          Object.fromEntries(
            Object.entries(settings.agents).map(([k, v]) => [k, { model: v.model, temperature: v.temperature, max_tokens: v.maxTokens }])
          )
        ),
      });
    } catch {}
    setRunning(true); setPipelineStatus("running"); setActiveAgent(null);
    setIteration(1); setCurrentDraft(null); setFinalDraft(null);
    setCritiques([]); setCompletedSteps(new Set()); setErrorMsg(null);
    setTokenUsage([]); setTotalCost(0); setActiveTab("draft");
    setLogs((p) => [...p, "Starter pipeline..."]);
    wsRef.current?.send("ping");
    try {
      const res = await fetch(`${API}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId, task,
          writer_config: { max_words: settings.pipeline.maxWords, language: settings.pipeline.language === "norsk" ? "norsk bokmål" : "english" },
          evaluator_config: { score_threshold: settings.pipeline.scoreThreshold, max_iterations: settings.pipeline.maxIterations },
        }),
      });
      const data = await res.json();
      if (data.error) { setLogs((p) => [...p, `Feil: ${data.error}`]); setRunning(false); setPipelineStatus("error"); setErrorMsg(data.error); }
    } catch (err) { setLogs((p) => [...p, `Startfeil: ${err.message}`]); setRunning(false); setPipelineStatus("error"); setErrorMsg(err.message); }
  }

  // ── Reset to input mode ──
  function resetToInput() {
    localStorage.removeItem("exphil-active-session");
    setSessionId(null); setFiles([]); setTask("");
    setPipelineStatus("idle"); setActiveAgent(null);
    setCurrentDraft(null); setFinalDraft(null);
    setCritiques([]); setCompletedSteps(new Set());
    setIteration(1); setDraftHistory([]); setLogs([]); setErrorMsg(null);
    setTokenUsage([]); setTotalCost(0); setActiveTab("draft"); setShowDiff(false);
    autoTabRef.current = true; setAutoTabEnabled(true); setLastAutoTab(null); setToasts([]);
  }

  // ── Toast helpers ──
  function addToast(message, icon, color) {
    const id = ++toastIdRef.current;
    setToasts((p) => [...p.slice(-3), { id, message, icon, color }]);
  }
  function dismissToast(id) {
    setToasts((p) => p.filter((t) => t.id !== id));
  }

  // ── Manual tab click ──
  function handleTabClick(tabId) {
    autoTabRef.current = false;
    setAutoTabEnabled(false);
    setActiveTab(tabId);
  }

  // ── Save edited draft ──
  function saveEditedDraft(newBody) {
    if (finalDraft) {
      const updated = { ...finalDraft, body: newBody, word_count: newBody.trim().split(/\s+/).length };
      setFinalDraft(updated);
    }
  }

  // ── Re-critique edited text ──
  async function handleReCritique(editedBody) {
    if (!sessionId) return;
    setReCritiquing(true);
    addToast("Kjører kritikk på redigert tekst...", RefreshCw, "text-amber-400/70");
    try {
      const res = await fetch(`${API}/api/critique`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          body: editedBody,
          title: finalDraft?.title || "",
          references: finalDraft?.references || [],
        }),
      });
      const data = await res.json();
      if (data.error) {
        addToast(`Kritikk feilet: ${data.error}`, AlertTriangle, "text-red-400/70");
      } else if (data.critique) {
        setCritiques((p) => [...p, { ...data.critique, _iteration: "re-eval" }]);
        addToast(`Ny kritikk: ${data.critique.score}/10`, MessageSquare, "text-emerald-400/70");
        setActiveTab("critique");
      }
    } catch (err) {
      addToast(`Feil: ${err.message}`, AlertTriangle, "text-red-400/70");
    } finally {
      setReCritiquing(false);
    }
  }

  // ── PDF download ──
  function downloadPdf() {
    if (!sessionId) return;
    const a = document.createElement("a");
    a.href = `${API}/api/export/pdf/${sessionId}`;
    a.download = `exphil-essay-${sessionId.slice(0, 8)}.pdf`;
    a.click();
  }

  const pl = settings.pipeline;

  // ═══════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════
  return (
    <div className="min-h-screen relative">
      <GradientBackground />
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* ════════════════ FIXED HEADER ════════════════ */}
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-2xl bg-black/40 border-b border-white/[0.04]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Left: brand */}
          <div className="flex items-center gap-3">
            <span className="text-lg font-light tracking-tight text-white/85">
              Exphil Agent
            </span>
            {connected && (
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </div>

          {/* Center: stepper (only when pipeline is active) */}
          {isPipelineMode && (
            <div className="hidden sm:flex">
              <HeaderStepper activeAgent={activeAgent} completedSteps={completedSteps} pipelineStatus={pipelineStatus} />
            </div>
          )}

          {/* Right: actions */}
          <div className="flex items-center gap-1">
            {/* New session — always visible when pipeline is active */}
            {isPipelineMode && (
              <button
                onClick={resetToInput}
                className="flex items-center gap-1.5 px-3 py-1.5 mr-1 text-[11px] text-white/50 hover:text-white/80 bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.06] rounded-lg transition"
              >
                <Plus className="w-3 h-3" /> Ny
              </button>
            )}

            {/* History */}
            <div className="relative" data-history-dropdown>
              <button
                onClick={() => { setShowHistory(!showHistory); if (!showHistory) fetchHistory(); }}
                className="p-2 text-white/25 hover:text-white/50 transition rounded-lg hover:bg-white/[0.04]"
              >
                <History className="w-4 h-4" />
              </button>
              <AnimatePresence>
                {showHistory && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-2 w-80 z-50 bg-black/90 backdrop-blur-2xl border border-white/[0.06] rounded-xl shadow-2xl shadow-black/50 max-h-80 overflow-y-auto"
                  >
                    {historyList.length === 0 ? (
                      <div className="px-4 py-6 text-center text-[11px] text-white/25">Ingen historikk enda</div>
                    ) : (
                      historyList.map((s) => (
                        <button
                          key={s.session_id}
                          onClick={() => loadSession(s.session_id)}
                          className={`w-full text-left px-4 py-3 hover:bg-white/[0.03] border-b border-white/[0.03] last:border-0 transition ${
                            s.session_id === sessionId ? "bg-violet-500/[0.04]" : ""
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] text-white/55 truncate flex-1 mr-2">
                              {s.task_text || "Uten oppgave"}
                            </span>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${
                              s.status === "completed" ? "bg-emerald-500/10 text-emerald-400/80" :
                              s.status === "error" ? "bg-red-500/10 text-red-400/80" :
                              "bg-violet-500/10 text-violet-400/80"
                            }`}>
                              {s.status === "completed" ? "Ferdig" : s.status === "error" ? "Feil" : "Pågår"}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[9px] text-white/15">
                              {s.updated_at ? new Date(s.updated_at).toLocaleString("nb-NO", { dateStyle: "short", timeStyle: "short" }) : ""}
                            </span>
                            {s.score != null && <span className="text-[9px] text-white/25">{s.score}/10</span>}
                            {s.total_cost_usd > 0 && <span className="text-[9px] text-white/15">${s.total_cost_usd.toFixed(4)}</span>}
                          </div>
                        </button>
                      ))
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Settings trigger */}
            <button
              data-settings-trigger
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 text-white/25 hover:text-white/50 transition rounded-lg hover:bg-white/[0.04]"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Mobile stepper — below header bar */}
        {isPipelineMode && (
          <div className="sm:hidden flex justify-center pb-2">
            <HeaderStepper activeAgent={activeAgent} completedSteps={completedSteps} pipelineStatus={pipelineStatus} />
          </div>
        )}
      </header>

      {/* ════════════════ SETTINGS SLIDE-OVER ════════════════ */}
      <AnimatePresence>
        {showSettings && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[60] bg-black/50"
              onClick={() => setShowSettings(false)}
            />
            {/* Panel — from right on desktop, bottom-sheet on mobile */}
            <motion.div
              data-settings-panel
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="fixed top-0 right-0 bottom-0 z-[70] w-full sm:w-96 bg-black/80 backdrop-blur-3xl border-l border-white/[0.04] overflow-y-auto"
            >
              <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-light text-white/80">Innstillinger</h2>
                  <button onClick={() => setShowSettings(false)} className="p-1.5 text-white/25 hover:text-white/50 transition rounded-lg hover:bg-white/[0.04]">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Agent configs */}
                <div>
                  <h3 className="text-[10px] text-white/25 uppercase tracking-wider mb-2 px-1">Agenter</h3>
                  <Glass>
                    {AGENTS.map((a) => (
                      <AgentConfigSection
                        key={a.id} agent={a}
                        config={settings.agents[a.id]}
                        onChange={(cfg) => updateAgent(a.id, cfg)}
                      />
                    ))}
                  </Glass>
                </div>

                {/* Pipeline settings */}
                <div>
                  <h3 className="text-[10px] text-white/25 uppercase tracking-wider mb-2 px-1">Pipeline</h3>
                  <Glass className="p-4 space-y-4">
                    {/* Max iterations */}
                    <div>
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] text-white/25 uppercase tracking-wider">Maks iterasjoner</label>
                        <span className="text-[10px] text-violet-400/60 font-mono">{pl.maxIterations}</span>
                      </div>
                      <input type="range" min="1" max="10" step="1" value={pl.maxIterations}
                        onChange={(e) => updatePipeline("maxIterations", parseInt(e.target.value))} className="w-full mt-1.5" />
                    </div>
                    {/* Score threshold */}
                    <div>
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] text-white/25 uppercase tracking-wider">Godkjenningsterskel</label>
                        <span className="text-[10px] text-violet-400/60 font-mono">{pl.scoreThreshold.toFixed(1)}</span>
                      </div>
                      <input type="range" min="5" max="10" step="0.5" value={pl.scoreThreshold}
                        onChange={(e) => updatePipeline("scoreThreshold", parseFloat(e.target.value))} className="w-full mt-1.5" />
                    </div>
                    {/* Max words */}
                    <div>
                      <label className="text-[10px] text-white/25 uppercase tracking-wider">Maks ord</label>
                      <div className="flex items-center gap-2 mt-1.5">
                        <button onClick={() => updatePipeline("maxWords", Math.max(500, pl.maxWords - 100))}
                          className="w-7 h-7 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/35 hover:text-white/60 flex items-center justify-center text-sm transition">-</button>
                        <span className="flex-1 text-center text-sm text-white/60 font-mono">{pl.maxWords}</span>
                        <button onClick={() => updatePipeline("maxWords", Math.min(3000, pl.maxWords + 100))}
                          className="w-7 h-7 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/35 hover:text-white/60 flex items-center justify-center text-sm transition">+</button>
                      </div>
                    </div>
                    {/* Language */}
                    <div>
                      <label className="text-[10px] text-white/25 uppercase tracking-wider">Språk</label>
                      <div className="flex mt-1.5 bg-white/[0.02] rounded-lg border border-white/[0.04] p-0.5">
                        <button onClick={() => updatePipeline("language", "norsk")}
                          className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${pl.language === "norsk" ? "bg-white/[0.06] text-white/70" : "text-white/25 hover:text-white/45"}`}>
                          Norsk
                        </button>
                        <button onClick={() => updatePipeline("language", "english")}
                          className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${pl.language === "english" ? "bg-white/[0.06] text-white/70" : "text-white/25 hover:text-white/45"}`}>
                          <Globe className="w-3 h-3" /> English
                        </button>
                      </div>
                    </div>
                  </Glass>
                </div>

                {/* Cost tracker */}
                {(tokenUsage.length > 0 || totalCost > 0) && (
                  <div>
                    <h3 className="text-[10px] text-white/25 uppercase tracking-wider mb-2 px-1">Kostnad</h3>
                    <Glass className="p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <DollarSign className="w-3 h-3 text-white/20" />
                          <span className="text-xs text-white/40">Total</span>
                        </div>
                        <span className="text-xs font-mono text-emerald-400/70">${totalCost.toFixed(4)}</span>
                      </div>
                      <div className="space-y-1.5">
                        {tokenUsage.map((u, i) => (
                          <div key={i} className="flex items-center justify-between text-[10px]">
                            <span className="text-white/30 capitalize">{u.agent}</span>
                            <div className="flex items-center gap-2">
                              <span className="text-white/15 font-mono">{((u.input_tokens || 0) + (u.output_tokens || 0)).toLocaleString()} tok</span>
                              <span className="text-white/25 font-mono">${(u.cost_usd || 0).toFixed(4)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </Glass>
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ════════════════ MAIN CONTENT ════════════════ */}
      <div className="relative z-10 pt-14 min-h-screen">
        <AnimatePresence mode="wait">

          {/* ──────────── MODE 1: INPUT ──────────── */}
          {isInputMode && (
            <motion.div
              key="input-mode"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -30, transition: { duration: 0.3 } }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] px-4 sm:px-6"
            >
              <div className="w-full max-w-2xl lg:max-w-3xl space-y-8">
                {/* Heading */}
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1, duration: 0.6 }}
                  className="text-center space-y-3"
                >
                  <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extralight tracking-tight text-white/90 leading-tight">
                    Hva skal du skrive om?
                  </h1>
                  <p className="text-sm sm:text-base text-white/25 font-light">
                    Last opp pensum, lim inn oppgaven, og la agentene gjøre resten.
                  </p>
                </motion.div>

                {/* Main input card */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2, duration: 0.6 }}
                >
                  <Glass className="p-1" active={!!task.trim()}>
                    <textarea
                      value={task}
                      onChange={(e) => setTask(e.target.value)}
                      placeholder="Lim inn oppgaveteksten her..."
                      rows={5}
                      className="w-full px-5 py-4 bg-transparent text-[15px] text-white/80 placeholder-white/15 resize-y leading-relaxed rounded-xl"
                    />
                  </Glass>
                </motion.div>

                {/* Action row */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3, duration: 0.6 }}
                  className="flex flex-wrap items-center gap-3"
                >
                  {/* File upload button */}
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    className="flex items-center gap-2"
                  >
                    <button
                      onClick={() => document.getElementById("file-input").click()}
                      className={`flex items-center gap-2 px-4 py-2.5 text-[13px] bg-white/[0.03] hover:bg-white/[0.06] border rounded-xl transition-all ${
                        dragOver ? "border-violet-400/30 bg-violet-500/[0.04]" : "border-white/[0.06]"
                      } text-white/45 hover:text-white/65`}
                    >
                      <Upload className="w-4 h-4" />
                      <span>Legg til pensum</span>
                    </button>
                    <input
                      id="file-input" type="file" multiple accept=".pdf,.txt"
                      className="hidden"
                      onChange={(e) => addFiles(e.target.files)}
                    />
                  </div>

                  {/* File chips inline */}
                  <AnimatePresence>
                    {files.map((f, i) => (
                      <FileChip key={f.name} file={f} onRemove={() => removeFile(i)} />
                    ))}
                  </AnimatePresence>

                  {/* Spacer */}
                  <div className="flex-1" />

                  {/* Upload then Start */}
                  {!sessionId && files.length > 0 && (
                    <button
                      onClick={handleUpload}
                      disabled={uploading}
                      className="flex items-center gap-2 px-5 py-2.5 text-[13px] font-medium bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.08] rounded-xl transition text-white/60 disabled:opacity-30"
                    >
                      {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      {uploading ? "Laster opp..." : "Last opp"}
                    </button>
                  )}

                  <button
                    onClick={handleStart}
                    disabled={!sessionId || !task.trim() || running}
                    className="flex items-center gap-2.5 px-6 py-2.5 text-[13px] font-medium text-white rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-25 disabled:hover:scale-100"
                    style={{
                      background: "linear-gradient(135deg, #8b5cf6, #3b82f6, #06b6d4)",
                      boxShadow: sessionId && task.trim() ? "0 0 30px rgba(139, 92, 246, 0.2), 0 0 60px rgba(59, 130, 246, 0.1)" : "none",
                    }}
                  >
                    {running ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Jobber...</>
                    ) : (
                      <><Sparkles className="w-4 h-4" /> Start</>
                    )}
                  </button>
                </motion.div>

                {/* Error in input mode */}
                <AnimatePresence>
                  {errorMsg && (
                    <motion.div
                      initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className="flex items-start gap-2 px-4 py-3 bg-red-500/[0.05] border border-red-500/[0.08] rounded-xl"
                    >
                      <AlertTriangle className="w-4 h-4 text-red-400/70 mt-0.5 shrink-0" />
                      <p className="text-xs text-red-300/70 leading-relaxed">{errorMsg}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          )}

          {/* ──────────── MODE 2: PIPELINE ──────────── */}
          {isPipelineMode && (
            <motion.div
              key="pipeline-mode"
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="max-w-2xl lg:max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-4"
            >
              {/* Tabs */}
              <div className="flex items-center gap-1 p-1 bg-white/[0.02] rounded-xl border border-white/[0.04]">
                {[
                  { id: "draft", label: "Utkast", badge: currentDraft ? `v${currentDraft.revision_number || 1}` : null },
                  { id: "critique", label: "Kritikk", badge: critiques.length > 0 ? `${latestCritique?.score}/10` : null },
                  { id: "final", label: "Endelig", badge: finalDraft ? "OK" : null },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => handleTabClick(tab.id)}
                    className={`relative flex-1 py-2.5 px-3 rounded-lg text-xs font-medium transition-all ${
                      activeTab === tab.id
                        ? "bg-white/[0.06] text-white/85"
                        : "text-white/30 hover:text-white/50"
                    }`}
                  >
                    {tab.label}
                    {tab.badge && (
                      <span className={`ml-1.5 text-[9px] px-1.5 py-0.5 rounded-full ${
                        activeTab === tab.id ? "bg-violet-500/15 text-violet-300/80" : "bg-white/4 text-white/25"
                      }`}>
                        {tab.badge}
                      </span>
                    )}
                    {autoTabEnabled && activeTab === tab.id && lastAutoTab === tab.id && pipelineStatus === "running" && (
                      <span className="absolute -top-1.5 -right-1 text-[8px] px-1 py-px bg-violet-500/20 text-violet-300/60 rounded-full">
                        auto
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Main content card */}
              <Glass className="min-h-[60vh] flex flex-col" active={pipelineStatus === "running"}>
                <div className="flex-1 overflow-y-auto px-5 sm:px-8 py-6">
                  <AnimatePresence mode="wait">
                    {/* DRAFT TAB */}
                    {activeTab === "draft" && (
                      <motion.div key="draft" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
                        {currentDraft?.body ? (
                          <div>
                            {/* Diff toggle — only show when there are multiple drafts */}
                            {draftHistory.length >= 2 && (
                              <div className="flex items-center justify-between mb-4">
                                <span className="text-[10px] text-white/25 font-mono">
                                  v{currentDraft.revision_number || draftHistory.length} — {currentDraft.word_count || "?"} ord
                                </span>
                                <button
                                  onClick={() => setShowDiff((d) => !d)}
                                  className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] rounded-lg border transition ${
                                    showDiff
                                      ? "bg-violet-500/10 border-violet-500/20 text-violet-300/80"
                                      : "bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/60"
                                  }`}
                                >
                                  <Eye className="w-3 h-3" />
                                  {showDiff ? "Skjul endringer" : "Vis endringer"}
                                </button>
                              </div>
                            )}

                            {showDiff && draftHistory.length >= 2 ? (
                              <ParagraphDiff
                                prevBody={draftHistory[draftHistory.length - 2]?.body}
                                currBody={currentDraft.body}
                              />
                            ) : (
                              <div className="prose prose-sm prose-glass max-w-none">
                                <Markdown>{currentDraft.body}</Markdown>
                              </div>
                            )}

                            {currentDraft.references?.length > 0 && (
                              <div className="mt-8 pt-4 border-t border-white/[0.04]">
                                <h4 className="text-[10px] font-medium text-white/25 uppercase tracking-wider mb-2">
                                  Referanser ({currentDraft.references.length})
                                </h4>
                                <ul className="space-y-1 list-none pl-0">
                                  {currentDraft.references.map((ref, i) => (
                                    <li key={i} className="text-[11px] text-white/35 !pl-0 !my-0">
                                      {ref.author} ({ref.year}). <em>{ref.title}</em>.
                                      {ref.page ? ` s. ${ref.page}.` : ""}
                                      {ref.url && <a href={ref.url} target="_blank" rel="noreferrer" className="ml-1 text-violet-400/50 hover:text-violet-400 transition">[lenke]</a>}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center h-64 text-white/10">
                            <PenTool className="w-10 h-10 mb-3" />
                            <p className="text-sm font-light">Utkast vises her...</p>
                            {pipelineStatus === "running" && activeAgent === "writer" && (
                              <div className="mt-4 flex items-center gap-2 text-xs text-violet-400/40">
                                <Loader2 className="w-3 h-3 animate-spin" /> Skriver...
                              </div>
                            )}
                          </div>
                        )}
                      </motion.div>
                    )}

                    {/* CRITIQUE TAB */}
                    {activeTab === "critique" && (
                      <motion.div key="critique" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
                        {critiques.length > 0 ? (
                          <div className="space-y-8">
                            {critiques.map((c, i) => (
                              <div key={i}>
                                {critiques.length > 1 && (
                                  <div className="flex items-center gap-2 mb-4">
                                    <span className="text-[10px] font-medium text-white/25 uppercase tracking-wider">Iterasjon {c._iteration || i + 1}</span>
                                    <div className="flex-1 h-px bg-white/[0.03]" />
                                  </div>
                                )}
                                <CritiqueView critique={c} />
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center h-64 text-white/10">
                            <MessageSquare className="w-10 h-10 mb-3" />
                            <p className="text-sm font-light">Kritikk vises her...</p>
                            {pipelineStatus === "running" && activeAgent === "critic" && (
                              <div className="mt-4 flex items-center gap-2 text-xs text-violet-400/40">
                                <Loader2 className="w-3 h-3 animate-spin" /> Evaluerer...
                              </div>
                            )}
                          </div>
                        )}
                      </motion.div>
                    )}

                    {/* FINAL TAB */}
                    {activeTab === "final" && (
                      <motion.div key="final" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
                        {finalDraft?.body ? (
                          <div>
                            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-emerald-500/8 flex items-center justify-center">
                                  <CheckCircle2 className="w-4 h-4 text-emerald-400/80" />
                                </div>
                                <div>
                                  <p className="text-sm font-light text-white/75">Essay godkjent</p>
                                  <p className="text-[11px] text-white/25">
                                    {finalDraft.word_count} ord
                                    {latestCritique && ` — score ${latestCritique.score}/10`}
                                    {iteration > 1 && ` — ${iteration - 1} revisjon(er)`}
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <ExportButtons draft={finalDraft} sessionId={sessionId} />
                                {sessionId && (
                                  <button
                                    onClick={downloadPdf}
                                    className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] bg-red-500/[0.06] hover:bg-red-500/[0.1] border border-red-500/[0.1] rounded-lg transition text-red-300/60 hover:text-red-300/80"
                                  >
                                    <FileDown className="w-3 h-3" /> .pdf
                                  </button>
                                )}
                              </div>
                            </div>
                            <InlineEditor
                              draft={finalDraft}
                              onSave={saveEditedDraft}
                              onReCritique={handleReCritique}
                              reCritiquing={reCritiquing}
                              sessionId={sessionId}
                            />
                            {finalDraft.references?.length > 0 && (
                              <div className="mt-8 pt-4 border-t border-white/[0.04]">
                                <h4 className="text-[10px] font-medium text-white/25 uppercase tracking-wider mb-2">Referanser</h4>
                                <ul className="space-y-1">
                                  {finalDraft.references.map((ref, i) => (
                                    <li key={i} className="text-[11px] text-white/35">
                                      {ref.author} ({ref.year}). <em>{ref.title}</em>.
                                      {ref.page ? ` s. ${ref.page}.` : ""}
                                      {ref.url && <a href={ref.url} target="_blank" rel="noreferrer" className="ml-1 text-violet-400/50 hover:text-violet-400 transition">[lenke]</a>}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center h-64 text-white/10">
                            <CheckCircle2 className="w-10 h-10 mb-3" />
                            <p className="text-sm font-light">Endelig essay vises her når godkjent</p>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Log footer */}
                {logs.length > 0 && <LogFooter logs={logs} />}
              </Glass>

              {/* Info bar below card */}
              <div className="flex flex-wrap items-center justify-between gap-3 px-2 text-[10px] text-white/20">
                <div className="flex items-center gap-4">
                  {iteration > 1 && (
                    <span className="flex items-center gap-1">
                      <ArrowRight className="w-3 h-3" /> Iterasjon {iteration}
                    </span>
                  )}
                  {pipelineStatus === "completed" && <span className="text-emerald-400/50">Ferdig</span>}
                  {pipelineStatus === "error" && <span className="text-red-400/50">Feil</span>}
                  {pipelineStatus === "running" && <span className="text-violet-400/50 flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Pågår</span>}
                </div>
                <div className="flex items-center gap-4">
                  {tokenUsage.length > 0 && (
                    <span className="font-mono">
                      {tokenUsage.reduce((s, u) => s + (u.input_tokens || 0) + (u.output_tokens || 0), 0).toLocaleString()} tokens
                    </span>
                  )}
                  {totalCost > 0 && <span className="font-mono">${totalCost.toFixed(4)}</span>}
                </div>
              </div>

              {/* Error in pipeline mode */}
              <AnimatePresence>
                {errorMsg && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    className="flex items-start gap-2 px-4 py-3 bg-red-500/[0.04] border border-red-500/[0.06] rounded-xl"
                  >
                    <AlertTriangle className="w-4 h-4 text-red-400/60 mt-0.5 shrink-0" />
                    <p className="text-xs text-red-300/60 leading-relaxed">{errorMsg}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
