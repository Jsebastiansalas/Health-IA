// Fija el tema ANTES de pintar para evitar el destello. Archivo propio (no inline) por la CSP.
(function () {
  try {
    var guardado = localStorage.getItem("medtender-tema");
    var tema = guardado === "papel" || guardado === "nocturno"
      ? guardado
      : (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "nocturno" : "papel");
    document.documentElement.setAttribute("data-tema", tema);
  } catch (e) {
    document.documentElement.setAttribute("data-tema", "papel");
  }
})();
