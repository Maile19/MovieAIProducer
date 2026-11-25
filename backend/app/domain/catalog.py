"""Master Hollywood Prompt Engineering Catalog & Technical Matrices.

Defines the standard codes and specifications for visual styles, lighting,
acting, camera movement, optical lenses, composition geometry, and motion speeds.
"""

from typing import Any

STYLE_CATALOG: list[dict[str, str]] = [
    {
        "code": "#Style 01",
        "name": "Transformers / Michael Bay",
        "family": "photorealistic",
        "aesthetic_directives": "High-contrast anamorphic flare, metallic sheen, low-angle hero rotation, saturated golden hour, debris-laden air.",
        "color_grade_emulation": "Teal and orange color grade, Kodak 5219 film stock, heavy tungsten edge lighting.",
    },
    {
        "code": "#Style 02",
        "name": "Hollywood IMAX 70mm",
        "family": "photorealistic",
        "aesthetic_directives": "Pristine ultra-high resolution, deep dynamic range, lifelike skin pores, massive spatial depth, crisp shadow detail.",
        "color_grade_emulation": "Naturalistic color timing, 65mm sensor reproduction, zero artificial vignette.",
    },
    {
        "code": "#Style 03",
        "name": "Bollywood Grand",
        "family": "photorealistic",
        "aesthetic_directives": "Opulent color saturation, theatrical wind machines, sweeping crane movements, warm golden light, rich textile textures.",
        "color_grade_emulation": "Saturated jewel tones (crimson, emerald, gold), high-key fill, warm diffusion filtering.",
    },
    {
        "code": "#Style 04",
        "name": "Xianxia / Chinese Historical",
        "family": "photorealistic",
        "aesthetic_directives": "Ethereal mist, floating silk physics, pastel atmospheric scattering, elegant swordplay choreography, tranquil balance.",
        "color_grade_emulation": "Desaturated ink-wash wash, jade and porcelain tones, soft high-key diffusion.",
    },
    {
        "code": "#Style 05",
        "name": "K-Drama High-End",
        "family": "photorealistic",
        "aesthetic_directives": "Flawless porcelain skin tones, soft-focus shallow depth, gentle naturalistic backlighting, melancholic cityscapes.",
        "color_grade_emulation": "Pastel cyan and warm peach grading, creamy bokeh highlights, pristine commercial gloss.",
    },
    {
        "code": "#Style 06",
        "name": "Donghua 3D",
        "family": "stylized_3d",
        "aesthetic_directives": "Hyper-detailed stylized 3D animation, photorealistic particle effects, dynamic magical illumination, stylized anime proportions.",
        "color_grade_emulation": "Vibrant saturated neon and spiritual hues, sharp specular highlights, clean CGI rendering.",
    },
    {
        "code": "#Style 07",
        "name": "Epic High Fantasy",
        "family": "photorealistic",
        "aesthetic_directives": "Weathered leather, authentic chainmail reflection, ancient moss-covered masonry, sweeping Nordic landscape horizons.",
        "color_grade_emulation": "Desaturated earthen tones, muted greens, cold steel blues, overcast northern European lighting.",
    },
    {
        "code": "#Style 08",
        "name": "Sinema Nusantara",
        "family": "photorealistic",
        "aesthetic_directives": "Tropical humidity haze, warm bamboo and teak wood textures, practical oil-lamp glows, earthy tactile realism.",
        "color_grade_emulation": "Organic sepia and deep tropical greens, warm tungsten shadows, authentic South East Asian realism.",
    },
    {
        "code": "#Style 09",
        "name": "Pixar / Disney 3D Animation",
        "family": "stylized_3d",
        "aesthetic_directives": "Exaggerated emotive facial shapes, subsurface scattering on skin, rich whimsical lighting, charming physical squash-and-stretch.",
        "color_grade_emulation": "Warm primary color harmonies, velvety shadows, clean ray-traced global illumination.",
    },
    {
        "code": "#Style 10",
        "name": "DreamWorks / Illumination",
        "family": "stylized_3d",
        "aesthetic_directives": "Snappy comedic character timing, expressive cartoon eyes, tactile stylized materials, punchy visual gags.",
        "color_grade_emulation": "High-contrast vibrant saturated primaries, crisp rim highlights, energetic bounce lighting.",
    },
    {
        "code": "#Style 11",
        "name": "Arcane (2.5D Steampunk)",
        "family": "stylized_3d",
        "aesthetic_directives": "Painterly brushstroke textures mapped onto dynamic 3D geometry, graphic novel outlines, gritty steampunk industrialism.",
        "color_grade_emulation": "Monochromatic grime punctuated by glowing neon purples and hextech blues, rough oil-paint finishes.",
    },
    {
        "code": "#Style 12",
        "name": "Unreal Engine 5 Metahuman",
        "family": "photorealistic",
        "aesthetic_directives": "Real-time raytracing, nanite micro-polygon geometry, lumen dynamic global illumination, flawless synthetic human fidelity.",
        "color_grade_emulation": "Neutral digital calibration, physical camera sensor emulation, precise roughness map reflections.",
    },
    {
        "code": "#Style 13",
        "name": "Stop-Motion Animation",
        "family": "stop_motion",
        "aesthetic_directives": "Tactile plasticine / clay textures, visible fingerprint impressions, armature joint tension, 12 fps stepped motion cadence.",
        "color_grade_emulation": "Studio miniature warm spotlights, macro depth of field falloff, physical miniature set materials.",
    },
    {
        "code": "#Style 14",
        "name": "Classic 2D Cartoon",
        "family": "anime_2d",
        "aesthetic_directives": "Hand-drawn cel animation, ink line art with variable weighting, flat color fills, vintage multi-plane camera parallax.",
        "color_grade_emulation": "1990s retro animation palette, soft paper texture overlay, zero 3D shading artifacts.",
    },
    {
        "code": "#Style 15",
        "name": "Anime (Shinkai / Ufotable)",
        "family": "anime_2d",
        "aesthetic_directives": "Hyper-detailed sky cloud formations, photorealistic god rays, radiant lens flares, expressive hand-drawn emotional eyes.",
        "color_grade_emulation": "Luminous ultramarine blues, sunset magentas, glistening water reflections, cinematic anime polish.",
    },
    {
        "code": "#Style 16",
        "name": "Studio Ghibli",
        "family": "anime_2d",
        "aesthetic_directives": "Lush watercolor nature backgrounds, painterly flora, whimsical wind gusts, gentle nostalgic warmth, hand-painted cels.",
        "color_grade_emulation": "Earthy greens, gentle cerulean blues, soft eggshell whites, warm childhood nostalgia grading.",
    },
    {
        "code": "#Style 17",
        "name": "Dark Graphic Novel",
        "family": "anime_2d",
        "aesthetic_directives": "Heavy black ink shadows (chiaroscuro), stark angular silhouettes, stylized rain downpours, hard-boiled detective noir.",
        "color_grade_emulation": "High-contrast monochrome black-and-white accented by single spot colors (blood red, toxic yellow).",
    },
    {
        "code": "#Style 18",
        "name": "Vintage Film (1970s Technicolor)",
        "family": "photorealistic",
        "aesthetic_directives": "Organic heavy grain structure, chromatic aberration around frame perimeters, faded dye couplers, authentic gate weave.",
        "color_grade_emulation": "Warm faded yellows, sepia skin tones, cyan shadows, authentic 35mm archival print texture.",
    },
]

