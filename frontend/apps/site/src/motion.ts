import { useEffect, useRef, useState } from "react";

/** Adds `is-in` to the element the first time it scrolls into view (CSS class `reveal`). */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (typeof IntersectionObserver === "undefined") {
      element.classList.add("is-in");
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return ref;
}

/** Whether the page has scrolled past `threshold` pixels; re-renders only when that changes. */
export function useScrolledPast(threshold: number): boolean {
  const [past, setPast] = useState(false);
  useEffect(() => {
    const read = () => setPast(window.scrollY > threshold);
    read();
    window.addEventListener("scroll", read, { passive: true });
    return () => window.removeEventListener("scroll", read);
  }, [threshold]);
  return past;
}

export function prefersLessMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** Moves the element by `factor` × how far its section has scrolled, once per frame, without re-rendering. With
 * `fade`, it also fades out over the first `fade` pixels of scrolling. */
export function useParallax<T extends HTMLElement>(factor: number, fade = 0) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element || prefersLessMotion()) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = element.parentElement?.getBoundingClientRect();
        const scrolled = box ? -box.top : window.scrollY;
        element.style.transform = `translate3d(0, ${(scrolled * factor).toFixed(1)}px, 0)`;
        if (fade > 0) element.style.opacity = String(Math.max(0, 1 - Math.max(0, scrolled) / fade));
      });
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [factor, fade]);
  return ref;
}
