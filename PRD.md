# Product Requirements Document (PRD) - MovieAIProducer

## 1. Product Overview
### 1.1 Product Vision
MovieAIProducer is an intelligent virtual film production environment that transforms creative concepts into structured, executable, and quality-controlled cinematic production workflows. It combines creative intelligence, production planning, visual continuity management, AI provider orchestration, and quality assurance into one unified system.

### 1.2 Core Product Philosophy
The system operates as a production management system, not merely a prompt generator. It maintains the relationship between story, characters, locations, cinematography, lighting, acting, motion, audio, and scene continuity, with all decisions traceable to the Master Production Bible.

### 1.3 Product Principles
1. Story before visuals.
2. Consistency before generation volume.
3. Production specifications before execution.
4. Platform-independent production data.
5. Human approval for important creative decisions.
6. Automated validation wherever practical.

## 2. User Roles
- **Project Owner:** Manages projects.
- **Director:** Controls creative decisions and approvals.
- **Production Manager:** Manages stages, assets, and scene status.
- **AI Production Agent:** Assists with story, prompt engineering, and QC.

## 3. Product Modes
- **Director Mode:** AI proposes work and waits for approval.
- **Hybrid Mode (Default):** AI handles routine tasks; requests approval for creative/structural decisions.
- **Autopilot Mode:** Maximum automation with mandatory safety/validation checks.

## 4. Application Structure
- **Dashboard:** Project overview.
- **Project/Creative Studio:** Concept and story.
- **Character/World Studio:** DNA and asset management.
- **Visual Studio:** Cinematography, lighting, acting.
- **Storyboard/Prompt/Production Studio:** Execution and tracking.
- **Continuity/QC Studio:** Consistency and quality validation.

## 5. Core Production Methodology (The 12-Step Framework)
1. Genre, Emotion, Language, and Aspect Definition.
2. Visual Style Catalog (#Style 01–#Style 18).
3. Story Architecture and Scene Blueprint.
4. Character DNA, Voice DNA, and State Evolution (#State 01–#State 05).
5. Extras/Figurant Management (#Extras 01–#Extras 08).
6. Environment Bible & Prop DNA (#Env 01–#Env 05, #Prop 01–#Prop 05).
7. Audio/Script Calibration (J/L-Cut, #Audio 01–#Audio 05).
8. Camera, Lens, and Composition Matrix (#Lens 01-#06, #Comp 01-#08).
9. Cinematic Lighting Matrix (#Light 01–#Light 14).
10. Acting, Expression, and Action Matrix (#Act 01–#Act 24).
11. Multi-Layer Scene Motion & Speed (#Speed 01–#Speed 05).
12. Executable Studio-Grade Production (Master Execution).

## 6. Functional Requirements Summary
- **Project Mgmt:** Create/Manage multi-scene projects.
- **Creative Dev:** Storyboard, screenplay, and concept generation.
- **Consistency:** Character DNA, Voice DNA, and Environment DNA locking.
- **Production Specs:** Camera, Lighting, Action, and Composition matrices.
- **Orchestration:** Platform-specific prompt generation.
- **QC:** Status tracking (Planned -> Locked) and continuity validation.

## 7. MVP Prioritization (P0 Foundation)
- Project management.
- Creative Brief & Master Production Bible.
- Character/Environment/Prop DNA.
- Scene breakdown.
- Prompt Studio (Platform-specific output).
- Production status tracking.
