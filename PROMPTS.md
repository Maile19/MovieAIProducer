# Hollywood Prompt Engineering Catalog - MovieAIProducer

> Master catalog of Hollywood-standard prompt templates, cinematic matrices, optical physics directives, and DNA locking tokens for AI film production.

MovieAIProducer translates structured pre-production decisions from the Master Production Bible (MPB) into platform-executable prompt specifications. This document defines the prompt schemas for each step of the 12-Step Cinematic Pipeline, followed by the complete code matrices governing style, lighting, performance, camera optics, composition, and motion.

---

## 1. Anatomy of a Hollywood Cinematic Prompt

Generative video models (Runway Gen-3, Kling 1.5, Google Veo, OpenAI Sora) require strict structural syntax to minimize hallucinatory artifacts and visual drift. Every generated shot prompt compiles through this unified schema:

```text
[SHOT TYPE & COMPOSITION] + [OPTICAL PHYSICS & LENS] + [SUBJECT & CHARACTER DNA] +
[ACTION & PERFORMANCE (#Act)] + [ENVIRONMENT (#Env) & PROPS (#Prop)] +
[LIGHTING & ATMOSPHERE (#Light)] + [FOREGROUND/BACKGROUND MOTION (#FG/#BG) & SPEED (#Speed)] +
[VISUAL STYLE (#Style)] + [AUDIO TIMING (J/L-Cut)]
```

### Compiler Variables & DNA Token Locking

When compiling prompts, immutable DNA variables are extracted directly from the MPB:

- `{{CHARACTER_DNA_<ID>}}`: Physical descriptors, ethnic markers, eye color, facial hair, skin texture, and height.
- `{{STATE_PROFILE}}`: Dynamic physical condition and wardrobe integrity (`#State 01-05`).
- `{{ENV_DNA_<ID>}}`: Persistent spatial geometry, architecture, wall textures, and atmospheric haze.
- `{{PROP_DNA_<ID>}}`: Hero prop material, wear patterns, and scale.
- `{{STYLE_DIRECTIVE}}`: Aesthetic color grading, grain profile, and sensor response curve.

---

## 2. 12-Step Prompt Generation Templates

### Step 1: Genre, Emotion & Aspect Ratio Definition

```markdown
PROJECT CREATIVE DNA SPECIFICATION:

- Title: {{PROJECT_TITLE}}
- Primary Genre: {{PRIMARY_GENRE}}
- Sub-Genre: {{SUB_GENRE}} (e.g., Cyberpunk Neo-Noir, Supernatural Horror)
- Core Emotional Arc: {{DOMINANT_EMOTION}} (e.g., Claustrophobic Dread transitioning to Defiant Catharsis)
- Aspect Ratio: {{ASPECT_RATIO}} (16:9 Cinema 2.39:1 Anamorphic OR 9:16 Mobile Vertical 1.78:1)
- Target Pacing: {{PACING_PROFILE}} (50 Scenes total, calibrated strictly to 5.0 seconds per scene)
```

### Step 2: Visual Style Catalog Specification

```markdown
VISUAL AESTHETIC DIRECTIVE:

- Master Style Code: {{STYLE_CODE}} (Select from #Style 01 through #Style 18)
- Rendering Pipeline: {{RENDER_PIPELINE}} (Photorealistic 35mm Film Grain / 2.5D Stylized / UE5 Metahuman)
- Color Palette: {{COLOR_PALETTE}} (Primary, Secondary, Contrast Accents)
- Sensor / Film Emulation: {{FILM_EMULATION}} (Kodak Vision3 500T, Arri Alexa 65 sensor, IMAX 70mm print)
```

### Step 3: Story Ideation & 4-Act 50-Scene Blueprint

