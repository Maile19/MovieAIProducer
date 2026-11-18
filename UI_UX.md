# UI/UX Design Specification - MovieAIProducer

## 1. Design Vision
MovieAIProducer provides a professional, studio-grade cinematic interface that hides AI technical complexity behind a structured 12-step workflow. It emphasizes visual-first storytelling, narrative continuity, and precise director control.

## 2. Design Philosophy
- **Director-Centric:** Puts creative decision-making at the forefront.
- **Workflow-Driven:** UI maps directly to the 12-Step Cinematic Pipeline.
- **Visual-First:** Previews, storyboards, and keyframes are the primary navigation/work units.
- **Context Preservation:** Project/Scene context persists throughout the application.

## 3. Application Layout (Modular Design)
- **Global Header:** Project context, production stage indicator, global search, and alerts.
- **Primary Nav:** Pipeline stages (Creative -> Production -> Editorial -> QC).
- **Workspace:** Main content area (MPB Editor, Storyboard Canvas, Scene Board, Shot Details).
- **Activity Panel:** Side panel for production queue status, recent jobs, and QC findings.

## 4. Key Workspace Components
- **MPB Editor:** Structured form-based editor with versioning and visual references.
- **Storyboard Canvas:** Drag-and-drop frame management, timing configuration, and visual sequencing.
- **Production Board:** Shot-level status cards (Planned/Generating/Approved/Locked).
- **Shot Detail Workspace:** Integrated panels for Prompt Editing, Camera/Lens/Comp Matrix, and Lighting/Action settings.
- **Continuity/QC Panels:** Highlighting potential narrative/visual drift and providing resolution evidence.

## 5. UI/UX Rules
- **Progressive Disclosure:** Simple controls for common tasks, advanced technical parameters available via detail panels.
- **Safe Operations:** Destructive actions (approve/lock/delete) require explicit confirmation.
- **State Feedback:** Status badges and progress bars reflect real backend state, never faked.
- **Responsive:** Landscape-first for production work; tablet/mobile for monitoring and approval.

## 6. Implementation Priorities (MVP)
- **P0:** Dashboard, Project Workspace, MPB Editor, Story/Screenplay modules, Scene Production Board, and Asset Library.
- **P1:** Storyboard Workspace, Prompt Studio, Continuity/QC Visualization, and Approval Workflow.
- **P2:** Advanced Editorial, Multi-User Collaboration, and Analytics.
