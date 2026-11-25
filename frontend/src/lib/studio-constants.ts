/**
 * Hollywood 12-Step Framework & 16-Stage Pipeline Constants
 * DaVinci Obsidian Theme Specs & Hollywood Cinematic Matrices
 * 100% synchronized with backend/app/domain/catalog.py
 */

export interface StageDefinition {
  stage: number;
  phase: string;
  name: string;
  description: string;
  gate: string;
  stepRef?: number;
}

export const HOLLYWOOD_16_STAGES: StageDefinition[] = [
  {
    stage: 1,
    phase: "Phase 1: Pre-Production & Narrative Blueprint",
    name: "Concept & Logline Specification",
    description: "Core thematic premise, logline definition, emotional arc, and target demographic.",
    gate: "Showrunner Logline Approval",
    stepRef: 1,
  },
  {
    stage: 2,
    phase: "Phase 1: Pre-Production & Narrative Blueprint",
    name: "Genre & Visual Style Catalog (#Style)",
    description: "Selection of Hollywood visual style (#Style 01-18) and color science emulation.",
    gate: "Art Director Style Signoff",
    stepRef: 2,
  },
  {
    stage: 3,
    phase: "Phase 1: Pre-Production & Narrative Blueprint",
    name: "4-Act Storyboard & 50-Scene Blueprint",
    description: "Deterministic 50-scene structural distribution across 4 dramatic acts.",
    gate: "Narrative Blueprint Freeze",
    stepRef: 3,
  },
  {
    stage: 4,
    phase: "Phase 1: Pre-Production & Narrative Blueprint",
    name: "Character Profile & Voice DNA",
    description: "Protagonist/Antagonist biometric seed locking, face references, and voice DNA.",
    gate: "Casting & Character Lock",
    stepRef: 4,
  },
  {
    stage: 5,
    phase: "Phase 2: Visual Style & DNA Freeze",
    name: "Dynamic Character Evolution Matrix (#State)",
    description: "Progression states (#State 01 Normal to #State 05 Climax) and costume degradation.",
    gate: "Character State Matrix Lock",
    stepRef: 5,
  },
  {
    stage: 6,
    phase: "Phase 2: Visual Style & DNA Freeze",
    name: "Environment Bible & Hero Prop Continuity",
    description: "World architecture (#Env 01-05), spatial continuity, and signature props (#Prop 01-05).",
    gate: "Production Design Freeze",
    stepRef: 6,
  },
  {
    stage: 7,
    phase: "Phase 2: Visual Style & DNA Freeze",
    name: "Dialogue Pacing & Audio Bridge Calibration",
    description: "5-second ceiling calibration (<=14 words), speech rate, and J/L-cut audio planning.",
    gate: "Dialogue & Sound Script Gate",
    stepRef: 7,
  },
  {
    stage: 8,
    phase: "Phase 2: Visual Style & DNA Freeze",
    name: "Cinematography Optics & Framing Matrix",
    description: "Camera movements (#Cam 01-34), lenses (#Lens 01-06), and compositions (#Comp 01-08).",
    gate: "Director of Photography Approval",
    stepRef: 8,
  },
  {
    stage: 9,
    phase: "Phase 3: Generative Inference & Performance",
    name: "Cinematic Lighting & Performance Matrix",
    description: "Key/fill/rim illumination (#Light 01-14) and acting micro-expressions (#Act 01-24).",
    gate: "Lighting & Performance Gate",
    stepRef: 9,
  },
  {
    stage: 10,
    phase: "Phase 3: Generative Inference & Performance",
    name: "Prompt Transpilation & Compiler Freeze",
    description: "Deterministic compilation to Veo, Kling, Runway, Sora, and ComfyUI formats.",
    gate: "Engine Prompt Lock",
    stepRef: 10,
  },
  {
    stage: 11,
    phase: "Phase 3: Generative Inference & Performance",
    name: "Generative Video & Audio Inference Execution",
    description: "Multi-engine GPU batch synthesis and multi-layer foreground/background motion.",
    gate: "Raw Generation Batch Gate",
    stepRef: 11,
  },
  {
    stage: 12,
    phase: "Phase 3: Generative Inference & Performance",
    name: "Automated Biometric & Aesthetic QC Audit",
    description: "Automated InsightFace similarity, CLIP scores, LAION aesthetic, and SNR checks.",
    gate: "Continuity Quality Gate",
    stepRef: 12,
  },
  {
    stage: 13,
    phase: "Phase 4: Post-Production & Showrunner Delivery",
    name: "Timeline Multi-Track Assembly (NLE)",
    description: "Timeline multi-track sequencing, J/L audio overlays, and video synchronization.",
    gate: "Rough Cut Signoff",
  },
  {
    stage: 14,
    phase: "Phase 4: Post-Production & Showrunner Delivery",
    name: "Cinematic Color Timing & Film Emulation",
    description: "Kodak 5219 film stock emulation, halation, grain, and LUT grading.",
    gate: "Color Timing Final Lock",
  },
  {
    stage: 15,
    phase: "Phase 4: Post-Production & Showrunner Delivery",
    name: "Soundtrack & Foley Acoustic Mastering",
    description: "Binaural spatial mastering, dynamic loudness normalization (-14 LUFS), and Foley.",
    gate: "Audio Master Approval",
  },
  {
    stage: 16,
    phase: "Phase 4: Post-Production & Showrunner Delivery",
    name: "Final Showrunner Master Cut Delivery",
    description: "Hollywood master package release in 4K DCI widescreen with full script bundle.",
    gate: "Executive Producer Golden Cut",
  },
];