```markdown
NARRATIVE ARCHITECTURE SPECIFICATION:

- Logline: {{LOGLINE}}
- Dramatic Structure: 4-Act Hollywood Arc
  - Act I: The Setup (Scenes 01–12) - Inciting Incident at Scene 06, Plot Point 1 at Scene 12.
  - Act II-A: Rising Action (Scenes 13–25) - Midpoint Reversal at Scene 25.
  - Act II-B: Descent & Dark Night of Soul (Scenes 26–38) - All is Lost at Scene 35, Plot Point 2 at Scene 38.
  - Act III & IV: Climax & Resolution (Scenes 39–50) - Climax at Scene 45, Final Resolution at Scene 50.
- Scene Blueprint Matrix:
  - Scene {{SCENE_NUM}}: Slugline: {{INT_EXT}} {{LOCATION}} - {{TIME_OF_DAY}} | Dramatic Beat: {{DRAMATIC_BEAT}}
```

### Step 4: Character Sheets, Voice DNA & State Evolution

```markdown
CHARACTER PROFILE & DNA SPECIFICATION:

- Character ID: {{CHAR_ID}} (e.g., PROTAGONIST_01)
- Name & Archetype: {{NAME}}, {{ARCHETYPE}}
- Visual DNA Seed: {{BASE_AGE}}, {{GENDER}}, {{ETHNICITY}}, {{FACIAL_FEATURES}}, {{HAIR_STYLE_COLOR}}, {{BODY_BUILD}}
- Voice DNA Profile: Pitch: {{VOICE_PITCH}}, Cadence: {{VOICE_CADENCE}}, Accent: {{ACCENT}}, Emotion: {{VOCAL_TIMBRE}}
- Dynamic State Evolution:
  - Current Scene State: {{STATE_CODE}} (#State 01 Pristine / #State 02 Fatigued / #State 03 Damaged / #State 04 Exhausted / #State 05 Climax)
  - Wardrobe & Damage Condition: {{WARDROBE_CONDITION}}
```

### Step 5: Extras Character Sheet (Crowd & Figurants)

```markdown
EXTRAS & CROWD DESIGN SPECIFICATION:

- Crowd Cluster ID: {{EXTRAS_GROUP_ID}} (#Extras 01 through #Extras 08)
- Ensemble Size: {{CROWD_SIZE}} (e.g., Intimate 3-person background cluster vs 40-person market crowd)
- Cultural & Period Context: {{CULTURAL_COHERENCE}} (Uniform attire, demographic distribution, accessories)
- Spatial Placement: Secondary layer background, out-of-focus bokeh rendering, zero camera eye-contact.
```

### Step 6: Environment Bible & Key Prop DNA

```markdown
PRODUCTION DESIGN SPECIFICATION:

- Environment ID: {{ENV_CODE}} (#Env 01 through #Env 05)
- Spatial Geography: {{SET_DESCRIPTION}}, Architecture: {{ARCHITECTURAL_STYLE}}, Floor/Wall Material: {{SURFACE_TEXTURE}}
- Environmental Weather / Atmosphere: {{ATMOSPHERIC_CONDITION}} (Air particulate, volumetric haze, rain, dust)
- Hero Prop DNA:
  - Prop ID: {{PROP_CODE}} (#Prop 01 through #Prop 05)
  - Object Specifications: {{PROP_NAME}}, Material: {{PROP_MATERIAL}}, Wear & Tear: {{PROP_PATINA}}
```

### Step 7: Dialogue, Voiceover & Audio Calibration

```markdown
AUDIO & TEMPORAL CALIBRATION SPECIFICATION:

- Scene Duration: Exactly 5.0 seconds (120 frames at 24 fps).
- Dialogue / VO Line: "{{SCRIPT_LINE}}" (Maximum 14 words per 5-second interval).
- Vocal Delivery: Speed: {{WPM_RATE}} WPM, Emotional Stress: {{VOCAL_TENSION}}.
- Acoustic Space: Reverb: {{ACOUSTIC_REVERB}} (Tight interior booth, cathedral echo, damp outdoor concrete).
- Audio Transition Bridge:
  - J-Cut (Audio leads video by 0.8s): Incoming audio element: {{INCOMING_AUDIO}}
  - L-Cut (Video changes, dialogue extends 0.6s): Outgoing tail audio: {{OUTGOING_AUDIO}}
```

### Step 8: Cinematography, Optical Physics & Framing

