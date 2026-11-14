const targets = {
  wise: {
    name: 'WISE 0855', ra: 133.795129, dec: -7.245147, detector: 'SPHEREx D2',
    note: 'These two frames come from real SPHEREx DR1 data, aligned on the sky and shown with the same brightness scale. They demonstrate a reproducible time-comparison workflow; visual inspection alone cannot confirm motion or brightness change for WISE 0855.',
    observations: [
      { date: '2025-05-06 10:41 UTC', shortDate: '2025-05-06', timeline: '2025 MAY', id: '2025W19_1B_0231_1', wavelength: '1.280 µm', image: './wise0855-may.png', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=133.795129&dec=-7.245147&size=0.1&path=spherex/dr1/level2/2025W19_1B/l2b-v27-2026-197/2/level2_2025W19_1B_0231_1D2_spx_l2b-v27-2026-197.fits' },
      { date: '2025-11-07 18:49 UTC', shortDate: '2025-11-07', timeline: '2025 NOV', id: '2025W45_2A_0278_2', wavelength: '1.285 µm', image: './wise0855-nov.png', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=133.795129&dec=-7.245147&size=0.1&path=spherex/dr1/level2/2025W45_2A/l2b-v27-2026-247/2/level2_2025W45_2A_0278_2D2_spx_l2b-v27-2026-247.fits' },
    ],
  },
  rwaur: {
    name: 'RW Aurigae', ra: 76.95625, dec: 30.401417, detector: 'SPHEREx D1',
    note: 'These two frames come from real SPHEREx DR1 data, with central wavelengths near 0.85865 and 0.85822 µm at the target. The images are sky-aligned and use the same brightness scale. The central source is visible, but quality flags, error propagation, and photometry have not been applied, so brightness change cannot be confirmed.',
    observations: [
      { date: '2025-09-03 17:22 UTC', shortDate: '2025-09-03', timeline: '2025 SEP', id: '2025W36_1A_0606_1', wavelength: '0.859 µm', image: './rwaur-sep.png', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=76.95625&dec=30.401417&size=0.1&path=spherex/dr1/level2/2025W36_1A/l2b-v27-2026-232/1/level2_2025W36_1A_0606_1D1_spx_l2b-v27-2026-232.fits' },
      { date: '2026-03-04 07:54 UTC', shortDate: '2026-03-04', timeline: '2026 MAR', id: '2026W10_1A_0445_1', wavelength: '0.858 µm', image: './rwaur-mar.png', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=76.95625&dec=30.401417&size=0.1&path=spherex/dr1/level2/2026W10_1A/l2b-v27-2026-229/1/level2_2026W10_1A_0445_1D1_spx_l2b-v27-2026-229.fits' },
    ],
  },
};

const $ = (id) => document.getElementById(id);
let targetKey = 'wise';
let frame = 0;
let timer = null;
let comparing = false;
const current = () => targets[targetKey];

function showFrame(index) {
  frame = (index + current().observations.length) % current().observations.length;
  const item = current().observations[frame];
  $('frame-image').src = item.image;
  $('frame-image').alt = `SPHEREx observation of the ${current().name} field on ${item.shortDate}`;
  $('frame-slider').value = String(frame);
  if (!comparing) {
    $('observation-date').textContent = item.date;
    $('wavelength').textContent = item.wavelength;
    $('obs-id').textContent = item.id;
  }
}

function stopPlayback() {
  if (timer !== null) clearInterval(timer);
  timer = null;
  $('play').innerHTML = '▶ <span>Play</span>';
  $('play').setAttribute('aria-label', 'Play');
}

function setMode(mode) {
  comparing = mode === 'compare';
  stopPlayback();
  $('mode-play').classList.toggle('active', !comparing);
  $('mode-compare').classList.toggle('active', comparing);
  $('mode-play').setAttribute('aria-pressed', String(!comparing));
  $('mode-compare').setAttribute('aria-pressed', String(comparing));
  $('frame-stage').hidden = comparing;
  $('player-controls').hidden = comparing;
  $('compare-stage').hidden = !comparing;
  $('compare-controls').hidden = !comparing;
  if (comparing) {
    $('observation-date').textContent = current().observations.map((item) => item.shortDate).join(' / ');
    $('wavelength').textContent = current().observations.map((item) => item.wavelength).join(' / ');
    $('obs-id').textContent = 'Two observations';
  } else showFrame(frame);
}

function selectTarget(key) {
  targetKey = key;
  const target = current();
  $('ra').value = target.ra;
  $('dec').value = target.dec;
  $('target-name').textContent = `${target.name} field`;
  $('detector-name').textContent = target.detector;
  $('stage-title').textContent = `${target.name} · Two observations`;
  $('interpretation-text').textContent = target.note;
  $('compare-earlier-image').src = target.observations[0].image;
  $('compare-later-image').src = target.observations[1].image;
  $('timeline-earlier').textContent = target.observations[0].timeline;
  $('timeline-later').textContent = target.observations[1].timeline;
  $('compare-earlier').textContent = target.observations[0].shortDate;
  $('compare-later').textContent = target.observations[1].shortDate;
  $('source-earlier').href = target.observations[0].source;
  $('source-later').href = target.observations[1].source;
  for (const candidate of Object.keys(targets)) {
    const button = $(`target-${candidate}`);
    button.classList.toggle('active', candidate === key);
    button.setAttribute('aria-pressed', String(candidate === key));
  }
  frame = 0;
  setMode('play');
  $('search-status').classList.remove('error');
  $('search-status').textContent = `Loaded two real observations of ${target.name}.`;
}

$('prev').addEventListener('click', () => showFrame(frame - 1));
$('next').addEventListener('click', () => showFrame(frame + 1));
$('frame-slider').addEventListener('input', (event) => showFrame(Number(event.target.value)));
$('play').addEventListener('click', () => {
  if (timer !== null) { stopPlayback(); return; }
  timer = setInterval(() => showFrame(frame + 1), 900);
  $('play').innerHTML = 'Ⅱ <span>Pause</span>';
  $('play').setAttribute('aria-label', 'Pause');
});
$('mode-play').addEventListener('click', () => setMode('play'));
$('mode-compare').addEventListener('click', () => setMode('compare'));
$('target-wise').addEventListener('click', () => selectTarget('wise'));
$('target-rwaur').addEventListener('click', () => selectTarget('rwaur'));
$('compare-slider').addEventListener('input', (event) => {
  const percent = Number(event.target.value);
  $('top-layer').style.clipPath = `inset(0 ${100 - percent}% 0 0)`;
  $('comparison-line').style.left = `${percent}%`;
});

$('coordinate-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const ra = Number($('ra').value);
  const dec = Number($('dec').value);
  const status = $('search-status');
  status.classList.remove('error');
  if (!Number.isFinite(ra) || !Number.isFinite(dec) || ra < 0 || ra >= 360 || dec < -90 || dec > 90) {
    status.textContent = 'Enter valid coordinates: RA must be 0–360°, and Dec must be −90–90°.';
    status.classList.add('error');
    return;
  }
  const match = Object.keys(targets).find((key) => Math.abs(ra - targets[key].ra) < 0.001 && Math.abs(dec - targets[key].dec) < 0.001);
  if (match) selectTarget(match);
  else {
    status.textContent = 'This prototype currently includes prepared images for WISE 0855 and RW Aurigae only; no display image is available for these coordinates.';
    status.classList.add('error');
  }
});

document.addEventListener('keydown', (event) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  if ($('frame-stage').hidden) return;
  if (event.key === 'ArrowRight') showFrame(frame + 1);
  if (event.key === 'ArrowLeft') showFrame(frame - 1);
});