export interface StepDefinition {
  step: number;
  name: string;
  code: string;
  desc: string;
}

export const HOLLYWOOD_12_STEPS: StepDefinition[] = [
  { step: 1, name: "Genre & Ratio", code: "STEP_01", desc: "Genre tone & aspect ratio specification" },
  { step: 2, name: "Visual Style", code: "STEP_02", desc: "Master #Style 01-18 selection" },
  { step: 3, name: "Story Blueprint", code: "STEP_03", desc: "50-scene 4-act narrative curve" },
  { step: 4, name: "Character DNA", code: "STEP_04", desc: "Biometric seed & voice profile" },
  { step: 5, name: "Extras Sheet", code: "STEP_05", desc: "Crowd ensembles & secondary cast" },
  { step: 6, name: "Environment & Props", code: "STEP_06", desc: "#Env 01-05 & #Prop 01-05 tracking" },
  { step: 7, name: "Dialogue & Audio", code: "STEP_07", desc: "5s limiter & J/L-cut transitions" },
  { step: 8, name: "Cinematography", code: "STEP_08", desc: "#Cam 01-34, #Lens 01-06, #Comp 01-08" },
  { step: 9, name: "Lighting Matrix", code: "STEP_09", desc: "#Light 01-14 volumetric illumination" },
  { step: 10, name: "Acting Matrix", code: "STEP_10", desc: "#Act 01-24 micro-expression cues" },
  { step: 11, name: "Motion Dynamics", code: "STEP_11", desc: "#Speed 01-05 velocity & parallax" },
  { step: 12, name: "Studio Execution", code: "STEP_12", desc: "Prompt compile, inference & QC" },
];

export const WORKFLOW_STEPS = HOLLYWOOD_12_STEPS;

export interface OperationalStage {
  stage: number;
  name: string;
  category: "pre-production" | "production" | "post-production";
  description: string;
}

export const OPERATIONAL_STAGES: OperationalStage[] = [
  {
    stage: 1,
    name: "Bible & Character DNA",
    category: "pre-production",
    description: "Definition of core story bible, world rules, and character visual invariants.",
  },
  {
    stage: 2,
    name: "Visual Style & Color Science",
    category: "pre-production",
    description: "Selection of Hollywood visual style (#Style 01-18) and color science emulation.",
  },
  {
    stage: 3,
    name: "Screenplay Treatment & Beat Sheet",
    category: "pre-production",
    description: "Blake Snyder Beat Sheet decomposition into dramatic beats across 4 acts.",
  },
  {
    stage: 4,
    name: "Scene Breakdown & Shot List",
    category: "pre-production",
    description: "Full 50-scene structural breakdown with multi-shot camera and lighting configurations.",
  },
  {
    stage: 5,
    name: "Pre-Visualization & Approval Gate A",
    category: "pre-production",
    description: "Director and producer approval gate for bible consistency and shot readiness.",
  },
  {
    stage: 6,
    name: "Act I Production: Setup",
    category: "production",
    description: "Generative inference execution for Scenes 01-12 (Opening, Theme, Catalyst).",
  },
  {
    stage: 7,
    name: "Act II-A Production: Fun & Games",
    category: "production",
    description: "Generative inference execution for Scenes 13-25 (B-Story, Fun & Games, Midpoint).",
  },
  {
    stage: 8,
    name: "Act II-B Production: Bad Guys Close In",
    category: "production",
    description: "Generative inference execution for Scenes 26-38 (Downfall, All Is Lost, Dark Night).",
  },
  {
    stage: 9,
    name: "Act III Production: Finale",
    category: "production",
    description: "Generative inference execution for Scenes 39-50 (Break into Three, Climax, Resolution).",
  },
  {
    stage: 10,
    name: "Automated Continuity & Biometric QC",
    category: "production",
    description: "Automated validation of character facial features, color grade consistency, and action velocity.",
  },
  {
    stage: 11,
    name: "Director Retakes & Approval Gate B",
    category: "production",
    description: "Review of failed QC scenes and execution of targeted prompt retakes.",
  },
  {
    stage: 12,
    name: "Timeline Assembly & Pacing",
    category: "post-production",
    description: "Sequential assembly of approved video segments conforming to intended shot durations.",
  },
  {
    stage: 13,
    name: "Audio Stems & Sound Design",
    category: "post-production",
    description: "Integration of dialogue, Foley, sound effects, and emotional orchestral score.",
  },
  {
    stage: 14,
    name: "Color Timing & Master Grade",
    category: "post-production",
    description: "Final Hollywood color grading matching selected #Style Lut directives.",
  },
  {
    stage: 15,
    name: "Multi-Format Deliverables",
    category: "post-production",
    description: "Transcoding into 16:9 Cinema, 2.39:1 Anamorphic, and 9:16 Mobile Vertical formats.",
  },
  {
    stage: 16,
    name: "Final Distribution Package",
    category: "post-production",
    description: "Complete production asset delivery with audit log and metadata package.",
  },
];