LIGHTING_MATRIX: list[dict[str, str]] = [
    {
        "code": "#Light 01",
        "name": "Golden Hour Backlit",
        "technical_specifications": "Low-angle sun at 5° elevation, 2800K golden warmth, rim light enveloping subject silhouette, long dramatic cast shadows.",
        "mood_application": "Nostalgic longing, triumphant return, romantic reverie.",
    },
    {
        "code": "#Light 02",
        "name": "Volumetric God Rays",
        "technical_specifications": "Collimated sunbeams penetrating dense atmospheric haze/dust, 4500K beam contrast against 3000K ambient shadows.",
        "mood_application": "Spiritual epiphany, grand revelation, ancient temple mystery.",
    },
    {
        "code": "#Light 03",
        "name": "Low-Key Chiaroscuro",
        "technical_specifications": "8:1 Key-to-fill ratio, 3200K single hard key source, deep black unilluminated negative space, Rembrandt facial triangle.",
        "mood_application": "Psychological suspense, moral conflict, interrogation, classic noir.",
    },
    {
        "code": "#Light 04",
        "name": "Silvery Blue Moonlight",
        "technical_specifications": "6500K cool diffused overhead key, soft 2:1 fill, deep midnight cyan shadows, subtle specular catchlights in eye pupils.",
        "mood_application": "Vulnerable isolation, clandestine rendezvous, midnight dread.",
    },
    {
        "code": "#Light 05",
        "name": "Flickering Torch / Candle",
        "technical_specifications": "1800K dynamic flame luminance, random 4–8Hz flickering frequency, rapid light falloff conforming to inverse-square law.",
        "mood_application": "Medieval dungeon, intimate sanctuary, primal fear of darkness.",
    },
    {
        "code": "#Light 06",
        "name": "Neon Cyberpunk",
        "technical_specifications": "Saturated dual-complementary neon sources (cyan 480nm & magenta 650nm), wet pavement specular reflections.",
        "mood_application": "Urban alienation, futuristic crime underworld, dystopian noir.",
    },
    {
        "code": "#Light 07",
        "name": "Overcast Soft",
        "technical_specifications": "Fully diffused 6000K skylight through dense cloud deck, near-zero cast shadows, smooth tonal gradients across skin.",
        "mood_application": "Realism, somber melancholy, military procedural neutrality.",
    },
    {
        "code": "#Light 08",
        "name": "Harsh Midday",
        "technical_specifications": "Zenith sun at 90° elevation, 5800K blinding intensity, deep black racoon shadows under eye sockets and jawline.",
        "mood_application": "Bleak desert survival, brutalist interrogation, exposed vulnerability.",
    },
    {
        "code": "#Light 09",
        "name": "Practical Headlights",
        "technical_specifications": "Twin hard 4000K tungsten automotive beams cutting through rain/fog, blinding direct flares into camera lens, dark silhouettes.",
        "mood_application": "Impending vehicular catastrophe, rural roadblock, ominous pursuit.",
    },
    {
        "code": "#Light 10",
        "name": "High-Key Ethereal",
        "technical_specifications": "Low contrast 1.5:1 ratio, overexposed background by +2 EV, soft wrapping daylight, sparkling micro-particulate scatter.",
        "mood_application": "Dream sequences, heavenly transition, idyllic memory recollection.",
    },
    {
        "code": "#Light 11",
        "name": "Lightning Flash",
        "technical_specifications": "Instantaneous 10000K cold xenon burst lasting 2 frames, instantaneous hard shadow shifting, followed by absolute pitch black.",
        "mood_application": "Visceral terror, climactic thunderstorm combat, sudden shock.",
    },
    {
        "code": "#Light 12",
        "name": "Clinical Cold Sci-Fi",
        "technical_specifications": "Overhead fluorescent ceiling grids, 6500K sterile white with slight green spike, uniform shadowless illumination.",
        "mood_application": "Lab experimentation, totalitarian control, emotionless bureaucracy.",
    },
    {
        "code": "#Light 13",
        "name": "Dappled Forest",
        "technical_specifications": "Canopy-filtered sunlight creating organic moving fractal patterns across subject face, warm 4000K spots against 5200K shade.",
        "mood_application": "Wilderness journey, hidden refuge, psychological awakening.",
    },
    {
        "code": "#Light 14",
        "name": "Silhouette Against Fire",
        "technical_specifications": "Blazing 1500K raging inferno behind subject, camera exposing for flames, plunging foreground subject into total jet-black silhouette.",
        "mood_application": "Total destruction, villainous emergence, irreversible tragedy.",
    },
]

