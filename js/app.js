const state = {
  data: null,
  activeTab: 'ulusal',
  search: '',
  statusFilter: 'acik',
  scaleFilter: 'hepsi',
  temaFilter: 'hepsi',
};

const grid = document.getElementById('card-grid');
const emptyState = document.getElementById('empty-state');
const overlay = document.getElementById('detail-overlay');
const overlayContent = document.getElementById('overlay-content');

/* Tarihler kurum duyurularindaki gibi saatsiz (YYYY-MM-DD) tutulur ve
   Turkiye saatine gore yorumlanir. Saatsiz bir bitis tarihi o gunun SONU
   (23:59:59 TSI) kabul edilir; aksi halde tarayici UTC gece yarisi (03:00 TSI)
   sayar ve cagri son basvuru gunu kapanmis gorunur. */
const TR_OFFSET = '+03:00';
function saatsizMi(d){ return /^\d{4}-\d{2}-\d{2}$/.test(d || ''); }
function bitisZamani(d){ return new Date(saatsizMi(d) ? d + 'T23:59:59' + TR_OFFSET : d); }
function baslangicZamani(d){ return new Date(saatsizMi(d) ? d + 'T00:00:00' + TR_OFFSET : d); }
function trBugun(){
  // Turkiye'deki bugunun tarihi (YYYY-MM-DD), kullanicinin saat diliminden bagimsiz
  return new Intl.DateTimeFormat('en-CA', { timeZone:'Europe/Istanbul', year:'numeric', month:'2-digit', day:'2-digit' }).format(new Date());
}

function computeStatus(call){
  if (call.yururlukten_kaldirildi) return 'kaldirildi';
  if (call.cerceve_program) return 'cerceve';
  if (call.surekli_acik) return 'acik';
  if (!call.basvuru_bitis) return 'acik';
  if (new Date() > bitisZamani(call.basvuru_bitis)) return 'kapali';
  if (daysUntil(call.basvuru_bitis) <= 14) return 'yakinda-kapaniyor';
  return 'acik';
}

// Bitis gunune kalan TAKVIM gunu (0 = bugun son gun)
function daysUntil(dateStr){
  if (!dateStr) return null;
  const bitisGun = dateStr.slice(0, 10);
  return Math.round((Date.parse(bitisGun + 'T00:00:00Z') - Date.parse(trBugun() + 'T00:00:00Z')) / 86400000);
}
function kalanMetni(days){
  return days === 0 ? 'bugün son gün' : `${days} gün kaldı`;
}

function statusLabel(status, call){
  if (call.yururlukten_kaldirildi) return { text: 'Yürürlükten Kaldırıldı', cls: 'badge-kaldirildi' };
  if (call.cerceve_program) return { text: 'Çerçeve Program · Dönemsel', cls: 'badge-cerceve' };
  if (call.surekli_acik) return { text: 'Sürekli Açık', cls: 'badge-surekli' };
  const days = daysUntil(call.basvuru_bitis);
  switch(status){
    case 'acik': return { text: days !== null ? `Açık · ${kalanMetni(days)}` : 'Açık', cls: 'badge-acik' };
    case 'yakinda-kapaniyor': return { text: days !== null ? `Yakında Kapanıyor · ${kalanMetni(days)}` : 'Yakında Kapanıyor', cls: 'badge-yakinda' };
    case 'kapali': return { text: 'Kapalı / Arşiv', cls: 'badge-kapali' };
    default: return { text: 'Bilinmiyor', cls: '' };
  }
}

function fmtDate(d){
  if (!d) return '—';
  const date = saatsizMi(d) ? new Date(d + 'T12:00:00' + TR_OFFSET) : new Date(d);
  return date.toLocaleDateString('tr-TR', { day:'2-digit', month:'short', year:'numeric', timeZone:'Europe/Istanbul' });
}

function progressPct(call){
  if (call.surekli_acik || !call.basvuru_baslangic || !call.basvuru_bitis) return null;
  const start = baslangicZamani(call.basvuru_baslangic).getTime();
  const end = bitisZamani(call.basvuru_bitis).getTime();
  const now = Date.now();
  if (now <= start) return 0;
  if (now >= end) return 100;
  return Math.round(((now - start) / (end - start)) * 100);
}