export interface StyleItem {
  code: string;
  name: string;
  desc: string;
  aesthetic_directives?: string;
  color_grade_emulation?: string;
}

export const DEFAULT_STYLES: StyleItem[] = [
  {
    code: "#Style 01",
    name: "Transformers / Michael Bay",
    desc: "Teal-orange, anamorphic lens flares, high contrast, low-angle hero rotation",
    aesthetic_directives: "High-contrast anamorphic flare, metallic sheen, low-angle hero rotation, saturated golden hour, debris-laden air.",
    color_grade_emulation: "Teal and orange color grade, Kodak 5219 film stock, heavy tungsten edge lighting.",
  },
  {
    code: "#Style 02",
    name: "Hollywood IMAX 70mm",
    desc: "Ultra-high resolution, deep dynamic range, pristine depth, lifelike skin pores",
    aesthetic_directives: "Pristine ultra-high resolution, deep dynamic range, lifelike skin pores, massive spatial depth, crisp shadow detail.",
    color_grade_emulation: "Naturalistic color timing, 65mm sensor reproduction, zero artificial vignette.",
  },
  {
    code: "#Style 03",
    name: "Bollywood Grand",
    desc: "Opulent saturation, theatrical wind, warm jewel tones, sweeping crane movements",
    aesthetic_directives: "Opulent color saturation, theatrical wind machines, sweeping crane movements, warm golden light, rich textile textures.",
    color_grade_emulation: "Saturated jewel tones (crimson, emerald, gold), high-key fill, warm diffusion filtering.",
  },
  {
    code: "#Style 04",
    name: "Xianxia / Chinese Historical",
    desc: "Ethereal mist, floating silk physics, jade-ink wash, pastel atmospheric scattering",
    aesthetic_directives: "Ethereal mist, floating silk physics, pastel atmospheric scattering, elegant swordplay choreography, tranquil balance.",
    color_grade_emulation: "Desaturated ink-wash wash, jade and porcelain tones, soft high-key diffusion.",
  },
  {
    code: "#Style 05",
    name: "K-Drama High-End",
    desc: "Porcelain skin tones, shallow depth of field, pastel tones, creamy bokeh",
    aesthetic_directives: "Flawless porcelain skin tones, soft-focus shallow depth, gentle naturalistic backlighting, melancholic cityscapes.",
    color_grade_emulation: "Pastel cyan and warm peach grading, creamy bokeh highlights, pristine commercial gloss.",
  },
  {
    code: "#Style 06",
    name: "Donghua 3D",
    desc: "Hyper-detailed stylized 3D, glowing magical illumination, sharp particle effects",
    aesthetic_directives: "Hyper-detailed stylized 3D animation, photorealistic particle effects, dynamic magical illumination, stylized anime proportions.",
    color_grade_emulation: "Vibrant saturated neon and spiritual hues, sharp specular highlights, clean CGI rendering.",
  },
  {
    code: "#Style 07",
    name: "Epic High Fantasy",
    desc: "Weathered leather, Nordic horizons, desaturated earthen tones, authentic chainmail",
    aesthetic_directives: "Weathered leather, authentic chainmail reflection, ancient moss-covered masonry, sweeping Nordic landscape horizons.",
    color_grade_emulation: "Desaturated earthen tones, muted greens, cold steel blues, overcast northern European lighting.",
  },
  {
    code: "#Style 08",
    name: "Sinema Nusantara",
    desc: "Tropical humidity haze, authentic South East Asian realism, teak wood glows",
    aesthetic_directives: "Tropical humidity haze, warm bamboo and teak wood textures, practical oil-lamp glows, earthy tactile realism.",
    color_grade_emulation: "Organic sepia and deep tropical greens, warm tungsten shadows, authentic South East Asian realism.",
  },
  {
    code: "#Style 09",
    name: "Pixar / Disney 3D Animation",
    desc: "Emotive facial shapes, subsurface scattering, warm primaries, squash-and-stretch",
    aesthetic_directives: "Exaggerated emotive facial shapes, subsurface scattering on skin, rich whimsical lighting, charming physical squash-and-stretch.",
    color_grade_emulation: "Warm primary color harmonies, velvety shadows, clean ray-traced global illumination.",
  },
  {
    code: "#Style 10",
    name: "DreamWorks / Illumination",
    desc: "Snappy cartoon timing, expressive eyes, vibrant primaries, punchy visual gags",
    aesthetic_directives: "Snappy comedic character timing, expressive cartoon eyes, tactile stylized materials, punchy visual gags.",
    color_grade_emulation: "High-contrast vibrant saturated primaries, crisp rim highlights, energetic bounce lighting.",
  },
  {
    code: "#Style 11",
    name: "Arcane (2.5D Steampunk)",
    desc: "Painterly brushstrokes, graphic outlines, gritty neon purples, hextech blues",
    aesthetic_directives: "Painterly brushstroke textures mapped onto dynamic 3D geometry, graphic novel outlines, gritty steampunk industrialism.",
    color_grade_emulation: "Monochromatic grime punctuated by glowing neon purples and hextech blues, rough oil-paint finishes.",
  },
  {
    code: "#Style 12",
    name: "Unreal Engine 5 Metahuman",
    desc: "Real-time raytracing, nanite geometry, lumen lighting, synthetic fidelity",
    aesthetic_directives: "Real-time raytracing, nanite micro-polygon geometry, lumen dynamic global illumination, flawless synthetic human fidelity.",
    color_grade_emulation: "Neutral digital calibration, physical camera sensor emulation, precise roughness map reflections.",
  },
  {
    code: "#Style 13",
    name: "Stop-Motion Animation",
    desc: "Plasticine textures, 12fps stepped cadence, miniature studio lighting",
    aesthetic_directives: "Tactile plasticine / clay textures, visible fingerprint impressions, armature joint tension, 12 fps stepped motion cadence.",
    color_grade_emulation: "Studio miniature warm spotlights, macro depth of field falloff, physical miniature set materials.",
  },
  {
    code: "#Style 14",
    name: "Classic 2D Cartoon",
    desc: "Hand-drawn cel animation, ink line art, vintage multi-plane camera parallax",
    aesthetic_directives: "Hand-drawn cel animation, ink line art with variable weighting, flat color fills, vintage multi-plane camera parallax.",
    color_grade_emulation: "1990s retro animation palette, soft paper texture overlay, zero 3D shading artifacts.",
  },
  {
    code: "#Style 15",
    name: "Anime (Shinkai / Ufotable)",
    desc: "Hyper-detailed sky clouds, radiant flares, emotional eyes, cinematic polish",
    aesthetic_directives: "Hyper-detailed sky cloud formations, photorealistic god rays, radiant lens flares, expressive hand-drawn emotional eyes.",
    color_grade_emulation: "Luminous ultramarine blues, sunset magentas, glistening water reflections, cinematic anime polish.",
  },
  {
    code: "#Style 16",
    name: "Studio Ghibli",
    desc: "Lush watercolor backgrounds, pastoral nostalgia, hand-crafted painterly flora",
    aesthetic_directives: "Lush watercolor nature backgrounds, painterly flora, whimsical wind gusts, gentle nostalgic warmth, hand-painted cels.",
    color_grade_emulation: "Earthy greens, gentle cerulean blues, soft eggshell whites, warm childhood nostalgia grading.",
  },
  {
    code: "#Style 17",
    name: "Dark Graphic Novel",
    desc: "Heavy chiaroscuro black ink shadows, stark angular silhouettes, detective noir",
    aesthetic_directives: "Heavy black ink shadows (chiaroscuro), stark angular silhouettes, stylized rain downpours, hard-boiled detective noir.",
    color_grade_emulation: "High-contrast monochrome black-and-white accented by single spot colors (blood red, toxic yellow).",
  },
  {
    code: "#Style 18",
    name: "Vintage Film (1970s Technicolor)",
    desc: "Organic heavy grain, faded dye couplers, authentic 35mm archival print texture",
    aesthetic_directives: "Organic heavy grain structure, chromatic aberration around frame perimeters, faded dye couplers, authentic gate weave.",
    color_grade_emulation: "Warm faded yellows, sepia skin tones, cyan shadows, authentic 35mm archival print texture.",
  },
];

