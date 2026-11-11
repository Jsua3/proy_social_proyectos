// Las cifras del boletín aparecen con un desvanecimiento suave al llegar a ellas.
// Sin script, al imprimir o si la persona pidió menos movimiento, se ven quietas.
(function () {
  if (!("IntersectionObserver" in window)) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  document.documentElement.classList.add("con-movimiento");
  var observador = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (entrada) {
      if (entrada.isIntersecting) {
        entrada.target.classList.add("visible");
        observador.unobserve(entrada.target);
      }
    });
  }, { threshold: 0.2 });

  document.querySelectorAll(".cifra").forEach(function (cifra) {
    observador.observe(cifra);
  });
})();
