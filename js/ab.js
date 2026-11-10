/* AB Funding & Tenders Portalı çağrıları (data/ab_cagrilari.json, scripts/fetch_eu_calls.py üretir).
   Uluslararası sekmesinde ayrı bir bölümde gösterilir. app.js'teki yardımcıları kullanır. */
const ab = { veri: [], uretim: null, arama: '', program: 'hepsi', durum: 'hepsi', tur: 'hepsi', goster: 40 };
const AB_SAYFA = 40;
const AB_TUR = {
  'ab-cagri': { ad: 'AB çağrısı', cls: 'ab-tur-cagri' },
  'kaskad': { ad: 'Alt çağrı (kaskad)', cls: 'ab-tur-kaskad' },
  'dis-yardim': { ad: 'Dış yardım', cls: 'ab-tur-dis' },
};

function abEuro(n){
  return n == null ? null : new Intl.NumberFormat('tr-TR', { style:'currency', currency:'EUR', maximumFractionDigits:0 }).format(n);
}

// Yeni başvuru için sıradaki tarih; yoksa çağrı listeden düşer
function abDurum(k){
  const sonraki = (k.basvuru_tarihleri || []).find(d => daysUntil(d) >= 0);
  if (!sonraki) return null;
  const acik = !k.baslangic || k.baslangic <= trBugun();
  return { sonraki, gun: daysUntil(sonraki), acik };
}

function abFiltrele(){
  const q = ab.arama.trim().toLocaleLowerCase('tr-TR');
  return ab.veri.filter(k => {
    const d = abDurum(k);
    if (!d) return false;
    if (ab.durum === 'acik' && !d.acik) return false;
    if (ab.durum === 'yakinda' && d.acik) return false;
    if (ab.program !== 'hepsi' && k.program !== ab.program) return false;
    if (ab.tur !== 'hepsi' && k.tur !== ab.tur) return false;
    if (q){
      const metin = [k.baslik, k.id, k.cagri, k.program, k.eylem_turu, k.duzenleyen].join(' ').toLocaleLowerCase('tr-TR');
      if (!q.split(/\s+/).every(w => metin.includes(w))) return false;
    }
    return true;
  });
}