export interface LightingItem {
  code: string;
  name: string;
  mood?: string;
  technical_specifications?: string;
  mood_application?: string;
}

export const DEFAULT_LIGHTING: LightingItem[] = [
  { code: "#Light 01", name: "Golden Hour Backlit", mood: "Heroic, dramatic contour separation, 2800K warmth", mood_application: "Nostalgic longing, triumphant return, romantic reverie." },
  { code: "#Light 02", name: "Volumetric God Rays", mood: "Spiritual epiphany, temple mystery, 4500K beam contrast", mood_application: "Spiritual epiphany, grand revelation, ancient temple mystery." },
  { code: "#Light 03", name: "Low-Key Chiaroscuro", mood: "Psychological suspense, moral conflict, 8:1 ratio", mood_application: "Psychological suspense, moral conflict, interrogation, classic noir." },
  { code: "#Light 04", name: "Silvery Blue Moonlight", mood: "Midnight isolation, 6500K cool diffused overhead key", mood_application: "Vulnerable isolation, clandestine rendezvous, midnight dread." },
  { code: "#Light 05", name: "Flickering Torch / Candle", mood: "1800K dynamic flame luminance, intimate sanctuary", mood_application: "Medieval dungeon, intimate sanctuary, primal fear of darkness." },
  { code: "#Light 06", name: "Neon Cyberpunk", mood: "Dual cyan & magenta neon, wet pavement reflections", mood_application: "Urban alienation, futuristic crime underworld, dystopian noir." },
  { code: "#Light 07", name: "Overcast Soft", mood: "Diffused 6000K skylight, somber melancholy realism", mood_application: "Realism, somber melancholy, military procedural neutrality." },
  { code: "#Light 08", name: "Harsh Midday", mood: "Zenith sun 90°, 5800K blinding intensity, desert survival", mood_application: "Bleak desert survival, brutalist interrogation, exposed vulnerability." },
  { code: "#Light 09", name: "Practical Headlights", mood: "Twin 4000K tungsten automotive beams cutting through rain", mood_application: "Impending vehicular catastrophe, rural roadblock, ominous pursuit." },
  { code: "#Light 10", name: "High-Key Ethereal", mood: "Overexposed +2 EV background, soft wrapping daylight", mood_application: "Dream sequences, heavenly transition, idyllic memory recollection." },
  { code: "#Light 11", name: "Lightning Flash", mood: "Instantaneous 10000K xenon burst, visceral terror", mood_application: "Visceral terror, climactic thunderstorm combat, sudden shock." },
  { code: "#Light 12", name: "Clinical Cold Sci-Fi", mood: "Sterile 6500K ceiling fluorescent grids, lab control", mood_application: "Lab experimentation, totalitarian control, emotionless bureaucracy." },
  { code: "#Light 13", name: "Dappled Forest", mood: "Canopy-filtered fractal sunlight, wilderness journey", mood_application: "Wilderness journey, hidden refuge, psychological awakening." },
  { code: "#Light 14", name: "Silhouette Against Fire", mood: "1500K raging inferno backdrop, pure silhouette", mood_application: "Total destruction, villainous emergence, irreversible tragedy." },
];

