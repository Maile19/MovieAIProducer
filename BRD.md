# Business Requirements Document (BRD) - MovieAIProducer

> Business requirements, market analysis, operational pillars, and success metrics for the MovieAIProducer platform.

---

## 1. Executive Summary

Generative AI video models (Runway Gen-3, Kling, Google Veo, OpenAI Sora) have lowered the barrier to generating raw video clips. However, these tools operate as isolated clip generators. Commercial cinema requires sustained narrative coherence, character continuity, optical physics consistency, and spatial geometry across dozens of sequential scenes.

Without centralized production controls, producing a cohesive 5-minute short film or pilot episode requires hundreds of manual re-prompts, resulting in visual drift, mismatched lighting, broken axis-of-action lines, and ballooning GPU inference costs.

**MovieAIProducer** solves this operational bottleneck by acting as an automated virtual film studio. Built around a **50-scene (4-act) Hollywood production model** and governed by a **Master Production Bible (MPB)**, the platform coordinates the complete pre-production, visual engineering, prompt compilation, and quality control pipeline to produce production-grade cinematic narratives with deterministic continuity.

---

## 2. Market Problem & Opportunity Analysis

### 2.1 The Generative Video Continuity Gap

| Metric / Dimension              | Unassisted Generative Prompting                                                                | MovieAIProducer Virtual Studio                                                                                          |
| :------------------------------ | :--------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- |
| **Character Consistency**       | Faces, hair, and wardrobe morph between cuts (~70% drift across 5 scenes).                     | Immutable DNA tokens lock facial features, ethnic markers, and wardrobe state across all 50 scenes.                     |
| **Cinematography & Optics**     | Random lens focal lengths, arbitrary camera movement, and frequent 180-degree rule violations. | Explicit matrix codes enforce focal lengths (`#Lens 01-06`), framing (`#Comp 01-08`), and camera setups (`#Cam 01-34`). |
| **Production Cost Efficiency**  | High re-roll rate (8 to 15 attempts per usable 5-second cut; 80% prompt waste).                | Structured compiler with DNA pre-validation reduces re-rolls to fewer than 1.5 attempts per approved shot.              |
| **Editorial Assembly**          | Disconnected clips requiring intensive manual masking, color grading, and timing fixes.        | Calibrated 5.0-second shots with native J/L audio cut bridges and color timing directives.                              |
| **IP Ownership & Traceability** | Fragmented prompts across web interfaces with zero version history or provenance.              | Git-style versioning of the Master Production Bible with cryptographic asset provenance.                                |

---

## 3. Stakeholder Ecosystem & User Personas

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   MovieAIProducer Stakeholder Model                    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Showrunner /    │      │  Line Producer / │      │  AI Pipeline     │
│  Film Director   │      │  Financier       │      │  Engineer        │
│  (Creative Lead) │      │  (Operations)    │      │  (Technical)     │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 3.1 Personas & Key Objectives

1. **Showrunner / Creative Director:**
   - _Goal:_ Author a compelling 50-scene narrative without losing aesthetic control.
   - _Requirement:_ Immutable visual styles (`#Style 01-18`), precise acting performance cues (`#Act 01-24`), and dynamic character progression (`#State 01-05`).
2. **Line Producer / Studio Financier:**
   - _Goal:_ Control AI compute budgets, track shot delivery schedules, and guarantee delivery deadlines.
   - _Requirement:_ Granular provider cost routing, automated failure recovery, and transparent API quota management.
3. **AI Pipeline & Prompt Engineer:**
   - _Goal:_ Maintain stable integrations with evolving generative models (Runway, Kling, Veo, ElevenLabs).
   - _Requirement:_ Decoupled provider adapter layer, structured prompt schemas, and automated continuity scorecards.

---

## 4. The 5 Core Hollywood Production Pillars

To bridge the gap between amateur generative clips and commercial cinematic standards, MovieAIProducer mandates five operational pillars across all production workflows:

