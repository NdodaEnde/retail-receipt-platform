import React, { useState, useRef, useCallback, useEffect } from "react";
import { X, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

/**
 * ZoomableImage – click thumbnail to open a full-screen lightbox with zoom/pan.
 * Supports scroll-to-zoom (desktop) and pinch-to-zoom (mobile).
 */
export default function ZoomableImage({ src, alt = "Receipt", className = "" }) {
  const [open, setOpen] = useState(false);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const posStart = useRef({ x: 0, y: 0 });
  const containerRef = useRef(null);

  // Pinch state
  const lastPinchDist = useRef(null);

  const reset = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  const clampScale = (s) => Math.min(Math.max(s, 0.5), 5);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  // Prevent body scroll when lightbox is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  // Scroll-to-zoom (desktop)
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    setScale((prev) => clampScale(prev + (e.deltaY < 0 ? 0.2 : -0.2)));
  }, []);

  // Mouse drag
  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
    posStart.current = { ...position };
  };

  const handleMouseMove = useCallback((e) => {
    if (!dragging) return;
    setPosition({
      x: posStart.current.x + (e.clientX - dragStart.current.x),
      y: posStart.current.y + (e.clientY - dragStart.current.y),
    });
  }, [dragging]);

  const handleMouseUp = useCallback(() => setDragging(false), []);

  // Touch drag + pinch-to-zoom
  const handleTouchStart = (e) => {
    if (e.touches.length === 1) {
      setDragging(true);
      dragStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      posStart.current = { ...position };
    }
    if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      lastPinchDist.current = Math.hypot(dx, dy);
    }
  };

  const handleTouchMove = useCallback((e) => {
    if (e.touches.length === 1 && dragging) {
      setPosition({
        x: posStart.current.x + (e.touches[0].clientX - dragStart.current.x),
        y: posStart.current.y + (e.touches[0].clientY - dragStart.current.y),
      });
    }
    if (e.touches.length === 2 && lastPinchDist.current !== null) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.hypot(dx, dy);
      const delta = dist - lastPinchDist.current;
      setScale((prev) => clampScale(prev + delta * 0.005));
      lastPinchDist.current = dist;
    }
  }, [dragging]);

  const handleTouchEnd = useCallback(() => {
    setDragging(false);
    lastPinchDist.current = null;
  }, []);

  const openLightbox = () => {
    reset();
    setOpen(true);
  };

  return (
    <>
      {/* Thumbnail – clickable */}
      <img
        src={src}
        alt={alt}
        className={`${className} cursor-zoom-in`}
        onClick={openLightbox}
        title="Click to zoom"
      />

      {/* Full-screen lightbox */}
      {open && (
        <div className="fixed inset-0 z-[9999] flex flex-col bg-black/95 backdrop-blur-sm">
          {/* Toolbar */}
          <div className="flex items-center justify-between px-4 py-3 bg-black/60">
            <span className="text-white/70 text-sm">{Math.round(scale * 100)}%</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setScale((s) => clampScale(s + 0.3))}
                className="p-2 rounded-lg text-white/80 hover:text-white hover:bg-white/10 transition-colors"
                title="Zoom in"
              >
                <ZoomIn className="w-5 h-5" />
              </button>
              <button
                onClick={() => setScale((s) => clampScale(s - 0.3))}
                className="p-2 rounded-lg text-white/80 hover:text-white hover:bg-white/10 transition-colors"
                title="Zoom out"
              >
                <ZoomOut className="w-5 h-5" />
              </button>
              <button
                onClick={reset}
                className="p-2 rounded-lg text-white/80 hover:text-white hover:bg-white/10 transition-colors"
                title="Reset zoom"
              >
                <RotateCcw className="w-5 h-5" />
              </button>
              <button
                onClick={() => setOpen(false)}
                className="p-2 rounded-lg text-white/80 hover:text-white hover:bg-white/10 transition-colors ml-2"
                title="Close (Esc)"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Image area */}
          <div
            ref={containerRef}
            className="flex-1 overflow-hidden select-none"
            style={{ cursor: dragging ? "grabbing" : "grab", touchAction: "none" }}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
          >
            <div className="w-full h-full flex items-center justify-center">
              <img
                src={src}
                alt={alt}
                className="max-w-none pointer-events-none"
                style={{
                  transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
                  transition: dragging ? "none" : "transform 0.15s ease-out",
                }}
                draggable={false}
              />
            </div>
          </div>

          {/* Hint */}
          <div className="text-center py-2 text-white/40 text-xs">
            Scroll to zoom · Drag to pan · Pinch on mobile
          </div>
        </div>
      )}
    </>
  );
}