export interface ActingItem {
  code: string;
  name: string;
  category?: string;
  cue?: string;
  micro_expressions?: string;
  dramatic_context?: string;
}

export const DEFAULT_ACTING: ActingItem[] = [
  { code: "#Act 01", name: "Suppressed Trauma", cue: "Suppressed Trauma", category: "Emotional Subtext", micro_expressions: "Tightened orbicularis oris, rigid neck tendons, gaze fixated on middle distance, refusal to blink." },
  { code: "#Act 02", name: "Cold Calculation", cue: "Cold Calculation", category: "Dramatic Resolve", micro_expressions: "Narrowed eyelids, subtle slow pupil sweep across room, flat heart-rate rhythm, zero head tilt." },
  { code: "#Act 03", name: "Primal Rage", cue: "Primal Rage", category: "High Adrenaline", micro_expressions: "Flared nostrils, bared canine teeth, veins pulsing at temple, rapid chest heaving, hyper-focused gaze." },
  { code: "#Act 04", name: "Quiet Melancholy", cue: "Quiet Melancholy", category: "Simmering Conflict", micro_expressions: "Soft downward eye saccade, slow shallow exhalation through slightly parted lips, slack facial musculature." },
  { code: "#Act 05", name: "Paranoid Dread", cue: "Paranoid Dread", category: "Intimacy", micro_expressions: "Rapid jittery eye movements, micro-turning of ears toward ambient sounds, hunched shoulders, tight throat swallowing." },
  { code: "#Act 06", name: "Heroic Resolve", cue: "Heroic Resolve", category: "Charisma", micro_expressions: "Firmly set jaw, steady direct gaze locking on horizon, relaxed posture with grounded combat stance." },
  { code: "#Act 07", name: "Cynical Amusement", cue: "Cynical Amusement", category: "Physical Trauma", micro_expressions: "Asymmetrical smirk on left lip corner, single raised eyebrow, sarcastic head tilt, amused twinkle in eyes." },
  { code: "#Act 08", name: "Shock and Awe", cue: "Shock and Awe", category: "Action Tactical", micro_expressions: "Jaw dropped in paralysis, dilated pupils catching light, sudden intake of breath held stationary in lungs." },
  { code: "#Act 09", name: "Intimate Vulnerability", cue: "Intimate Vulnerability", category: "Intimacy", micro_expressions: "Soft hesitant smile breaking across lips, trembling eye gaze dropping to partner's lips then rising." },
  { code: "#Act 10", name: "Complete Breakdown", cue: "Complete Breakdown", category: "Emotional Subtext", micro_expressions: "Facial contortion into weeping, trembling hands attempting to cover face, loss of physical posture integrity." },
  { code: "#Act 11", name: "Stoic Endurance", cue: "Stoic Endurance", category: "Dramatic Resolve", micro_expressions: "Face weathered and emotionless, absorbing physical pain with clenched teeth, steady breathing cadence." },
  { code: "#Act 12", name: "Deceptive Charm", cue: "Deceptive Charm", category: "Charisma", micro_expressions: "Warm wide crinkled smile reaching crows-feet at eyes, open relaxed palms, predatory stillness beneath the warmth." },
  { code: "#Act 13", name: "Total Exhaustion", cue: "Total Exhaustion", category: "Physical Trauma", micro_expressions: "Drooping eyelids, heavy head sinking downward, trembling lower lip, slow slurred speech delivery." },
  { code: "#Act 14", name: "Euphoric Triumph", cue: "Euphoric Triumph", category: "High Adrenaline", micro_expressions: "Thrown-back head, chest fully expanded, roaring open-mouth laugh, tear of joy tracing cheek." },
  { code: "#Act 15", name: "Disgust / Repulsion", cue: "Disgust / Repulsion", category: "Emotional Subtext", micro_expressions: "Curled upper lip showing front teeth, wrinkled nasal bridge, instinctive backward recoil of head." },
  { code: "#Act 16", name: "Moral Hesitation", cue: "Moral Hesitation", category: "Dramatic Resolve", micro_expressions: "Hand pausing halfway to weapon, eyes darting between target and innocent bystander, conflicting facial muscle tension." },
  { code: "#Act 17", name: "Hypnotic Trance", cue: "Hypnotic Trance", category: "Intimacy", micro_expressions: "Unfocused glassy eyes, slack jaw, slow rhythmic swaying, complete absence of natural startle reflex." },
  { code: "#Act 18", name: "Panic Attack", cue: "Panic Attack", category: "High Adrenaline", micro_expressions: "Hyperventilating chest heave, wide unblinking eyes, trembling fingers grasping throat, beads of cold sweat on forehead." },
  { code: "#Act 19", name: "Seductive Playfulness", cue: "Seductive Playfulness", category: "Charisma", micro_expressions: "Tilted head looking up through eyelashes, gentle bite of lower lip, deliberate slow cat-like movement." },
  { code: "#Act 20", name: "Contemptuous Dismissal", cue: "Contemptuous Dismissal", category: "Dramatic Resolve", micro_expressions: "Half-closed eyes looking down bridge of nose, tiny dismissive puff of air from nostrils, turned shoulder." },
  { code: "#Act 21", name: "Sudden Realization", cue: "Sudden Realization", category: "Emotional Subtext", micro_expressions: "Widening eyes with sudden micro-nod, lips parting in silent vocalization, quick head snap toward clue." },
  { code: "#Act 22", name: "Physical Agony", cue: "Physical Agony", category: "Physical Trauma", micro_expressions: "Writhing neck muscles, tightly squeezed shut eyelids with tear leakage, gritted teeth with guttural groan." },
  { code: "#Act 23", name: "Guilt and Remorse", cue: "Guilt and Remorse", category: "Simmering Conflict", micro_expressions: "Downcast averted eyes unable to look at victim, hunched spine, nervous wringing of hands." },
  { code: "#Act 24", name: "Transcendent Peace", cue: "Transcendent Peace", category: "Dramatic Resolve", micro_expressions: "Serene neutral expression, faint tranquil smile, slow gentle breathing, relaxed shoulders welcoming fate." },
];

