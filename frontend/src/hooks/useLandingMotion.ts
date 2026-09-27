import { useEffect } from "react";
import type { RefObject } from "react";

/** Page-local choreography. Each moving layer has one transform owner. */
export function useLandingMotion(root: RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    const page = root.current;
    if (!page) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
    const hero = page.querySelector<HTMLElement>(".lp-hero");
    const scene = page.querySelector<HTMLElement>(".lp-scene");
    const sentence = page.querySelector<HTMLElement>(".lp-recognition h2");
    const words = [
      ...page.querySelectorAll<HTMLElement>(".lp-recognition-word"),
    ];
    const arrivals = [
      ...page.querySelectorAll<HTMLElement>("[data-lp-arrival]"),
    ];
    if (!hero || !scene || !sentence) return;

    let stopMotion = () => {};
    const configure = () => {
      stopMotion();
      if (reduced.matches) return;
      let frame = 0;
      let blinkTimer = 0;
      let lookX = 0;
      let lookY = 0;
      let heroVisible = true;
      let sentenceVisible = true;
      const clamp = (value: number, low: number, high: number) =>
        Math.min(high, Math.max(low, value));

      const paint = () => {
        frame = 0;
        if (document.hidden) return;
        if (heroVisible) {
          scene.style.setProperty("--lp-look-x", `${lookX * 8}px`);
          scene.style.setProperty("--lp-look-y", `${lookY * 5}px`);
          scene.style.setProperty("--lp-head-tilt", `${lookX * 3}deg`);
          scene.style.setProperty("--lp-paper-yaw", `${lookX * 5}deg`);
          scene.style.setProperty("--lp-paper-pitch", `${-lookY * 4}deg`);
        }
        if (sentenceVisible) {
          const rect = sentence.getBoundingClientRect();
          const progress = clamp(
            (innerHeight * 0.88 - rect.top) / (innerHeight * 0.38),
            0,
            1,
          );
          words.forEach((word, index) => {
            const emphasis = clamp(
              progress * 1.6 - (index / words.length) * 0.6,
              0,
              1,
            );
            word.style.setProperty(
              "--lp-word-opacity",
              `${0.6 + emphasis * 0.4}`,
            );
            word.style.setProperty("--lp-word-rise", `${(1 - emphasis) * 8}px`);
          });
        }
      };
      const schedule = () => {
        if (!frame) frame = requestAnimationFrame(paint);
      };
      const observe = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.target === hero) {
              heroVisible = entry.isIntersecting;
              if (heroVisible) hero.classList.add("lp-hero-awake");
            }
            if (entry.target === sentence)
              sentenceVisible = entry.isIntersecting;
            if (
              entry.isIntersecting &&
              entry.target.hasAttribute("data-lp-arrival")
            ) {
              entry.target.classList.add("lp-arrived");
              observe.unobserve(entry.target);
            }
          }
          schedule();
        },
        { threshold: 0.08 },
      );

      arrivals.forEach((element) => {
        // Enhance only elements that have not yet entered the viewport.
        if (element.getBoundingClientRect().top < innerHeight * 0.95) {
          element.classList.add("lp-arrived");
        }
        observe.observe(element);
      });
      observe.observe(hero);
      observe.observe(sentence);
      page.classList.add("lp-motion-ready");

      const resetPointer = () => {
        lookX = 0;
        lookY = 0;
        schedule();
      };
      const track = (event: PointerEvent) => {
        if (
          !finePointer.matches ||
          event.pointerType !== "mouse" ||
          !heroVisible
        )
          return;
        const rect = scene.getBoundingClientRect();
        lookX = clamp(
          (event.clientX - rect.left - rect.width / 2) / (rect.width / 2),
          -1,
          1,
        );
        lookY = clamp(
          (event.clientY - rect.top - rect.height / 2) / (rect.height / 2),
          -1,
          1,
        );
        schedule();
      };
      const blink = (event: PointerEvent) => {
        if (!finePointer.matches || event.pointerType !== "mouse") return;
        scene.classList.add("lp-panda-blinking");
        clearTimeout(blinkTimer);
        blinkTimer = window.setTimeout(
          () => scene.classList.remove("lp-panda-blinking"),
          260,
        );
      };
      const revealFocus = (event: FocusEvent) => {
        if (event.target instanceof Element) {
          event.target
            .closest("[data-lp-arrival]")
            ?.classList.add("lp-arrived");
        }
      };
      hero.addEventListener("pointermove", track);
      hero.addEventListener("pointerleave", resetPointer);
      scene.addEventListener("pointerenter", blink);
      page.addEventListener("focusin", revealFocus);
      finePointer.addEventListener("change", resetPointer);
      addEventListener("scroll", schedule, { passive: true });
      addEventListener("resize", schedule, { passive: true });
      document.addEventListener("visibilitychange", schedule);
      schedule();

      stopMotion = () => {
        cancelAnimationFrame(frame);
        clearTimeout(blinkTimer);
        observe.disconnect();
        hero.removeEventListener("pointermove", track);
        hero.removeEventListener("pointerleave", resetPointer);
        scene.removeEventListener("pointerenter", blink);
        page.removeEventListener("focusin", revealFocus);
        finePointer.removeEventListener("change", resetPointer);
        removeEventListener("scroll", schedule);
        removeEventListener("resize", schedule);
        document.removeEventListener("visibilitychange", schedule);
        page.classList.remove("lp-motion-ready");
        scene.classList.remove("lp-panda-blinking");
        hero.classList.remove("lp-hero-awake");
        [
          "--lp-look-x",
          "--lp-look-y",
          "--lp-head-tilt",
          "--lp-paper-yaw",
          "--lp-paper-pitch",
        ].forEach((property) => scene.style.removeProperty(property));
        words.forEach((word) => {
          word.style.removeProperty("--lp-word-opacity");
          word.style.removeProperty("--lp-word-rise");
        });
      };
    };
    configure();
    reduced.addEventListener("change", configure);
    return () => {
      stopMotion();
      reduced.removeEventListener("change", configure);
    };
  }, [root]);
}
