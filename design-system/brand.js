/*
 * Marca — Turnos Odontólogo.
 * (TBD) Nombre definitivo: cambiá SOLO BRAND_NAME y todo elemento [data-brand-name] se actualiza.
 * Autocontenido: sin dependencias, sin red.
 */
(function () {
  "use strict";
  var BRAND_NAME = "Turnos Odontólogo"; // (TBD) nombre provisional, tomado de frontend/index.html <title>
  window.BRAND_NAME = BRAND_NAME;

  function aplicar() {
    var nodos = document.querySelectorAll("[data-brand-name]");
    for (var i = 0; i < nodos.length; i++) {
      nodos[i].textContent = BRAND_NAME;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", aplicar);
  } else {
    aplicar();
  }
})();