```text
                  ┌────────────────────────────────────────┐
                  │    5 Hollywood Production Pillars      │
                  └──────────────────┬─────────────────────┘
                                     │
         ┌──────────────┬────────────┼────────────┬──────────────┐
         ▼              ▼            ▼            ▼              ▼
   ┌───────────┐  ┌───────────┐┌───────────┐┌───────────┐  ┌───────────┐
   │ Pillar 1: │  │ Pillar 2: ││ Pillar 3: ││ Pillar 4: │  │ Pillar 5: │
   │ Lighting  │  │   Lens    ││Composition││ Character │  │Multi-Layer│
   │(#Light 01)│  │(#Lens 01) ││ (#Comp 01)││  Evolution│  │  Dynamics │
   └───────────┘  └───────────┘└───────────┘└───────────┘  └───────────┘
```

1. **Cinematic Lighting & Atmosphere (`#Light 01–#14`):** Photometric consistency, key-to-fill ratios, color temperature (Kelvin), and volumetric particle scattering.
2. **Optical Lens Physics (`#Lens 01–#06`):** Focal length calibration (24mm wide through 135mm telephoto), anamorphic squeeze ratios (2.0x), and depth-of-field control.
3. **Composition & Spatial Geometry (`#Comp 01–#08`):** Strict adherence to the 180-degree axis of action, rule of thirds, golden spiral, and kubrickian one-point perspective.
4. **Character State Evolution (`#State 01–#05`):** Deterministic progression of physical wear, emotional trauma, and wardrobe degradation matching narrative beats.
5. **Multi-Layer Dynamics & Speed (`#Speed 01–#05`):** Separation of foreground bokeh (`#FG`), subject action, and background motion (`#BG`) to eliminate flat 2D rendering artifacts.

---

## 5. Alignment with the 16 Operational Stages

MovieAIProducer maps studio business workflows across 16 formal operational stages:

| Operational Stage | Stage Name                          | Business Function                                                                | Mandatory Quality Gate                                |
| :---------------- | :---------------------------------- | :------------------------------------------------------------------------------- | :---------------------------------------------------- |
| **Stage 01**      | Creative Brief & Film Strategy      | Defines project scope, target audience, format, and commercial goals.            | Executive approval of logline and format constraints. |
| **Stage 02**      | Visual Concept & Style Bible        | Establishes master aesthetic palette (`#Style 01-18`) and color timing.          | Visual style mood board sign-off.                     |
| **Stage 03**      | Story Architecture & Screenplay     | Generates 4-act structural arc and 50-scene treatment.                           | Narrative beat verification and scene count check.    |
| **Stage 04**      | Script Breakdown & Feasibility      | Evaluates visual feasibility, complexity, and estimated generation cost.         | Cost estimate model validation.                       |
| **Stage 05**      | Character Casting & Bible           | Synthesizes synthetic actor DNA seeds, facial profiles, and voice models.        | Synthetic actor identity lock.                        |
| **Stage 06**      | Extras & Creature Design            | Defines secondary background groups (`#Extras 01-08`) and cultural coherence.    | Background diversity and period accuracy sign-off.    |
| **Stage 07**      | Production Design & Environment     | Builds spatial environment bibles (`#Env 01-05`) and hero props (`#Prop 01-05`). | Environmental architectural lock.                     |
| **Stage 08**      | Wardrobe, Makeup & Prosthetics      | Defines costume states and damage progression (`#State 01-05`).                  | Wardrobe state continuity matrix sign-off.            |
| **Stage 09**      | Storyboard & Previsualization       | Generates keyframe visual sequences and rough temporal animatics.                | Spatial blocking and 180-degree check.                |
| **Stage 10**      | Director's Scene Direction          | Establishes dramatic subtext, pacing, and actor performance cues.                | Director beat-sheet approval.                         |
| **Stage 11**      | Cinematography & Camera Engineering | Assigns camera positions (`#Cam 01-34`) and lens profiles (`#Lens 01-06`).       | Optical physics and composition check.                |
| **Stage 12**      | Lighting & Atmospheric Engineering  | Configures lighting setups (`#Light 01-14`) and volumetric effects.              | Photometric balance and color temp review.            |
| **Stage 13**      | Performance & Dialogue Direction    | Calibrates voiceover pacing, emotional cues (`#Act 01-24`), and audio bridges.   | Audio timeline alignment (5.0s pacing).               |
| **Stage 14**      | Motion & Continuity Engineering     | Configures speed profiles (`#Speed 01-05`) and multi-layer parallax (`#FG/#BG`). | Frame bridging and parallax verification.             |
| **Stage 15**      | AI Production Orchestration         | Compiles prompts, manages provider quotas, and dispatches render jobs.           | API dispatch validation; error retry handling.        |
| **Stage 16**      | Scene Execution, Editorial & QC     | Runs automated continuity scorecards, detects drift, and exports final package.  | 95%+ QC score threshold; final director lock.         |

