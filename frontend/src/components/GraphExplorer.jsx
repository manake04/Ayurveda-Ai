import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

/** Force-directed layout + canvas renderer for the corpus knowledge graph, written from
 * scratch (no graph-viz library) to keep the frontend's dependency footprint at zero new
 * packages -- the corpus graph is small (a few hundred nodes/edges at most), so a plain
 * O(n^2) repulsion simulation on <canvas> is more than fast enough and keeps this
 * auditable without a black-box charting dependency. */

const WIDTH = 900;
const HEIGHT = 560;

const TYPE_COLORS = {
  document: "#57534e",
  regime: "#0e7490",
  jurisdiction: "#b45309",
  category: "#4d7c0f",
  institution: "#7c3aed",
};

const TYPE_RADIUS = {
  document: 5,
  regime: 10,
  jurisdiction: 12,
  category: 7,
  institution: 9,
};

const TYPE_LABELS = {
  document: "Document",
  regime: "Legal regime",
  jurisdiction: "Jurisdiction",
  category: "Formulation category",
  institution: "Institution",
};

export default function GraphExplorer() {
  const canvasRef = useRef(null);
  const nodesRef = useRef([]);
  const edgesRef = useRef([]);
  const nodeByIdRef = useRef(new Map());
  const draggingRef = useRef(null);
  const panningRef = useRef(null);
  const transformRef = useRef({ scale: 0.85, tx: WIDTH / 2, ty: HEIGHT / 2 });
  const alphaRef = useRef(1);
  const activeTypesRef = useRef(new Set(Object.keys(TYPE_COLORS)));
  const highlightRef = useRef(new Set());
  const selectedIdRef = useRef(null);

  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [related, setRelated] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [activeTypes, setActiveTypes] = useState(new Set(Object.keys(TYPE_COLORS)));
  const [stats, setStats] = useState(null);

  // ---- load graph ----
  useEffect(() => {
    api
      .graphExport()
      .then((data) => {
        const nodes = data.nodes.map((n) => ({
          ...n,
          x: WIDTH / 2 + (Math.random() - 0.5) * WIDTH * 0.7,
          y: HEIGHT / 2 + (Math.random() - 0.5) * HEIGHT * 0.7,
          vx: 0,
          vy: 0,
        }));
        const map = new Map(nodes.map((n) => [n.id, n]));
        nodesRef.current = nodes;
        nodeByIdRef.current = map;
        edgesRef.current = data.edges.filter((e) => map.has(e.source) && map.has(e.target));
        const byType = {};
        nodes.forEach((n) => (byType[n.node_type] = (byType[n.node_type] || 0) + 1));
        setStats({ nodes: nodes.length, edges: edgesRef.current.length, byType });
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, []);

  // keep refs in sync with UI state without restarting the simulation
  useEffect(() => {
    activeTypesRef.current = activeTypes;
  }, [activeTypes]);

  useEffect(() => {
    selectedIdRef.current = selected?.id || null;
  }, [selected]);

  useEffect(() => {
    const q = search.trim().toLowerCase();
    if (!q) {
      highlightRef.current = new Set();
      return;
    }
    const matches = nodesRef.current.filter((n) => n.label.toLowerCase().includes(q));
    highlightRef.current = new Set(matches.map((n) => n.id));
  }, [search, loaded]);

  // ---- simulation + render loop ----
  useEffect(() => {
    if (!loaded) return;
    let raf;
    let stopped = false;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    function step() {
      const nodes = nodesRef.current;
      const edges = edgesRef.current;
      const alpha = alphaRef.current;

      if (alpha > 0.01) {
        const n = nodes.length;
        const REPULSION = 2200;
        for (let i = 0; i < n; i++) {
          const a = nodes[i];
          for (let j = i + 1; j < n; j++) {
            const b = nodes[j];
            let dx = a.x - b.x;
            let dy = a.y - b.y;
            let distSq = dx * dx + dy * dy;
            if (distSq < 4) {
              dx = Math.random() - 0.5;
              dy = Math.random() - 0.5;
              distSq = 4;
            }
            const dist = Math.sqrt(distSq);
            const force = (REPULSION / distSq) * alpha;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            a.vx += fx;
            a.vy += fy;
            b.vx -= fx;
            b.vy -= fy;
          }
        }

        const SPRING_LEN = 65;
        const SPRING_K = 0.02;
        for (const e of edges) {
          const a = nodeByIdRef.current.get(e.source);
          const b = nodeByIdRef.current.get(e.target);
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
          const force = (dist - SPRING_LEN) * SPRING_K * alpha;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          a.vx += fx;
          a.vy += fy;
          b.vx -= fx;
          b.vy -= fy;
        }

        for (const node of nodes) {
          if (node === draggingRef.current) {
            node.vx = 0;
            node.vy = 0;
            continue;
          }
          node.vx += (WIDTH / 2 - node.x) * 0.008 * alpha;
          node.vy += (HEIGHT / 2 - node.y) * 0.008 * alpha;
          node.vx *= 0.82;
          node.vy *= 0.82;
          node.x += node.vx;
          node.y += node.vy;
        }
        alphaRef.current *= 0.985;
      }

      draw(ctx);
      if (!stopped) raf = requestAnimationFrame(step);
    }

    function draw(ctx) {
      const { scale, tx, ty } = transformRef.current;
      ctx.save();
      ctx.clearRect(0, 0, WIDTH, HEIGHT);
      ctx.fillStyle = "#fafaf9";
      ctx.fillRect(0, 0, WIDTH, HEIGHT);
      ctx.translate(tx, ty);
      ctx.scale(scale, scale);
      ctx.translate(-WIDTH / 2, -HEIGHT / 2);

      const active = activeTypesRef.current;
      const highlight = highlightRef.current;
      const selId = selectedIdRef.current;
      const visible = new Set(nodesRef.current.filter((n) => active.has(n.node_type)).map((n) => n.id));

      ctx.lineWidth = 1 / scale;
      for (const e of edgesRef.current) {
        if (!visible.has(e.source) || !visible.has(e.target)) continue;
        const a = nodeByIdRef.current.get(e.source);
        const b = nodeByIdRef.current.get(e.target);
        const dim = selId && a.id !== selId && b.id !== selId;
        ctx.strokeStyle = dim ? "rgba(168,162,158,0.15)" : "rgba(120,113,108,0.35)";
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }

      for (const node of nodesRef.current) {
        if (!active.has(node.node_type)) continue;
        const r = TYPE_RADIUS[node.node_type] || 5;
        const isSel = node.id === selId;
        const isHi = highlight.has(node.id);
        ctx.beginPath();
        ctx.arc(node.x, node.y, isSel ? r * 1.6 : r, 0, Math.PI * 2);
        ctx.fillStyle = TYPE_COLORS[node.node_type] || "#78716c";
        ctx.globalAlpha = highlight.size > 0 && !isHi && !isSel ? 0.25 : 1;
        ctx.fill();
        if (isSel || isHi) {
          ctx.lineWidth = 2 / scale;
          ctx.strokeStyle = isSel ? "#1c1917" : "#f59e0b";
          ctx.stroke();
        }
        ctx.globalAlpha = 1;

        if (scale > 0.7 || isSel || isHi) {
          ctx.font = `${11 / Math.max(scale, 0.6)}px sans-serif`;
          ctx.fillStyle = "#292524";
          ctx.globalAlpha = highlight.size > 0 && !isHi && !isSel ? 0.35 : 0.9;
          const label = node.label.length > 34 ? node.label.slice(0, 34) + "…" : node.label;
          ctx.fillText(label, node.x + r + 3, node.y + 3);
          ctx.globalAlpha = 1;
        }
      }
      ctx.restore();
    }

    raf = requestAnimationFrame(step);
    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
    };
  }, [loaded]);

  // ---- pointer interaction ----
  function canvasPoint(evt) {
    const rect = canvasRef.current.getBoundingClientRect();
    const cx = ((evt.clientX - rect.left) / rect.width) * WIDTH;
    const cy = ((evt.clientY - rect.top) / rect.height) * HEIGHT;
    const { scale, tx, ty } = transformRef.current;
    return {
      x: (cx - tx) / scale + WIDTH / 2,
      y: (cy - ty) / scale + HEIGHT / 2,
      screenX: cx,
      screenY: cy,
    };
  }

  function nodeAt(pt) {
    const active = activeTypesRef.current;
    let hit = null;
    let hitDist = Infinity;
    for (const node of nodesRef.current) {
      if (!active.has(node.node_type)) continue;
      const r = (TYPE_RADIUS[node.node_type] || 5) + 3;
      const dx = node.x - pt.x;
      const dy = node.y - pt.y;
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d <= r && d < hitDist) {
        hit = node;
        hitDist = d;
      }
    }
    return hit;
  }

  function selectNode(node) {
    setSelected(node);
    setRelatedLoading(true);
    api
      .graphRelated(node.id, 1)
      .then((res) => setRelated(res.related))
      .catch(() => setRelated([]))
      .finally(() => setRelatedLoading(false));
  }

  function handleMouseDown(evt) {
    const pt = canvasPoint(evt);
    const hit = nodeAt(pt);
    if (hit) {
      draggingRef.current = hit;
      alphaRef.current = Math.max(alphaRef.current, 0.3);
    } else {
      panningRef.current = { startScreenX: pt.screenX, startScreenY: pt.screenY, ...transformRef.current };
    }
  }

  function handleMouseMove(evt) {
    if (draggingRef.current) {
      const pt = canvasPoint(evt);
      draggingRef.current.x = pt.x;
      draggingRef.current.y = pt.y;
    } else if (panningRef.current) {
      const pt = canvasPoint(evt);
      const p = panningRef.current;
      transformRef.current = {
        ...transformRef.current,
        tx: p.tx + (pt.screenX - p.startScreenX),
        ty: p.ty + (pt.screenY - p.startScreenY),
      };
    }
  }

  function handleMouseUp(evt) {
    if (draggingRef.current) {
      const pt = canvasPoint(evt);
      const dx = draggingRef.current.x - pt.x;
      const moved = Math.abs(dx) > 1;
      const node = draggingRef.current;
      draggingRef.current = null;
      if (!moved) selectNode(node);
      return;
    }
    if (panningRef.current) {
      panningRef.current = null;
      return;
    }
  }

  function handleWheel(evt) {
    evt.preventDefault();
    const { scale, tx, ty } = transformRef.current;
    const factor = evt.deltaY < 0 ? 1.1 : 0.9;
    const newScale = Math.min(Math.max(scale * factor, 0.25), 3);
    transformRef.current = { scale: newScale, tx, ty };
  }

  // React attaches its synthetic wheel listener as passive, so evt.preventDefault() inside
  // a JSX onWheel handler throws a console warning and silently fails to stop page scroll.
  // Attaching a real, non-passive listener directly to the canvas node avoids that.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const listener = (evt) => handleWheel(evt);
    canvas.addEventListener("wheel", listener, { passive: false });
    return () => canvas.removeEventListener("wheel", listener);
  }, []);

  function toggleType(t) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  }

  if (error) {
    return (
      <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
        Couldn't load the knowledge graph: {error}
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
      <div className="bg-white border border-stone-200 rounded-lg p-3 space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex flex-wrap gap-1.5">
            {Object.keys(TYPE_COLORS).map((t) => (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className={`text-[11px] font-medium px-2 py-1 rounded-full border flex items-center gap-1.5 transition-opacity ${
                  activeTypes.has(t) ? "opacity-100" : "opacity-35"
                }`}
                style={{ borderColor: TYPE_COLORS[t] }}
              >
                <span className="w-2 h-2 rounded-full" style={{ background: TYPE_COLORS[t] }} />
                {TYPE_LABELS[t]}
                {stats?.byType?.[t] ? ` (${stats.byType[t]})` : ""}
              </button>
            ))}
          </div>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes…"
            className="text-xs border border-stone-300 rounded-lg px-2.5 py-1.5 w-40 focus:outline-none focus:ring-2 focus:ring-stone-400"
          />
        </div>

        <canvas
          ref={canvasRef}
          width={WIDTH}
          height={HEIGHT}
          className="w-full rounded-lg border border-stone-100 cursor-grab active:cursor-grabbing touch-none"
          style={{ aspectRatio: `${WIDTH} / ${HEIGHT}` }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />
        <p className="text-[11px] text-stone-400">
          Drag the background to pan, scroll to zoom, drag a node to reposition it, click a node to inspect it.
          {stats ? ` ${stats.nodes} nodes · ${stats.edges} edges.` : ""}
        </p>
      </div>

      <div className="bg-white border border-stone-200 rounded-lg p-4 space-y-3 h-fit">
        {!selected && (
          <p className="text-sm text-stone-500">
            Click any node in the graph to see its details and what it's connected to. Document nodes are corpus
            entries; regime, jurisdiction, category and institution nodes group them.
          </p>
        )}
        {selected && (
          <>
            <div>
              <span
                className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded text-white"
                style={{ background: TYPE_COLORS[selected.node_type] }}
              >
                {TYPE_LABELS[selected.node_type] || selected.node_type}
              </span>
              <div className="text-sm font-semibold text-stone-900 mt-1.5">{selected.label}</div>
              {(selected.jurisdiction || selected.regime) && (
                <div className="text-xs text-stone-500 mt-0.5">
                  {[selected.jurisdiction, selected.regime].filter(Boolean).join(" · ")}
                </div>
              )}
              {selected.source_url && (
                <a
                  href={selected.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-stone-600 underline mt-1 inline-block"
                >
                  Open source
                </a>
              )}
            </div>

            <div>
              <div className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1.5">
                Connected nodes {relatedLoading ? "" : `(${related.length})`}
              </div>
              {relatedLoading && <div className="text-xs text-stone-400 animate-pulse">Loading…</div>}
              <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
                {related.map((r) => (
                  <button
                    key={`${r.id}-${r.relation}`}
                    onClick={() => {
                      const node = nodeByIdRef.current.get(r.id);
                      if (node) selectNode(node);
                    }}
                    className="w-full text-left text-xs border border-stone-200 rounded-lg px-2 py-1.5 hover:border-stone-400 hover:bg-stone-50"
                  >
                    <div className="font-medium text-stone-800 truncate">{r.label}</div>
                    <div className="text-stone-400 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: TYPE_COLORS[r.node_type] }} />
                      {(r.relation || "related").toLowerCase().replace(/_/g, " ")}
                    </div>
                  </button>
                ))}
                {!relatedLoading && related.length === 0 && (
                  <div className="text-xs text-stone-400">No directly connected nodes.</div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