ACTING_MATRIX: list[dict[str, str]] = [
    {"code": "#Act 01", "cue": "Suppressed Trauma", "micro_expressions": "Tightened orbicularis oris, rigid neck tendons, gaze fixated on middle distance, refusal to blink.", "dramatic_context": "Hearing an unexpected truth, bearing witness to past horror."},
    {"code": "#Act 02", "cue": "Cold Calculation", "micro_expressions": "Narrowed eyelids, subtle slow pupil sweep across room, flat heart-rate rhythm, zero head tilt.", "dramatic_context": "Strategist anticipating an adversary’s ambush."},
    {"code": "#Act 03", "cue": "Primal Rage", "micro_expressions": "Flared nostrils, bared canine teeth, veins pulsing at temple, rapid chest heaving, hyper-focused gaze.", "dramatic_context": "Climax physical confrontation, betrayal realization."},
    {"code": "#Act 04", "cue": "Quiet Melancholy", "micro_expressions": "Soft downward eye saccade, slow shallow exhalation through slightly parted lips, slack facial musculature.", "dramatic_context": "Solitary aftermath of loss, accepting unrequited love."},
    {"code": "#Act 05", "cue": "Paranoid Dread", "micro_expressions": "Rapid jittery eye movements, micro-turning of ears toward ambient sounds, hunched shoulders, tight throat swallowing.", "dramatic_context": "Trapped in enemy territory, hunted in the shadows."},
    {"code": "#Act 06", "cue": "Heroic Resolve", "micro_expressions": "Firmly set jaw, steady direct gaze locking on horizon, relaxed posture with grounded combat stance.", "dramatic_context": "Stepping forward to sacrifice self for the collective."},
    {"code": "#Act 07", "cue": "Cynical Amusement", "micro_expressions": "Asymmetrical smirk on left lip corner, single raised eyebrow, sarcastic head tilt, amused twinkle in eyes.", "dramatic_context": "Anti-hero outsmarting an arrogant official."},
    {"code": "#Act 08", "cue": "Shock and Awe", "micro_expressions": "Jaw dropped in paralysis, dilated pupils catching light, sudden intake of breath held stationary in lungs.", "dramatic_context": "Witnessing cosmic catastrophe or supernatural arrival."},
    {"code": "#Act 09", "cue": "Intimate Vulnerability", "micro_expressions": "Soft hesitant smile breaking across lips, trembling eye gaze dropping to partner’s lips then rising.", "dramatic_context": "Confession of truth in a quiet bedroom sanctuary."},
    {"code": "#Act 10", "cue": "Complete Breakdown", "micro_expressions": "Facial contortion into weeping, trembling hands attempting to cover face, loss of physical posture integrity.", "dramatic_context": "Discovering the death of an irreplaceable companion."},
    {"code": "#Act 11", "cue": "Stoic Endurance", "micro_expressions": "Face weathered and emotionless, absorbing physical pain with clenched teeth, steady breathing cadence.", "dramatic_context": "Wounded soldier walking through an artillery blizzard."},
    {"code": "#Act 12", "cue": "Deceptive Charm", "micro_expressions": "Warm wide crinkled smile reaching crows-feet at eyes, open relaxed palms, predatory stillness beneath the warmth.", "dramatic_context": "Antagonist manipulating protagonist during dinner."},
    {"code": "#Act 13", "cue": "Total Exhaustion", "micro_expressions": "Drooping eyelids, heavy head sinking downward, trembling lower lip, slow slurred speech delivery.", "dramatic_context": "Reaching the finish line after a 50-mile desert march."},
    {"code": "#Act 14", "cue": "Euphoric Triumph", "micro_expressions": "Thrown-back head, chest fully expanded, roaring open-mouth laugh, tear of joy tracing cheek.", "dramatic_context": "Victory in the final championship or battle triumph."},
    {"code": "#Act 15", "cue": "Disgust / Repulsion", "micro_expressions": "Curled upper lip showing front teeth, wrinkled nasal bridge, instinctive backward recoil of head.", "dramatic_context": "Uncovering a grotesque crime scene or poisoned chalice."},
    {"code": "#Act 16", "cue": "Moral Hesitation", "micro_expressions": "Hand pausing halfway to weapon, eyes darting between target and innocent bystander, conflicting facial muscle tension.", "dramatic_context": "Sniper deciding whether to pull trigger on flawed intel."},
    {"code": "#Act 17", "cue": "Hypnotic Trance", "micro_expressions": "Unfocused glassy eyes, slack jaw, slow rhythmic swaying, complete absence of natural startle reflex.", "dramatic_context": "Mind control, psychic takeover, alien communication."},
    {"code": "#Act 18", "cue": "Panic Attack", "micro_expressions": "Hyperventilating chest heave, wide unblinking eyes, trembling fingers grasping throat, beads of cold sweat on forehead.", "dramatic_context": "Trapped in an elevator losing oxygen rapidly."},
    {"code": "#Act 19", "cue": "Seductive Playfulness", "micro_expressions": "Tilted head looking up through eyelashes, gentle bite of lower lip, deliberate slow cat-like movement.", "dramatic_context": "Espionage operative extracting codes at high-society gala."},
    {"code": "#Act 20", "cue": "Contemptuous Dismissal", "micro_expressions": "Half-closed eyes looking down bridge of nose, tiny dismissive puff of air from nostrils, turned shoulder.", "dramatic_context": "Royalty addressing an insolent commoner."},
    {"code": "#Act 21", "cue": "Sudden Realization", "micro_expressions": "Widening eyes with sudden micro-nod, lips parting in silent vocalization, quick head snap toward clue.", "dramatic_context": "Detective piecing together the killer’s fatal mistake."},
    {"code": "#Act 22", "cue": "Physical Agony", "micro_expressions": "Writhing neck muscles, tightly squeezed shut eyelids with tear leakage, gritted teeth with guttural groan.", "dramatic_context": "Field surgery without anesthesia, extracting shrapnel."},
    {"code": "#Act 23", "cue": "Guilt and Remorse", "micro_expressions": "Downcast averted eyes unable to look at victim, hunched spine, nervous wringing of hands.", "dramatic_context": "Confessing a lie that caused catastrophic damage."},
    {"code": "#Act 24", "cue": "Transcendent Peace", "micro_expressions": "Serene neutral expression, faint tranquil smile, slow gentle breathing, relaxed shoulders welcoming fate.", "dramatic_context": "The dying hero watching the sun rise over a liberated city."},
]

