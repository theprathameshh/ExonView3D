import './style.css';
import 'molstar/build/viewer/molstar.css';

import { Viewer } from 'molstar/lib/apps/viewer/app.js';
import { MolScriptBuilder as MS } from 'molstar/lib/mol-script/language/builder.js';
import { Script } from 'molstar/lib/mol-script/script.js';
import { StructureSelection } from 'molstar/lib/mol-model/structure/query/selection.js';
import { StructureElement, StructureProperties } from 'molstar/lib/mol-model/structure/structure.js';
import { Color } from 'molstar/lib/mol-util/color/color.js';

const $ = (id) => document.getElementById(id);

/* ---------- small DOM helpers (all text via textContent: no HTML injection) ---------- */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key === 'style') Object.assign(node.style, value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}
const link = (href, text) => el('a', { href, target: '_blank', rel: 'noopener noreferrer' }, text);
const row = (dl, label, value) => {
  if (value === null || value === undefined || value === '') return;
  dl.append(el('dt', {}, label), el('dd', {}, value));
};

/* ---------- notices ---------- */
function notice(kind, message, hint) {
  const box = $('notice');
  if (!message) { box.hidden = true; return; }
  box.className = kind;
  box.replaceChildren(message, hint ? el('span', { class: 'hint' }, hint) : '');
  box.hidden = false;
}

async function api(path) {
  let response;
  try {
    response = await fetch(path);
  } catch (e) {
    throw { message: 'Cannot reach the ExonView3D server.', hint: 'Is "exonview3d serve" still running?' };
  }
  let data = null;
  try { data = await response.json(); } catch (e) { /* non-JSON */ }
  if (!response.ok) {
    throw (data && data.error) || { message: `Request failed (HTTP ${response.status}).` };
  }
  return data;
}

/* ---------- state ---------- */
const state = { gene: null, geneToken: 0, txToken: 0, detail: null, activeExon: null, onlyWithStructure: false, scene: null };
let viewerPromise = null;

function getViewer() {
  if (!viewerPromise) {
    viewerPromise = Viewer.create('viewer', {
      layoutIsExpanded: false, layoutShowControls: false, layoutShowRemoteState: false,
      layoutShowSequence: false, layoutShowLog: false, layoutShowLeftPanel: false,
      collapseLeftPanel: true, collapseRightPanel: true,
      viewportShowExpand: false, viewportShowSelectionMode: false, viewportShowAnimation: false,
      viewportShowSettings: false, viewportShowTrajectoryControls: false,
      volumeStreamingDisabled: true, extensions: [], viewportBackgroundColor: '#ffffff',
    }).then((viewer) => { window.exonViewer = viewer; subscribeHover(viewer); return viewer; });
  }
  return viewerPromise;
}

function viewerMessage(title, text) {
  const box = $('viewer-message');
  if (!title) { box.classList.remove('show'); return; }
  box.replaceChildren(el('div', {}, el('strong', {}, title), text || ''));
  box.classList.add('show');
}

/* ---------- gene search ---------- */
async function searchGene(rawId, preselect) {
  const id = String(rawId || '').trim();
  const token = ++state.geneToken;
  notice(null);
  resetTranscript();
  $('transcript-panel').hidden = true;
  $('gene-panel').replaceChildren(el('h2', {}, 'Gene'), el('div', { class: 'empty' }, 'Searching…'));
  try {
    const data = await api(`/api/gene/${encodeURIComponent(id)}`);
    if (token !== state.geneToken) return;
    state.gene = data;
    $('gene-input').value = String(data.gene.gene_id);
    renderGene(data);
    renderTranscripts(data);
    const target = data.transcripts.find((t) => t.transcript_id === preselect)
      || data.transcripts.find((t) => t.structure_available) || data.transcripts[0];
    if (target) selectTranscript(target.transcript_id);
  } catch (e) {
    if (token !== state.geneToken) return;
    state.gene = null;
    $('gene-panel').replaceChildren(el('h2', {}, 'Gene'), el('div', { class: 'empty' }, 'No gene loaded.'));
    notice('error', e.message, e.hint);
    viewerMessage('No structure loaded', 'Search for a gene and choose a transcript.');
  }
}

function renderGene(data) {
  const g = data.gene;
  const dl = el('dl', { class: 'kv' });
  row(dl, 'Symbol', g.symbol);
  row(dl, 'Name', g.description);
  row(dl, 'NCBI Gene ID', link(`https://www.ncbi.nlm.nih.gov/gene/${g.gene_id}`, String(g.gene_id)));
  row(dl, 'Organism', g.organism);
  row(dl, 'Transcripts', `${data.summary.transcripts} (${data.summary.with_structure} with AlphaFold structure)`);
  $('gene-panel').replaceChildren(el('h2', {}, 'Gene'), dl);
}