function sortCalls(calls){
  const priority = { 'yakinda-kapaniyor': 0, 'acik': 1, 'cerceve': 2, 'kapali': 3, 'kaldirildi': 4 };
  return [...calls].sort((a, b) => {
    const sa = computeStatus(a), sb = computeStatus(b);
    const aSurekli = !!a.surekli_acik, bSurekli = !!b.surekli_acik;
    if (priority[sa] !== priority[sb]) return priority[sa] - priority[sb];
    if (sa === 'kapali'){
      return new Date(b.basvuru_bitis || 0) - new Date(a.basvuru_bitis || 0);
    }
    if (sa === 'cerceve') return a.baslik.localeCompare(b.baslik, 'tr');
    if (aSurekli !== bSurekli) return aSurekli ? 1 : -1;
    if (aSurekli && bSurekli) return a.baslik.localeCompare(b.baslik, 'tr');
    return new Date(a.basvuru_bitis || 0) - new Date(b.basvuru_bitis || 0);
  });
}

function matchesFilters(call){
  if (call.kategori !== state.activeTab) return false;
  const status = computeStatus(call);
  if (state.statusFilter === 'acik-veya-yakinda'){
    if (status !== 'acik' && status !== 'yakinda-kapaniyor') return false;
  } else if (state.statusFilter === 'acik'){
    // "Açık" görünümü: yalnızca şu an başvuru yapılabilen çağrılar.
    // Çerçeve programlar (tek bir başvuru tarihi olmayan, dönemsel açılan) ayrı filtrede.
    if (status !== 'acik' && status !== 'yakinda-kapaniyor') return false;
  } else if (state.statusFilter === 'kapali'){
    // Arşiv: kapanmış çağrılar + yürürlükten kaldırılmış programlar
    if (status !== 'kapali' && status !== 'kaldirildi') return false;
  } else if (state.statusFilter !== 'hepsi' && state.statusFilter !== status) {
    return false;
  }
  if (state.scaleFilter !== 'hepsi' && !(call.olcek || []).includes(state.scaleFilter)) return false;
  if (state.temaFilter !== 'hepsi' && !(call.tema || []).includes(state.temaFilter)) return false;
  if (state.search){
    const q = state.search.toLowerCase();
    const haystack = [call.baslik, call.kurum, call.ozet, call.sektor_odagi, (call.tema||[]).join(' ')].join(' ').toLowerCase();
    if (!haystack.includes(q)) return false;
  }
  return true;
}

function renderCards(){
  const calls = sortCalls(state.data.calls.filter(matchesFilters));
  grid.innerHTML = '';
  emptyState.hidden = calls.length !== 0;

  const summary = document.getElementById('result-summary');
  if (state.data){
    const allInTab = state.data.calls.filter(c => c.kategori === state.activeTab);
    const archivedCount = allInTab.filter(c => ['kapali','kaldirildi'].includes(computeStatus(c))).length;
    const cerceveCount = allInTab.filter(c => computeStatus(c) === 'cerceve').length;
    if (state.statusFilter === 'kapali'){
      summary.textContent = `Arşivde ${archivedCount} kapalı çağrı gösteriliyor.`;
    } else {
      // Sayilar ekranda gosterilen kartlardan hesaplanir (filtrelerle tutarli kalsin)
      const gAcik = calls.filter(c => ['acik','yakinda-kapaniyor'].includes(computeStatus(c))).length;
      const gAcil = calls.filter(c => computeStatus(c) === 'yakinda-kapaniyor').length;
      const gCerceve = calls.filter(c => computeStatus(c) === 'cerceve').length;
      const parcalar = [];
      if (gAcik) parcalar.push(`${gAcik} başvuruya açık` + (gAcil ? ` (${gAcil} tanesi 14 gün içinde kapanıyor)` : ''));
      if (gCerceve) parcalar.push(`${gCerceve} çerçeve program (dönemsel açılır)`);
      const detay = parcalar.length ? ': ' + parcalar.join(', ') : '';
      const cerceveIpucu = (state.statusFilter === 'acik' && cerceveCount) ? ` ${cerceveCount} çerçeve program "Çerçeve programlar" filtresinde.` : '';
      summary.textContent = `${calls.length} çağrı gösteriliyor${detay}.${cerceveIpucu} ${archivedCount} kapalı çağrı arşivde — Durum filtresinden "Arşiv"i seçin.`;
    }
  }

  calls.forEach(call => {
    const status = computeStatus(call);
    const badge = statusLabel(status, call);
    const pct = progressPct(call);

    const card = document.createElement('button');
    card.className = 'card';
    card.setAttribute('type', 'button');
    card.innerHTML = `
      <div class="card-top">
        <div>
          <div class="card-org">${escapeHtml(call.kurum)}</div>
          <h3 class="card-title">${escapeHtml(call.baslik)}</h3>
        </div>
        <span class="badge ${badge.cls}">${badge.text}</span>
      </div>
      <p class="card-desc">${escapeHtml(call.ozet)}</p>
      <div class="tema-chips">
        ${(call.tema||[]).map(t => `<span class="tema-chip">${escapeHtml(t)}</span>`).join('')}
      </div>
      ${pct !== null ? `<div class="deadline-bar"><div class="deadline-bar-fill" style="width:${pct}%"></div></div>` : ''}
      ${araTarihSatiri(call)}
      <div class="card-meta">
        <span><strong>${escapeHtml((call.olcek||[]).join(', '))}</strong></span>
        <span>Bitiş: <strong>${call.surekli_acik ? 'Sürekli' : fmtDate(call.basvuru_bitis)}</strong></span>
        <span>${escapeHtml(call.destek_turu || '')}</span>
      </div>
      ${teyitSatiri(call, status)}
    `;
    card.addEventListener('click', () => openDetail(call));
    grid.appendChild(card);
  });
}

