import { ExternalLink, Network, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api.js";
import ErrorNote from "../ui/ErrorNote.jsx";
import PageHeader from "../ui/PageHeader.jsx";

/** Force-directed layout on <canvas>. The graph is small (~100 nodes), so a plain O(n^2)
 * simulation is fast enough and avoids a graph-visualisation dependency. */

const DPR = typeof window !== "undefined" ? Math.min(window.devicePixelRatio || 1, 2) : 1;
const cssVar = (name) => `rgb(${getComputedStyle(document.documentElement).getPropertyValue(name).trim()})`;

const WIDTH = 900;
const HEIGHT = 560;

// Mid-tone hues that read on both the light and the dark background.
const TYPE_COLORS = {
  document: "#8a948f",
  regime: "#2a9d8f",
  jurisdiction: "#d08a2c",
  category: "#5a9e4b",
  institution: "#8b6fd6",
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

export default function GraphView() {
  const canvasRef = useRef(null);
  const nodesRef = useRef([]);
  const edgesRef = useRef([]);
  const nodeByIdRef = useRef(new Map());
  const draggingRef = useRef(null);
  const panningRef = useRef(null);
  const transformRef = useRef({ scale: 0.7, tx: WIDTH / 2, ty: HEIGHT / 2 });
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
      .graph()
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
        const REPULSION = 5200;
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

        const SPRING_LEN = 95;
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
          node.vx += (WIDTH / 2 - node.x) * 0.004 * alpha;
          node.vy += (HEIGHT / 2 - node.y) * 0.006 * alpha;
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
      const theme = { bg: cssVar("--surface"), ink: cssVar("--ink"), line: cssVar("--faint"), accent: cssVar("--accent") };
      ctx.save();
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      ctx.clearRect(0, 0, WIDTH, HEIGHT);
      ctx.fillStyle = theme.bg;
      ctx.fillRect(0, 0, WIDTH, HEIGHT);
      ctx.translate(tx, ty);
      ctx.scale(scale, scale);
      ctx.translate(-WIDTH / 2, -HEIGHT / 2);

      const active = activeTypesRef.current;
      const highlight = highlightRef.current;
      const selId = selectedIdRef.current;
      const neighbours = new Set();
      if (selId) {
        for (const e of edgesRef.current) {
          if (e.source === selId) neighbours.add(e.target);
          if (e.target === selId) neighbours.add(e.source);
        }
      }
      const visible = new Set(nodesRef.current.filter((n) => active.has(n.node_type)).map((n) => n.id));

      ctx.lineWidth = 1 / scale;
      for (const e of edgesRef.current) {
        if (!visible.has(e.source) || !visible.has(e.target)) continue;
        const a = nodeByIdRef.current.get(e.source);
        const b = nodeByIdRef.current.get(e.target);
        const dim = selId && a.id !== selId && b.id !== selId;
        ctx.strokeStyle = theme.line;
        ctx.globalAlpha = dim ? 0.12 : 0.35;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

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
          ctx.strokeStyle = isSel ? theme.ink : theme.accent;
          ctx.stroke();
        }
        ctx.globalAlpha = 1;

        // Concept nodes are always labelled; documents only when zoomed in, selected,
        // matched by search, or directly linked to the selected node.
        const showLabel =
          node.node_type !== "document" || scale > 1.3 || isSel || isHi || (selId && neighbours.has(node.id));
        if (showLabel) {
          ctx.font = `${11 / Math.max(scale, 0.6)}px Inter, sans-serif`;
          ctx.fillStyle = theme.ink;
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
      .related(node.id)
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

  return (
    <>
      <PageHeader icon={Network} title="Knowledge graph">
        How the statutes, treaties, regulators and product categories in the corpus connect. The assistant follows
        these links to surface related requirements that a search alone would miss.
      </PageHeader>
      {error ? (
        <ErrorNote>Couldn't load the knowledge graph: {error}</ErrorNote>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="card space-y-3 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2 px-1 pt-1">
              <div className="flex flex-wrap gap-1.5">
                {Object.keys(TYPE_COLORS).map((type) => (
                  <button
                    key={type}
                    onClick={() => toggleType(type)}
                    aria-pressed={activeTypes.has(type)}
                    className={`flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[11px] font-medium text-muted transition ${
                      activeTypes.has(type) ? "opacity-100" : "opacity-40"
                    }`}
                  >
                    <span className="h-2 w-2 rounded-full" style={{ background: TYPE_COLORS[type] }} />
                    {TYPE_LABELS[type]}
                    {stats?.byType?.[type] ? <span className="text-faint">{stats.byType[type]}</span> : null}
                  </button>
                ))}
              </div>
              <label className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 focus-within:border-primary/40">
                <Search className="h-3.5 w-3.5 text-faint" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Find a node"
                  className="w-32 bg-transparent text-xs placeholder:text-faint focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </label>
            </div>
            <canvas
              ref={canvasRef}
              width={WIDTH * DPR}
              height={HEIGHT * DPR}
              className="w-full cursor-grab touch-none rounded-xl active:cursor-grabbing"
              style={{ aspectRatio: `${WIDTH} / ${HEIGHT}` }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            />
            <p className="px-1 pb-1 text-[11px] text-faint">
              Drag to pan, scroll to zoom, click a node to inspect it.
              {stats ? ` ${stats.nodes} nodes · ${stats.edges} links.` : ""}
            </p>
          </div>

          <aside className="card h-fit space-y-4 p-5">
            {!selected ? (
              <p className="text-sm leading-relaxed text-muted">
                Select a node to see what it connects to. Documents are statutes, rules and treaties; the other node
                types group them by legal regime, jurisdiction, product category and regulator.
              </p>
            ) : (
              <>
                <div>
                  <span
                    className="rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white"
                    style={{ background: TYPE_COLORS[selected.node_type] }}
                  >
                    {TYPE_LABELS[selected.node_type] || selected.node_type}
                  </span>
                  <h2 className="mt-2 font-display text-lg font-semibold leading-snug text-ink">{selected.label}</h2>
                  {(selected.jurisdiction || selected.regime) && (
                    <div className="mt-0.5 text-xs text-muted">
                      {[selected.jurisdiction, selected.regime?.replace(/_/g, " ")].filter(Boolean).join(" · ")}
                    </div>
                  )}
                  {selected.source_url && (
                    <a
                      href={selected.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    >
                      Open source <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
                <div>
                  <div className="eyebrow mb-2">Connected {relatedLoading ? "" : `(${related.length})`}</div>
                  {relatedLoading && <div className="skeleton h-16" />}
                  <div className="max-h-96 space-y-1.5 overflow-y-auto pr-1">
                    {related.map((r) => (
                      <button
                        key={`${r.id}-${r.relation}`}
                        onClick={() => {
                          const node = nodeByIdRef.current.get(r.id);
                          if (node) selectNode(node);
                        }}
                        className="w-full rounded-xl border border-line px-3 py-2 text-left text-xs transition hover:border-primary/40 hover:bg-sunken"
                      >
                        <div className="truncate font-medium text-ink">{r.label}</div>
                        <div className="mt-0.5 flex items-center gap-1.5 text-faint">
                          <span className="h-1.5 w-1.5 rounded-full" style={{ background: TYPE_COLORS[r.node_type] }} />
                          {(r.relation || "related").toLowerCase().replace(/_/g, " ")}
                        </div>
                      </button>
                    ))}
                    {!relatedLoading && related.length === 0 && <div className="text-xs text-faint">No direct connections.</div>}
                  </div>
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