export interface CameraItem {
  code: string;
  name: string;
  movement?: string;
  description?: string;
}

export const DEFAULT_CAMERAS: CameraItem[] = [
  { code: "#Cam 01", name: "Extreme Close-Up", movement: "Macro ECU", description: "ECU - Eyes/Mouth tight macro focus" },
  { code: "#Cam 02", name: "Close-Up", movement: "Tight CU", description: "CU - Head & Neck framing" },
  { code: "#Cam 03", name: "Medium Close-Up", movement: "MCU", description: "MCU - Chest Up perspective" },
  { code: "#Cam 04", name: "Medium Shot", movement: "Waist Up", description: "MS - Waist Up dialogue framing" },
  { code: "#Cam 05", name: "Cowboy Shot", movement: "American", description: "American - Mid-Thigh Up holstered stance" },
  { code: "#Cam 06", name: "Full Shot", movement: "Head to Toe", description: "FS - Head to Toe character introduction" },
  { code: "#Cam 07", name: "Wide Shot", movement: "Master WS", description: "WS - Complete Environment spatial relation" },
  { code: "#Cam 08", name: "Extreme Wide Shot", movement: "Panorama EWS", description: "EWS - Epic Scale panoramic vista" },
  { code: "#Cam 09", name: "Bird's Eye View", movement: "Overhead 90°", description: "Overhead 90° Zenith omniscient perspective" },
  { code: "#Cam 10", name: "Worm's Eye View", movement: "Ground 90° Up", description: "Ground Level 90° Up imposing authority" },
  { code: "#Cam 11", name: "Over-The-Shoulder", movement: "Dialogue OTS", description: "OTS - Dialogue conversational geography" },
  { code: "#Cam 12", name: "Point of View", movement: "Subjective POV", description: "POV - First Person subjective lens" },
  { code: "#Cam 13", name: "Low-Angle Hero Shot", movement: "Low 30° Arc", description: "Looking Up 30° majestic power stance" },
  { code: "#Cam 14", name: "High-Angle Vulnerability", movement: "High 30° Down", description: "Looking Down 30° diminished status" },
  { code: "#Cam 15", name: "Dutch Angle Tilt", movement: "Axis Roll 25°", description: "Canted camera axis signaling vertigo or psychological disarray" },
  { code: "#Cam 16", name: "Profile Side Silhouette", movement: "Lateral 90°", description: "Lateral 90° contour framing" },
  { code: "#Cam 17", name: "Frontal Symmetrical Master", movement: "Centered One-Point", description: "One-point linear perspective centered horizon" },
  { code: "#Cam 18", name: "Tracking Shot", movement: "Dolly Lateral", description: "Dolly Sideways parallel tracking lateral motion" },
  { code: "#Cam 19", name: "Dolly-In", movement: "Dolly Forward", description: "Emotional Push forward emphasizing realization" },
  { code: "#Cam 20", name: "Dolly-Out", movement: "Dolly Backward", description: "Isolation Reveal moving backward abandoning subject" },
  { code: "#Cam 21", name: "Crane / Jib Sweeping Overhead", movement: "Sweeping Jib", description: "Grand vertical ascent revealing sprawling battlefield" },
  { code: "#Cam 22", name: "Whip Pan", movement: "Kinetic Blur Pan", description: "Fast kinetic blur transition between subjects" },
  { code: "#Cam 23", name: "360-Degree Orbital Arc", movement: "Orbital Steadicam", description: "Circular camera orbit locking center axis" },
  { code: "#Cam 24", name: "Steadicam Forward Push", movement: "Fluid Steadicam", description: "Fluid walking pace following character into interior" },
  { code: "#Cam 25", name: "Handheld Shaky-Cam", movement: "Visceral Documentary", description: "Visceral documentary warzone realism" },
  { code: "#Cam 26", name: "Crash Zoom", movement: "Zoom Snap", description: "Sudden dramatic focal shift mimicking 1970s kung fu snap" },
  { code: "#Cam 27", name: "Rack Focus", movement: "Depth Pull", description: "Shifting Depth from FG obstacle to BG subject" },
  { code: "#Cam 28", name: "Snorricam", movement: "Body-Mounted Rig", description: "Body-Mounted Subject Lock experiencing drunken disorientation" },
  { code: "#Cam 29", name: "Split-Diopter Dual Plane Focus", movement: "Dual Focal Plane", description: "Simultaneous tack-sharp focus on near FG and far BG" },
  { code: "#Cam 30", name: "Drone Panoramic Flyover", movement: "Aerial Drone", description: "Aerial terrain sweep surveying vast landscape" },
  { code: "#Cam 31", name: "Two-Shot", movement: "Dual Character Frame", description: "Balanced Profile Dynamic pairing duo in conflict or intimacy" },
  { code: "#Cam 32", name: "Crowd Ensemble Master", movement: "Choreographed Group", description: "Choreographed multi-subject interaction" },
  { code: "#Cam 33", name: "Atmospheric Establishing Master", movement: "Establishing Atmosphere", description: "Setting tone, climate, and geography for sequence" },
  { code: "#Cam 34", name: "Microscopic Macro Insert", movement: "Extreme Macro", description: "Super close-up on needle touching vinyl or eye pupil dial" },
];