```markdown
CINEMATOGRAPHY SPECIFICATION:

- Camera Angle & Distance: {{CAMERA_CODE}} (#Cam 01 through #Cam 34)
- Optical Lens Profile: {{LENS_CODE}} (#Lens 01 through #Lens 06)
  - Focal Length: {{FOCAL_LENGTH_MM}} (e.g., 35mm Prime, 85mm Telephoto)
  - Aperture: {{APERTURE}} (f/1.4 shallow depth of field with oval anamorphic bokeh)
- Composition Framing: {{COMPOSITION_CODE}} (#Comp 01 through #Comp 08)
- Spatial Rule: Strict adherence to the 180-Degree Line of Action across Scene {{PREV_SCENE}} and Scene {{CURR_SCENE}}.
```

### Step 9: Cinematic Lighting & Atmosphere

```markdown
LIGHTING DESIGN SPECIFICATION:

- Primary Lighting Style: {{LIGHT_CODE}} (#Light 01 through #Light 14)
- Color Temperature: {{KELVIN_TEMP}} (e.g., 3200K Tungsten warm vs 5600K Daylight clean)
- Key-to-Fill Ratio: {{LIGHTING_RATIO}} (e.g., High-contrast 8:1 chiaroscuro vs low-contrast 2:1 even commercial)
- Volumetric Qualities: Tyndall ray scattering, dust-mote refraction, atmospheric depth falloff.
```

### Step 10: Acting & Facial Performance

```markdown
PERFORMANCE DIRECTIVE:

- Performance Code: {{ACTING_CODE}} (#Act 01 through #Act 24)
- Micro-Expression: {{FACIAL_MICRO_CUE}} (Subtle eye twitch, jaw clench, suppressed sorrow, calculating pupil dilation)
- Gaze Direction: Eye vector fixed at {{GAZE_COORDINATE}} (Maintaining 180-degree sightline continuity)
- Physical Gestural Tension: Breathing cadence: {{BREATHING_RATE}}, Posture: {{PHYSICAL_POSTURE}}
```

### Step 11: Multi-Layer Scene Motion Dynamics

```markdown
MOTION & PARALLAX SPECIFICATION:

- Motion Velocity Profile: {{SPEED_CODE}} (#Speed 01 through #Speed 05)
- Foreground Dynamics (#FG): {{FOREGROUND_ELEMENT}} (Falling rain droplets, drifting debris, passing shoulder silhouette)
- Subject Midground: {{SUBJECT_MOTION}} (Forward tracking velocity, steady directional movement)
- Background Dynamics (#BG): {{BACKGROUND_MOVEMENT}} (Parallax city lights drifting, slow atmospheric smoke swirl)
```

### Step 12: Executable Studio Master Generation Prompt

```markdown
MASTER EXECUTABLE PROMPT TEMPLATE (For Video Engine Dispatch):

[CINEMATOGRAPHY]: {{CAM_CODE}} {{LENS_CODE}}, {{COMP_CODE}}, anamorphic widescreen 2.39:1 aspect ratio, cinematic 8k film still, photorealistic raw footage.
[SUBJECT]: {{CHARACTER_DNA}}, {{STATE_CODE}} condition.
[PERFORMANCE]: {{ACTING_CODE}}, {{PHYSICAL_GESTURE}}, precise eye line locked on target.
[SETTING]: {{ENV_CODE}}, {{PROP_CODE}}, {{ATMOSPHERIC_CONDITION}}.
[LIGHTING]: {{LIGHT_CODE}}, dramatic key light, natural shadows, volumetric depth.
[MOTION]: {{SPEED_CODE}}, multi-layer parallax with {{FG_MOTION}} foreground and {{BG_MOTION}} background drift.
[STYLE]: {{STYLE_CODE}}, Kodak Vision3 film grain, cinematic color timing, zero digital oversaturation.

NEGATIVE PROMPT BASELINE:
cartoonish, plastic skin, CGI render, video game graphics, morphed extra limbs, extra fingers, jittery camera shakes, flickering lighting, continuity jump cuts, text watermarks, oversaturated colors, flat lighting.
```

---

## 3. Style Catalog (#Style 01–#Style 18)

