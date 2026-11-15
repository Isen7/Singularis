const targets = {
  wise: {
    name: 'WISE 0855', ra: 133.795129, dec: -7.245147, detector: 'SPHEREx D2', nativePixels: [59, 59],
    note: 'These real SPHEREx DR1 frames demonstrate time comparison. The fixed marker has not been adjusted for WISE 0855’s large proper motion and parallax, and the target has not been identified in both frames. No target motion or brightness change is established.',
    observations: [
      { date: '2025-05-06 10:41 UTC', shortDate: '2025-05-06', timeline: '2025 MAY', id: '2025W19_1B_0231_1', wavelength: '1.280 µm', image: './wise0855-may.png?v=2', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=133.795129&dec=-7.245147&size=0.1&path=spherex/dr1/level2/2025W19_1B/l2b-v27-2026-197/2/level2_2025W19_1B_0231_1D2_spx_l2b-v27-2026-197.fits' },
      { date: '2025-11-07 18:49 UTC', shortDate: '2025-11-07', timeline: '2025 NOV', id: '2025W45_2A_0278_2', wavelength: '1.285 µm', image: './wise0855-nov.png?v=2', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=133.795129&dec=-7.245147&size=0.1&path=spherex/dr1/level2/2025W45_2A/l2b-v27-2026-247/2/level2_2025W45_2A_0278_2D2_spx_l2b-v27-2026-247.fits' },
    ],
  },
  rwaur: {
    name: 'RW Aurigae', ra: 76.95625, dec: 30.401417, detector: 'SPHEREx D1', nativePixels: [58, 59],
    note: 'These real SPHEREx DR1 frames have similar target-position wavelengths (0.85865 and 0.85822 µm). The target core carries the OVERFLOW quality flag in both observations; the first also carries BLOOM. Direct core brightness comparison is unreliable, so variability is not established.',
    observations: [
      { date: '2025-09-03 17:22 UTC', shortDate: '2025-09-03', timeline: '2025 SEP', id: '2025W36_1A_0606_1', wavelength: '0.859 µm', image: './rwaur-sep.png?v=2', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=76.95625&dec=30.401417&size=0.1&path=spherex/dr1/level2/2025W36_1A/l2b-v27-2026-232/1/level2_2025W36_1A_0606_1D1_spx_l2b-v27-2026-232.fits' },
      { date: '2026-03-04 07:54 UTC', shortDate: '2026-03-04', timeline: '2026 MAR', id: '2026W10_1A_0445_1', wavelength: '0.858 µm', image: './rwaur-mar.png?v=2', source: 'https://irsa.ipac.caltech.edu/ibe/cutout?ra=76.95625&dec=30.401417&size=0.1&path=spherex/dr1/level2/2026W10_1A/l2b-v27-2026-229/1/level2_2026W10_1A_0445_1D1_spx_l2b-v27-2026-229.fits' },
    ],
  },
};

const API_BASE = window.SINGULARIS_API_BASE || '';
const $ = (id) => document.getElementById(id);
let targetKey = 'wise';
let frame = 0;
let timer = null;
let comparing = false;
let showingDifference = false;
let skyMap = null;
let skyFootprint = null;
let mapLoading = false;
const current = () => targets[targetKey];

function mapPosition(ra, dec) {
  if (!skyMap) return;
  skyMap.gotoRaDec(ra, dec);
  skyFootprint.removeAll();
  skyFootprint.add(window.A.circle(ra, dec, 0.05));
}

function loadSkyMap() {
  if (skyMap || mapLoading) return;
  mapLoading = true;
  $('sky-map-status').textContent = 'Loading the CDS background sky survey…';
  const script = document.createElement('script');
  script.src = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js';
  script.async = true;
  script.onerror = () => {
    mapLoading = false;
    $('sky-map-status').textContent = 'Sky Map is unavailable. The SPHEREx viewer remains ready.';
  };
  script.onload = async () => {
    try {
      await Promise.race([
        window.A.init,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Map initialization timed out.')), 12000)),
      ]);
      const ra = Number($('ra').value);
      const dec = Number($('dec').value);
      skyMap = window.A.aladin('#sky-map', { target: `${ra} ${dec}`, fov: 0.3, cooFrame: 'ICRSd', survey: 'P/DSS2/color' });
      skyFootprint = window.A.graphicOverlay({ color: '#ebde2d', lineWidth: 2 });
      skyMap.addOverlay(skyFootprint);
      skyFootprint.add(window.A.circle(ra, dec, 0.05));
      skyMap.on('positionChanged', ({ ra: centerRa, dec: centerDec }) => {
        if (!Number.isFinite(centerRa) || !Number.isFinite(centerDec)) return;
        $('ra').value = centerRa.toFixed(6);
        $('dec').value = centerDec.toFixed(6);
      });
      $('sky-map-status').textContent = 'CDS background survey loaded. Pan the map or change the coordinate fields.';
    } catch (error) {
      $('sky-map-status').textContent = 'Sky Map is unavailable. The SPHEREx viewer remains ready.';
    } finally {
      mapLoading = false;
    }
  };
  document.head.appendChild(script);
}

function showFrame(index) {
  frame = (index + current().observations.length) % current().observations.length;
  const item = current().observations[frame];
  $('frame-image').src = item.image;
  $('frame-image').alt = `SPHEREx observation of the ${current().name} field on ${item.shortDate}`;
  $('frame-slider').value = String(frame);
  $('frame-index').textContent = `${frame + 1} / ${current().observations.length}`;
  $('source-current').href = item.source;
  if (!comparing && !showingDifference) {
    $('observation-date').textContent = item.date;
    $('wavelength').textContent = item.wavelength;
    const version = item.processingVersion || item.source.match(/\/(l2b-v[^/]+)\//)?.[1];
    $('obs-id').textContent = [item.id, item.collection, version].filter(Boolean).join(' · ');
    $('interpretation-text').textContent = current().note + (Number.isFinite(item.maskedFraction)
      ? ` This frame masks ${(item.maskedFraction * 100).toFixed(1)}% of cutout pixels based on quality flags.` : '')
      + (item.targetMasked ? ' The pixel at the input coordinate has an unusable quality flag.' : '')
      + (Number.isFinite(item.usableFraction) ? ` ${(item.usableFraction * 100).toFixed(1)}% of the aligned image has usable coverage.` : '');
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
  showingDifference = mode === 'difference' && Boolean(current().difference);
  stopPlayback();
  $('mode-play').classList.toggle('active', !comparing && !showingDifference);
  $('mode-compare').classList.toggle('active', comparing);
  $('mode-difference').classList.toggle('active', showingDifference);
  $('mode-play').setAttribute('aria-pressed', String(!comparing && !showingDifference));
  $('mode-compare').setAttribute('aria-pressed', String(comparing));
  $('mode-difference').setAttribute('aria-pressed', String(showingDifference));
  $('callout-text').textContent = showingDifference
    ? 'Yellow in the difference image marks invalid overlap. A residual is not a confirmed detection.'
    : 'The yellow cross marks the input coordinate; it is not a confirmed detection.';
  $('frame-stage').hidden = comparing;
  $('player-controls').hidden = comparing || showingDifference;
  $('compare-stage').hidden = !comparing;
  $('compare-controls').hidden = !comparing;
  if (comparing || showingDifference) {
    const endpoints = [current().observations[0], current().observations.at(-1)];
    $('observation-date').textContent = endpoints.map((item) => item.shortDate).join(' / ');
    $('wavelength').textContent = endpoints.map((item) => item.wavelength).join(' / ');
    $('obs-id').textContent = showingDifference ? 'Preliminary difference' : `${current().observations.length} observations`;
    $('interpretation-text').textContent = showingDifference
      ? `${current().note} Difference display: white means later brighter, black means earlier brighter, mid-gray means little change, and yellow marks invalid overlap. Background was subtracted; differing point-spread functions and alignment errors can still create residuals. This is not a confirmed detection.`
      : current().note;
    if (showingDifference) {
      $('frame-image').src = current().difference;
      $('frame-image').alt = `Preliminary difference between ${endpoints[0].shortDate} and ${endpoints[1].shortDate}`;
    }
  } else showFrame(frame);
}

function selectTarget(key) {
  targetKey = key;
  const target = current();
  const last = target.observations.length - 1;
  $('ra').value = target.ra;
  $('dec').value = target.dec;
  mapPosition(target.ra, target.dec);
  $('target-name').textContent = `${target.name} field`;
  $('detector-name').textContent = target.detector;
  $('resolution-note').textContent = `Native SPHEREx cutout: ${target.nativePixels[0]} × ${target.nativePixels[1]} pixels, enlarged for viewing. Smoothing does not add detail.`;
  $('dataset-name').textContent = target.dataset || 'DR1';
  $('stage-title').textContent = `${target.name} · ${target.observations.length} observations`;
  $('frame-count').textContent = String(target.observations.length);
  $('frame-slider').max = String(last);
  $('mode-difference').disabled = !target.difference;
  $('interpretation-text').textContent = target.note;
  $('compare-earlier-image').src = target.observations[0].image;
  $('compare-later-image').src = target.observations[last].image;
  $('timeline-earlier').textContent = target.observations[0].timeline;
  $('timeline-later').textContent = target.observations[last].timeline;
  $('compare-earlier').textContent = target.observations[0].shortDate;
  $('compare-later').textContent = target.observations[last].shortDate;
  $('source-earlier').href = target.observations[0].source;
  $('source-later').href = target.observations[last].source;
  for (const candidate of ['wise', 'rwaur']) {
    const button = $(`target-${candidate}`);
    button.classList.toggle('active', candidate === key);
    button.setAttribute('aria-pressed', String(candidate === key));
  }
  frame = 0;
  setMode('play');
  $('search-status').classList.remove('error');
  $('search-status').textContent = `Loaded ${target.observations.length} real observations of ${target.name}.`;
}

$('prev').addEventListener('click', () => showFrame(frame - 1));
$('next').addEventListener('click', () => showFrame(frame + 1));
$('frame-slider').addEventListener('input', (event) => showFrame(Number(event.target.value)));
$('play').addEventListener('click', () => {
  if (timer !== null) { stopPlayback(); return; }
  timer = setInterval(() => showFrame(frame + 1), Number($('playback-speed').value));
  $('play').innerHTML = 'Ⅱ <span>Pause</span>';
  $('play').setAttribute('aria-label', 'Pause');
});
$('playback-speed').addEventListener('change', () => {
  if (timer === null) return;
  clearInterval(timer);
  timer = setInterval(() => showFrame(frame + 1), Number($('playback-speed').value));
});
$('mode-play').addEventListener('click', () => setMode('play'));
$('mode-compare').addEventListener('click', () => setMode('compare'));
$('mode-difference').addEventListener('click', () => setMode('difference'));
$('target-wise').addEventListener('click', () => selectTarget('wise'));
$('target-rwaur').addEventListener('click', () => selectTarget('rwaur'));
$('sky-map-panel').addEventListener('toggle', () => {
  if ($('sky-map-panel').open) loadSkyMap();
});
$('map-search').addEventListener('click', () => $('coordinate-form').requestSubmit());
for (const id of ['ra', 'dec']) $(id).addEventListener('change', () => {
  const ra = Number($('ra').value);
  const dec = Number($('dec').value);
  if (Number.isFinite(ra) && Number.isFinite(dec) && ra >= 0 && ra < 360 && dec >= -90 && dec <= 90) mapPosition(ra, dec);
});
$('compare-slider').addEventListener('input', (event) => {
  const percent = Number(event.target.value);
  $('top-layer').style.clipPath = `inset(0 ${100 - percent}% 0 0)`;
  $('comparison-line').style.left = `${percent}%`;
});

$('coordinate-form').addEventListener('submit', async (event) => {
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
  if (match) { selectTarget(match); return; }
  if (!API_BASE) {
    status.textContent = 'Live archive search is temporarily unavailable. Try one of the prepared fields.';
    status.classList.add('error');
    return;
  }
  const submit = $('coordinate-form').querySelector('button[type="submit"]');
  submit.disabled = true;
  status.textContent = 'Searching the SPHEREx archive and preparing aligned observations. This may take a minute.';
  try {
    const response = await fetch(`${API_BASE}/api/search?ra=${encodeURIComponent(ra)}&dec=${encodeURIComponent(dec)}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Archive search failed.');
    if (!Array.isArray(result.frames) || result.frames.length < 2) throw new Error('Too few usable observations were returned.');
    const name = `${ra.toFixed(5)}°, ${dec.toFixed(5)}°`;
    targets.live = {
      name, ra, dec, detector: result.detector.replace('-', ' '), nativePixels: result.native_pixels,
      dataset: [...new Set(result.frames.map((item) => item.collection.replace('spherex_', '').toUpperCase()))].join(' / '),
      note: result.warning,
      difference: result.difference,
      observations: result.frames.map((item, index) => ({
        date: `${item.date.replace('T', ' ').slice(0, 16)} UTC`,
        shortDate: item.date.slice(0, 10),
        timeline: item.date.slice(0, 7),
        id: item.observation_id || `Archive frame ${index + 1}`,
        collection: item.collection?.replace('spherex_', '').toUpperCase(),
        processingVersion: item.processing_version,
        wavelength: Number.isFinite(item.wavelength_um) ? `${item.wavelength_um.toFixed(3)} µm` : 'Not available',
        maskedFraction: item.masked_fraction,
        usableFraction: item.usable_fraction,
        targetMasked: item.target_masked,
        image: item.image,
        source: item.source,
      })),
    };
    selectTarget('live');
    status.textContent = `Loaded ${result.frames.length} SPHEREx archive observations for these coordinates.`;
  } catch (error) {
    status.textContent = error.message || 'The archive could not be reached. Try again later.';
    status.classList.add('error');
  } finally {
    submit.disabled = false;
  }
});

document.addEventListener('keydown', (event) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  if ($('frame-stage').hidden) return;
  if (event.key === 'ArrowRight') showFrame(frame + 1);
  if (event.key === 'ArrowLeft') showFrame(frame - 1);
});

selectTarget('wise');