function openDetail(call){
  const status = computeStatus(call);
  const badge = statusLabel(status, call);
  overlayContent.innerHTML = `
    <div class="detail-org">${escapeHtml(call.kurum)}</div>
    <h2 class="detail-title">${escapeHtml(call.baslik)}</h2>
    <span class="badge ${badge.cls}">${badge.text}</span>
    <div class="tema-chips" style="margin-top:10px">
      ${(call.tema||[]).map(t => `<span class="tema-chip">${escapeHtml(t)}</span>`).join('')}
    </div>
    <p class="detail-desc">${escapeHtml(call.ozet)}</p>
    <dl class="detail-grid">
      <div class="detail-field"><dt>Başvuru Başlangıç</dt><dd>${fmtDate(call.basvuru_baslangic)}</dd></div>
      <div class="detail-field"><dt>Başvuru Bitiş</dt><dd>${call.surekli_acik ? 'Sürekli açık' : fmtDate(call.basvuru_bitis)}</dd></div>
      ${(call.ara_tarihler||[]).map(a => `<div class="detail-field"><dt>${escapeHtml(a.ad)}</dt><dd>${fmtDate(a.tarih)}</dd></div>`).join('')}
      <div class="detail-field"><dt>Destek Türü</dt><dd>${escapeHtml(call.destek_turu || '—')}</dd></div>
      <div class="detail-field"><dt>Destek Miktarı</dt><dd>${escapeHtml(call.destek_miktari || '—')}</dd></div>
      <div class="detail-field"><dt>Destek Oranı</dt><dd>${escapeHtml(call.destek_orani || '—')}</dd></div>
      <div class="detail-field"><dt>Proje Süresi</dt><dd>${escapeHtml(call.proje_suresi || '—')}</dd></div>
      <div class="detail-field"><dt>Firma Ölçeği</dt><dd>${escapeHtml((call.olcek||[]).join(', '))}</dd></div>
      <div class="detail-field"><dt>Sektör Odağı</dt><dd>${escapeHtml(call.sektor_odagi || '—')}</dd></div>
    </dl>
    <p class="detail-field"><dt>Kimler Başvurabilir</dt></p>
    <p class="detail-desc" style="margin-top:-8px">${escapeHtml(call.kimler_basvurabilir || '—')}</p>
    ${call.notlar ? `<p class="detail-note">${escapeHtml(call.notlar)}</p>` : ''}
    ${teyitDetayi(call, status)}
    <a class="detail-link" href="${call.kaynak_url}" target="_blank" rel="noopener">Resmi kaynağa git ↗</a>
  `;
  overlay.hidden = false;
  document.body.style.overflow = 'hidden';
}

/* ---------- Doğrulama bilgisi ---------- */
const TEYIT_GECERLILIK_GUN = 30; // scripts/dogrulama_kurallari.py ile ayni
state.izleme = {};

