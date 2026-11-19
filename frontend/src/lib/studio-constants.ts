/**
 * Hollywood 12-Step Framework & 16-Stage Pipeline Constants
 * DaVinci Obsidian Theme Specs & Hollywood Cinematic Matrices
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

export const HOLLYWOOD_12_STEPS = [
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

export const DEFAULT_STYLES = [
  { code: "#Style 01", name: "Transformers / Michael Bay", desc: "Teal-orange, anamorphic lens flares, high contrast" },
  { code: "#Style 02", name: "Hollywood IMAX 70mm", desc: "Ultra-high resolution, deep dynamic range, pristine depth" },
  { code: "#Style 03", name: "Bollywood Grand", desc: "Opulent saturation, theatrical wind, warm jewel tones" },
  { code: "#Style 04", name: "Xianxia / Chinese Historical", desc: "Ethereal mist, floating silk physics, jade-ink wash" },
  { code: "#Style 05", name: "K-Drama High-End", desc: "Porcelain skin tones, shallow depth of field, pastel tones" },
  { code: "#Style 06", name: "Donghua 3D", desc: "Hyper-detailed stylized 3D, glowing magical illumination" },
  { code: "#Style 07", name: "Epic High Fantasy", desc: "Weathered leather, Nordic horizons, desaturated earthen tones" },
  { code: "#Style 08", name: "Sinema Nusantara", desc: "Tropical humidity haze, authentic South East Asian realism" },
  { code: "#Style 09", name: "Pixar / Disney 3D", desc: "Emotive facial shapes, subsurface scattering, warm primaries" },
  { code: "#Style 10", name: "DreamWorks / Illumination", desc: "Snappy cartoon timing, expressive eyes, vibrant primaries" },
  { code: "#Style 11", name: "Arcane (2.5D Steampunk)", desc: "Painterly brushstrokes, graphic outlines, gritty neon purples" },
  { code: "#Style 12", name: "Unreal Engine 5 Metahuman", desc: "Real-time raytracing, nanite geometry, lumen lighting" },
  { code: "#Style 13", name: "Stop-Motion Animation", desc: "Plasticine textures, 12fps stepped cadence, miniature lighting" },
  { code: "#Style 14", name: "Classic 2D Cartoon", desc: "Hand-drawn cel animation, ink line art, vintage multi-plane" },
  { code: "#Style 15", name: "Anime (Shinkai / Ufotable)", desc: "Hyper-detailed sky clouds, radiant flares, emotional eyes" },
  { code: "#Style 16", name: "Studio Ghibli", desc: "Lush watercolor backgrounds, pastoral nostalgia, hand-crafted" },
  { code: "#Style 17", name: "Dune / Denis Villeneuve", desc: "Monolithic brutalism, spice atmospheric particulate, sepia" },
  { code: "#Style 18", name: "Vintage 1970s Panavision", desc: "Kodachrome warm grain, organic edge halation, analog film" },
];

export const DEFAULT_LIGHTING = [
  { code: "#Light 01", name: "Volumetric Amber Rim", mood: "Heroic, dramatic contour separation" },
  { code: "#Light 02", name: "High-Contrast Chiaroscuro", mood: "Tension, moral ambiguity, deep noir shadows" },
  { code: "#Light 03", name: "Neon Sodium Vapor Rain", mood: "Cyberpunk urban isolation, reflections" },
  { code: "#Light 04", name: "Golden Hour Sunset Softbox", mood: "Nostalgia, romance, gentle skin illumination" },
  { code: "#Light 05", name: "Motivated Practical Lamp", mood: "Intimate realism, naturalistic falloff" },
  { code: "#Light 06", name: "Bioluminescent Cyan Glow", mood: "Sci-fi alien environment, supernatural mystery" },
  { code: "#Light 07", name: "Cold Overcast Fluorescent", mood: "Sterile bureaucracy, institutional tension" },
  { code: "#Light 08", name: "Searchlight Sweeping Beam", mood: "Paranoia, interrogation, active pursuit" },
  { code: "#Light 09", name: "Candlelight Flicker", mood: "Period drama, vulnerable intimacy" },
  { code: "#Light 10", name: "Sunlight Window Blinds", mood: "Classic detective noir, fragmented psyche" },
  { code: "#Light 11", name: "Strobe Emergency Red", mood: "Imminent danger, system failure, combat" },
  { code: "#Light 12", name: "Underwater Caustics", mood: "Dreamlike weightlessness, subconscious depth" },
  { code: "#Light 13", name: "Dappled Forest Canopy", mood: "Natural adventure, transient tranquility" },
  { code: "#Light 14", name: "Studio Silhouette Key", mood: "Pure graphic outline, anonymous menace" },
];

export const DEFAULT_ACTING = [
  { code: "#Act 01", name: "Subtle Micro-Expression", category: "Emotional Subtext" },
  { code: "#Act 02", name: "Stoic Hardened Gaze", category: "Dramatic Resolve" },
  { code: "#Act 03", name: "Explosive Panic & Breathing", category: "High Adrenaline" },
  { code: "#Act 04", name: "Method Restrained Anger", category: "Simmering Conflict" },
  { code: "#Act 05", name: "Whispered Vulnerability", category: "Intimacy" },
  { code: "#Act 06", name: "Sardonic Smirk & Tilt", category: "Charisma" },
  { code: "#Act 07", name: "Disoriented Concussion Stumble", category: "Physical Trauma" },
  { code: "#Act 08", name: "Combat Stance Weapon Ready", category: "Action Tactical" },
];

export const DEFAULT_CAMERAS = [
  { code: "#Cam 01", name: "Slow Anamorphic Push-In", movement: "Dolly Forward" },
  { code: "#Cam 02", name: "Low-Angle Hero Arc", movement: "Orbital Crane" },
  { code: "#Cam 03", name: "Orbital Steadicam 360", movement: "Dynamic Steadicam" },
  { code: "#Cam 04", name: "Whip Pan Transition", movement: "Kinetic Blur Pan" },
  { code: "#Cam 05", name: "Static Master Horizon", movement: "Locked Tripod" },
  { code: "#Cam 06", name: "Handheld Warzone Shaky", movement: "Visceral Documentary" },
  { code: "#Cam 07", name: "Dutch Canted Vertigo", movement: "Axis Roll 25°" },
  { code: "#Cam 08", name: "Overhead Top-Down God View", movement: "Rigid Crane Down" },
];

export const DEFAULT_LENSES = [
  { code: "#Lens 01", name: "2.0x Anamorphic Prime", focal: "Anamorphic Scope (2.39:1)" },
  { code: "#Lens 02", name: "35mm Spherical Prime", focal: "Human Eye Perspective (f/1.8)" },
  { code: "#Lens 03", name: "85mm Portrait Prime", focal: "Creamy Bokeh Separation (f/1.4)" },
  { code: "#Lens 04", name: "24mm Ultra-Wide Angle", focal: "Expansive Architectural Depth" },
  { code: "#Lens 05", name: "135mm Heavy Telephoto", focal: "Compressed Distance & Stalking" },
  { code: "#Lens 06", name: "Tilt-Shift Miniature", focal: "Selective Plane Diorama" },
];

export const DEFAULT_COMPOSITIONS = [
  { code: "#Comp 01", name: "Rule of Thirds", framing: "Classic balanced intersections" },
  { code: "#Comp 02", name: "Golden Spiral (Fibonacci)", framing: "Curved visual focus flow" },
  { code: "#Comp 03", name: "Central Kubrick Symmetry", framing: "One-point vanishing corridor" },
  { code: "#Comp 04", name: "Frame Within A Frame", framing: "Doorway / Window geometry" },
  { code: "#Comp 05", name: "Leading Lines", framing: "Architectural vector focus" },
  { code: "#Comp 06", name: "Deep Focus Multi-Plane", framing: "f/11 Hyperfocal sharpness" },
];

export const DEFAULT_SPEEDS = [
  { code: "#Speed 01", name: "24fps Cinematic Standard", fps: 24, timing: "Standard cinema cadence" },
  { code: "#Speed 02", name: "Subtle Organic Drift", fps: 24, timing: "0.2 m/s breathing drift" },
  { code: "#Speed 03", name: "High-Octane Action Track", fps: 24, timing: "3.5 m/s fast dynamic sweep" },
  { code: "#Speed 04", name: "60fps Smooth Slow-Motion", fps: 60, timing: "2.5x cinematic deceleration" },
  { code: "#Speed 05", name: "120fps Ultra Slow-Motion", fps: 120, timing: "5.0x fluid bullet-time capture" },
];