| Code            | Style Name                       | Aesthetic Directives                                                                                                             | Color Grade & Emulation                                                                             |
| :-------------- | :------------------------------- | :------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------- |
| **`#Style 01`** | Transformers / Michael Bay       | High-contrast anamorphic flare, metallic sheen, low-angle hero rotation, saturated golden hour, debris-laden air.                | Teal and orange color grade, Kodak 5219 film stock, heavy tungsten edge lighting.                   |
| **`#Style 02`** | Hollywood IMAX 70mm              | Pristine ultra-high resolution, deep dynamic range, lifelike skin pores, massive spatial depth, crisp shadow detail.             | Naturalistic color timing, 65mm sensor reproduction, zero artificial vignette.                      |
| **`#Style 03`** | Bollywood Grand                  | Opulent color saturation, theatrical wind machines, sweeping crane movements, warm golden light, rich textile textures.          | Saturated jewel tones (crimson, emerald, gold), high-key fill, warm diffusion filtering.            |
| **`#Style 04`** | Xianxia / Chinese Historical     | Ethereal mist, floating silk physics, pastel atmospheric scattering, elegant swordplay choreography, tranquil balance.           | Desaturated ink-wash wash, jade and porcelain tones, soft high-key diffusion.                       |
| **`#Style 05`** | K-Drama High-End                 | Flawless porcelain skin tones, soft-focus shallow depth, gentle naturalistic backlighting, melancholic cityscapes.               | Pastel cyan and warm peach grading, creamy bokeh highlights, pristine commercial gloss.             |
| **`#Style 06`** | Donghua 3D                       | Hyper-detailed stylized 3D animation, photorealistic particle effects, dynamic magical illumination, stylized anime proportions. | Vibrant saturated neon and spiritual hues, sharp specular specularities, clean CGI rendering.       |
| **`#Style 07`** | Epic High Fantasy                | Weathered leather, authentic chainmail reflection, ancient moss-covered masonry, sweeping Nordic landscape horizons.             | Desaturated earthen tones, muted greens, cold steel blues, overcast northern European lighting.     |
| **`#Style 08`** | Sinema Nusantara                 | Tropical humidity haze, warm bamboo and teak wood textures, practical oil-lamp glows, earthy tactile realism.                    | Organic sepia and deep tropical greens, warm tungsten shadows, authentic South East Asian realism.  |
| **`#Style 09`** | Pixar / Disney 3D Animation      | Exaggerated emotive facial shapes, subsurface scattering on skin, rich whimsical lighting, charming physical squash-and-stretch. | Warm primary color harmonies, velvety shadows, clean ray-traced global illumination.                |
| **`#Style 10`** | DreamWorks / Illumination        | Snappy comedic character timing, expressive cartoon eyes, tactile stylized materials, punchy visual gags.                        | High-contrast vibrant saturated primaries, crisp rim highlights, energetic bounce lighting.         |
| **`#Style 11`** | Arcane (2.5D Steampunk)          | Painterly brushstroke textures mapped onto dynamic 3D geometry, graphic novel outlines, gritty steampunk industrialism.          | Monochromatic grime punctuated by glowing neon purples and hextech blues, rough oil-paint finishes. |
| **`#Style 12`** | Unreal Engine 5 Metahuman        | Real-time raytracing, nanite micro-polygon geometry, lumen dynamic global illumination, flawless synthetic human fidelity.       | Neutral digital calibration, physical camera sensor emulation, precise roughness map reflections.   |
| **`#Style 13`** | Stop-Motion Animation            | Tactile plasticine / clay textures, visible fingerprint impressions, armature joint tension, 12 fps stepped motion cadence.      | Studio miniature warm spotlights, macro depth of field falloff, physical miniature set materials.   |
| **`#Style 14`** | Classic 2D Cartoon               | Hand-drawn cel animation, ink line art with variable weighting, flat color fills, vintage multi-plane camera parallax.           | 1990s retro animation palette, soft paper texture overlay, zero 3D shading artifacts.               |
| **`#Style 15`** | Anime (Shinkai / Ufotable)       | Hyper-detailed sky cloud formations, photorealistic god rays, radiant lens flares, expressive hand-drawn emotional eyes.         | Luminous ultramarine blues, sunset magentas, glistening water reflections, cinematic anime polish.  |
| **`#Style 16`** | Studio Ghibli                    | Lush watercolor nature backgrounds, painterly flora, whimsical wind gusts, gentle nostalgic warmth, hand-painted cels.           | Earthy greens, gentle cerulean blues, soft eggshell whites, warm childhood nostalgia grading.       |
| **`#Style 17`** | Dark Graphic Novel               | Heavy black ink shadows (chiaroscuro), stark angular silhouettes, stylized rain downpours, hard-boiled detective noir.           | High-contrast monochrome black-and-white accented by single spot colors (blood red, toxic yellow).  |
| **`#Style 18`** | Vintage Film (1970s Technicolor) | Organic heavy grain structure, chromatic aberration around frame perimeters, faded dye couplers, authentic gate weave.           | Warm faded yellows, sepia skin tones, cyan shadows, authentic 35mm archival print texture.          |

