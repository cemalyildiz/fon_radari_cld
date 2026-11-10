/* Arayüz: tema anahtarı (açık varsayılan, koyu isteğe bağlı) ve "yukarı çık" butonu */
(function(){
  const kok = document.documentElement;
  const ANAHTAR = 'fon-radari-tema';
  const anahtar = document.getElementById('tema-anahtar');

  function temaUygula(koyu){
    if (koyu) kok.dataset.theme = 'dark'; else delete kok.dataset.theme;
    anahtar.setAttribute('aria-checked', String(koyu));
  }
  temaUygula(kok.dataset.theme === 'dark');
  anahtar.addEventListener('click', () => {
    const koyu = kok.dataset.theme !== 'dark';
    temaUygula(koyu);
    try { koyu ? localStorage.setItem(ANAHTAR, 'dark') : localStorage.removeItem(ANAHTAR); } catch(e) {}
  });

  // Yukarı çık: ilk ekranı geçince görünür; halka sayfadaki ilerlemeyi gösterir
  const buton = document.getElementById('yukari');
  const halka = document.getElementById('yukari-ilerleme');
  const CEVRE = 2 * Math.PI * 22;
  const azHareket = window.matchMedia('(prefers-reduced-motion: reduce)');
  let bekliyor = false;

  function guncelle(){
    bekliyor = false;
    const y = window.scrollY;
    const toplam = document.documentElement.scrollHeight - window.innerHeight;
    buton.classList.toggle('gorunur', y > Math.min(600, window.innerHeight * 0.8));
    const oran = toplam > 0 ? Math.min(1, y / toplam) : 0;
    halka.style.strokeDashoffset = String(CEVRE * (1 - oran));
  }
  window.addEventListener('scroll', () => { if (!bekliyor){ bekliyor = true; requestAnimationFrame(guncelle); } }, { passive:true });
  window.addEventListener('resize', guncelle);
  buton.addEventListener('click', () => {
    window.scrollTo({ top:0, behavior: azHareket.matches ? 'auto' : 'smooth' });
    // Klavye kullanıcısı için odağı sayfa başına taşı
    const hedef = document.querySelector('.brand');
    if (hedef){ hedef.setAttribute('tabindex', '-1'); hedef.focus({ preventScroll:true }); }
  });
  guncelle();
})();