export interface LensItem {
  code: string;
  name: string;
  focal?: string;
  optical_physics?: string;
  visual_field?: string;
}

export const DEFAULT_LENSES: LensItem[] = [
  { code: "#Lens 01", name: "2.0x Anamorphic Prime", focal: "Anamorphic Scope (2.39:1)", visual_field: "Horizontal streak flares, oval bokeh discs, widescreen Hollywood film grandeur" },
  { code: "#Lens 02", name: "35mm Spherical Prime", focal: "Human Eye Perspective (f/1.8)", visual_field: "Minimal distortion, organic human perspective, conversational realism" },
  { code: "#Lens 03", name: "85mm Portrait Prime", focal: "Creamy Bokeh Separation (f/1.4)", visual_field: "Heroic close-up isolation, dramatic emotional intimacy" },
  { code: "#Lens 04", name: "24mm Ultra-Wide Angle", focal: "Expansive Architectural Depth", visual_field: "Exaggerated spatial depth, dynamic perspective lines, action choreography" },
  { code: "#Lens 05", name: "135mm Heavy Telephoto", focal: "Compressed Distance & Stalking", visual_field: "Severe background compression, flattening foreground and background threat" },
  { code: "#Lens 06", name: "Tilt-Shift Miniature", focal: "Selective Plane Diorama", visual_field: "Selected plane of focus, selective blur producing miniature diorama illusion" },
];