---

## 4. Cinematic Lighting Matrix (#Light 01–#Light 14)

| Code            | Lighting Designation      | Technical Specifications & Photometry                                                                                                 | Cinematic Mood & Application                                           |
| :-------------- | :------------------------ | :------------------------------------------------------------------------------------------------------------------------------------ | :--------------------------------------------------------------------- |
| **`#Light 01`** | Golden Hour Backlit       | Low-angle sun at 5° elevation, 2800K golden warmth, rim light enveloping subject silhouette, long dramatic cast shadows.              | Nostalgic longing, triumphant return, romantic reverie.                |
| **`#Light 02`** | Volumetric God Rays       | Collimated sunbeams penetrating dense atmospheric haze/dust, 4500K beam contrast against 3000K ambient shadows.                       | Spiritual epiphany, grand revelation, ancient temple mystery.          |
| **`#Light 03`** | Low-Key Chiaroscuro       | 8:1 Key-to-fill ratio, 3200K single hard key source, deep black unilluminated negative space, Rembrandt facial triangle.              | Psychological suspense, moral conflict, interrogation, classic noir.   |
| **`#Light 04`** | Silvery Blue Moonlight    | 6500K cool diffused overhead key, soft 2:1 fill, deep midnight cyan shadows, subtle specular catchlights in eye pupils.               | Vulnerable isolation, clandestine rendezvous, midnight dread.          |
| **`#Light 05`** | Flickering Torch / Candle | 1800K dynamic flame luminance, random 4–8Hz flickering frequency, rapid light falloff conforming to inverse-square law.               | Medieval dungeon, intimate sanctuary, primal fear of darkness.         |
| **`#Light 06`** | Neon Cyberpunk            | Saturated dual-complementary neon sources (cyan 480nm & magenta 650nm), wet pavement specular reflections.                            | Urban alienation, futuristic crime underworld, dystopian noir.         |
| **`#Light 07`** | Overcast Soft             | Fully diffused 6000K skylight through dense cloud deck, near-zero cast shadows, smooth tonal gradients across skin.                   | Realism, somber melancholy, military procedural neutrality.            |
| **`#Light 08`** | Harsh Midday              | Zenith sun at 90° elevation, 5800K blinding intensity, deep black racoon shadows under eye sockets and jawline.                       | Bleak desert survival, brutalist interrogation, exposed vulnerability. |
| **`#Light 09`** | Practical Headlights      | Twin hard 4000K tungsten automotive beams cutting through rain/fog, blinding direct flares into camera lens, dark silhouettes.        | Impending vehicular catastrophe, rural roadblock, ominous pursuit.     |
| **`#Light 10`** | High-Key Ethereal         | Low contrast 1.5:1 ratio, overexposed background by +2 EV, soft wrapping daylight, sparkling micro-particulate scatter.               | Dream sequences, heavenly transition, idyllic memory recollection.     |
| **`#Light 11`** | Lightning Flash           | Instantaneous 10000K cold xenon burst lasting 2 frames, instantaneous hard shadow shifting, followed by absolute pitch black.         | Visceral terror, climactic thunderstorm combat, sudden shock.          |
| **`#Light 12`** | Clinical Cold Sci-Fi      | Overhead fluorescent ceiling grids, 6500K sterile white with slight green spike, uniform shadowless illumination.                     | Lab experimentation, totalitarian control, emotionless bureaucracy.    |
| **`#Light 13`** | Dappled Forest            | Canopy-filtered sunlight creating organic moving fractal patterns across subject face, warm 4000K spots against 5200K shade.          | Wilderness journey, hidden refuge, psychological awakening.            |
| **`#Light 14`** | Silhouette Against Fire   | Blazing 1500K raging inferno behind subject, camera exposing for flames, plunging foreground subject into total jet-black silhouette. | Total destruction, villainous emergence, irreversible tragedy.         |