function teyitDurumu(call, status){
  const dg = call.dogrulama || {};
  const aktif = ['acik','yakinda-kapaniyor','cerceve'].includes(status);
  const iz = state.izleme[call.id];
  const gunOnce = dg.tarih ? Math.round((Date.parse(trBugun()+'T00:00:00Z') - Date.parse(dg.tarih.slice(0,10)+'T00:00:00Z'))/86400000) : null;
  if (!dg.tarih) return { cls:'teyit-yok', metin:'Resmî kaynaktan teyit bilgisi yok' };
  if (aktif && iz && (iz.duyurular || []).length) {
    const d = iz.duyurular[0];
    return { cls:'teyit-uyari teyit-duyuru', metin:`DİKKAT: Kurum ${fmtDate(d.ilk_gorulme)} tarihinde bu çağrıyla ilgili yeni bir duyuru yayımladı ("${d.baslik}"). Karttaki tarihler güncel olmayabilir; duyuruyu esas alın.`, link: d.url };
  }
  if (aktif && iz && iz.durum === 'yeniden_teyit') return { cls:'teyit-uyari', metin:`Resmî kaynak sayfası ${fmtDate(dg.tarih)} teyidinden sonra değişti — yeniden teyit bekleniyor` };
  if (aktif && gunOnce > TEYIT_GECERLILIK_GUN) return { cls:'teyit-uyari', metin:`Son teyit ${fmtDate(dg.tarih)} (${gunOnce} gün önce) — teyit tarihi eski` };
  if (dg.durum === 'kismi') return { cls:'teyit-kismi', metin:`Kısmi teyit · ${fmtDate(dg.tarih)}` };
  if (dg.durum === 'onceki') return { cls:'teyit-onceki', metin:`Son teyit ${fmtDate(dg.tarih)} (arşiv kaydı)` };
  return { cls:'teyit-tam', metin:`Resmî kaynaktan teyit · ${fmtDate(dg.tarih)}` };
}

function teyitSatiri(call, status){
  const t = teyitDurumu(call, status);
  return `<div class="teyit ${t.cls}">${escapeHtml(t.metin)}${t.link ? ` <a href="${guvenliUrl(t.link)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Duyuruyu aç ↗</a>` : ''}</div>`;
}

function teyitDetayi(call, status){
  const dg = call.dogrulama;
  if (!dg) return `<div class="teyit-detay"><strong>Doğrulama:</strong> Bu kayıt için resmî kaynak teyidi bulunmuyor.</div>`;
  const t = teyitDurumu(call, status);
  const iz = state.izleme[call.id];
  const durumAd = { tam:'Tam (tarih, destek ve uygunluk resmî kaynaktan okundu)', kismi:'Kısmi', onceki:'Önceki teyit (arşiv kaydı)' }[dg.durum || 'tam'];
  return `<div class="teyit-detay ${t.cls}">
    <strong>Doğrulama</strong>
    <div>Son teyit: ${fmtDate(dg.tarih)} · ${escapeHtml(durumAd)}${dg.kaynak_turu === 'ikincil' ? ' · <em>ikincil (resmî olmayan) kaynak</em>' : ''}</div>
    ${dg.eksik ? `<div><strong>Teyit edilemeyen:</strong> ${escapeHtml(dg.eksik)}</div>` : ''}
    ${dg.kanit ? `<div class="teyit-kanit">Kanıt: ${escapeHtml(dg.kanit)}</div>` : ''}
    ${iz && iz.durum === 'yeniden_teyit' ? `<div><strong>Otomatik kaynak kontrolü (${fmtDate(iz.son_kontrol)}):</strong> ${escapeHtml((iz.bulgular||[]).join(' · '))}</div>` : ''}
    ${dg.kaynak ? `<div><a href="${guvenliUrl(dg.kaynak)}" target="_blank" rel="noopener">Teyit kaynağı ↗</a></div>` : ''}
  </div>`;
}

// Bugünden sonraki en yakın ara tarih (ör. ön kayıt son günü)
function siradakiAraTarih(call){
  return (call.ara_tarihler || [])
    .map(a => ({ ...a, gun: daysUntil(a.tarih) }))
    .filter(a => a.gun !== null && a.gun >= 0)
    .sort((x, y) => x.gun - y.gun)[0] || null;
}

function araTarihSatiri(call){
  const a = siradakiAraTarih(call);
  if (!a) return '';
  return `<div class="ara-tarih">⚑ ${escapeHtml(a.ad)}: <strong>${fmtDate(a.tarih)}</strong> (${kalanMetni(a.gun)})</div>`;
}

function closeDetail(){
  overlay.hidden = true;
  document.body.style.overflow = '';
}

