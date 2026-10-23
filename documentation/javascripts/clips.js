// Clips play only while they are on screen, and stop when they scroll away. This keeps a page with many clips
// light (a browser can only decode so many videos at once) and saves data on phones.
// Readers who ask for less motion get the poster frame and the controls instead of autoplay.
document$.subscribe(() => {
  const videos = document.querySelectorAll("figure.clip video");
  if (!videos.length) return;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  videos.forEach((v) => {
    v.removeAttribute("autoplay");
    if (still) v.setAttribute("controls", "");
  });
  if (still || !("IntersectionObserver" in window)) return;
  const seen = new IntersectionObserver((entries) => {
    entries.forEach(({ target, isIntersecting }) => {
      if (isIntersecting) {
        if (target.preload !== "auto") { target.preload = "auto"; }
        target.play().catch(() => {});
      } else {
        target.pause();
      }
    });
  }, { threshold: 0.35 });
  videos.forEach((v) => seen.observe(v));
});