CAMERA_MATRIX: list[dict[str, str]] = [
    {"code": "#Cam 01", "name": "Extreme Close-Up", "description": "ECU - Eyes/Mouth tight macro focus"},
    {"code": "#Cam 02", "name": "Close-Up", "description": "CU - Head & Neck framing"},
    {"code": "#Cam 03", "name": "Medium Close-Up", "description": "MCU - Chest Up perspective"},
    {"code": "#Cam 04", "name": "Medium Shot", "description": "MS - Waist Up dialogue framing"},
    {"code": "#Cam 05", "name": "Cowboy Shot", "description": "American - Mid-Thigh Up holstered stance"},
    {"code": "#Cam 06", "name": "Full Shot", "description": "FS - Head to Toe character introduction"},
    {"code": "#Cam 07", "name": "Wide Shot", "description": "WS - Complete Environment spatial relation"},
    {"code": "#Cam 08", "name": "Extreme Wide Shot", "description": "EWS - Epic Scale panoramic vista"},
    {"code": "#Cam 09", "name": "Bird's Eye View", "description": "Overhead 90° Zenith omniscient perspective"},
    {"code": "#Cam 10", "name": "Worm's Eye View", "description": "Ground Level 90° Up imposing authority"},
    {"code": "#Cam 11", "name": "Over-The-Shoulder", "description": "OTS - Dialogue conversational geography"},
    {"code": "#Cam 12", "name": "Point of View", "description": "POV - First Person subjective lens"},
    {"code": "#Cam 13", "name": "Low-Angle Hero Shot", "description": "Looking Up 30° majestic power stance"},
    {"code": "#Cam 14", "name": "High-Angle Vulnerability", "description": "Looking Down 30° diminished status"},
    {"code": "#Cam 15", "name": "Dutch Angle Tilt", "description": "Canted camera axis signaling vertigo or psychological disarray"},
    {"code": "#Cam 16", "name": "Profile Side Silhouette", "description": "Lateral 90° contour framing"},
    {"code": "#Cam 17", "name": "Frontal Symmetrical Master", "description": "One-point linear perspective centered horizon"},
    {"code": "#Cam 18", "name": "Tracking Shot", "description": "Dolly Sideways parallel tracking lateral motion"},
    {"code": "#Cam 19", "name": "Dolly-In", "description": "Emotional Push forward emphasizing realization"},
    {"code": "#Cam 20", "name": "Dolly-Out", "description": "Isolation Reveal moving backward abandoning subject"},
    {"code": "#Cam 21", "name": "Crane / Jib Sweeping Overhead", "description": "Grand vertical ascent revealing sprawling battlefield"},
    {"code": "#Cam 22", "name": "Whip Pan", "description": "Fast kinetic blur transition between subjects"},
    {"code": "#Cam 23", "name": "360-Degree Orbital Arc", "description": "Circular camera orbit locking center axis"},
    {"code": "#Cam 24", "name": "Steadicam Forward Push", "description": "Fluid walking pace following character into interior"},
    {"code": "#Cam 25", "name": "Handheld Shaky-Cam", "description": "Visceral documentary warzone realism"},
    {"code": "#Cam 26", "name": "Crash Zoom", "description": "Sudden dramatic focal shift mimicking 1970s kung fu snap"},
    {"code": "#Cam 27", "name": "Rack Focus", "description": "Shifting Depth from FG obstacle to BG subject"},
    {"code": "#Cam 28", "name": "Snorricam", "description": "Body-Mounted Subject Lock experiencing drunken disorientation"},
    {"code": "#Cam 29", "name": "Split-Diopter Dual Plane Focus", "description": "Simultaneous tack-sharp focus on near FG and far BG"},
    {"code": "#Cam 30", "name": "Drone Panoramic Flyover", "description": "Aerial terrain sweep surveying vast landscape"},
    {"code": "#Cam 31", "name": "Two-Shot", "description": "Balanced Profile Dynamic pairing duo in conflict or intimacy"},
    {"code": "#Cam 32", "name": "Crowd Ensemble Master", "description": "Choreographed multi-subject interaction"},
    {"code": "#Cam 33", "name": "Atmospheric Establishing Master", "description": "Setting tone, climate, and geography for sequence"},
    {"code": "#Cam 34", "name": "Microscopic Macro Insert", "description": "Super close-up on needle touching vinyl or eye pupil dial"},
]

