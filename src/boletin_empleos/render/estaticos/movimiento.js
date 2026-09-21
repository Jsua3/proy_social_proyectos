// Movimiento del sitio. Sin librerías: la página tiene que abrir igual de rápido
// desde un celular con datos móviles.
//
// Dos cosas nada más, siguiendo el lenguaje de iOS: el contenido aparece al
// entrar en pantalla, y la barra superior se asienta cuando uno baja. Quien
// pida menos movimiento no recibe ninguno.
(function () {
  "use strict";

  var menosMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var aparecen = document.querySelectorAll(".aparece");
  if (menosMovimiento || !("IntersectionObserver" in window)) {
    aparecen.forEach(function (el) {
      el.classList.add("aparece--visible");
    });
  } else {
    var observador = new IntersectionObserver(
      function (entradas) {
        entradas.forEach(function (entrada, i) {
          if (!entrada.isIntersecting) return;
          // Escalonado corto: la lista se asienta, no desfila.
          entrada.target.style.transitionDelay = Math.min(i * 40, 160) + "ms";
          entrada.target.classList.add("aparece--visible");
          observador.unobserve(entrada.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
    );
    aparecen.forEach(function (el) {
      observador.observe(el);
    });
  }

  // La barra gana peso cuando el contenido pasa por debajo: el borde de scroll
  // de iOS, no una línea fija.
  var barra = document.querySelector(".barra");
  if (!barra) return;
  var ultimo = null;
  function alDesplazar() {
    var asentada = window.scrollY > 8;
    if (asentada === ultimo) return;
    ultimo = asentada;
    barra.classList.toggle("barra--asentada", asentada);
  }
  alDesplazar();
  window.addEventListener("scroll", alDesplazar, { passive: true });
})();