---

## 6. Functional Business Requirements

### 6.1 Master Production Bible (MPB) as Single Source of Truth

- The system must store all project specifications in an immutable, relational database schema.
- Once a creative entity (Character DNA, Environment, Prop) is approved, it must receive a permanent UUID and be locked against unversioned modification.

### 6.2 Provider Independence & Cost Routing

- Generation requests must route through an abstract adapter interface, supporting Kling, Runway, Google Veo, OpenAI Sora, Midjourney, and ElevenLabs.
- The platform must support dynamic provider failover: if Provider A times out or returns rate limits, the system must transparently fall back to an equivalent secondary provider.
- Inference costs must be tracked per scene and aggregated at the project level.

### 6.3 Automated Quality Control & Continuity Verification

- The platform must compute a quantitative Continuity Score for every rendered scene based on:
  1. Facial similarity vector compared to the MPB Character DNA seed (target: `>=0.92` cosine similarity).
  2. Color palette histogram match against the Master Style specification.
  3. Spatial vector continuity confirming compliance with the 180-degree action line.
- Scenes scoring below 85% must be flagged for automated regeneration with adjusted compiler constraints.

---

## 7. Key Performance Indicators (KPIs)

| KPI                                 | Target                                  | Measurement Method                                                                         |
| :---------------------------------- | :-------------------------------------- | :----------------------------------------------------------------------------------------- |
| **Re-Prompt / Waste Ratio**         | `<= 1.5` attempts per approved cut      | Total provider generation jobs divided by total approved shots in the 50-scene timeline.   |
| **Character Visual Continuity**     | `>= 92%` visual match across 50 scenes  | Automated facial embedding distance analysis between Scene 01 and subsequent cuts.         |
| **End-to-End Production Time**      | `<= 6` hours for complete 50-scene film | Total elapsed duration from Creative Brief approval to Final Editorial QC lock.            |
| **Cost per Finished Minute**        | `<= $35.00` per minute of final cinema  | Total API inference spend (LLM + T2I + I2V + TTS) divided by total runtime (4.16 minutes). |
| **System Uptime & Job Reliability** | `>= 99.5%` background job completion    | Percentage of scheduled generation jobs completed without fatal unhandled exceptions.      |

---

## 8. Regulatory, Ethics & IP Protection

1. **Synthetic Actor Consent & Integrity:** MovieAIProducer enforces the generation of purely synthetic character identities. Using prompts designed to clone the likeness of living real-world persons without explicit digital twin licensing is prohibited.
2. **Provenance & Content Authenticity:** All exported video assets must embed standardized C2PA metadata manifests, cryptographically recording the generation models, timestamps, and pipeline version.
3. **Data Privacy & Ownership:** All creative assets, screenplay text, DNA embeddings, and production bibles remain the sole property of the user and are stored locally or within user-controlled cloud storage.