LENS_MATRIX: list[dict[str, str]] = [
    {
        "code": "#Lens 01",
        "name": "2.0x Anamorphic Prime",
        "optical_physics": "Horizontal blue/streak lens flares, oval out-of-focus bokeh discs, slight barrel distortion at edges.",
        "visual_field": "2.39:1 widescreen scope, cinematic Hollywood film grandeur.",
    },
    {
        "code": "#Lens 02",
        "name": "35mm Spherical Prime",
        "optical_physics": "Minimal distortion, organic human eye perspective field, smooth spherical bokeh falloff, f/1.8 aperture.",
        "visual_field": "Environmental character framing, conversational realism.",
    },
    {
        "code": "#Lens 03",
        "name": "85mm Portrait Prime",
        "optical_physics": "Tight telephoto background compression, creamy bokeh melting background into abstract color, f/1.4 aperture.",
        "visual_field": "Heroic close-up isolation, dramatic emotional intimacy.",
    },
    {
        "code": "#Lens 04",
        "name": "24mm Ultra-Wide Angle",
        "optical_physics": "Exaggerated spatial depth, dynamic perspective lines, dynamic foreground emphasis, slight edge distortion.",
        "visual_field": "Majestic architectural scale, dynamic action choreography.",
    },
    {
        "code": "#Lens 05",
        "name": "135mm Heavy Telephoto",
        "optical_physics": "Severe background spatial compression, flattening distance between foreground subject and background threat.",
        "visual_field": "Sniper line-of-sight, tense pursuit, claustrophobic crowds.",
    },
    {
        "code": "#Lens 06",
        "name": "Tilt-Shift Miniature",
        "optical_physics": "Selected plane of focus across diagonal axis, selective blur producing miniature diorama illusion.",
        "visual_field": "Surreal disorientation, omniscient surveillance god-view.",
    },
]

