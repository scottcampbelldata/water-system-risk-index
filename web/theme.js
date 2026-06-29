// Applies the saved theme before first paint to avoid a flash of the wrong
// theme. Kept as a tiny external script (not inline) so it complies with the
// Content-Security-Policy (script-src 'self'). The fuller control logic lives
// in app.js; this only needs to read the stored choice.
//
// Stored value: "light" | "dark" | "system" (or absent => system).
// "system" / absent leaves no attribute set, so the CSS prefers-color-scheme
// media query governs.
(function () {
  try {
    var choice = localStorage.getItem("theme");
    if (choice === "light" || choice === "dark") {
      document.documentElement.setAttribute("data-theme", choice);
    }
  } catch (e) {
    /* localStorage unavailable (private mode); fall back to system. */
  }
})();
