"use client";

import React, { useState } from "react";
import {
  Users,
  Plus,
  Layers,
  Mic,
  Camera,
  X,
  Loader2,
} from "lucide-react";
import { Character, api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface CharacterMatrixTabProps {
  projectId: string;
  characters: Character[];
  isLocked: boolean;
  onRefresh: () => void;
}

export default function CharacterMatrixTab({
  projectId,
  characters,
  isLocked,
  onRefresh,
}: CharacterMatrixTabProps) {
  const [selectedCharId, setSelectedCharId] = useState<string>(
    characters[0]?.id || "char_1"
  );
  const [addCharModalOpen, setAddCharModalOpen] = useState(false);
  const [addStateModalOpen, setAddStateModalOpen] = useState(false);

  // Add Character form
  const [newCharName, setNewCharName] = useState("");
  const [newCharRole, setNewCharRole] = useState("PROTAGONIST");
  const [newCharPrompt, setNewCharPrompt] = useState("");
  const [isSubmittingChar, setIsSubmittingChar] = useState(false);

  // Add State form
  const [newStateCode, setNewStateCode] = useState("#State 01");
  const [newWardrobe, setNewWardrobe] = useState("");
  const [newInjuries, setNewInjuries] = useState("");
  const [newExpression, setNewExpression] = useState("");
  const [isSubmittingState, setIsSubmittingState] = useState(false);

  // Fallback mock characters if database has none
  const activeCharacters: Character[] =
    characters.length > 0
      ? characters
      : [
          {
            id: "char_1",
            project_id: projectId,
            name: "Cipher Vance",
            role: "PROTAGONIST",
            base_prompt:
              "Male cybernetic operative, 34 years old, sharp angular jawline, obsidian fiber-optic jacket, amber cybernetic optical lens implant in right eye.",
            voice_ref_asset_id: "elevenlabs_vance_gravel_noir",
            states: [
              {
                id: "st_1",
                character_id: "char_1",
                state_code: "#State 01",
                wardrobe: "Pristine tailored obsidian trenchcoat, carbon-fiber tactical underlayer.",
                injuries_and_wear: "Zero defects, immaculate posture, polished cybernetic eye housing.",
                expression_anchor: "Stoic, guarded, calculating ocular focus.",
              },
              {
                id: "st_2",
                character_id: "char_1",
                state_code: "#State 02",
                wardrobe: "Trenchcoat unbuttoned, water-soaked lapels, fraying ballistic seams.",
                injuries_and_wear: "Light cheek lacerations, soot smudge across collarbone.",
                expression_anchor: "Fatigued, hyper-vigilant scanning.",
              },
              {
                id: "st_3",
                character_id: "char_1",
                state_code: "#State 03",
                wardrobe: "Trenchcoat torn at left shoulder, exposed reactive armor plates.",
                injuries_and_wear: "Singed synthetic skin, leaking amber fluid from optic socket.",
                expression_anchor: "Adrenaline surge, jaw clenched in defiance.",
              },
              {
                id: "st_4",
                character_id: "char_1",
                state_code: "#State 04",
                wardrobe: "Shredded armor, emergency tourniquet on cybernetic forearm.",
                injuries_and_wear: "Sparks emitting from damaged ocular servo, bloodied temple.",
                expression_anchor: "Desperation transitioning to lethal focus.",
              },
              {
                id: "st_5",
                character_id: "char_1",
                state_code: "#State 05",
                wardrobe: "Overcharged neural suit glowing with violet discharge.",
                injuries_and_wear: "Full cybernetic overload, shattered lens, heroic battle patina.",
                expression_anchor: "Transcendent catharsis, absolute resolve.",
              },
            ],
          },
          {
            id: "char_2",
            project_id: projectId,
            name: "Director Mara Thorne",
            role: "ANTAGONIST",
            base_prompt:
              "Female Syndicate Overseer, 45 years old, cold alabaster skin, sharp asymmetrical bob haircut, monochromatic silver velvet power suit.",
            voice_ref_asset_id: "elevenlabs_thorne_crisp_cold",
            states: [
              {
                id: "st_6",
                character_id: "char_2",
                state_code: "#State 01",
                wardrobe: "Immaculate silver velvet power suit, gold geometric cufflinks.",
                injuries_and_wear: "Flawless aristocratic composure.",
                expression_anchor: "Chilled condescension, predatory calm.",
              },
            ],
          },
        ];

  const selectedChar =
    activeCharacters.find((c) => c.id === selectedCharId) || activeCharacters[0];

  const handleCreateCharacter = async () => {
    if (!newCharName.trim()) return;
    try {
      setIsSubmittingChar(true);
      await api.bible.createCharacter(projectId, {
        name: newCharName.trim(),
        role: newCharRole,
        base_prompt: newCharPrompt || `${newCharName}, Hollywood cinematic character.`,
      });
      setAddCharModalOpen(false);
      setNewCharName("");
      setNewCharPrompt("");
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmittingChar(false);
    }
  };

  const handleCreateState = async () => {
    if (!selectedChar?.id || !newWardrobe.trim()) return;
    try {
      setIsSubmittingState(true);
      await api.bible.createCharacterState(selectedChar.id, {
        state_code: newStateCode,
        wardrobe: newWardrobe.trim(),
        injuries_and_wear: newInjuries.trim(),
        expression_anchor: newExpression.trim(),
      });
      setAddStateModalOpen(false);
      setNewWardrobe("");
      setNewInjuries("");
      setNewExpression("");
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmittingState(false);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Top Section: Character Roster Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-panel border border-border">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-amber-500" />
          <h3 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary">
            Character Cast &amp; Dynamic State Matrix
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {!isLocked && (
            <button
              type="button"
              onClick={() => setAddCharModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs transition-all shadow-glow"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Character</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Character Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        {activeCharacters.map((char) => (
          <button
            key={char.id}
            type="button"
            onClick={() => setSelectedCharId(char.id)}
            className={cn(
              "flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-xs font-mono transition-all border shrink-0",
              selectedChar.id === char.id
                ? "bg-amber-500/15 border-amber-500/50 text-obsidian-primary shadow-sm"
                : "bg-panel hover:bg-canvas border-border text-obsidian-secondary"
            )}
          >
            <div className="w-6 h-6 rounded-full bg-canvas border border-border flex items-center justify-center font-bold text-amber-400 text-[10px]">
              {char.name[0]}
            </div>
            <div className="text-left">
              <span className="font-bold block">{char.name}</span>
              <span className="text-[9px] uppercase text-obsidian-muted font-semibold">
                {char.role}
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* Selected Character Profile & 3-Angle Turnaround Previews */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Bio & Voice DNA */}
        <div className="lg:col-span-1 p-4 rounded-xl bg-panel border border-border space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono text-amber-500 font-bold uppercase">
                {selectedChar.role}
              </span>
              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                DNA SEED LOCKED
              </span>
            </div>
            <h4 className="font-cinzel text-base font-bold text-obsidian-primary">
              {selectedChar.name}
            </h4>
          </div>

          <div className="space-y-1.5 text-xs font-mono">
            <label className="text-[11px] text-obsidian-muted uppercase">Base Visual Prompt</label>
            <div className="p-2.5 rounded-lg bg-canvas border border-border text-obsidian-primary leading-relaxed text-[11px]">
              {selectedChar.base_prompt}
            </div>
          </div>

          <div className="space-y-1.5 text-xs font-mono">
            <label className="text-[11px] text-obsidian-muted uppercase flex items-center gap-1.5">
              <Mic className="w-3.5 h-3.5 text-amber-500" />
              <span>Voice DNA Profile</span>
            </label>
            <div className="p-2.5 rounded-lg bg-canvas border border-border flex items-center justify-between">
              <span className="text-obsidian-secondary text-[11px]">
                {selectedChar.voice_ref_asset_id || "Acoustic Timbre Default"}
              </span>
              <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[9px] font-bold">
                128kbps HQ
              </span>
            </div>
          </div>
        </div>

        {/* Right: Three-Angle Turnaround Previews (Front, Side, 3/4) */}
        <div className="lg:col-span-2 p-4 rounded-xl bg-panel border border-border space-y-3">
          <div className="flex items-center justify-between">
            <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
              <Camera className="w-4 h-4 text-amber-500" />
              <span>Three-Angle Turnaround Geometry</span>
            </label>
            <span className="text-[10px] font-mono text-obsidian-muted">
              InsightFace Geometry Consistency
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Front View */}
            <div className="aspect-[3/4] rounded-lg bg-canvas border border-border p-3 flex flex-col justify-between relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10" />
              <div className="relative z-20 flex justify-between items-center text-[10px] font-mono">
                <span className="px-1.5 py-0.5 rounded bg-black/60 text-amber-400 font-bold border border-border">
                  FRONT VIEW
                </span>
                <span className="text-emerald-400">99.1%</span>
              </div>
              <div className="flex-1 flex items-center justify-center text-obsidian-muted group-hover:text-amber-500/60 transition-colors">
                <Users className="w-16 h-16 opacity-30 group-hover:opacity-60 transition-opacity" />
              </div>
              <div className="relative z-20 text-[10px] font-mono text-obsidian-secondary">
                Orthogonal 0° &bull; Neutral Lighting
              </div>
            </div>

            {/* Profile Side View */}
            <div className="aspect-[3/4] rounded-lg bg-canvas border border-border p-3 flex flex-col justify-between relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10" />
              <div className="relative z-20 flex justify-between items-center text-[10px] font-mono">
                <span className="px-1.5 py-0.5 rounded bg-black/60 text-amber-400 font-bold border border-border">
                  SIDE PROFILE
                </span>
                <span className="text-emerald-400">97.8%</span>
              </div>
              <div className="flex-1 flex items-center justify-center text-obsidian-muted group-hover:text-amber-500/60 transition-colors">
                <Users className="w-16 h-16 opacity-30 group-hover:opacity-60 transition-opacity" />
              </div>
              <div className="relative z-20 text-[10px] font-mono text-obsidian-secondary">
                Profile 90° &bull; Silhouette Ridge
              </div>
            </div>

            {/* 3/4 Dynamic Angle */}
            <div className="aspect-[3/4] rounded-lg bg-canvas border border-border p-3 flex flex-col justify-between relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10" />
              <div className="relative z-20 flex justify-between items-center text-[10px] font-mono">
                <span className="px-1.5 py-0.5 rounded bg-black/60 text-amber-400 font-bold border border-border">
                  3/4 HERO ANGLE
                </span>
                <span className="text-emerald-400">98.5%</span>
              </div>
              <div className="flex-1 flex items-center justify-center text-obsidian-muted group-hover:text-amber-500/60 transition-colors">
                <Users className="w-16 h-16 opacity-30 group-hover:opacity-60 transition-opacity" />
              </div>
              <div className="relative z-20 text-[10px] font-mono text-obsidian-secondary">
                Oblique 45° &bull; Anamorphic Key
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dynamic State Progression Matrix (#State 01 to #State 05) */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
              <Layers className="w-4 h-4 text-amber-500" />
              <span>Dynamic State Progression Matrix (#State 01 - #State 05)</span>
            </h4>
            <p className="text-[11px] font-mono text-obsidian-muted mt-0.5">
              Tracks continuous costume weathering, physical wear/injuries, and psychological anchors across 50 scenes.
            </p>
          </div>

          {!isLocked && (
            <button
              type="button"
              onClick={() => setAddStateModalOpen(true)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-mono transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add State</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {(selectedChar.states || []).map((st) => (
            <div
              key={st.id || st.state_code}
              className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-2.5 font-mono text-xs"
            >
              <div className="flex items-center justify-between border-b border-border/80 pb-2">
                <span className="font-bold text-amber-400 text-xs">{st.state_code}</span>
                <span className="text-[10px] text-obsidian-muted">
                  {st.state_code === "#State 01"
                    ? "Normal Baseline"
                    : st.state_code === "#State 02"
                    ? "Fatigue & Wear"
                    : st.state_code === "#State 03"
                    ? "Battle Damaged"
                    : st.state_code === "#State 04"
                    ? "Psychological Breakdown"
                    : "Climax / Metamorphosis"}
                </span>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-obsidian-muted uppercase">Wardrobe:</span>
                <p className="text-[11px] text-obsidian-primary leading-tight font-sans">
                  {st.wardrobe}
                </p>
              </div>

              {st.injuries_and_wear && (
                <div className="space-y-1">
                  <span className="text-[10px] text-rose-400 uppercase">Physical Damage:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                    {st.injuries_and_wear}
                  </p>
                </div>
              )}

              {st.expression_anchor && (
                <div className="space-y-1">
                  <span className="text-[10px] text-amber-500 uppercase">Emotional Anchor:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                    {st.expression_anchor}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Add Character Modal */}
      {addCharModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                Add Cast Character
              </h4>
              <button
                type="button"
                onClick={() => setAddCharModalOpen(false)}
                className="text-obsidian-muted hover:text-obsidian-primary"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="space-y-1 font-mono">
                <label className="text-obsidian-secondary">Character Name</label>
                <input
                  type="text"
                  value={newCharName}
                  onChange={(e) => setNewCharName(e.target.value)}
                  placeholder="e.g. Elena Rostova"
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1 font-mono">
                <label className="text-obsidian-secondary">Role</label>
                <select
                  value={newCharRole}
                  onChange={(e) => setNewCharRole(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
                >
                  <option value="PROTAGONIST">Protagonist</option>
                  <option value="ANTAGONIST">Antagonist</option>
                  <option value="DEUTERAGONIST">Deuteragonist</option>
                  <option value="MENTOR">Mentor</option>
                  <option value="EXTRAS">Extras Ensemble</option>
                </select>
              </div>

              <div className="space-y-1 font-mono">
                <label className="text-obsidian-secondary">Base Visual Prompt</label>
                <textarea
                  value={newCharPrompt}
                  onChange={(e) => setNewCharPrompt(e.target.value)}
                  rows={3}
                  placeholder="Detailed physical visual description..."
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setAddCharModalOpen(false)}
                className="px-3.5 py-1.5 rounded-lg bg-canvas border border-border text-xs text-obsidian-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreateCharacter}
                disabled={isSubmittingChar || !newCharName.trim()}
                className="px-4 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs flex items-center gap-2 disabled:opacity-50"
              >
                {isSubmittingChar ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                <span>Create Character</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add State Modal */}
      {addStateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                Add State: {selectedChar?.name}
              </h4>
              <button
                type="button"
                onClick={() => setAddStateModalOpen(false)}
                className="text-obsidian-muted hover:text-obsidian-primary"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div className="space-y-1">
                <label className="text-obsidian-secondary">State Code</label>
                <select
                  value={newStateCode}
                  onChange={(e) => setNewStateCode(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
                >
                  <option value="#State 01">#State 01 - Normal</option>
                  <option value="#State 02">#State 02 - Wear &amp; Tear</option>
                  <option value="#State 03">#State 03 - Battle Damaged</option>
                  <option value="#State 04">#State 04 - Psychological Breakdown</option>
                  <option value="#State 05">#State 05 - Climax / Catharsis</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-obsidian-secondary">Wardrobe</label>
                <textarea
                  value={newWardrobe}
                  onChange={(e) => setNewWardrobe(e.target.value)}
                  rows={2}
                  placeholder="Costume and attire description..."
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-obsidian-secondary">Injuries &amp; Physical Damage</label>
                <input
                  type="text"
                  value={newInjuries}
                  onChange={(e) => setNewInjuries(e.target.value)}
                  placeholder="e.g. Scratched armor, bruised cheek"
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-obsidian-secondary">Expression Anchor</label>
                <input
                  type="text"
                  value={newExpression}
                  onChange={(e) => setNewExpression(e.target.value)}
                  placeholder="e.g. Fierce resolve, calculating gaze"
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setAddStateModalOpen(false)}
                className="px-3.5 py-1.5 rounded-lg bg-canvas border border-border text-xs text-obsidian-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreateState}
                disabled={isSubmittingState || !newWardrobe.trim()}
                className="px-4 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs flex items-center gap-2 disabled:opacity-50"
              >
                {isSubmittingState ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                <span>Save State</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