COMPOSITION_MATRIX: list[dict[str, str]] = [
    {"code": "#Comp 01", "name": "Rule of Thirds", "description": "Key facial features and horizons aligned along 1/3 and 2/3 coordinate intersections."},
    {"code": "#Comp 02", "name": "Golden Spiral (Fibonacci)", "description": "Dynamic logarithmic curve leading eye from environmental periphery to micro-detail."},
    {"code": "#Comp 03", "name": "Central Symmetry", "description": "Exact geometric centering of subject; Kubrick-style one-point linear perspective."},
    {"code": "#Comp 04", "name": "Leading Lines", "description": "Structural architecture (railways, corridors, bridges) forcing eye vector to vanishing point."},
    {"code": "#Comp 05", "name": "180-Degree Action Line", "description": "Rigid spatial camera positioning preserving screen direction between shots."},
    {"code": "#Comp 06", "name": "Frame Within a Frame", "description": "Subject framed inside doorways, broken arches, windows, or rear-view mirrors."},
    {"code": "#Comp 07", "name": "Dutch Angle (Canted)", "description": "15° to 30° roll on camera axis, creating psychological vertigo and systemic disorder."},
    {"code": "#Comp 08", "name": "Deep Focus Mise-en-Scène", "description": "f/11 hyperfocal aperture keeping foreground, midground, and background tack sharp."},
]

