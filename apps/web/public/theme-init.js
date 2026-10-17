// Set the colour theme before the first paint, so dark-mode visitors never see a white flash.
// (The app takes over from here: src/lib/theme.ts. Kept tiny, and external because the
// Content-Security-Policy allows no inline scripts.)
(function () {
  var choice = "system";
  try {
    var v = localStorage.getItem("iid.theme");
    if (v === "light" || v === "dark" || v === "system") choice = v;
  } catch (e) {}
  var dark = choice === "dark" || (choice === "system" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
})();