---

## 5. Acting & Emotion Matrix (#Act 01–#Act 24)

| Code          | Performance Cue        | Micro-Expression & Muscular Cues                                                                                        | Cinematic Dramatic Context                                   |
| :------------ | :--------------------- | :---------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------- |
| **`#Act 01`** | Suppressed Trauma      | Tightened orbicularis oris, rigid neck tendons, gaze fixated on middle distance, refusal to blink.                      | Hearing an unexpected truth, bearing witness to past horror. |
| **`#Act 02`** | Cold Calculation       | Narrowed eyelids, subtle slow pupil sweep across room, flat heart-rate rhythm, zero head tilt.                          | Strategist anticipating an adversary’s ambush.               |
| **`#Act 03`** | Primal Rage            | Flared nostrils, bared canine teeth, veins pulsing at temple, rapid chest heaving, hyper-focused gaze.                  | Climax physical confrontation, betrayal realization.         |
| **`#Act 04`** | Quiet Melancholy       | Soft downward eye saccade, slow shallow exhalation through slightly parted lips, slack facial musculature.              | Solitary aftermath of loss, accepting unrequited love.       |
| **`#Act 05`** | Paranoid Dread         | Rapid jittery eye movements, micro-turning of ears toward ambient sounds, hunched shoulders, tight throat swallowing.   | Trapped in enemy territory, hunted in the shadows.           |
| **`#Act 06`** | Heroic Resolve         | Firmly set jaw, steady direct gaze locking on horizon, relaxed posture with grounded combat stance.                     | Stepping forward to sacrifice self for the collective.       |
| **`#Act 07`** | Cynical Amusement      | Asymmetrical smirk on left lip corner, single raised eyebrow, sarcastic head tilt, amused twinkle in eyes.              | Anti-hero outsmarting an arrogant official.                  |
| **`#Act 08`** | Shock and Awe          | Jaw dropped in paralysis, dilated pupils catching light, sudden intake of breath held stationary in lungs.              | Witnessing cosmic catastrophe or supernatural arrival.       |
| **`#Act 09`** | Intimate Vulnerability | Soft hesitant smile breaking across lips, trembling eye gaze dropping to partner’s lips then rising.                    | Confession of truth in a quiet bedroom sanctuary.            |
| **`#Act 10`** | Complete Breakdown     | Facial contortion into weeping, trembling hands attempting to cover face, loss of physical posture integrity.           | Discovering the death of an irreplaceable companion.         |
| **`#Act 11`** | Stoic Endurance        | Face weathered and emotionless, absorbing physical pain with clenched teeth, steady breathing cadence.                  | Wounded soldier walking through an artillery blizzard.       |
| **`#Act 12`** | Deceptive Charm        | Warm wide crinkled smile reaching crows-feet at eyes, open relaxed palms, predatory stillness beneath the warmth.       | Antagonist manipulating protagonist during dinner.           |
| **`#Act 13`** | Total Exhaustion       | Drooping eyelids, heavy head sinking downward, trembling lower lip, slow slurred speech delivery.                       | Reaching the finish line after a 50-mile desert march.       |
| **`#Act 14`** | Euphoric Triumph       | Thrown-back head, chest fully expanded, roaring open-mouth laugh, tear of joy tracing cheek.                            | Victory in the final championship or battle triumph.         |
| **`#Act 15`** | Disgust / Repulsion    | Curled upper lip showing front teeth, wrinkled nasal bridge, instinctive backward recoil of head.                       | Uncovering a grotesque crime scene or poisoned chalice.      |
| **`#Act 16`** | Moral Hesitation       | Hand pausing halfway to weapon, eyes darting between target and innocent bystander, conflicting facial muscle tension.  | Sniper deciding whether to pull trigger on flawed intel.     |
| **`#Act 17`** | Hypnotic Trance        | Unfocused glassy eyes, slack jaw, slow rhythmic swaying, complete absence of natural startle reflex.                    | Mind control, psychic takeover, alien communication.         |
| **`#Act 18`** | Panic Attack           | Hyperventilating chest heave, wide unblinking eyes, trembling fingers grasping throat, beads of cold sweat on forehead. | Trapped in an elevator losing oxygen rapidly.                |
| **`#Act 19`** | Seductive Playfulness  | Tilted head looking up through eyelashes, gentle bite of lower lip, deliberate slow cat-like movement.                  | Espionage operative extracting codes at high-society gala.   |
| **`#Act 20`** | Contemptuous Dismissal | Half-closed eyes looking down bridge of nose, tiny dismissive puff of air from nostrils, turned shoulder.               | Royalty addressing an insolent commoner.                     |
| **`#Act 21`** | Sudden Realization     | Widening eyes with sudden micro-nod, lips parting in silent vocalization, quick head snap toward clue.                  | Detective piecing together the killer’s fatal mistake.       |
| **`#Act 22`** | Physical Agony         | Writhing neck muscles, tightly squeezed shut eyelids with tear leakage, gritted teeth with guttural groan.              | Field surgery without anesthesia, extracting shrapnel.       |
| **`#Act 23`** | Guilt and Remorse      | Downcast averted eyes unable to look at victim, hunched spine, nervous wringing of hands.                               | Confessing a lie that caused catastrophic damage.            |
| **`#Act 24`** | Transcendent Peace     | Serene neutral expression, faint tranquil smile, slow gentle breathing, relaxed shoulders welcoming fate.               | The dying hero watching the sun rise over a liberated city.  |

