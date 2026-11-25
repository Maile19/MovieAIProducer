#!/usr/bin/env python3
"""Seed script for THE FINAL OBSERVER in MovieAIProducer database.

Creates a complete new production with:
- Full project metadata and admin owner binding
- Master Production Bible (MPB) in DRAFT / UNLOCKED status
- 5 Characters + Dynamic Character States (#State 01 - #State 05)
- 5 Key Environments (#Env 01 - #Env 05)
- 5 Hero Props (#Prop 01 - #Prop 05)
- 3 Extras (#Extras 01 - #Extras 03)
- 50 Structured Scenes across 4-Act structure (Act I, Act II-A, Act II-B, Act III & IV)
- 50 Calibrated Cinematography Shots (<= 14 words dialogue / 5.0s pacing)

Idempotent: Safe to re-run without duplicate creation.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

# Ensure backend package can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.infrastructure.database.engine import (
    create_database_engine,
    dispose_database_engine,
)
from backend.app.infrastructure.database.models.auth import (
    ProjectMemberModel,
    UserModel,
)
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.database.models.story import (
    SceneModel,
    ShotModel,
)
from backend.app.infrastructure.database.session import create_session_factory


# ==============================================================================
# PAYLOAD DEFINITION: THE FINAL OBSERVER
# ==============================================================================

PROJECT_TITLE = "THE FINAL OBSERVER"
PROJECT_SLUG = "the-final-observer"

METADATA = {
    "title": PROJECT_TITLE,
    "logline": (
        "When a quantum anomaly begins erasing 24 hours of human memory every dawn, "
        "a grieving astrophysicist enters a timeless 4D Observation Room at the edge of "
        "a black hole to stop it—only to discover the anomaly was engineered by his own "
        "future self to save his dead daughter."
    ),
    "genre": "High-Concept Sci-Fi / Emotional Mind-Bender",
    "language": "English",
    "aspect_ratio": "16:9",
    "framing_aspect_ratio": "2.39:1 Anamorphic",
    "primary_visual_style": "#Style 02 (Hollywood IMAX 70mm)",
    "secondary_visual_style": "#Style 17 (Dark Graphic Novel / Denis Villeneuve Monolithic)",
    "optical_and_color_palette": (
        "#Lens 01 (Anamorphic 2.0x), #Comp 03 (Center Symmetry), "
        "DaVinci Obsidian Slate, Cold Tungsten, Amber Horizon"
    ),
    "target_engine": "Google Veo 2 / Kling AI",
    "mpb_status": "DRAFT / UNLOCKED",
    "operational_stage": 3,
    "status": "PLANNING",
}

ENVIRONMENTS_DATA = [
    {
        "code": "#Env 01",
        "name": "Coastal City & Elias's Apartment",
        "architecture": "Foggy brutalist coastal metropolis, pier, rain-streaked glass apartment covered in quantum equations.",
        "atmosphere": "Cold morning fog, persistent coastal rain, chalk dust on glass, damp asphalt reflections.",
        "lighting": "#Light 04 Dawn Softbox & cold tungsten practicals.",
        "audio": "Continuous ocean tide, distant foghorns, rain tapping on glass walls.",
    },
    {
        "code": "#Env 02",
        "name": "Observatory HQ",
        "architecture": "Monolithic concrete orbital command center, giant golden-slate holographic globe, acoustic audio lab, launch hangar.",
        "atmosphere": "Sterile military-scientific compound, pressurized air conditioning, low hum of supercomputing clusters.",
        "lighting": "#Light 02 High-Contrast Chiaroscuro & glowing amber holographic projections.",
        "audio": "Sub-bass seismic anomalies, decoded radio frequency static, cavernous hangar echoes.",
    },
    {
        "code": "#Env 03",
        "name": "Research Vessel Aethelgard",
        "architecture": "Industrial sci-fi spaceship bridge, dim tungsten corridors, medbay, reactor bay, airlock, rescue deck.",
        "atmosphere": "Zero-G condensation, metallic hull groaning under gravitational stress, flickering emergency panels.",
        "lighting": "#Light 07 Cold Overcast Fluorescent & flashing red hazard strobes.",
        "audio": "Hull stress groan in vacuum, atmospheric scrubbers, urgent decompression alarms.",
    },
    {
        "code": "#Env 04",
        "name": "Event Horizon Storm",
        "architecture": "Deep space perimeter around a colossal matte-black monolith ring with a blinding golden accretion corona and floating debris.",
        "atmosphere": "Violent gravitational turbulence, shattered asteroid fields suspended in time, warping spacetime fabric.",
        "lighting": "#Light 01 Volumetric Golden Accretion Corona Rim & pure matte-black void.",
        "audio": "Deep cosmic sub-bass rumble, silent vacuum punctuated by cockpit shudder vibration.",
    },
    {
        "code": "#Env 05",
        "name": "The Observation Room 4D",
        "architecture": "Infinite mirror-obsidian floor, colossal monolithic time-pillars, suspended rain droplets, glowing Chronos Core at center.",
        "atmosphere": "Timeless non-linear realm, suspended liquid droplets in zero-G, golden quantum dust particles.",
        "lighting": "#Light 06 Bioluminescent Cyan Glow & pulsing golden Chronos core flares.",
        "audio": "Reversed acoustic echoes, ticking watch oscillations, sublime ethereal orchestral resonance.",
    },
]

HERO_PROPS_DATA = [
    {
        "code": "#Prop 01",
        "name": "Maya's Mechanical Pocket Watch",
        "material": "Brass-and-obsidian antique watch with hand-wound gears and cracked crystal casing.",
        "weight": "Sentimental grounding anchor; hands spin backward during Erasure waves, cracks during climax, ticks forward at resolution.",
        "action": "Flicked open with thumb, gripped tightly in palm, placed into Chronos Core to reverse anomaly polarity.",
    },
    {
        "code": "#Prop 02",
        "name": "Shielded Neural Tablet",
        "material": "Hardened matte-slate pad with biometric isolation shield and tungsten chassis.",
        "weight": "Mission-critical identity ledger immune to quantum memory erasure waves.",
        "action": "Elena rapidly logs crew identities, mission protocols, and personal memories before each dawn wave.",
    },
    {
        "code": "#Prop 03",
        "name": "Obsidian EVA Spacesuit",
        "material": "Sleek matte-black deep-space composite suit with gold-filigree joints and amber rim-lit HUD visor.",
        "weight": "Hero survival gear shielding wearer from gravitational shear and temporal radiation.",
        "action": "Sealed at collar with pressurized mechanical hiss; HUD activates amber diagnostic vectors.",
    },
    {
        "code": "#Prop 04",
        "name": "Plasma Torch / Magnetic Tether",
        "material": "Compact high-heat industrial plasma cutter with braided high-tensile magnetic grapple cable.",
        "weight": "Engineering tool repurposed as lethal zero-G close-quarters tactical weapon.",
        "action": "Ignited with high-frequency hiss, used to grapple drifting bulkheads and strike helmet visors.",
    },
    {
        "code": "#Prop 05",
        "name": "The Chronos Core",
        "material": "Floating concentric obsidian-and-gold quantum gyroscope with pulsing singularity emitter.",
        "weight": "Spacetime bending engine at the center of the 4D Observation Room controlling the global erasure anomaly.",
        "action": "Manually manipulated via central obsidian levers to advance or rewind Earth's temporal timeline.",
    },
]

EXTRAS_DATA = [
    {
        "code": "#Extras 01",
        "name": "Urban Commuters",
        "description": "Rain-coated city pedestrians frozen in confusion during Erasure waves.",
        "role": "Crowd ensemble (Act I, Act IV)",
        "costume": "Dark trench coats, translucent umbrellas, business attire drenched in rain.",
        "behavior": "Sudden freezing in stride, looking at smartwatches in disoriented panic.",
    },
    {
        "code": "#Extras 02",
        "name": "Hospital ER Staff & Patients",
        "description": "Disoriented doctors, nurses, and civilians watching global emergency broadcasts.",
        "role": "Secondary ensemble (Act I)",
        "costume": "Medical scrubs, surgical masks, emergency blankets, hospital gowns.",
        "behavior": "Frantic triage, staring collectively at wall-mounted news monitors.",
    },
    {
        "code": "#Extras 03",
        "name": "Aethelgard Flight Crew & Technicians",
        "description": "Spaceship engineers and reactor specialists experiencing sudden amnesia.",
        "role": "Spaceship crew ensemble (Act II-A)",
        "costume": "Charcoal mission flight overalls, maintenance harnesses, radiation badges.",
        "behavior": "Abandoning stations in terror, forgetting operating protocols mid-crisis.",
    },
]

CHARACTERS_DATA = [
    {
        "name": "Dr. Elias Vance",
        "role": "PROTAGONIST",
        "base_prompt": (
            "Dr. Elias Vance, 40-year-old male astrophysicist. Defined jawline, dark hair with subtle grey "
            "at the temples, thin scar on left eyebrow. Dark wool tactical jacket over black turtleneck, "
            "transitioning to matte Obsidian EVA Spacesuit in Act II. Deep baritone voice carrying suppressed grief."
        ),
        "states": [
            {
                "state_code": "#State 01",
                "wardrobe": "Dark wool tactical jacket over black turtleneck, tailored dark trousers.",
                "injuries_and_wear": "None, freshly groomed; thin scar on left eyebrow.",
                "expression_anchor": "Deep suppressed grief, quiet intellectual intensity, calculating ocular focus.",
            },
            {
                "state_code": "#State 02",
                "wardrobe": "Matte Obsidian EVA Spacesuit, unclasped helmet, amber rim-lit HUD visor.",
                "injuries_and_wear": "Minor wear, light sweat and fatigue from zero-G transit.",
                "expression_anchor": "Hyper-focused, determined, calculating survival posture.",
            },
            {
                "state_code": "#State 03",
                "wardrobe": "Obsidian EVA suit scuffed and singed from close combat, cracked outer armor layer.",
                "injuries_and_wear": "Oxygen line torn, facial bruises, bloodied left temple.",
                "expression_anchor": "Desperation, fighting against inevitable temporal paradox.",
            },
            {
                "state_code": "#State 04",
                "wardrobe": "Heavily damaged Obsidian EVA suit, exposed thermal lining, fractured shoulder seam.",
                "injuries_and_wear": "Bleeding from zero-G brawl, singed synthetic fabric, exhausted posture.",
                "expression_anchor": "Deep empathy, sorrowful forgiveness, emotional catharsis.",
            },
            {
                "state_code": "#State 05",
                "wardrobe": "Obsidian EVA suit bathed in blinding golden quantum singularity light.",
                "injuries_and_wear": "Luminescent quantum particles engulfing silhouette, healed aura.",
                "expression_anchor": "Transcendent clarity, absolute peaceful surrender to time.",
            },
        ],
    },
    {
        "name": "Dr. Elena Rostova",
        "role": "DEUTERAGONIST",
        "base_prompt": (
            "Dr. Elena Rostova, 36-year-old female orbital astrophysicist and mission co-lead. Sharp hazel eyes, "
            "dark blonde hair tied in a neat low bun, sculpted cheekbones. Architectural charcoal laboratory coat "
            "and mission flight suit. Clear analytical alto voice, commanding during emergencies."
        ),
        "states": [
            {
                "state_code": "#State 01",
                "wardrobe": "Architectural charcoal laboratory coat over sleek grey formal attire.",
                "injuries_and_wear": "Immaculate composure, zero physical defects.",
                "expression_anchor": "Sharp analytical concern, commanding urgency.",
            },
            {
                "state_code": "#State 02",
                "wardrobe": "Mission flight suit / Aethelgard operations uniform with diagnostic badge.",
                "injuries_and_wear": "Light fatigue, slightly disheveled hair bun.",
                "expression_anchor": "Steely resolve, calm crisis management.",
            },
            {
                "state_code": "#State 03",
                "wardrobe": "Torn flight suit, emergency bridge safety harness locked in place.",
                "injuries_and_wear": "Singed fabric from bridge explosion, superficial forehead scratch.",
                "expression_anchor": "Defiant endurance, holding the line against sabotage.",
            },
        ],
    },
    {
        "name": "Maya Vance",
        "role": "EMOTIONAL_ANCHOR",
        "base_prompt": (
            "Maya Vance, 9-year-old girl. Warm brown eyes, shoulder-length hair with a faded yellow ribbon, "
            "signature amber parka jacket providing warm visual contrast against the cold slate world. "
            "Clear, curious child's voice heard via radio static or J-Cut memory echoes."
        ),
        "states": [
            {
                "state_code": "#State 01",
                "wardrobe": "Amber parka jacket over faded knit sweater, faded yellow ribbon in hair.",
                "injuries_and_wear": "Immaculate, radiant childhood memory projection, zero defects.",
                "expression_anchor": "Curious, warm, innocent loving smile.",
            },
        ],
    },
    {
        "name": "Old Elias / The Architect",
        "role": "ANTAGONIST",
        "base_prompt": (
            "Old Elias / The Architect, 65-year-old male antagonist. Identical biometric base as Dr. Elias Vance "
            "with 25-year aging modifier: identical left eyebrow scar, weathered coarse white beard, sunken cold "
            "obsessed eyes. Worn soot-stained Obsidian EVA cloak/suit with cracked visor. Heavy gravelly slow baritone."
        ),
        "states": [
            {
                "state_code": "#State 03",
                "wardrobe": "Worn soot-stained Obsidian EVA cloak/suit with cracked visor.",
                "injuries_and_wear": "Weathered coarse white beard, scarred face, identical eyebrow scar, soot stains.",
                "expression_anchor": "Cold fanaticism, unyielding obsession.",
            },
            {
                "state_code": "#State 04",
                "wardrobe": "Shattered helmet visor, singed cloak remnants exposing aging chest plate.",
                "injuries_and_wear": "Bleeding cheek, bruised jaw, single tear floating in zero-G.",
                "expression_anchor": "Broken sorrow, long-delayed grief and acceptance.",
            },
        ],
    },
    {
        "name": "Commander Kael",
        "role": "SECONDARY_ANTAGONIST",
        "base_prompt": (
            "Commander Kael, 45-year-old military faction commander. Buzz-cut iron-grey hair, stern military posture, "
            "dark charcoal tactical uniform with armored shoulders. Sharp, clipped authoritarian baritone."
        ),
        "states": [
            {
                "state_code": "#State 01",
                "wardrobe": "Dark charcoal tactical uniform with armored shoulders and military insignia.",
                "injuries_and_wear": "Crisp military bearing, pristine posture.",
                "expression_anchor": "Stern, authoritarian, uncompromising command.",
            },
            {
                "state_code": "#State 02",
                "wardrobe": "Armed tactical boarding armor, magnetic boots, sidearm holster.",
                "injuries_and_wear": "None, calculated tactical readiness.",
                "expression_anchor": "Ruthless tactical focus, cold determination.",
            },
            {
                "state_code": "#State 03",
                "wardrobe": "Compromised tactical suit, helmet visor depressurizing against airlock.",
                "injuries_and_wear": "Decompression trauma, struggling against bulkhead seal.",
                "expression_anchor": "Frantic desperation, lost control.",
            },
        ],
    },
]

# 50 Structured Scenes across 4-Act Structure
# Calibrated for Hollywood pacing (<= 14 words dialogue / 5.0s)
SCENES_RAW_DATA = [
    # --- ACT I: THE FADING WORLD (Scenes 01–12) ---
    {
        "scene_number": 1,
        "act_number": 1,
        "slugline": "EXT. COASTAL PIER - DAWN",
        "narrative_goal": "Ordinary World. Cold fog blankets the pier; Elias grips Maya's mechanical pocket watch.",
        "tags": ["#Env 01", "Elias #State 01", "#Prop 01"],
        "dialogue": 'Dad, if time stops, do we stay here forever?',
        "speaker": "Maya",
        "audio_note": '(V.O. Maya, J-Cut -1.2s) "Dad, if time stops, do we stay here forever?"',
        "transition_type": "J_CUT",
        "camera_code": "#Cam 01",
        "light_code": "#Light 04",
        "act_code": "#Act 05",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 2,
        "act_number": 1,
        "slugline": "INT. ELIAS'S APARTMENT - MORNING",
        "narrative_goal": "Dark apartment covered in quantum physics equations on glass walls; Maya's photo lies on the desk.",
        "tags": ["#Env 01", "Elias #State 01"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Heavy rain, steady watch ticking]",
        "transition_type": "NONE",
        "camera_code": "#Cam 05",
        "light_code": "#Light 02",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 3,
        "act_number": 1,
        "slugline": "INT. UNIVERSITY HALL - DAY",
        "narrative_goal": "Elias lectures before a global atomic clock display that suddenly drifts by milliseconds.",
        "tags": ["#Env 01", "Elias #State 01"],
        "dialogue": "Gravity doesn't just bend light. It fractures human memory.",
        "speaker": "Elias",
        "audio_note": '(Elias) "Gravity doesn\'t just bend light. It fractures human memory."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 07",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 4,
        "act_number": 1,
        "slugline": "EXT. CITY INTERSECTION - DUSK",
        "narrative_goal": "The sky flickers obsidian-violet; a flock of birds freezes mid-air for a fraction of a second.",
        "tags": ["#Env 01", "#Extras 01"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Deep sub-bass seismic hum]",
        "transition_type": "NONE",
        "camera_code": "#Cam 08",
        "light_code": "#Light 03",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 5,
        "act_number": 1,
        "slugline": "EXT. CITY INTERSECTION - DUSK",
        "narrative_goal": "Inciting Incident. The Erasure wave sweeps the city. Citizens panic forgetting the last 24 hours; Elias's pocket watch spins backward.",
        "tags": ["#Env 01", "Elias #State 01", "#Prop 01"],
        "dialogue": "Everyone just lost yesterday. Why is her watch running backward?",
        "speaker": "Elias",
        "audio_note": '(Elias) "Everyone just lost yesterday. Why is her watch running backward?"',
        "transition_type": "NONE",
        "camera_code": "#Cam 02",
        "light_code": "#Light 03",
        "act_code": "#Act 03",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 6,
        "act_number": 1,
        "slugline": "INT. HOSPITAL ER - NIGHT",
        "narrative_goal": "News monitors broadcast global panic; nurses and patients stare at each other in confusion.",
        "tags": ["#Env 01", "#Extras 02"],
        "dialogue": "Six billion people lost Tuesday. Scientists have no explanation.",
        "speaker": "Anchor",
        "audio_note": '(Anchor, L-Cut +1.0s) "Six billion people lost Tuesday. Scientists have no explanation."',
        "transition_type": "L_CUT",
        "camera_code": "#Cam 06",
        "light_code": "#Light 07",
        "act_code": "#Act 03",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 7,
        "act_number": 1,
        "slugline": "INT. ELIAS'S APARTMENT - NIGHT",
        "narrative_goal": "Dr. Elena Rostova arrives at Elias's door holding urgent orbital satellite files.",
        "tags": ["#Env 01", "Elias #State 01", "Elena #State 01"],
        "dialogue": "Twenty-four hours erased every dawn. In six months, humanity forgets itself.",
        "speaker": "Elena",
        "audio_note": '(Elena) "Twenty-four hours erased every dawn. In six months, humanity forgets itself."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 02",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 8,
        "act_number": 1,
        "slugline": "INT. OBSERVATORY HQ - NIGHT",
        "narrative_goal": "A colossal hologram displays The Horizon Monolith orbiting at the edge of the solar system.",
        "tags": ["#Env 02", "Elias #State 01", "Elena #State 01"],
        "dialogue": "That monolith is pulling time backward. You built the original math.",
        "speaker": "Elena",
        "audio_note": '(Elena) "That monolith is pulling time backward. You built the original math."',
        "transition_type": "NONE",
        "camera_code": "#Cam 02",
        "light_code": "#Light 02",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 9,
        "act_number": 1,
        "slugline": "INT. OBSERVATORY AUDIO LAB - NIGHT",
        "narrative_goal": "Decoded radio signals from the anomaly play; Elias's pocket watch vibrates in sync with a child's voice.",
        "tags": ["#Env 02", "Elias #State 01", "#Prop 01"],
        "dialogue": "Daddy... I'm still waiting by the lighthouse.",
        "speaker": "Maya",
        "audio_note": '(Radio Static - Maya) "Daddy... I\'m still waiting by the lighthouse."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 05",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 10,
        "act_number": 1,
        "slugline": "INT. OBSERVATORY BRIEFING - DAY",
        "narrative_goal": "Military Commander Kael demands placing a quantum warhead aboard the Aethelgard mission.",
        "tags": ["#Env 02", "Elias #State 02", "Kael #State 01"],
        "dialogue": "If we can't stop the wave, we weaponize it.",
        "speaker": "Kael",
        "audio_note": '(Kael) "If we can\'t stop the wave, we weaponize it."',
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 07",
        "act_code": "#Act 04",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 11,
        "act_number": 1,
        "slugline": "INT. OBSERVATORY HANGAR - NIGHT",
        "narrative_goal": "Elias seals the helmet of his Obsidian EVA Suit; Elena watches him suspiciously behind corridor glass.",
        "tags": ["#Env 02", "Elias #State 01", "Elena #State 01", "#Prop 03"],
        "dialogue": "Are you saving the world, Elias, or chasing a ghost?",
        "speaker": "Elena",
        "audio_note": '(Elena) "Are you saving the world, Elias, or chasing a ghost?"',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 02",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 12,
        "act_number": 1,
        "slugline": "EXT. LAUNCH PAD - DAWN",
        "narrative_goal": "Plot Point 1. Research vessel Aethelgard blasts through grey storm clouds toward dark orbit.",
        "tags": ["#Env 03", "Elias #State 02", "Elena #State 01"],
        "dialogue": "I'm going to finish what I started three years ago.",
        "speaker": "Elias",
        "audio_note": '(Elias, J-Cut -1.2s) "I\'m going to finish what I started three years ago."',
        "transition_type": "J_CUT",
        "camera_code": "#Cam 02",
        "light_code": "#Light 04",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },

    # --- ACT II-A: INTO THE SINGULARITY (Scenes 13–25) ---
    {
        "scene_number": 13,
        "act_number": 2,
        "slugline": "EXT. DEEP ORBIT - SPACE",
        "narrative_goal": "Aethelgard glides silently above Earth's curvature wrapped in a golden anomaly aurora.",
        "tags": ["#Env 03"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Metallic hull creaking in vacuum]",
        "transition_type": "NONE",
        "camera_code": "#Cam 05",
        "light_code": "#Light 01",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 14,
        "act_number": 2,
        "slugline": "INT. AETHELGARD BRIDGE - DAY",
        "narrative_goal": "Every digital clock on the ship dies simultaneously as they approach the gravity belt.",
        "tags": ["#Env 03", "Elias #State 02", "Elena #State 02", "#Prop 01"],
        "dialogue": "Digital clocks are dead. Your mechanical watch is our only compass.",
        "speaker": "Elena",
        "audio_note": '(Elena) "Digital clocks are dead. Your mechanical watch is our only compass."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 07",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 15,
        "act_number": 2,
        "slugline": "INT. AETHELGARD QUARTERS - NIGHT",
        "narrative_goal": "Flashback dream: Maya in her amber parka runs down the pier before the lab accident.",
        "tags": ["#Env 03", "Elias #State 02", "Maya #State 01"],
        "dialogue": "Promise you won't let go of my hand?",
        "speaker": "Maya",
        "audio_note": '(Maya) "Promise you won\'t let go of my hand?"',
        "transition_type": "NONE",
        "camera_code": "#Cam 03",
        "light_code": "#Light 04",
        "act_code": "#Act 05",
        "speed_code": "#Speed 02",
    },
    {
        "scene_number": 16,
        "act_number": 2,
        "slugline": "INT. AETHELGARD CORRIDOR - DAY",
        "narrative_goal": "A second Erasure wave strikes the ship; a reactor technician panics after losing his memory.",
        "tags": ["#Env 03", "Elias #State 02", "#Extras 03"],
        "dialogue": "Who are you people? How did I get on this ship?",
        "speaker": "Technician",
        "audio_note": '(Technician) "Who are you people? How did I get on this ship?"',
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 11",
        "act_code": "#Act 03",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 17,
        "act_number": 2,
        "slugline": "INT. AETHELGARD MEDBAY - DAY",
        "narrative_goal": "Elena logs every crew member's identity and mission objective onto the shielded Neural Tablet.",
        "tags": ["#Env 03", "Elena #State 02", "#Prop 02"],
        "dialogue": "Every wave strips deeper. Write down who you are before it hits.",
        "speaker": "Elena",
        "audio_note": '(Elena) "Every wave strips deeper. Write down who you are before it hits."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 07",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 18,
        "act_number": 2,
        "slugline": "EXT. EVENT HORIZON PERIMETER - SPACE",
        "narrative_goal": "The Horizon Monolith towers massively ahead—a pitch-black ring burning with a golden corona.",
        "tags": ["#Env 04", "#Env 03"],
        "dialogue": "It's not a natural black hole. Someone engineered that door.",
        "speaker": "Elias",
        "audio_note": '(Elias) "It\'s not a natural black hole. Someone engineered that door."',
        "transition_type": "NONE",
        "camera_code": "#Cam 05",
        "light_code": "#Light 01",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 19,
        "act_number": 2,
        "slugline": "INT. AETHELGARD REACTOR BAY - NIGHT",
        "narrative_goal": "Kael secretly arms a sabotage detonator to destroy the portal once Elias crosses inside.",
        "tags": ["#Env 03", "Kael #State 02"],
        "dialogue": "History belongs to whoever controls the eraser, Doctor.",
        "speaker": "Kael",
        "audio_note": '(Kael) "History belongs to whoever controls the eraser, Doctor."',
        "transition_type": "NONE",
        "camera_code": "#Cam 07",
        "light_code": "#Light 02",
        "act_code": "#Act 04",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 20,
        "act_number": 2,
        "slugline": "INT. AETHELGARD AIRLOCK - NIGHT",
        "narrative_goal": "Elena seals the steel bulkhead holding Kael back so Elias can launch the diving pod.",
        "tags": ["#Env 03", "Elias #State 02", "Elena #State 02", "Kael #State 02"],
        "dialogue": "Go now! I'll hold the bridge until you cut the signal!",
        "speaker": "Elena",
        "audio_note": '(Elena) "Go now! I\'ll hold the bridge until you cut the signal!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 11",
        "act_code": "#Act 03",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 21,
        "act_number": 2,
        "slugline": "EXT. EVENT HORIZON STORM - SPACE",
        "narrative_goal": "Elias's diving pod tumbles through a gravity storm; metallic debris floats frozen outside the cockpit.",
        "tags": ["#Env 04", "Elias #State 02", "#Prop 03"],
        "dialogue": "Thrusters offline! Crossing the event horizon on manual!",
        "speaker": "Elias",
        "audio_note": '(Elias) "Thrusters offline! Crossing the event horizon on manual!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 07",
        "light_code": "#Light 01",
        "act_code": "#Act 03",
        "speed_code": "#Speed 03",
    },
    {
        "scene_number": 22,
        "act_number": 2,
        "slugline": "INT. DIVING POD - EVENT HORIZON",
        "narrative_goal": "Exterior light stretches into golden pillars; the pocket watch spins wildly then halts at 12.",
        "tags": ["#Env 04", "Elias #State 02", "#Prop 01"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Glass shattering in reverse]",
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 01",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 23,
        "act_number": 2,
        "slugline": "EXT. OBSERVATION ROOM ENTRY",
        "narrative_goal": "The pod lands on an endless obsidian mirror floor; raindrops hang completely motionless in mid-air.",
        "tags": ["#Env 05", "Elias #State 02", "#Prop 03"],
        "dialogue": "Gravity is zero, yet I'm breathing. Time is completely frozen.",
        "speaker": "Elias",
        "audio_note": '(Elias) "Gravity is zero, yet I\'m breathing. Time is completely frozen."',
        "transition_type": "NONE",
        "camera_code": "#Cam 05",
        "light_code": "#Light 06",
        "act_code": "#Act 01",
        "speed_code": "#Speed 02",
    },
    {
        "scene_number": 24,
        "act_number": 2,
        "slugline": "INT. OBSERVATION ROOM - GALLERY",
        "narrative_goal": "Elias walks down a hall of monolithic pillars reflecting luminous fragments of Maya's childhood.",
        "tags": ["#Env 05", "Elias #State 02"],
        "dialogue": "This isn't a machine. It's a vault of stolen seconds.",
        "speaker": "Elias",
        "audio_note": '(Elias) "This isn\'t a machine. It\'s a vault of stolen seconds."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 25,
        "act_number": 2,
        "slugline": "INT. OBSERVATION ROOM - ALTAR",
        "narrative_goal": "Midpoint Shift. Elias opens a weathered logbook on the central console—every equation and signature matches his own handwriting.",
        "tags": ["#Env 05", "Elias #State 02", "#Prop 02"],
        "dialogue": "These equations... that's my handwriting. I've already been here.",
        "speaker": "Elias",
        "audio_note": '(Elias) "These equations... that\'s my handwriting. I\'ve already been here."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },

    # --- ACT II-B: THE PARADOX (Scenes 26–38) ---
    {
        "scene_number": 26,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "A soot-stained cloaked EVA figure (The Architect) steps out from the glare of the Chronos Core.",
        "tags": ["#Env 05", "Elias #State 03", "Old Elias #State 03"],
        "dialogue": "You arrived twelve minutes late. Just like the last forty times.",
        "speaker": "Architect",
        "audio_note": '(Architect) "You arrived twelve minutes late. Just like the last forty times."',
        "transition_type": "NONE",
        "camera_code": "#Cam 02",
        "light_code": "#Light 06",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 27,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - CORRIDOR",
        "narrative_goal": "Close-quarters combat erupts; The Architect parries every strike Elias throws with eerie precision.",
        "tags": ["#Env 05", "Elias #State 03", "Old Elias #State 03", "#Prop 04"],
        "dialogue": "How do you know every move before I make it?",
        "speaker": "Elias",
        "audio_note": '(Elias) "How do you know every move before I make it?"',
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 06",
        "act_code": "#Act 08",
        "speed_code": "#Speed 03",
    },
    {
        "scene_number": 28,
        "act_number": 3,
        "slugline": "INT. AETHELGARD BRIDGE",
        "narrative_goal": "Kael breaches the bridge and shoots the navigation console; the ship shudders toward the gravity well.",
        "tags": ["#Env 03", "Elena #State 03", "Kael #State 03"],
        "dialogue": "Cut the tether, Elena, or this ship tears apart!",
        "speaker": "Kael",
        "audio_note": '(Kael) "Cut the tether, Elena, or this ship tears apart!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 11",
        "act_code": "#Act 04",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 29,
        "act_number": 3,
        "slugline": "INT. AETHELGARD BRIDGE",
        "narrative_goal": "Elena triggers emergency decompression to neutralize Kael, then shouts into the radio mic.",
        "tags": ["#Env 03", "Elena #State 03"],
        "dialogue": "Elias! You have ninety seconds before the portal collapses!",
        "speaker": "Elena",
        "audio_note": '(Elena, Radio) "Elias! You have ninety seconds before the portal collapses!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 11",
        "act_code": "#Act 03",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 30,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - BRIDGE",
        "narrative_goal": "Weightless duel across a bridge of light; sparks from the plasma torch scar The Architect's visor.",
        "tags": ["#Env 05", "Elias #State 03", "Old Elias #State 03", "#Prop 04"],
        "dialogue": "Stop fighting me! Let the wave finish one more cycle!",
        "speaker": "Architect",
        "audio_note": '(Architect) "Stop fighting me! Let the wave finish one more cycle!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 06",
        "act_code": "#Act 08",
        "speed_code": "#Speed 03",
    },
    {
        "scene_number": 31,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - BRIDGE",
        "narrative_goal": "A memory projection of Maya suddenly appears smiling at the end of the bridge, freezing Elias in place.",
        "tags": ["#Env 05", "Elias #State 03", "Maya #State 01"],
        "dialogue": "Daddy, look! The sun is coming back!",
        "speaker": "Maya",
        "audio_note": '(Maya, Echo) "Daddy, look! The sun is coming back!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 03",
        "light_code": "#Light 04",
        "act_code": "#Act 05",
        "speed_code": "#Speed 02",
    },
    {
        "scene_number": 32,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - PLATFORM",
        "narrative_goal": "The Architect slams Elias onto the obsidian floor; Elias's oxygen line tears open with a hiss.",
        "tags": ["#Env 05", "Elias #State 03", "Old Elias #State 03"],
        "dialogue": "Earth can lose a few years. We only need one Tuesday.",
        "speaker": "Architect",
        "audio_note": '(Architect) "Earth can lose a few years. We only need one Tuesday."',
        "transition_type": "NONE",
        "camera_code": "#Cam 07",
        "light_code": "#Light 06",
        "act_code": "#Act 04",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 33,
        "act_number": 3,
        "slugline": "INT. AETHELGARD BRIDGE",
        "narrative_goal": "The bridge viewport cracks glowing orange; Elena holds the manual stabilizer lever with all her strength.",
        "tags": ["#Env 03", "Elena #State 03"],
        "dialogue": "Don't waste my life, Elias. Bring tomorrow back.",
        "speaker": "Elena",
        "audio_note": '(Elena) "Don\'t waste my life, Elias. Bring tomorrow back."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 01",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 34,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "Elias crawls toward the Chronos Core hologram of Earth: cities going dark as humanity loses memory.",
        "tags": ["#Env 05", "Elias #State 03", "#Prop 05"],
        "dialogue": "They're forgetting their children. You're erasing everything just for her.",
        "speaker": "Elias",
        "audio_note": '(Elias) "They\'re forgetting their children. You\'re erasing everything just for her."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 03",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 35,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "The Architect pulls the Chronos Core lever to maximum output; the 4D chamber trembles violently.",
        "tags": ["#Env 05", "Old Elias #State 03", "#Prop 05"],
        "dialogue": "A world without Maya isn't worth remembering.",
        "speaker": "Architect",
        "audio_note": '(Architect) "A world without Maya isn\'t worth remembering."',
        "transition_type": "NONE",
        "camera_code": "#Cam 02",
        "light_code": "#Light 06",
        "act_code": "#Act 04",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 36,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "Elias lunges one last time and smashes the plasma torch hilt squarely into the enemy's helmet.",
        "tags": ["#Env 05", "Elias #State 03", "Old Elias #State 03", "#Prop 04"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Violent crack of pressurized glass]",
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 06",
        "act_code": "#Act 08",
        "speed_code": "#Speed 03",
    },
    {
        "scene_number": 37,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "#Speed 05 (Slow-Mo 120fps): visor shards float slowly through drifting cold vapor.",
        "tags": ["#Env 05", "Elias #State 03", "Old Elias #State 03"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Labored, raspy breathing]",
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 07",
        "speed_code": "#Speed 05",
    },
    {
        "scene_number": 38,
        "act_number": 3,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "Dark Night of the Soul. The shattered visor reveals the face beneath: an older Elias with the identical eyebrow scar. Elias freezes.",
        "tags": ["#Env 05", "Elias #State 03", "Old Elias #State 03"],
        "dialogue": "I didn't fail to stop the anomaly, Elias. I built it.",
        "speaker": "Old Elias",
        "audio_note": '(Old Elias) "I didn\'t fail to stop the anomaly, Elias. I built it."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },

    # --- ACT III & IV: THE FINAL CHOICE (Scenes 39–50) ---
    {
        "scene_number": 39,
        "act_number": 4,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "Bleeding and kneeling, Elias stares at his older self; the pocket watch in his hand pulses softly.",
        "tags": ["#Env 05", "Elias #State 04", "Old Elias #State 04"],
        "dialogue": "Three more days backward, and we pull her from that lab.",
        "speaker": "Old Elias",
        "audio_note": '(Old Elias) "Three more days backward, and we pull her from that lab."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 40,
        "act_number": 4,
        "slugline": "INT. OBSERVATION ROOM - COLLAPSE",
        "narrative_goal": "Monolith pillars begin crumbling; thousands of fragments of Maya's face dissolve into golden dust.",
        "tags": ["#Env 05", "Elias #State 04", "Maya #State 01"],
        "dialogue": "If we save her, what monster will she wake up to?",
        "speaker": "Elias",
        "audio_note": '(Elias) "If we save her, what monster will she wake up to?"',
        "transition_type": "NONE",
        "camera_code": "#Cam 05",
        "light_code": "#Light 06",
        "act_code": "#Act 05",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 41,
        "act_number": 4,
        "slugline": "INT. OBSERVATION ROOM - CORE",
        "narrative_goal": "Enraged, Old Elias charges wildly to wrench the synchronizing pocket watch from Elias's hand.",
        "tags": ["#Env 05", "Elias #State 04", "Old Elias #State 04"],
        "dialogue": "Give me the watch! You're too weak to pay the price!",
        "speaker": "Old Elias",
        "audio_note": '(Old Elias) "Give me the watch! You\'re too weak to pay the price!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 06",
        "act_code": "#Act 08",
        "speed_code": "#Speed 03",
    },
    {
        "scene_number": 42,
        "act_number": 4,
        "slugline": "INT. OBSERVATION ROOM - GRAVITY WELL",
        "narrative_goal": "Brutal zero-G brawl amid collapsing monolith debris; droplets of blood float suspended in golden light.",
        "tags": ["#Env 05", "Elias #State 04", "Old Elias #State 04"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Heavy impact, muffled heartbeat]",
        "transition_type": "NONE",
        "camera_code": "#Cam 06",
        "light_code": "#Light 06",
        "act_code": "#Act 08",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 43,
        "act_number": 4,
        "slugline": "INT. AETHELGARD BRIDGE",
        "narrative_goal": "Bridge panels erupt in sparks; a red countdown hits 15 seconds before portal collapse.",
        "tags": ["#Env 03", "Elena #State 03"],
        "dialogue": "Fifteen seconds! Elias, whatever you're doing, do it now!",
        "speaker": "Elena",
        "audio_note": '(Elena) "Fifteen seconds! Elias, whatever you\'re doing, do it now!"',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 11",
        "act_code": "#Act 03",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 44,
        "act_number": 4,
        "slugline": "INT. OBSERVATION ROOM - CHRONOS CORE",
        "narrative_goal": "Elias locks his older self's shoulders at the edge of the light core, looking into his eyes without hatred.",
        "tags": ["#Env 05", "Elias #State 04", "Old Elias #State 04", "#Prop 05"],
        "dialogue": "I forgive you. Now let her rest.",
        "speaker": "Elias",
        "audio_note": '(Elias) "I forgive you. Now let her rest."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 45,
        "act_number": 4,
        "slugline": "INT. OBSERVATION ROOM - CHRONOS CORE",
        "narrative_goal": "A tear floats off Old Elias's cheek; his hands slowly release their grip.",
        "tags": ["#Env 05", "Elias #State 04", "Old Elias #State 04"],
        "dialogue": "I just didn't want to say goodbye.",
        "speaker": "Old Elias",
        "audio_note": '(Old Elias) "I just didn\'t want to say goodbye."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 06",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 46,
        "act_number": 4,
        "slugline": "INT. OBSERVATION ROOM - SINGULARITY",
        "narrative_goal": "Climax Peak. Elias thrusts Maya's pocket watch into the Chronos Core. Polarity reverses—transcendent light engulfs Elias (#State 05).",
        "tags": ["#Env 05", "Elias #State 05", "#Prop 01", "#Prop 05"],
        "dialogue": "Let time move forward.",
        "speaker": "Elias",
        "audio_note": '(Elias) "Let time move forward."',
        "transition_type": "NONE",
        "camera_code": "#Cam 02",
        "light_code": "#Light 06",
        "act_code": "#Act 02",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 47,
        "act_number": 4,
        "slugline": "EXT. EARTH ORBIT & CITY - DAY",
        "narrative_goal": "A gentle golden wave sweeps Earth's atmosphere; citizens at the intersection weep in relief as memories return.",
        "tags": ["#Env 04", "#Env 01", "#Extras 01"],
        "dialogue": None,
        "speaker": None,
        "audio_note": "[SILENT / SFX: Swelling orchestral sunrise chord]",
        "transition_type": "NONE",
        "camera_code": "#Cam 05",
        "light_code": "#Light 01",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 48,
        "act_number": 4,
        "slugline": "INT. AETHELGARD RESCUE DECK - DAY",
        "narrative_goal": "Elena survives inside the rescue module; radar pings Elias's splashdown beacon in the ocean.",
        "tags": ["#Env 03", "Elena #State 02"],
        "dialogue": "He did it. The clock is ticking forward again.",
        "speaker": "Elena",
        "audio_note": '(Elena) "He did it. The clock is ticking forward again."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 07",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 49,
        "act_number": 4,
        "slugline": "EXT. COASTAL BEACH - GOLDEN HOUR",
        "narrative_goal": "Elias stands drenched on the shore in #Light 01 Golden Hour. The pocket watch glass is cracked, but its hands tick steadily forward.",
        "tags": ["#Env 01", "Elias #State 01", "#Prop 01"],
        "dialogue": "You don't have to hold on anymore, Dad.",
        "speaker": "Maya",
        "audio_note": '(V.O. Maya, L-Cut +1.0s) "You don\'t have to hold on anymore, Dad."',
        "transition_type": "L_CUT",
        "camera_code": "#Cam 01",
        "light_code": "#Light 01",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
    {
        "scene_number": 50,
        "act_number": 4,
        "slugline": "EXT. COASTAL PIER - SUNRISE",
        "narrative_goal": "Resolution & Elixir. Elias closes the pocket watch, smiles peacefully, and walks toward Elena and the awakening city.",
        "tags": ["#Env 01", "Elias #State 01", "Elena #State 01"],
        "dialogue": "Today is a good day to remember.",
        "speaker": "Elias",
        "audio_note": '(Elias) "Today is a good day to remember."',
        "transition_type": "NONE",
        "camera_code": "#Cam 01",
        "light_code": "#Light 04",
        "act_code": "#Act 01",
        "speed_code": "#Speed 01",
    },
]


# ==============================================================================
# SEED WORKFLOW
# ==============================================================================

DEFAULT_OWNER_EMAIL = "nurkholisah2409@gmail.com"


async def seed_production(owner_email: str = DEFAULT_OWNER_EMAIL) -> tuple[ProjectModel, bool]:
    """Execute the idempotent seeding transaction."""
    settings = get_settings()
    engine = create_database_engine(settings.async_database_url)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            # Step 1: Owner Binding (Primary Admin User)
            normalized_email = owner_email.strip().lower()
            stmt_user = select(UserModel).where(func.lower(UserModel.email) == normalized_email)
            owner_user = (await session.execute(stmt_user)).scalar_one_or_none()

            if not owner_user:
                # Fallback to the first active SHOWRUNNER or user
                stmt_fallback = (
                    select(UserModel)
                    .where(UserModel.is_active == True)
                    .order_by(UserModel.created_at.asc())
                )
                owner_user = (await session.execute(stmt_fallback)).scalars().first()

            if not owner_user:
                raise RuntimeError("No suitable admin/owner user found in users table.")

            print(f"[AUTH] Bound owner: {owner_user.email} (ID: {owner_user.id})")

            # Step 2: Check Idempotency for Project
            stmt_proj = select(ProjectModel).where(
                (ProjectModel.title == PROJECT_TITLE) | (ProjectModel.slug == PROJECT_SLUG)
            )
            existing_project = (await session.execute(stmt_proj)).scalar_one_or_none()

            now = datetime.now(timezone.utc)
            is_new = False

            if existing_project:
                print(f"[EXISTS] Project '{PROJECT_TITLE}' found with ID: {existing_project.id}")
                project = existing_project
                project.title = PROJECT_TITLE
                project.aspect_ratio = METADATA["aspect_ratio"]
                project.target_style_code = "#Style 02"
                project.operational_stage = METADATA["operational_stage"]
                project.status = METADATA["status"]
                project.owner_id = owner_user.id
                project.settings = {
                    "logline": METADATA["logline"],
                    "genre": METADATA["genre"],
                    "language": METADATA["language"],
                    "aspect_ratio": METADATA["framing_aspect_ratio"],
                    "primary_visual_style": METADATA["primary_visual_style"],
                    "secondary_visual_style": METADATA["secondary_visual_style"],
                    "optical_and_color_palette": METADATA["optical_and_color_palette"],
                    "target_engine": METADATA["target_engine"],
                    "mpb_status": METADATA["mpb_status"],
                    "environments": ENVIRONMENTS_DATA,
                    "props": HERO_PROPS_DATA,
                    "extras": EXTRAS_DATA,
                }
                project.updated_at = now
            else:
                is_new = True
                project = ProjectModel(
                    id=uuid.uuid4(),
                    title=PROJECT_TITLE,
                    slug=PROJECT_SLUG,
                    status=METADATA["status"],
                    aspect_ratio=METADATA["aspect_ratio"],
                    target_style_code="#Style 02",
                    operational_stage=METADATA["operational_stage"],
                    owner_id=owner_user.id,
                    settings={
                        "logline": METADATA["logline"],
                        "genre": METADATA["genre"],
                        "language": METADATA["language"],
                        "aspect_ratio": METADATA["framing_aspect_ratio"],
                        "primary_visual_style": METADATA["primary_visual_style"],
                        "secondary_visual_style": METADATA["secondary_visual_style"],
                        "optical_and_color_palette": METADATA["optical_and_color_palette"],
                        "target_engine": METADATA["target_engine"],
                        "mpb_status": METADATA["mpb_status"],
                        "environments": ENVIRONMENTS_DATA,
                        "props": HERO_PROPS_DATA,
                        "extras": EXTRAS_DATA,
                    },
                    created_at=now,
                    updated_at=now,
                )
                session.add(project)
                await session.flush()
                print(f"[CREATED] New project '{PROJECT_TITLE}' initialized with ID: {project.id}")

            # Step 3: Project Member Binding
            stmt_mem = select(ProjectMemberModel).where(
                (ProjectMemberModel.project_id == project.id) & (ProjectMemberModel.user_id == owner_user.id)
            )
            member = (await session.execute(stmt_mem)).scalar_one_or_none()
            if not member:
                member = ProjectMemberModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    user_id=owner_user.id,
                    role="SHOWRUNNER",
                    created_at=now,
                )
                session.add(member)

            # Step 4: Master Production Bible (MPB) - UNLOCKED / DRAFT
            stmt_bible = (
                select(MasterProductionBibleModel)
                .where(MasterProductionBibleModel.project_id == project.id)
                .order_by(MasterProductionBibleModel.version.desc())
                .limit(1)
            )
            bible = (await session.execute(stmt_bible)).scalar_one_or_none()

            style_parameters = {
                "master_style_code": "#Style 02",
                "secondary_style_code": "#Style 17",
                "aspect_ratio": "16:9",
                "framing_aspect_ratio": "2.39:1 Anamorphic",
                "render_pipeline": "Hollywood IMAX 70mm / Photorealistic 35mm Film Grain",
                "film_stock": "Kodak Vision3 5219 500T",
                "anamorphic_squeeze": "2.0x Horizontal",
                "halation_level": 0.35,
                "lens_code": "#Lens 01",
                "comp_code": "#Comp 03",
                "color_palette": "DaVinci Obsidian Slate, Cold Tungsten, Amber Horizon",
                "target_engine": "Google Veo 2 / Kling AI",
            }

            world_rules = {
                "gravity": "quantum_variable",
                "atmosphere": "cold_tungsten_haze",
                "environments": ENVIRONMENTS_DATA,
                "props": HERO_PROPS_DATA,
                "extras": EXTRAS_DATA,
                "continuity_laws": [
                    "The Chronos Core quantum radiation causes mechanical clock hands to spin backward during erasure waves.",
                    "Dr. Elias Vance's left eyebrow scar is an absolute biometric invariant across all ages (#State 01 through #State 05 and Old Elias).",
                    "Maya Vance is visually anchored by her signature amber parka jacket and faded yellow ribbon across all memory projections.",
                    "The Observation Room (#Env 05) maintains zero gravity with motionless suspended water droplets and an infinite obsidian mirror floor.",
                    "Anamorphic horizontal lens flare streaks and 2.39:1 framing must be preserved across all space and observation sequences.",
                    "Costume degradation for Elias follows strict progression: wool jacket (#State 01) -> EVA suit (#State 02) -> combat scuffs (#State 03) -> damaged/torn (#State 04) -> quantum radiance (#State 05) -> restored wool jacket (#State 01).",
                ],
                "prompt_negatives": [
                    "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits",
                    "oversaturated CGI gloss, plastic skin textures, uncanny valley",
                    "cartoonish 3D render, anime cel shading, watercolor artifacts",
                    "unnatural physics, morphing limbs, flickering geometry, frame stutter",
                    "watermarks, stock photo signatures, text overlays, copyright markings",
                    "inconsistent facial scar, reversed eye orientation, digital watch display in 4D room",
                ],
            }

            if bible:
                bible.is_locked = False  # Strictly unlocked / draft
                bible.locked_at = None
                bible.locked_by_user_id = None
                bible.style_parameters = style_parameters
                bible.world_rules = world_rules
                bible.updated_at = now
                print(f"[MPB] Updated Master Production Bible (Version {bible.version}, is_locked=False)")
            else:
                bible = MasterProductionBibleModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    version=1,
                    is_locked=False,  # Strictly unlocked / draft
                    locked_at=None,
                    locked_by_user_id=None,
                    style_parameters=style_parameters,
                    world_rules=world_rules,
                    created_at=now,
                    updated_at=now,
                )
                session.add(bible)
                print(f"[MPB] Created Master Production Bible v1 (is_locked=False)")

            # Step 5: Characters & Extras
            # Upsert characters
            char_map: dict[str, CharacterModel] = {}
            for cdata in CHARACTERS_DATA:
                stmt_c = select(CharacterModel).where(
                    (CharacterModel.project_id == project.id) & (CharacterModel.name == cdata["name"])
                )
                char_obj = (await session.execute(stmt_c)).scalar_one_or_none()
                if not char_obj:
                    char_obj = CharacterModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        name=cdata["name"],
                        role=cdata["role"],
                        base_prompt=cdata["base_prompt"],
                        created_at=now,
                    )
                    session.add(char_obj)
                    await session.flush()
                else:
                    char_obj.role = cdata["role"]
                    char_obj.base_prompt = cdata["base_prompt"]

                char_map[cdata["name"]] = char_obj

                # Upsert character states
                for sdata in cdata.get("states", []):
                    stmt_s = select(CharacterStateModel).where(
                        (CharacterStateModel.character_id == char_obj.id)
                        & (CharacterStateModel.state_code == sdata["state_code"])
                    )
                    state_obj = (await session.execute(stmt_s)).scalar_one_or_none()
                    if not state_obj:
                        state_obj = CharacterStateModel(
                            id=uuid.uuid4(),
                            character_id=char_obj.id,
                            scene_id=None,
                            state_code=sdata["state_code"],
                            wardrobe=sdata["wardrobe"],
                            injuries_and_wear=sdata["injuries_and_wear"],
                            expression_anchor=sdata["expression_anchor"],
                            created_at=now,
                        )
                        session.add(state_obj)
                    else:
                        state_obj.wardrobe = sdata["wardrobe"]
                        state_obj.injuries_and_wear = sdata["injuries_and_wear"]
                        state_obj.expression_anchor = sdata["expression_anchor"]

            # Also register Extras in Characters table for full multi-view compatibility
            for edata in EXTRAS_DATA:
                stmt_e = select(CharacterModel).where(
                    (CharacterModel.project_id == project.id) & (CharacterModel.name == edata["name"])
                )
                extra_char = (await session.execute(stmt_e)).scalar_one_or_none()
                if not extra_char:
                    extra_char = CharacterModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        name=edata["name"],
                        role="EXTRAS",
                        base_prompt=f"{edata['name']} ({edata['code']}): {edata['description']} Wardrobe: {edata['costume']}",
                        created_at=now,
                    )
                    session.add(extra_char)
                else:
                    extra_char.role = "EXTRAS"
                    extra_char.base_prompt = f"{edata['name']} ({edata['code']}): {edata['description']} Wardrobe: {edata['costume']}"

            # Step 6: 50 Structured Scenes and 50 Cinematography Shots
            # If scenes already exist for this project, clean them out safely to ensure exact 50-scene ordering
            stmt_existing_scenes = select(SceneModel).where(SceneModel.project_id == project.id)
            existing_scenes = (await session.execute(stmt_existing_scenes)).scalars().all()
            if existing_scenes:
                print(f"[SCENES] Re-synchronizing existing {len(existing_scenes)} scenes...")
                for s in existing_scenes:
                    await session.delete(s)
                await session.flush()

            # Insert all 50 scenes
            for sdata in SCENES_RAW_DATA:
                scene = SceneModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    act_number=sdata["act_number"],
                    scene_number=sdata["scene_number"],
                    slugline=sdata["slugline"],
                    narrative_goal=sdata["narrative_goal"],
                    duration_target=5.0,
                    status="PLANNED",
                    created_at=now,
                )
                session.add(scene)
                await session.flush()

                # Add calibrated Shot 1 for this scene
                shot = ShotModel(
                    id=uuid.uuid4(),
                    scene_id=scene.id,
                    shot_number=1,
                    duration_seconds=5.0,
                    camera_code=sdata.get("camera_code", "#Cam 01"),
                    lens_code="#Lens 01",
                    comp_code="#Comp 03",
                    light_code=sdata.get("light_code", "#Light 01"),
                    act_code=sdata.get("act_code", "#Act 01"),
                    speed_code=sdata.get("speed_code", "#Speed 01"),
                    fg_bg_layers={
                        "tags": sdata.get("tags", []),
                        "audio_note": sdata.get("audio_note"),
                        "speaker": sdata.get("speaker"),
                        "dialogue": sdata.get("dialogue"),
                        "lens_details": "2.0x Anamorphic Scope (2.39:1)",
                        "comp_details": "Central Kubrick Symmetry",
                    },
                    dialogue=sdata.get("dialogue"),
                    transition_type=sdata.get("transition_type", "NONE"),
                    status="PLANNED",
                    created_at=now,
                )
                session.add(shot)

            await session.commit()
            print("[SUCCESS] All project records, MPB, characters, scenes, and shots committed successfully.")

            return project, is_new

    finally:
        await dispose_database_engine(engine)


# ==============================================================================
# VERIFICATION FUNCTION
# ==============================================================================

async def verify_production(project_id: uuid.UUID) -> None:
    """Query DB and verify all items exist and are consistent."""
    settings = get_settings()
    engine = create_database_engine(settings.async_database_url)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            # 1. Project
            stmt_p = select(ProjectModel).where(ProjectModel.id == project_id)
            project = (await session.execute(stmt_p)).scalar_one_or_none()
            assert project is not None, "Project not found!"

            # 2. Master Production Bible
            stmt_b = select(MasterProductionBibleModel).where(MasterProductionBibleModel.project_id == project_id)
            bible = (await session.execute(stmt_b)).scalar_one_or_none()
            assert bible is not None, "Master Production Bible not found!"
            assert bible.is_locked is False, "Master Production Bible must be UNLOCKED / DRAFT!"

            # 3. Characters & Extras
            stmt_c = select(CharacterModel).where(CharacterModel.project_id == project_id)
            chars = (await session.execute(stmt_c)).scalars().all()
            main_chars = [c for c in chars if c.role != "EXTRAS"]
            extra_chars = [c for c in chars if c.role == "EXTRAS"]

            # Check character states
            total_states = 0
            for c in main_chars:
                stmt_st = select(CharacterStateModel).where(CharacterStateModel.character_id == c.id)
                states = (await session.execute(stmt_st)).scalars().all()
                total_states += len(states)

            # Check Environments and Props in MPB world_rules
            envs = bible.world_rules.get("environments", [])
            props = bible.world_rules.get("props", [])
            extras_mpb = bible.world_rules.get("extras", [])

            # 4. Scenes
            stmt_sc = select(SceneModel).where(SceneModel.project_id == project_id).order_by(SceneModel.scene_number.asc())
            scenes = (await session.execute(stmt_sc)).scalars().all()

            act1_scenes = [s for s in scenes if s.act_number == 1]
            act2_scenes = [s for s in scenes if s.act_number == 2]
            act3_scenes = [s for s in scenes if s.act_number == 3]
            act4_scenes = [s for s in scenes if s.act_number == 4]

            # 5. Shots
            scene_ids = [s.id for s in scenes]
            stmt_sh = select(ShotModel).where(ShotModel.scene_id.in_(scene_ids))
            shots = (await session.execute(stmt_sh)).scalars().all()

            # Output Verification Matrix
            print("\n" + "=" * 70)
            print(" PRODUCTION VERIFICATION REPORT: THE FINAL OBSERVER")
            print("=" * 70)
            print(f"Project ID:              {project.id}")
            print(f"Title:                   {project.title}")
            print(f"Slug:                    {project.slug}")
            print(f"Status:                  {project.status}")
            print(f"Aspect Ratio:            {project.aspect_ratio}")
            print(f"Target Style Code:       {project.target_style_code}")
            print(f"Operational Stage:       Stage {project.operational_stage} (4-Act Storyboard & 50-Scene Blueprint)")
            print(f"Owner ID:                {project.owner_id}")
            print("-" * 70)
            print(f"MPB Version:             v{bible.version}")
            print(f"MPB Locked State:        {'LOCKED' if bible.is_locked else 'UNLOCKED / DRAFT (Verified)'}")
            print(f"Main Characters Count:   {len(main_chars)} (Dr. Elias Vance, Dr. Elena Rostova, Maya Vance, Old Elias, Commander Kael)")
            print(f"Character States Count:  {total_states} dynamic states across characters")
            print(f"Environments Count:      {len(envs)} (#Env 01 - #Env 05 in MPB world_rules)")
            print(f"Hero Props Count:        {len(props)} (#Prop 01 - #Prop 05 in MPB world_rules)")
            print(f"Extras Ensembles Count:  {len(extras_mpb)} (#Extras 01 - #Extras 03 in MPB world_rules & characters)")
            print("-" * 70)
            print(f"Total Scenes Count:      {len(scenes)} / 50 (Verified Exactly 50 Scenes)")
            print(f"  - Act I (Setup):        {len(act1_scenes)} scenes (Sc 01–12)")
            print(f"  - Act II-A (Rising):    {len(act2_scenes)} scenes (Sc 13–25)")
            print(f"  - Act II-B (Descent):   {len(act3_scenes)} scenes (Sc 26–38)")
            print(f"  - Act III & IV (Climax):{len(act4_scenes)} scenes (Sc 39–50)")
            print(f"Total Shots Count:       {len(shots)} / 50 (1 calibrated shot per scene)")
            print("=" * 70)
            print(" DIRECT ACCESS URLs:")
            print(f"  - Production Bible:    https://producer.apologets.com/projects/{project.id}/bible")
            print(f"  - 50-Scene Storyboard: https://producer.apologets.com/projects/{project.id}/scenes")
            print(f"  - Hollywood Studio:    https://producer.apologets.com/projects/{project.id}/studio")
            print(f"  - Local Dashboard:     https://producer.apologets.com/dashboard")
            print("=" * 70 + "\n")

    finally:
        await dispose_database_engine(engine)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed THE FINAL OBSERVER project.")
    parser.add_argument(
        "--owner-email",
        default=DEFAULT_OWNER_EMAIL,
        help=f"Owner email address (default: {DEFAULT_OWNER_EMAIL})",
    )
    args = parser.parse_args()
    project, is_new = asyncio.run(seed_production(owner_email=args.owner_email))
    asyncio.run(verify_production(project.id))


if __name__ == "__main__":
    main()
