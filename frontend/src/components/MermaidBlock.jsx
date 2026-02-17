import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

// Initialize mermaid with dark theme matching the app
mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  themeVariables: {
    primaryColor: "#4f46e5",
    primaryTextColor: "#e2e8f0",
    primaryBorderColor: "#6366f1",
    lineColor: "#94a3b8",
    secondaryColor: "#7c3aed",
    tertiaryColor: "#1e1b4b",
    background: "#0a0a0a",
    mainBkg: "#1a1a2e",
    nodeBorder: "#6366f1",
    clusterBkg: "#0f0f1a",
    titleColor: "#e2e8f0",
    edgeLabelBackground: "#0a0a0a",
  },
  flowchart: {
    curve: "basis",
    padding: 16,
    htmlLabels: true,
    useMaxWidth: true,
  },
  fontFamily: "'DM Sans', sans-serif",
  fontSize: 13,
});

let idCounter = 0;

export default function MermaidBlock({ chart }) {
  const containerRef = useRef(null);
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(null);
  const idRef = useRef(`mermaid-${++idCounter}-${Date.now()}`);

  useEffect(() => {
    if (!chart?.trim()) return;

    let cancelled = false;

    async function render() {
      try {
        const { svg: rendered } = await mermaid.render(
          idRef.current,
          chart.trim()
        );
        if (!cancelled) {
          setSvg(rendered);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Kunne ikke rendre diagram");
          setSvg("");
        }
      }
    }

    render();
    return () => { cancelled = true; };
  }, [chart]);

  if (error) {
    return (
      <div className="my-6 p-4 rounded-xl border border-amber-500/20 bg-amber-500/[0.03]">
        <p className="text-[11px] text-amber-400/60 mb-2">Kunne ikke rendre Mermaid-diagram:</p>
        <pre className="text-[10px] text-white/30 overflow-x-auto whitespace-pre-wrap">{chart}</pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-6 flex items-center justify-center h-32 rounded-xl border border-white/[0.04] bg-white/[0.01]">
        <span className="text-[11px] text-white/20 animate-pulse">Rendrer diagram...</span>
      </div>
    );
  }

  return (
    <div className="my-6 p-4 rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-x-auto">
      <div
        ref={containerRef}
        className="flex justify-center [&_svg]:max-w-full"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}