---

## 6. Camera Optics & Composition Geometry

### Optical Physics Matrix (#Lens 01–#Lens 06)

| Code           | Lens Designation      | Optical Physics & Bokeh Characteristics                                                                      | Visual Field & Compression                                  |
| :------------- | :-------------------- | :----------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------- |
| **`#Lens 01`** | 2.0x Anamorphic Prime | Horizontal blue/streak streak lens flares, oval out-of-focus bokeh discs, slight barrel distortion at edges. | 2.39:1 widescreen scope, cinematic Hollywood film grandeur. |
| **`#Lens 02`** | 35mm Spherical Prime  | Minimal distortion, organic human eye perspective field, smooth spherical bokeh falloff, f/1.8 aperture.     | Environmental character framing, conversational realism.    |
| **`#Lens 03`** | 85mm Portrait Prime   | Tight telephoto background compression, creamy bokeh melting background into abstract color, f/1.4 aperture. | Heroic close-up isolation, dramatic emotional intimacy.     |
| **`#Lens 04`** | 24mm Ultra-Wide Angle | Exaggerated spatial depth, dynamic perspective lines, dynamic foreground emphasis, slight edge distortion.   | Majestic architectural scale, dynamic action choreography.  |
| **`#Lens 05`** | 135mm Heavy Telephoto | Severe background spatial compression, flattening distance between foreground subject and background threat. | Sniper line-of-sight, tense pursuit, claustrophobic crowds. |
| **`#Lens 06`** | Tilt-Shift Miniature  | Selected plane of focus across diagonal axis, selective blur producing miniature diorama illusion.           | Surreal disorientation, omniscient surveillance god-view.   |

### Composition Matrix (#Comp 01–#Comp 08)