export interface CompositionItem {
  code: string;
  name: string;
  framing?: string;
  description?: string;
}

export const DEFAULT_COMPOSITIONS: CompositionItem[] = [
  { code: "#Comp 01", name: "Rule of Thirds", framing: "Classic balanced intersections", description: "Key facial features and horizons aligned along 1/3 and 2/3 coordinate intersections." },
  { code: "#Comp 02", name: "Golden Spiral (Fibonacci)", framing: "Curved visual focus flow", description: "Dynamic logarithmic curve leading eye from environmental periphery to micro-detail." },
  { code: "#Comp 03", name: "Central Symmetry", framing: "One-point vanishing corridor", description: "Exact geometric centering of subject; Kubrick-style one-point linear perspective." },
  { code: "#Comp 04", name: "Leading Lines", framing: "Architectural vector focus", description: "Structural architecture (railways, corridors, bridges) forcing eye vector to vanishing point." },
  { code: "#Comp 05", name: "180-Degree Action Line", framing: "Spatial screen direction preservation", description: "Rigid spatial camera positioning preserving screen direction between shots." },
  { code: "#Comp 06", name: "Frame Within a Frame", framing: "Doorway / Window geometry", description: "Subject framed inside doorways, broken arches, windows, or rear-view mirrors." },
  { code: "#Comp 07", name: "Dutch Angle (Canted)", framing: "Psychological disorder 15°-30°", description: "15° to 30° roll on camera axis, creating psychological vertigo and systemic disorder." },
  { code: "#Comp 08", name: "Deep Focus Mise-en-Scène", framing: "f/11 Hyperfocal multi-plane sharpness", description: "f/11 hyperfocal aperture keeping foreground, midground, and background tack sharp." },
];

export interface SpeedItem {
  code: string;
  name: string;
  fps: number;
  timing: string;
  description?: string;
}

export const DEFAULT_SPEEDS: SpeedItem[] = [
  { code: "#Speed 01", name: "Static / Locked-Off", fps: 24, timing: "Standard cinema cadence", description: "Zero camera movement. Micro-movements strictly limited to blinking, smoke, and breathing." },
  { code: "#Speed 02", name: "Subtle Organic Drift", fps: 24, timing: "0.2 m/s breathing drift", description: "Micro-Steadicam breathing drift (0.2 m/s). Soft naturalistic character repositioning." },
  { code: "#Speed 03", name: "Cinematic Paced", fps: 24, timing: "1.0 m/s purposeful dolly", description: "Deliberate smooth dolly movement (1.0 m/s). Purposeful narrative pacing." },
  { code: "#Speed 04", name: "High-Octane Action", fps: 24, timing: "3.5 m/s fast dynamic sweep", description: "Rapid camera pan and tracking (3.5 m/s). Fast combat choreography and chase dynamics." },
  { code: "#Speed 05", name: "Hyper-Speed / Time-Lapse", fps: 120, timing: "5.0x fluid bullet-time capture", description: "Time acceleration or high-speed slow-motion (120 fps burst capture)." },
];