function renderTranscripts(data) {
  const panel = $('transcript-panel');
  const list = el('div', { id: 'transcript-list' });
  const draw = () => {
    list.replaceChildren();
    for (const t of data.transcripts) {
      if (state.onlyWithStructure && !t.structure_available) continue;
      const badge = el('span', {
        class: 'badge' + (t.structure_available ? ' ok' : ''), title: t.alphafold.message,
      }, t.structure_available ? 'AlphaFold ✓' : 'No structure');
      list.append(el('button', {
        type: 'button', class: 'tx', dataset: { tid: t.transcript_id },
        'aria-pressed': String(state.detail && state.detail.transcript.transcript_id === t.transcript_id),
        onclick: () => selectTranscript(t.transcript_id),
      }, el('span', {}, el('span', { class: 'mono' }, t.transcript_id),
        el('small', {}, [t.protein_length != null ? `${t.protein_length} aa` : null,
          t.number_of_exons != null ? `${t.number_of_exons} exons` : null, t.uniprot_id].filter(Boolean).join(' · '))), badge));
    }
    if (!list.children.length) list.append(el('div', { class: 'empty' }, 'No transcripts match.'));
  };
  state.redrawTranscripts = draw;
  const filter = el('label', { class: 'filter' },
    el('input', { type: 'checkbox', onchange: (ev) => { state.onlyWithStructure = ev.target.checked; draw(); } }),
    ' Only transcripts with an AlphaFold structure');
  panel.replaceChildren(el('h2', {}, 'Transcripts'), filter, list);
  panel.hidden = false;
  draw();
}

/* ---------- transcript selection ---------- */
function resetTranscript() {
  state.detail = null; state.activeExon = null; state.scene = null;
  $('info-panel').hidden = true; $('exon-panel').hidden = true;
}

async function selectTranscript(transcriptId) {
  const token = ++state.txToken;
  const gid = state.gene.gene.gene_id;
  notice(null);
  resetTranscript();
  document.querySelectorAll('.tx').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.tid === transcriptId)));
  history.replaceState(null, '', `?gene=${gid}&transcript=${encodeURIComponent(transcriptId)}`);
  viewerMessage('Loading…', 'Retrieving exon annotation and structure.');
  try {
    const detail = await api(`/api/gene/${gid}/transcript/${encodeURIComponent(transcriptId)}`);
    if (token !== state.txToken) return;
    state.detail = detail;
    renderInfo(detail);
    renderExons(detail);
    await showStructure(detail, token);
  } catch (e) {
    if (token !== state.txToken) return;
    notice('error', e.message, e.hint);
    viewerMessage('Transcript could not be loaded', e.message);
  }
}

function renderInfo(d) {
  const panel = $('info-panel');
  const tx = el('dl', { class: 'kv' });
  row(tx, 'Transcript', link(`https://www.ncbi.nlm.nih.gov/protein/${d.transcript.transcript_id}`, d.transcript.transcript_id));
  row(tx, 'Protein', d.protein.name);
  row(tx, 'Length', `${d.protein.length} aa`);
  row(tx, 'Coding exons', d.transcript.number_of_exons);
  const u = d.uniprot;
  if (u.accession) {
    row(tx, 'UniProt', [link(u.url, u.accession), ` (${u.source})`]);
    const v = u.validation || {};
    const text = { identical: 'sequence identical to UniProt', different: `differs from UniProt (${v.number_of_mismatches ?? '?'} mismatches)`,
      unavailable: 'UniProt sequence not available' }[v.status];
    row(tx, 'Sequence check', text);
  } else {
    row(tx, 'UniProt', 'No accession available');
  }
  if (d.protein.mean_plddt != null) row(tx, 'Mean pLDDT', d.protein.mean_plddt);
  const s = d.structure;
  const st = el('dl', { class: 'kv' });
  if (s.status === 'available') {
    row(st, 'AlphaFold model', [link(`https://alphafold.ebi.ac.uk/entry/${s.accession}`, s.model_id), ` (v${s.model_version})`]);
    row(st, 'Chain', s.chain_id);
    row(st, 'Sequence identity', `${s.sequence_identity_percent}%`);
    row(st, 'Mapping coverage', `${d.mapping.mapped_residues}/${d.mapping.protein_length} residues (${d.mapping.coverage_percent}%)`);
  } else {
    row(st, 'AlphaFold', s.message);
  }
  panel.replaceChildren(el('h2', {}, 'Transcript, protein and structure'), tx, el('hr'), st,
    el('details', {}, el('summary', {}, 'Protein sequence'), el('pre', { class: 'mono seq' }, d.protein.sequence)));
  panel.hidden = false;
}

