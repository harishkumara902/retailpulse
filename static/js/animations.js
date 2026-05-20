document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".panel, .metric").forEach((el, index) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(10px)";
    setTimeout(() => {
      el.style.transition = "opacity .35s ease, transform .35s ease, border-color .2s ease";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    }, 45 * index);
  });
});