function abSatir(k){
  const d = abDurum(k);
  const tur = AB_TUR[k.tur] || { ad: k.tur, cls: '' };
  const b = k.butce || {};
  const butceParca = [];
  if (b.toplam_eur) butceParca.push(`Toplam bütçe ${abEuro(b.toplam_eur)}`);
  if (b.proje_min_eur || b.proje_max_eur){
    butceParca.push(b.proje_min_eur === b.proje_max_eur ? `proje başına ${abEuro(b.proje_max_eur)}` : `proje başına ${abEuro(b.proje_min_eur)} – ${abEuro(b.proje_max_eur)}`);
  }
  if (b.beklenen_proje) butceParca.push(`beklenen proje sayısı ${b.beklenen_proje}`);
  const durumMetni = d.acik
    ? `<span class="badge badge-acik">Açık · ${kalanMetni(d.gun)}</span>${d.gun === 0 ? ' <span class="ab-not">son başvuru saati çağrı sayfasında</span>' : ''}`
    : `<span class="badge badge-ab-yakinda">Açılış ${fmtDate(k.baslangic)} (planlanan)</span>`;
  const digerKesim = (k.basvuru_tarihleri || []).filter(x => x > d.sonraki);
  return `<li class="ab-oge">
    <div class="ab-ust">
      <span class="ab-program">${escapeHtml(k.program)}</span>
      <span class="ab-tur ${tur.cls}">${escapeHtml(tur.ad)}</span>
      ${durumMetni}
    </div>
    <a class="ab-baslik" href="${guvenliUrl(k.url)}" target="_blank" rel="noopener">${escapeHtml(k.baslik)} ↗</a>
    <div class="ab-kimlik">${escapeHtml(k.tur === 'kaskad' ? (k.ust_cagri || '') : k.id)}${k.eylem_turu ? ' · ' + escapeHtml(k.eylem_turu) : ''}${k.cagri ? ' · ' + escapeHtml(k.cagri) : ''}</div>
    <div class="ab-tarih">
      <strong>${k.asama === 'two-stage' ? '1. aşama (yeni başvuru) son tarihi' : 'Son başvuru'}:</strong> ${fmtDate(d.sonraki)}
      ${d.acik ? '' : ` · ${d.gun} gün sonra`}
      ${(k.ikinci_asama_tarihleri || []).length ? ` · 2. aşama (yalnızca 1. aşamayı geçenler): ${k.ikinci_asama_tarihleri.map(fmtDate).join(', ')}` : ''}
      ${digerKesim.length ? ` · Sonraki tarihler: ${digerKesim.map(fmtDate).join(', ')}` : ''}
    </div>
    ${k.tarih_notu ? `<div class="ab-not">${escapeHtml(k.tarih_notu)}</div>` : ''}
    ${butceParca.length ? `<div class="ab-butce">${escapeHtml(butceParca.join(' · '))}</div>` : ''}
    ${k.tur === 'kaskad' ? `<div class="ab-not">AB'nin doğrudan çağrısı değildir: AB destekli bir projenin (${escapeHtml(k.duzenleyen || '—')}) üçüncü taraflara açtığı alt çağrıdır; başvuru ve koşullar o projenin kendi sayfasındadır.</div>` : ''}
    ${k.tur === 'dis-yardim' ? `<div class="ab-not">AB dış yardım teklif çağrısı · hedef ülke kodu: ${escapeHtml(k.hedef_ulke || '—')}</div>` : ''}
  </li>`;
}

function abRender(){
  const bolum = document.getElementById('ab-portal');
  if (!bolum) return;
  bolum.hidden = !(state.activeTab === 'uluslararasi' && ab.veri.length);
  if (bolum.hidden) return;
  const liste = abFiltrele();
  const acikSayi = liste.filter(k => abDurum(k).acik).length;
  document.getElementById('ab-ozet').textContent =
    `${liste.length} çağrı · ${acikSayi} şu an açık, ${liste.length - acikSayi} yakında açılacak · portal verisi ${ab.uretim ? fmtDate(ab.uretim) : '—'} tarihinde alındı`;
  const ul = document.getElementById('ab-liste');
  ul.innerHTML = liste.length ? liste.slice(0, ab.goster).map(abSatir).join('') : '<li class="ab-bos">Filtrelere uyan çağrı yok.</li>';
  const daha = document.getElementById('ab-daha');
  daha.hidden = liste.length <= ab.goster;
  daha.textContent = `Daha fazla göster (${liste.length - ab.goster} kaldı)`;
}

function abKur(veri){
  ab.veri = veri.cagrilar || [];
  ab.uretim = veri.generated_at;
  const programlar = [...new Set(ab.veri.map(k => k.program))].sort((x, y) => x.localeCompare(y, 'tr'));
  const sel = document.getElementById('ab-program');
  sel.innerHTML = '<option value="hepsi">Hepsi</option>' + programlar.map(p => {
    const n = ab.veri.filter(k => k.program === p && abDurum(k)).length;
    return `<option value="${escapeHtml(p)}">${escapeHtml(p)} (${n})</option>`;
  }).join('');
  const sifirla = () => { ab.goster = AB_SAYFA; abRender(); };
  document.getElementById('ab-arama').addEventListener('input', e => { ab.arama = e.target.value; sifirla(); });
  sel.addEventListener('change', e => { ab.program = e.target.value; sifirla(); });
  document.getElementById('ab-durum').addEventListener('change', e => { ab.durum = e.target.value; sifirla(); });
  document.getElementById('ab-tur').addEventListener('change', e => { ab.tur = e.target.value; sifirla(); });
  document.getElementById('ab-daha').addEventListener('click', () => { ab.goster += AB_SAYFA; abRender(); });
  abRender();
}

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => abRender()));

fetch('data/ab_cagrilari.json?_=' + Date.now())
  .then(r => r.ok ? r.json() : null)
  .then(v => { if (v) abKur(v); })
  .catch(err => console.warn('AB çağrıları yüklenemedi:', err));
