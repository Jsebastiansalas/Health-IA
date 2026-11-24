// Fija el tema ANTES de pintar para evitar el destello. Archivo propio (no inline) por la CSP.
// Claro por defecto; el oscuro solo si la persona lo eligió.
(function () {
  try {
    var guardado = localStorage.getItem("medtender-tema");
    document.documentElement.setAttribute("data-tema", guardado === "oscuro" ? "oscuro" : "claro");
  } catch (e) {
    document.documentElement.setAttribute("data-tema", "claro");
  }
})();