SPEED_MATRIX: list[dict[str, str]] = [
    {"code": "#Speed 01", "name": "Static / Locked-Off", "description": "Zero camera movement. Micro-movements strictly limited to blinking, smoke, and breathing."},
    {"code": "#Speed 02", "name": "Subtle Organic Drift", "description": "Micro-Steadicam breathing drift (0.2 m/s). Soft naturalistic character repositioning."},
    {"code": "#Speed 03", "name": "Cinematic Paced", "description": "Deliberate smooth dolly movement (1.0 m/s). Purposeful narrative pacing."},
    {"code": "#Speed 04", "name": "High-Octane Action", "description": "Rapid camera pan and tracking (3.5 m/s). Fast combat choreography and chase dynamics."},
    {"code": "#Speed 05", "name": "Hyper-Speed / Time-Lapse", "description": "Time acceleration or high-speed slow-motion (120 fps burst capture)."},
]


def get_full_matrix_catalog() -> dict[str, list[dict[str, Any]]]:
    """Return the aggregated Hollywood matrix catalog."""
    return {
        "styles": STYLE_CATALOG,
        "lighting": LIGHTING_MATRIX,
        "acting": ACTING_MATRIX,
        "cameras": CAMERA_MATRIX,
        "lenses": LENS_MATRIX,
        "compositions": COMPOSITION_MATRIX,
        "speeds": SPEED_MATRIX,
    }


_LAYER_CATALOG_MAP: dict[str, list[dict[str, str]]] = {
    "style": STYLE_CATALOG,
    "style_code": STYLE_CATALOG,
    "camera": CAMERA_MATRIX,
    "camera_code": CAMERA_MATRIX,
    "cam": CAMERA_MATRIX,
    "lens": LENS_MATRIX,
    "lens_code": LENS_MATRIX,
    "comp": COMPOSITION_MATRIX,
    "comp_code": COMPOSITION_MATRIX,
    "composition": COMPOSITION_MATRIX,
    "composition_code": COMPOSITION_MATRIX,
    "light": LIGHTING_MATRIX,
    "light_code": LIGHTING_MATRIX,
    "lighting": LIGHTING_MATRIX,
    "lighting_code": LIGHTING_MATRIX,
    "act": ACTING_MATRIX,
    "act_code": ACTING_MATRIX,
    "action": ACTING_MATRIX,
    "action_code": ACTING_MATRIX,
    "speed": SPEED_MATRIX,
    "speed_code": SPEED_MATRIX,
}

_LAYER_VALID_CODES: dict[str, set[str]] = {
    layer_key: {item["code"] for item in entries if item.get("code")}
    for layer_key, entries in _LAYER_CATALOG_MAP.items()
}

_LAYER_CANONICAL_LOOKUP: dict[str, dict[str, str]] = {
    layer_key: {item["code"].lower(): item["code"] for item in entries if item.get("code")}
    for layer_key, entries in _LAYER_CATALOG_MAP.items()
}


def validate_matrix_code(layer: str, code: str | None) -> str | None:
    """Validate and canonicalize a matrix code against catalog.py.

    Accepts None or empty string cleanly for partial updates; raises ValueError on malformed codes.
    """
    if code is None:
        return None
    cleaned = code.strip()
    if not cleaned:
        return ""
    norm_layer = (layer or "").strip().lower()
    canonical_map = _LAYER_CANONICAL_LOOKUP.get(norm_layer)
    valid_codes = _LAYER_VALID_CODES.get(norm_layer)
    if canonical_map is None or valid_codes is None:
        raise ValueError(f"Unknown matrix layer '{layer}'")
    canonical = canonical_map.get(cleaned.lower())
    if canonical is None:
        ordered = sorted(valid_codes)
        raise ValueError(
            f"Invalid {layer} matrix code '{code}'. Expected canonical code ({ordered[0]}..{ordered[-1]})."
        )
    return canonical