function genomicText(g) {
  if (!g) return null;
  const pair = (a, b) => (a != null && b != null ? `${a}–${b}` : null);
  const coding = pair(g.coding_start, g.coding_end);
  const raw = pair(g.raw_start, g.raw_end);
  return [coding && `coding ${coding}`, raw && `exon ${raw}`].filter(Boolean).join(' · ') || null;
}

function renderExons(d) {
  const panel = $('exon-panel');
  const total = d.protein.length;
  const track = el('div', { id: 'track', role: 'group', 'aria-label': 'Exon map along the protein' });
  const list = el('div', { id: 'exon-list' });
  d.exons.forEach((exon, i) => {
    track.append(el('button', {
      type: 'button', style: { background: exon.colour, flex: `${exon.protein_length} 0 0` },
      dataset: { exon: i }, title: `${exon.exon_id}: ${exon.protein_start}–${exon.protein_end}`,
      'aria-label': `Exon ${exon.exon_id}`, onclick: () => selectExon(i, true),
    }));
    const mapped = exon.coverage_percent != null;
    const structText = !mapped ? 'no structure mapping'
      : `structure ${exon.structure_residue_segments.map((s) => `${s.start}–${s.end}`).join(', ') || '-'} · coverage ${exon.coverage_percent}%`;
    const card = el('div', {
      class: 'exon-card' + (mapped ? '' : ' nomap'), role: 'button', tabindex: '0', 'aria-pressed': 'false',
      style: { borderLeftColor: exon.colour, color: exon.colour }, dataset: { exon: i },
      onclick: () => selectExon(i, true),
      onkeydown: (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); selectExon(i, true); } },
      onmouseenter: () => highlightExon(i, true), onmouseleave: () => highlightExon(i, false),
    },
    el('strong', { style: { color: '#1c2430' } }, exon.exon_id),
    el('div', { class: 'meta', style: { color: '#5d6b7c' } }, `protein ${exon.protein_start}–${exon.protein_end} · ${exon.protein_length} aa`),
    el('div', { class: 'meta', style: { color: '#5d6b7c' } }, structText),
    genomicText(exon.genomic) ? el('div', { class: 'meta', style: { color: '#5d6b7c' } }, genomicText(exon.genomic)) : null);
    list.append(card);
  });
  const toolbar = el('div', { class: 'toolbar' },
    el('button', { type: 'button', onclick: () => clearExon(true) }, 'Clear selection / reset view'));
  panel.replaceChildren(el('h2', {}, `Exons (${d.exons.length})`), toolbar, track, list);
  panel.hidden = false;
}

/* ---------- Mol* scene ---------- */
function exonExpression(exon) {
  const groups = exon.structure_residue_segments.map((seg) => MS.struct.generator.atomGroups({
    'chain-test': MS.core.rel.eq([MS.struct.atomProperty.macromolecular.auth_asym_id(), seg.chain_id]),
    'residue-test': MS.core.rel.inRange([MS.struct.atomProperty.macromolecular.auth_seq_id(), seg.start, seg.end]),
  }));
  return groups.length ? (groups.length === 1 ? groups[0] : MS.struct.combinator.merge(groups)) : null;
}

async function showStructure(d, token) {
  const s = d.structure;
  const viewer = await getViewer();
  if (token !== state.txToken) return;
  const plugin = viewer.plugin;
  await plugin.clear();
  state.scene = null;
  if (s.status !== 'available') {
    viewerMessage('No 3D structure for this transcript', s.message);
    return;
  }
  try {
    const data = await plugin.builders.data.download({ url: s.url, isBinary: false, label: s.model_id }, { state: { isGhost: true } });
    const trajectory = await plugin.builders.structure.parseTrajectory(data, 'mmcif');
    const model = await plugin.builders.structure.createModel(trajectory);
    const structure = await plugin.builders.structure.createStructure(model);
    await plugin.dataTransaction(async () => {
      for (const exon of d.exons) {
        const expression = exonExpression(exon);
        if (!expression) continue;
        const component = await plugin.builders.structure.tryCreateComponentFromExpression(
          structure, expression, `exon-${exon.index}`, { label: exon.exon_id });
        if (!component) continue;
        await plugin.builders.structure.representation.addRepresentation(component, {
          type: 'cartoon', color: 'uniform', colorParams: { value: Color.fromHexStyle(exon.colour) },
        });
      }
    });
    if (token !== state.txToken) return;
    // Lookup used by the hover handler: chain -> sorted list of [start, end, exonIndex].
    const lookup = new Map();
    d.exons.forEach((exon, i) => exon.structure_residue_segments.forEach((seg) => {
      if (!lookup.has(seg.chain_id)) lookup.set(seg.chain_id, []);
      lookup.get(seg.chain_id).push([seg.start, seg.end, i]);
    }));
    state.scene = { structure, lookup, loci: new Map() };
    viewerMessage(null);
  } catch (e) {
    console.error(e);
    viewerMessage('The structure could not be displayed', String(e && e.message ? e.message : e));
  }
}

