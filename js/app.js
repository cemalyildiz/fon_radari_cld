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

function computeStatus(call){
  const now = new Date();
  if (call.surekli_acik) return 'acik';
  if (!call.basvuru_bitis) return 'acik';
  const end = new Date(call.basvuru_bitis);
  if (now > end) return 'kapali';
  const daysLeft = (end - now) / (1000*60*60*24);
  if (daysLeft <= 14) return 'yakinda-kapaniyor';
  return 'acik';
}

function statusLabel(status, call){
  if (call.surekli_acik) return { text: 'Sürekli Açık', cls: 'badge-surekli' };
  switch(status){
    case 'acik': return { text: 'Açık', cls: 'badge-acik' };
    case 'yakinda-kapaniyor': return { text: 'Yakında Kapanıyor', cls: 'badge-yakinda' };
    case 'kapali': return { text: 'Kapalı / Arşiv', cls: 'badge-kapali' };
    default: return { text: 'Bilinmiyor', cls: '' };
  }
}

function fmtDate(d){
  if (!d) return '—';
  const date = new Date(d);
  return date.toLocaleDateString('tr-TR', { day:'2-digit', month:'short', year:'numeric' });
}

function progressPct(call){
  if (call.surekli_acik || !call.basvuru_baslangic || !call.basvuru_bitis) return null;
  const start = new Date(call.basvuru_baslangic).getTime();
  const end = new Date(call.basvuru_bitis).getTime();
  const now = Date.now();
  if (now <= start) return 0;
  if (now >= end) return 100;
  return Math.round(((now - start) / (end - start)) * 100);
}

function matchesFilters(call){
  if (call.kategori !== state.activeTab) return false;
  const status = computeStatus(call);
  if (state.statusFilter === 'acik-veya-yakinda'){
    if (status !== 'acik' && status !== 'yakinda-kapaniyor') return false;
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
  const calls = state.data.calls.filter(matchesFilters);
  grid.innerHTML = '';
  emptyState.hidden = calls.length !== 0;

  const summary = document.getElementById('result-summary');
  if (state.data){
    const allInTab = state.data.calls.filter(c => c.kategori === state.activeTab);
    const openCount = allInTab.filter(c => computeStatus(c) === 'acik' || computeStatus(c) === 'yakinda-kapaniyor').length;
    const archivedCount = allInTab.filter(c => computeStatus(c) === 'kapali').length;
    if (state.statusFilter === 'kapali'){
      summary.textContent = `Arşivde ${archivedCount} kapalı çağrı gösteriliyor.`;
    } else {
      summary.textContent = `${calls.length} çağrı gösteriliyor (${openCount} açık) — ${archivedCount} kapalı çağrı arşivde. Görmek için Durum filtresinden "Arşiv"i seçin.`;
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
      <div class="card-meta">
        <span><strong>${escapeHtml((call.olcek||[]).join(', '))}</strong></span>
        <span>Bitiş: <strong>${call.surekli_acik ? 'Sürekli' : fmtDate(call.basvuru_bitis)}</strong></span>
        <span>${escapeHtml(call.destek_turu || '')}</span>
      </div>
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
    <a class="detail-link" href="${call.kaynak_url}" target="_blank" rel="noopener">Resmi kaynağa git ↗</a>
  `;
  overlay.hidden = false;
  document.body.style.overflow = 'hidden';
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

fetch('data/calls.json?_=' + Date.now())
  .then(res => res.json())
  .then(data => {
    state.data = data;
    populateTemaFilter(data.calls);
    renderCards();
    const label = document.getElementById('last-checked-label');
    label.textContent = `veri kontrolü: ${relativeTime(data.last_checked)}`;
  })
  .catch(err => {
    grid.innerHTML = '<p class="empty-state">Veri yüklenemedi. Lütfen sayfayı yenileyin.</p>';
    console.error(err);
  });
