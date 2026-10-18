import { useTranslation } from "@frutti/i18n";
import { Icon } from "@frutti/ui";
import { type CSSProperties, useEffect, useRef } from "react";

import { HERO } from "./media";
import { prefersLessMotion, useParallax } from "./motion";

// Ice flakes and bubbles: fixed sizes and timings, so every visit looks the same and nothing is random.
const BUBBLES = Array.from({ length: 16 }, (_, index) => ({
  left: `${(index * 61) % 100}%`,
  size: 4 + ((index * 7) % 10),
  duration: 9 + ((index * 5) % 9),
  delay: (index * 1.3) % 11,
  sway: ((index % 2 === 0 ? 1 : -1) * (12 + ((index * 11) % 30))).toString() + "px",
}));

function Words({ text, offset, shine = false }: { text: string; offset: number; shine?: boolean }) {
  return text.split(" ").map((word, index) => (
    <span key={index} className="rise me-[0.25em]" style={{ "--i": offset + index } as CSSProperties}>
      {/* The gradient is drawn on an inner span: on the moving outer one the clipped background would not show. */}
      {shine ? <span className="shine">{word}</span> : word}
    </span>
  ));
}

/** Full-screen dawn over the port: a 10-second loop made with Artlist, its still as the poster. */
export function Hero({ onOrder, onQuote }: { onOrder: () => void; onQuote: () => void }) {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement>(null);
  const backdrop = useParallax<HTMLDivElement>(0.3);
  const content = useParallax<HTMLDivElement>(-0.15, 650);
  const titleA = t("site.hero.titleA");

  useEffect(() => {
    if (prefersLessMotion()) video.current?.pause();
  }, []);

  return (
    <section
      id="top"
      className="relative isolate flex min-h-[100svh] items-end overflow-hidden bg-[#0c2633] text-white"
    >
      <div ref={backdrop} className="absolute inset-0 -z-20">
        <video
          ref={video}
          className="size-full scale-105 object-cover"
          poster={HERO.poster}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden
        >
          <source src={HERO.webm} type="video/webm" />
          <source src={HERO.mp4} type="video/mp4" />
        </video>
      </div>
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,rgba(7,26,35,0.55)_0%,rgba(7,26,35,0.15)_35%,rgba(7,26,35,0.85)_100%)]" />
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        {BUBBLES.map((bubble, index) => (
          <span
            key={index}
            className="bubble"
            style={
              {
                left: bubble.left,
                width: bubble.size,
                height: bubble.size,
                animationDuration: `${bubble.duration}s`,
                animationDelay: `${bubble.delay}s`,
                "--sway": bubble.sway,
              } as CSSProperties
            }
          />
        ))}
      </div>

      <div ref={content} className="site-container pt-28 pb-24 md:pb-32">
        <p className="rise eyebrow text-white/80" style={{ "--i": 0 } as CSSProperties}>
          <Icon name="anchor" className="me-2 inline size-4 align-[-2px]" />
          {t("site.hero.eyebrow")}
        </p>
        <h1 className="mt-4 max-w-4xl font-display text-[clamp(2.6rem,7.5vw,6rem)] leading-[0.95] font-extrabold tracking-tight">
          <Words text={titleA} offset={1} />
          <br />
          <Words text={t("site.hero.titleB")} offset={1 + titleA.split(" ").length} shine />
        </h1>
        <p
          className="rise mt-6 max-w-xl text-[1.05rem] leading-relaxed text-white/85 md:text-[1.15rem]"
          style={{ "--i": 7 } as CSSProperties}
        >
          {t("site.hero.body")}
        </p>
        <div className="rise mt-8 flex flex-wrap gap-3" style={{ "--i": 9 } as CSSProperties}>
          <button
            type="button"
            onClick={onOrder}
            className="group flex items-center gap-2 rounded-full bg-coral px-6 py-3.5 text-[1rem] font-bold text-white shadow-[0_12px_32px_-12px_rgba(232,96,76,0.9)] transition hover:-translate-y-0.5 hover:brightness-105"
          >
            <Icon name="cart" />
            {t("site.hero.order")}
          </button>
          <button
            type="button"
            onClick={onQuote}
            className="flex items-center gap-2 rounded-full border border-white/40 bg-white/10 px-6 py-3.5 text-[1rem] font-bold text-white backdrop-blur transition hover:-translate-y-0.5 hover:bg-white/20"
          >
            <Icon name="quote" />
            {t("site.hero.quote")}
          </button>
        </div>
      </div>

      <a
        href="#valeurs"
        className="scroll-cue absolute bottom-6 max-sm:hidden left-1/2 -translate-x-1/2 text-[0.75rem] font-semibold tracking-[0.2em] text-white/70 uppercase"
      >
        {t("site.hero.scroll")}
        <span aria-hidden className="mx-auto mt-2 block h-8 w-px bg-white/60" />
      </a>
      <svg
        aria-hidden
        viewBox="0 0 2880 80"
        preserveAspectRatio="none"
        className="wave absolute -bottom-px left-0 h-10 w-[200%] fill-[var(--bg)] md:h-16"
      >
        <path d="M0 40 C 240 0 480 80 720 40 S 1200 0 1440 40 S 1920 80 2160 40 S 2640 0 2880 40 V 80 H 0 Z" />
      </svg>
    </section>
  );
}