- **`#Comp 01` - Rule of Thirds:** Key facial features and horizons aligned along 1/3 and 2/3 coordinate intersections.
- **`#Comp 02` - Golden Spiral (Fibonacci):** Dynamic logarithmic curve leading eye from environmental periphery to micro-detail.
- **`#Comp 03` - Central Symmetry:** Exact geometric centering of subject; Kubrick-style one-point linear perspective.
- **`#Comp 04` - Leading Lines:** Structural architecture (railways, corridors, bridges) forcing eye vector to vanishing point.
- **`#Comp 05` - 180-Degree Action Line:** Rigid spatial camera positioning preserving screen direction between shots.
- **`#Comp 06` - Frame Within a Frame:** Subject framed inside doorways, broken arches, windows, or rear-view mirrors.
- **`#Comp 07` - Dutch Angle (Canted):** 15° to 30° roll on camera axis, creating psychological vertigo and systemic disorder.
- **`#Comp 08` - Deep Focus Mise-en-Scène:** f/11 hyperfocal aperture keeping foreground, midground, and background tack sharp.

### Camera Angles Matrix (#Cam 01–#Cam 34)

```text
#Cam 01: Extreme Close-Up (ECU - Eyes/Mouth)    #Cam 18: Tracking Shot (Dolly Sideways)
#Cam 02: Close-Up (CU - Head & Neck)            #Cam 19: Dolly-In (Emotional Push)
#Cam 03: Medium Close-Up (MCU - Chest Up)       #Cam 20: Dolly-Out (Isolation Reveal)
#Cam 04: Medium Shot (MS - Waist Up)            #Cam 21: Crane / Jib Sweeping Overhead
#Cam 05: Cowboy Shot (American - Mid-Thigh Up)  #Cam 22: Whip Pan (Fast Motion Transition)
#Cam 06: Full Shot (FS - Head to Toe)           #Cam 23: 360-Degree Orbital Arc
#Cam 07: Wide Shot (WS - Complete Environment)   #Cam 24: Steadicam Forward Push
#Cam 08: Extreme Wide Shot (EWS - Epic Scale)   #Cam 25: Handheld Shaky-Cam (Warzone Realism)
#Cam 09: Bird's Eye View (Overhead 90° Zenith)  #Cam 26: Crash Zoom (Sudden Dramatic Focal Shift)
#Cam 10: Worm's Eye View (Ground Level 90° Up)  #Cam 27: Rack Focus (Shifting Depth from FG to BG)
#Cam 11: Over-The-Shoulder (OTS - Dialogue)     #Cam 28: Snorricam (Body-Mounted Subject Lock)
#Cam 12: Point of View (POV - First Person)     #Cam 29: Split-Diopter Dual Plane Focus
#Cam 13: Low-Angle Hero Shot (Looking Up 30°)   #Cam 30: Drone Panoramic Flyover
#Cam 14: High-Angle Vulnerability (Looking Down)#Cam 31: Two-Shot (Balanced Profile Dynamic)
#Cam 15: Dutch Angle Tilt                       #Cam 32: Crowd Ensemble Master
#Cam 16: Profile Side Silhouette                #Cam 33: Atmospheric Establishing Master
#Cam 17: Frontal Symmetrical Master             #Cam 34: Microscopic Macro Insert
```

---

## 7. Motion Dynamics & Velocity Profiles

### Speed Profiles (#Speed 01–#Speed 05)

- **`#Speed 01` - Static / Locked-Off:** Zero camera movement. Micro-movements strictly limited to blinking, smoke, and breathing.
- **`#Speed 02` - Subtle Organic Drift:** Micro-Steadicam breathing drift (0.2 m/s). Soft naturalistic character repositioning.
- **`#Speed 03` - Cinematic Paced:** Deliberate smooth dolly movement (1.0 m/s). Purposeful narrative pacing.
- **`#Speed 04` - High-Octane Action:** Rapid camera pan and tracking (3.5 m/s). Fast combat choreography and chase dynamics.
- **`#Speed 05` - Hyper-Speed / Time-Lapse:** Time acceleration or high-speed slow-motion (120 fps burst capture).

### Multi-Layer Foreground / Background Dynamics

To prevent flat 2D renders, every video generation prompt specifies foreground and background layers:

- **Foreground (`#FG`):** Out-of-focus falling snow, dust motes, passing pedestrians, or wet foliage brushing lens.
- **Midground (Subject):** The primary character and hero prop action.
- **Background (`#BG`):** Drifting atmospheric smoke, distant traffic headlights, moving neon reflections, and wind-blown curtains.
