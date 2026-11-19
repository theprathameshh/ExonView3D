import './style.css';

import { Viewer } from 'molstar/lib/apps/viewer/app';
import 'molstar/build/viewer/molstar.css';

import { MolScriptBuilder as MS } from 'molstar/lib/mol-script/language/builder';
import { Color } from 'molstar/lib/mol-util/color/color';

import {
  StructureElement,
  StructureProperties
} from 'molstar/lib/mol-model/structure/structure';

const GENE_ID = 7157;
const TRANSCRIPT_ID = 'NP_001119584.1';

const API_URL =
  `/api/genes/${GENE_ID}/transcripts/${TRANSCRIPT_ID}/structure/`;

async function initialiseExonView3D() {
  const geneInfo = document.getElementById('gene-info');
  const transcriptInfo = document.getElementById('transcript-info');
  const exonList = document.getElementById('exon-list');

  try {
    // Initialise Mol* viewer
    const viewer = await Viewer.create('molstar-viewer');
    window.exonViewer = viewer;

    // Retrieve transcript and exon annotations from Django
    const response = await fetch(API_URL);

    if (!response.ok) {
      throw new Error(`Django API returned HTTP ${response.status}`);
    }

    const data = await response.json();
    window.exonViewData = data;
    
    // Display gene information
    geneInfo.textContent =
      `${data.gene.gene_name} (${data.gene.gene_id}) — ${data.gene.organism}`;

    // Display transcript information
    transcriptInfo.textContent =
      `${data.transcript.transcript_id} | ` +
      `UniProt: ${data.transcript.uniprot_id} | ` +
      `${data.transcript.protein_length} amino acids`;

    // Display interactive exon annotations
    exonList.replaceChildren();

    data.exons.forEach((exon, exonIndex) => {
      const item = document.createElement('div');

      item.style.padding = '10px';
      item.style.marginBottom = '8px';
      item.style.borderLeft = `5px solid ${exon.colour}`;
      item.style.background = '#f5f7fa';
      item.style.borderRadius = '4px';
      item.style.cursor = 'pointer';
      item.style.transition = 'background 0.2s, outline 0.2s';

      item.setAttribute('role', 'button');
      item.setAttribute('tabindex', '0');
      
      item.dataset.exonId = exon.exon_id;
      item.classList.add('exon-card');

      const title = document.createElement('strong');
      title.textContent = exon.exon_id;

      const details = document.createElement('p');
      details.style.margin = '5px 0 0';
      details.textContent =
        `Protein positions: ${exon.protein_start}–${exon.protein_end} | ` +
        `Coverage: ${exon.coverage_percent}%`;

      item.append(title, details);

      // Focus this exon in the Mol* viewer
      const focusExon = () => {
        const segments = exon.structure_residue_segments || [];

        if (segments.length === 0) {
          console.warn(`No mapped structure segments for ${exon.exon_id}`);
          return;
        }

        // Focus the first segment (current TP53 data has one segment per exon)
        const segment = segments[0];

        const expression = MS.struct.generator.atomGroups({
          'chain-test': MS.core.rel.eq([
            MS.struct.atomProperty.macromolecular.auth_asym_id(),
            segment.chain_id
          ]),

          'residue-test': MS.core.rel.inRange([
            MS.struct.atomProperty.macromolecular.auth_seq_id(),
            segment.start,
            segment.end
          ])
        });

        viewer.structureInteractivity({
          expression,
          action: 'focus'
        });

        // Update annotation panel selection
        exonList.querySelectorAll('[role="button"]').forEach(card => {
          card.style.background = '#f5f7fa';
          card.style.outline = 'none';
          card.setAttribute('aria-pressed', 'false');
        });

        item.style.background = '#e3eee9';
        item.style.outline = `2px solid ${exon.colour}`;
        item.setAttribute('aria-pressed', 'true');

        console.log(`Focused exon: ${exon.exon_id}`);
      };

      item.addEventListener('click', focusExon);

      item.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          focusExon();
        }
      });

      exonList.appendChild(item);
    });

    // Load AlphaFold CIF structure through Django
    await viewer.loadStructureFromUrl(
      data.structure.url,
      'mmcif',
      false
    );
    
    // Hide the default whole-protein cartoon
    const hierarchy = viewer.plugin.managers.structure.hierarchy.current;

    const defaultRepresentations =
      hierarchy.structures[0].components[0].representations;

    viewer.plugin.managers.structure.hierarchy.toggleVisibility(
      defaultRepresentations,
      'hide'
    );

    console.log('Default cartoon hidden.');
    
    // Get the loaded protein structure
    const structureRef = hierarchy.structures[0];
    
    
    // Detect residues hovered in the Mol* viewer
    viewer.plugin.behaviors.interaction.hover.subscribe(({ current }) => {
    console.log('Hover event:', current?.loci?.kind);
    console.log('Mol* hover event received');
    console.log('Hover current:', current);
    console.log('Inner loci kind:', current?.loci?.kind);

      if (
        !StructureElement.Loci.is(current.loci) ||
        StructureElement.Loci.isEmpty(current.loci)
      ) {
        document.querySelectorAll('.exon-card.structure-hover')
          .forEach(card => card.classList.remove('structure-hover'));
        return;
      }

      const location = StructureElement.Loci.getFirstLocation(current.loci);

      if (!location) return;

      const chainId =
        StructureProperties.chain.auth_asym_id(location);

      const residueNumber =
        StructureProperties.residue.auth_seq_id(location);
        
      console.log('Residue details:', {
        chainId,
        chainType: typeof chainId,
        residueNumber,
        residueType: typeof residueNumber
      });

      const hoveredExon = data.exons.find(exon =>
        (exon.structure_residue_segments || []).some(segment =>
          segment.chain_id === chainId &&
          residueNumber >= segment.start &&
          residueNumber <= segment.end
        )
      );

      // Remove previous temporary highlight
      document.querySelectorAll('.exon-card.structure-hover')
         .forEach(card => card.classList.remove('structure-hover'));

      // Highlight corresponding exon card
      if (hoveredExon) {
        const exonCard = document.querySelector(
          `[data-exon-id="${hoveredExon.exon_id}"]`
        );

        if (exonCard) {
          exonCard.classList.add('structure-hover');
        }
      }

      console.log('3D hover:', {
        chain: chainId,
        residue: residueNumber,
        exon: hoveredExon ? hoveredExon.exon_id : 'Unassigned'
      });
    });

    
    // Create an independently coloured representation for each exon
    for (let exonIndex = 0; exonIndex < data.exons.length; exonIndex++) {
      const exon = data.exons[exonIndex];

      const segments = exon.structure_residue_segments || [];

      for (let segmentIndex = 0; segmentIndex < segments.length; segmentIndex++) {
        const segment = segments[segmentIndex];

        // Select the required chain and author residue range
        const expression = MS.struct.generator.atomGroups({
          'chain-test': MS.core.rel.eq([
            MS.struct.atomProperty.macromolecular.auth_asym_id(),
            segment.chain_id
          ]),

          'residue-test': MS.core.rel.inRange([
            MS.struct.atomProperty.macromolecular.auth_seq_id(),
            segment.start,
            segment.end
          ])
        });

        // Create an exon-specific structural component
        const component =
          await viewer.plugin.builders.structure.tryCreateComponentFromExpression(
            structureRef.cell,
            expression,
            `exon-${exonIndex}-segment-${segmentIndex}`,
            {
              label: `${exon.exon_id} (${segment.start}-${segment.end})`
            }
          );

        if (!component) {
          console.warn(`Could not create component for ${exon.exon_id}`);
          continue;
        }

        // Apply the exon colour using Mol*'s uniform colour theme
        await viewer.plugin.builders.structure.representation.addRepresentation(
          component,
          {
            type: 'cartoon',
            color: 'uniform',
            colorParams: {
              value: Color.fromHexStyle(exon.colour)
            }
          }
        );

        console.log(
          `Exon representation created: ${exon.exon_id}`,
           exon.colour,
          `${segment.chain_id}:${segment.start}-${segment.end}`
        );
      }
    }

    console.log('All exon representations created.');    
    

    console.log('ExonView3D initialised successfully.');
    console.log('Structure:', data.structure.model_id);

  } catch (error) {
    console.error('ExonView3D initialisation failed:', error);

    geneInfo.textContent = 'Unable to load gene information.';
    transcriptInfo.textContent = error.message;
    exonList.textContent = 'Check the Django server and browser console.';
  }
}

initialiseExonView3D();