function escapeHtml(str){
  if (str === undefined || str === null) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

document.getElementById('overlay-close').addEventListener('click', closeDetail);
overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDetail(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDetail(); });

document.getElementById('reset-filters-btn').addEventListener('click', () => {
  state.search = '';
  state.statusFilter = 'acik';
  state.scaleFilter = 'hepsi';
  state.temaFilter = 'hepsi';
  document.getElementById('search-input').value = '';
  document.getElementById('status-filter').value = 'acik';
  document.getElementById('scale-filter').value = 'hepsi';
  document.getElementById('tema-filter').value = 'hepsi';
  renderCards();
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected','false'); });
    tab.classList.add('active');
    tab.setAttribute('aria-selected','true');
    state.activeTab = tab.dataset.tab;
    renderCards();
  });
});

document.getElementById('search-input').addEventListener('input', (e) => {
  state.search = e.target.value;
  renderCards();
});
document.getElementById('status-filter').addEventListener('change', (e) => {
  state.statusFilter = e.target.value;
  renderCards();
});
document.getElementById('scale-filter').addEventListener('change', (e) => {
  state.scaleFilter = e.target.value;
  renderCards();
});
document.getElementById('tema-filter').addEventListener('change', (e) => {
  state.temaFilter = e.target.value;
  renderCards();
});

function populateTemaFilter(calls){
  const select = document.getElementById('tema-filter');
  const uniqueTemas = [...new Set(calls.flatMap(c => c.tema || []))].sort((a,b) => a.localeCompare(b, 'tr'));
  uniqueTemas.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    select.appendChild(opt);
  });
}

function relativeTime(iso){
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs/60000);
  if (mins < 1) return 'az önce';
  if (mins < 60) return `${mins} dk önce`;
  const hrs = Math.round(mins/60);
  if (hrs < 24) return `${hrs} sa önce`;
  const days = Math.round(hrs/24);
  return `${days} gün önce`;
}

function renderAlertBanner(){
  const banner = document.getElementById('alert-banner');
  if (!banner || !state.data) return;
  // Uyarılar client-side hesaplanır: otomasyon çalışmasa bile her zaman doğru kalır
  const yaklasan = state.data.calls
    .map(c => ({ c, status: computeStatus(c), gun: daysUntil(c.basvuru_bitis) }))
    .filter(x => x.status === 'yakinda-kapaniyor')
    .sort((a, b) => a.gun - b.gun);

  if (!yaklasan.length){ banner.hidden = true; return; }

  const items = yaklasan.map(({c, gun}) => {
    const ara = siradakiAraTarih(c);
    const araTxt = (ara && ara.gun < gun) ? ` · <span style="font-weight:400">${escapeHtml(ara.ad)}: ${kalanMetni(ara.gun)}</span>` : '';
    const sure = (gun <= 0 ? 'bugün son gün' : `${gun} gün kaldı`) + araTxt;
    return `<li><a href="${c.kaynak_url}" target="_blank" rel="noopener">${escapeHtml(c.baslik)}</a> — <strong style="display:inline;font-size:0.8rem;text-transform:none;letter-spacing:0">${sure}</strong></li>`;
  }).join('');

  banner.innerHTML = `<strong>Son tarih yaklaşıyor (${yaklasan.length} çağrı)</strong><ul>${items}</ul>`;
  banner.hidden = false;
}

/* ---------- Otomatik tarama adaylari (dogrulanmamis) ---------- */

function kesifAnahtar(s){
  return (s || '').toLocaleLowerCase('tr-TR')
    .replace(/ı/g,'i').replace(/ş/g,'s').replace(/ğ/g,'g')
    .replace(/ü/g,'u').replace(/ö/g,'o').replace(/ç/g,'c')
    .replace(/[^a-z0-9]+/g,' ').trim();
}
const KESIF_GENEL = new Set(['destek','programi','program','kosgeb','tubitak','cagrisi','cagri','ve','yili']);