function exonLoci(i) {
  const scene = state.scene;
  if (!scene) return null;
  if (!scene.loci.has(i)) {
    const expression = exonExpression(state.detail.exons[i]);
    const data = scene.structure.data;
    if (!expression || !data) return null;
    const selection = Script.getStructureSelection(expression, data);
    scene.loci.set(i, StructureSelection.toLociWithSourceUnits(selection));
  }
  return scene.loci.get(i);
}

async function highlightExon(i, on) {
  document.querySelectorAll('#track button').forEach((b) => b.classList.toggle('hover', on && Number(b.dataset.exon) === i));
  if (!state.scene) return;
  const viewer = await getViewer();
  const manager = viewer.plugin.managers.interactivity.lociHighlights;
  if (!on) { manager.clearHighlights(); return; }
  const loci = exonLoci(i);
  if (loci) manager.highlightOnly({ loci });
}

async function selectExon(i, focus) {
  state.activeExon = i;
  document.querySelectorAll('.exon-card').forEach((c) => {
    const active = Number(c.dataset.exon) === i;
    c.classList.toggle('active', active);
    c.setAttribute('aria-pressed', String(active));
  });
  document.querySelectorAll('#track button').forEach((b) => b.classList.toggle('active', Number(b.dataset.exon) === i));
  const card = document.querySelector(`.exon-card[data-exon="${i}"]`);
  if (card) card.scrollIntoView({ block: 'nearest' });
  if (!state.scene) return;
  const loci = exonLoci(i);
  if (!loci) { notice('info', `Exon ${state.detail.exons[i].exon_id} has no mapped region in this structure.`); return; }
  const viewer = await getViewer();
  const plugin = viewer.plugin;
  plugin.managers.interactivity.lociSelects.selectOnly({ loci });
  if (focus) plugin.managers.camera.focusLoci(loci);
}

async function clearExon(resetCamera) {
  state.activeExon = null;
  document.querySelectorAll('.exon-card.active').forEach((c) => { c.classList.remove('active'); c.setAttribute('aria-pressed', 'false'); });
  document.querySelectorAll('#track button.active').forEach((b) => b.classList.remove('active'));
  if (!state.scene) return;
  const viewer = await getViewer();
  viewer.plugin.managers.interactivity.lociSelects.deselectAll();
  if (resetCamera) viewer.plugin.managers.camera.reset();
}

/* ---------- hover over the structure -> identify the exon ---------- */
function subscribeHover(viewer) {
  viewer.plugin.behaviors.interaction.hover.subscribe(({ current }) => {
    const tip = $('hover-tip');
    document.querySelectorAll('.exon-card.structure-hover').forEach((c) => c.classList.remove('structure-hover'));
    document.querySelectorAll('#track button.hover').forEach((b) => b.classList.remove('hover'));
    const loci = current && current.loci;
    if (!state.scene || !loci || !StructureElement.Loci.is(loci) || StructureElement.Loci.isEmpty(loci)) {
      tip.style.display = 'none';
      return;
    }
    const loc = StructureElement.Loci.getFirstLocation(loci);
    if (!loc) { tip.style.display = 'none'; return; }
    const chain = StructureProperties.chain.auth_asym_id(loc);
    const seq = StructureProperties.residue.auth_seq_id(loc);
    const comp = StructureProperties.atom.label_comp_id(loc);
    const hit = (state.scene.lookup.get(chain) || []).find(([a, b]) => seq >= a && seq <= b);
    if (!hit) { tip.style.display = 'none'; return; }
    const exon = state.detail.exons[hit[2]];
    tip.textContent = `${comp} ${seq} (chain ${chain}) · exon ${exon.exon_id} · protein ${exon.protein_start}–${exon.protein_end}`;
    tip.style.display = 'block';
    const card = document.querySelector(`.exon-card[data-exon="${hit[2]}"]`);
    if (card) { card.classList.add('structure-hover'); card.scrollIntoView({ block: 'nearest' }); }
    const seg = document.querySelector(`#track button[data-exon="${hit[2]}"]`);
    if (seg) seg.classList.add('hover');
  });
}

/* ---------- wiring ---------- */
$('gene-form').addEventListener('submit', (ev) => { ev.preventDefault(); searchGene($('gene-input').value); });
document.querySelectorAll('.chip[data-gene]').forEach((b) => b.addEventListener('click', () => {
  $('gene-input').value = b.dataset.gene; searchGene(b.dataset.gene);
}));

const params = new URLSearchParams(location.search);
if (params.get('gene')) {
  $('gene-input').value = params.get('gene');
  searchGene(params.get('gene'), params.get('transcript'));
}
getViewer().catch((e) => notice('error', 'The 3D viewer could not start: ' + (e && e.message ? e.message : e),
  'Your browser may not support WebGL.'));
