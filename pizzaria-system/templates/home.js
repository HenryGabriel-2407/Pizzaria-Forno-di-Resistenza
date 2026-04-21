
const btn = document.querySelector(".btn-saiba-mais");
const extraTexto = document.querySelector(".conteudo-extra");
const extraImg = document.querySelector(".storia-imagem .imagem-extra");

btn.addEventListener("click", () => {
const isVisible = extraTexto.style.display === "block";

if (isVisible) {
    extraTexto.style.display = "none";
    extraImg.style.display = "none";
    btn.textContent = "Saiba Mais";
} else {
    extraTexto.style.display = "block";
    extraImg.style.display = "block";
    btn.textContent = "Mostrar Menos";
}
});




document.addEventListener("DOMContentLoaded", () => {
  const track = document.querySelector('.carousel-track');

  // DUPLICAR os cards dinamicamente (pra não precisar repetir no HTML)
  track.innerHTML += track.innerHTML;

  let speed = 1; // pixels por frame
  let scroll = 0;

  function loopCarousel() {
    scroll += speed;
    if (scroll >= track.scrollWidth / 2) {
      scroll = 0;
    }
    track.style.transform = `translateX(-${scroll}px)`;
    requestAnimationFrame(loopCarousel);
  }

  loopCarousel();

  // pausa hover (opcional)
  track.parentElement.addEventListener('mouseenter', () => speed = 0);
  track.parentElement.addEventListener('mouseleave', () => speed = 1);
});