// Adayla iliskili olabilecek dogrulanmis kaydi bulur. Kesin eslesme iddia etmez;
// sadece kullaniciyi "bu zaten listede olabilir" diye uyarmak icindir.
function kesifIliskili(aday, calls){
  const kod = (aday.baslik.match(/^\s*(\d{4})\b/) || [])[1];
  // Birden fazla eslesme varsa acik/surekli kaydi, kapanmis kayda tercih et
  // Hepsi kapaliysa basvuru bitis tarihi en yeni olani sec
  const enIyi = list => {
    if (!list.length) return null;
    const acik = list.find(c => !['kapali','kaldirildi'].includes(computeStatus(c)));
    if (acik) return acik;
    return [...list].sort((x, y) => String(y.basvuru_bitis || '').localeCompare(String(x.basvuru_bitis || '')))[0];
  };
  if (kod){
    const r = enIyi(calls.filter(c => new RegExp('\\b' + kod + '\\b').test(c.baslik + ' ' + c.id)));
    if (r) return r;
  }
  const a = kesifAnahtar(aday.baslik).split(' ').filter(w => w.length > 2 && !KESIF_GENEL.has(w));
  if (!a.length) return null;
  return enIyi(calls.filter(c => {
    const ck = ' ' + kesifAnahtar(c.baslik) + ' ';
    return a.every(w => ck.includes(' ' + w + ' '));
  }));
}

function kesifTur(aday){
  const b = kesifAnahtar(aday.baslik);
  if (/duyuru/i.test(aday.kaynak || '') || /\bacildi\b|\bbasladi\b/.test(b)) return 'Duyuru';
  return 'Program sayfası';
}

function guvenliUrl(u){
  if (!/^https?:\/\//i.test(u || '')) return '#';
  return u.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function loadKesif(calls){
  fetch('data/discovered.json?_=' + Date.now())
    .then(r => r.ok ? r.json() : null)
    .then(d => {
      if (!d || !Array.isArray(d.adaylar)) return;
      const dogrulanmisUrl = new Set(calls.map(c => (c.kaynak_url || '').split(/[?#]/)[0].replace(/\/$/, '')));
      const adaylar = d.adaylar
        .filter(a => a.durum === 'yeni' && a.url && !dogrulanmisUrl.has(a.url.split(/[?#]/)[0].replace(/\/$/, '')))
        .map(a => ({ ...a, iliskili: kesifIliskili(a, calls), tur: kesifTur(a) }))
        // once listede karsiligi olmayanlar, sonra duyurular, sonra en yeni gorulen
        .sort((x, y) =>
          (!!x.iliskili - !!y.iliskili) ||
          ((x.tur === 'Program sayfası') - (y.tur === 'Program sayfası')) ||
          String(y.ilk_gorulme).localeCompare(String(x.ilk_gorulme)));
      if (!adaylar.length) return;

      const eslesmeyen = adaylar.filter(a => !a.iliskili).length;
      document.getElementById('kesif-sayi').textContent =
        `${adaylar.length} sayfa · ${eslesmeyen} tanesinin listede karşılığı yok`;

      document.getElementById('kesif-liste').innerHTML = adaylar.map(a => {
        const gun = (a.ilk_gorulme || '').slice(0, 10);
        const iliski = a.iliskili
          ? `<span class="kesif-iliski">Sitede ilgili kayıt var: ${escapeHtml(a.iliskili.baslik)}</span>`
          : '';
        return `<li class="kesif-oge${a.iliskili ? ' kesif-oge-iliskili' : ''}">
          <a href="${guvenliUrl(a.url)}" target="_blank" rel="noopener">${escapeHtml(a.baslik)}</a>
          <span class="kesif-meta">${escapeHtml(a.tur)} · ${escapeHtml(a.kaynak || '')}${gun ? ' · ilk görülme: ' + escapeHtml(gun) : ''}</span>
          ${iliski}
        </li>`;
      }).join('');
      document.getElementById('kesif').hidden = false;
    })
    .catch(err => console.warn('Tarama verisi yüklenemedi:', err));
}

fetch('data/calls.json?_=' + Date.now())
  .then(res => res.json())
  .then(data => {
    state.data = data;
    populateTemaFilter(data.calls);
    renderAlertBanner();
    renderCards();
    const label = document.getElementById('last-checked-label');
    label.textContent = `veri kontrolü: ${relativeTime(data.last_checked)}`;
    loadKesif(data.calls);
    fetch('data/kaynak_izleme.json?_=' + Date.now())
      .then(r => r.ok ? r.json() : null)
      .then(iz => { if (iz && iz.kayitlar){ state.izleme = iz.kayitlar; renderCards(); } })
      .catch(() => {});
  })
  .catch(err => {
    grid.innerHTML = '<p class="empty-state">Veri yüklenemedi. Lütfen sayfayı yenileyin.</p>';
    console.error(err);
  });
