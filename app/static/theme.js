(() => {
  let theme = null;
  try {
    theme = window.localStorage.getItem("uspg-theme");
  } catch (_) {
    // Without storage the page follows the system preference.
  }
  if (theme !== "light" && theme !== "dark") {
    theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.dataset.theme = theme;
})();
