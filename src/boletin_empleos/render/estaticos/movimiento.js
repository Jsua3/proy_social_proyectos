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

// Filtro por lugar. La edición puede traer cientos de vacantes; quien quiere
// mirar fuera del eje o fuera del país llega de un toque, y el enlace queda en
// la URL para poder compartirlo.
(function () {
  "use strict";

  var pastillas = [].slice.call(document.querySelectorAll("[data-filtro]"));
  var secciones = [].slice.call(document.querySelectorAll("[data-seccion]"));
  if (!pastillas.length || !secciones.length) return;

  function aplicar(filtro) {
    var conocido = filtro === "todas" || secciones.some(function (s) {
      return s.getAttribute("data-seccion") === filtro;
    });
    if (!conocido) filtro = "todas";

    secciones.forEach(function (seccion) {
      var visible = filtro === "todas" || seccion.getAttribute("data-seccion") === filtro;
      // `hidden` también la saca del árbol de accesibilidad, no solo de la vista.
      if (visible) seccion.removeAttribute("hidden");
      else seccion.setAttribute("hidden", "");
    });

    pastillas.forEach(function (pastilla) {
      var activa = pastilla.getAttribute("data-filtro") === filtro;
      pastilla.classList.toggle("filtro__pastilla--activa", activa);
      pastilla.setAttribute("aria-pressed", activa ? "true" : "false");
    });

    return filtro;
  }

  pastillas.forEach(function (pastilla) {
    pastilla.addEventListener("click", function () {
      var filtro = aplicar(pastilla.getAttribute("data-filtro"));
      // replaceState: cambia la dirección sin ensuciar el historial ni saltar.
      var destino = filtro === "todas" ? " " : "#" + filtro;
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", destino);
      }
    });
  });

  // Se puede llegar directo desde un enlace: .../2026-09-22.html#internacional
  function desdeLaDireccion() {
    if (window.location.hash.length > 1) aplicar(window.location.hash.slice(1));
  }
  desdeLaDireccion();
  // Y si la dirección cambia sin recargar —un enlace interno, el botón de
  // atrás—, el filtro tiene que seguirla igual.
  window.addEventListener("hashchange", desdeLaDireccion);
})();
