"use client";

import React, { useState } from "react";
import { Globe, Package, MapPin } from "lucide-react";

interface WorldPropsTabProps {
  worldRules: Record<string, any>;
  isLocked?: boolean;
  onSave?: (rules: Record<string, any>) => void;
}

export default function WorldPropsTab({
  worldRules,
  isLocked: _isLocked,
  onSave: _onSave,
}: WorldPropsTabProps) {
  // Environments #Env 01 - 05
  const [environments] = useState<any[]>(
    worldRules?.environments || [
      {
        code: "#Env 01",
        name: "Neo-Shinjuku Rain Corridor",
        architecture: "Dense brutalist cyber-concrete with towering holographic billboards.",
        atmosphere: "Heavy rainfall, steam venting from street grates, puddle reflections.",
        lighting: "#Light 03 Neon Sodium Vapor & cyan volumetric mist.",
        audio: "Continuous rain drizzle, distant sirens, low sub-bass hum.",
      },
      {
        code: "#Env 02",
        name: "Syndicate Executive Penthouse",
        architecture: "Minimalist black marble, floor-to-ceiling smart glass looking over skyline.",
        atmosphere: "Pristine, climate-controlled, dry air, zero ambient debris.",
        lighting: "#Light 01 Volumetric Amber Rim & golden backlights.",
        audio: "Whisper-quiet HVAC, soft glass chimes, distant air traffic.",
      },
      {
        code: "#Env 03",
        name: "Subterranean Server Catacombs",
        architecture: "Sub-basement cavernous rack rows, exposed liquid-nitrogen coolant piping.",
        atmosphere: "Freezing cold condensation, frost creeping up steel floor grating.",
        lighting: "#Light 06 Bioluminescent Cyan Glow & pulsing server LEDs.",
        audio: "High-frequency server fan whirring, periodic cryogenic hiss.",
      },
      {
        code: "#Env 04",
        name: "Abandoned Neon Cathedral",
        architecture: "Gothic stained-glass windows refitted with broken neon tubes and scaffolding.",
        atmosphere: "Dust motes suspended in sunbeams, incense smoke, decaying velvet.",
        lighting: "#Light 02 High-Contrast Chiaroscuro & amber god rays.",
        audio: "Deep cavernous acoustic echo, dripping water, wind whistling through broken glass.",
      },
      {
        code: "#Env 05",
        name: "Orbital Skyhook Transit Hub",
        architecture: "Titanium tether architecture, maglev train boarding tube suspended at 40,000 ft.",
        atmosphere: "Thin stratospheric clouds sweeping across transparent acrylic floor plates.",
        lighting: "#Light 04 Golden Hour Sunset Softbox at high altitude.",
        audio: "Ultrasonic maglev hum, wind sheer howling against aerodynamic composite hull.",
      },
    ]
  );

  // Signature Props #Prop 01 - 05
  const [propsList] = useState<any[]>(
    worldRules?.props || [
      {
        code: "#Prop 01",
        name: "Neural Deck 'Onyx-7'",
        material: "Matte carbon-fiber chassis with copper cooling ribs and braided fiber-optic cable.",
        weight: "Hero operational device carried by the protagonist.",
        action: "Plugs directly into occipital cranial port with tactile mechanical click.",
      },
      {
        code: "#Prop 02",
        name: "High-Frequency Monoblade",
        material: "Tungsten carbide core emitting 450nm violet plasma oscillation along the blade edge.",
        weight: "Lethal close-quarters weapon capable of piercing titanium armor.",
        action: "Unsheathes with high-frequency acoustic whine and brief violet flash.",
      },
      {
        code: "#Prop 03",
        name: "Syndicate Encrypted Key-Token",
        material: "Heavy obsidian prism inlaid with micro-etched gold circuitry and biometric thumb pad.",
        weight: "MacGuffin containing decrypted master AI source code.",
        action: "Pulses with slow amber heartbeat glow when brought near Syndicate terminal.",
      },
      {
        code: "#Prop 04",
        name: "Antique Brass Pocket Watch",
        material: "Weathered mechanical pocket watch with cracked crystal face stopped at 03:42 AM.",
        weight: "Sentimental grounding object connecting protagonist to past world.",
        action: "Flicked open with thumb during quiet moments before high-stakes operations.",
      },
      {
        code: "#Prop 05",
        name: "Aerosol Adrenaline Injector",
        material: "Pressurized pneumatic glass ampoule with surgical steel needle and pneumatic gauge.",
        weight: "Combat medical stimulant used in #State 04 to push beyond human tolerance.",
        action: "Slammed into sternum with loud pneumatic hiss and glowing orange fluid discharge.",
      },
    ]
  );

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-panel border border-border">
        <div>
          <h3 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
            <Globe className="w-4 h-4 text-amber-500" />
            <span>World Environments &amp; Signature Hero Props</span>
          </h3>
          <p className="text-xs font-mono text-obsidian-muted mt-0.5">
            Maintains visual architecture, lighting anchors, and signature tactile continuity across scenes.
          </p>
        </div>
      </div>

      {/* Environments Section (#Env 01 - 05) */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <div className="flex items-center justify-between">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-amber-500" />
            <span>Key Environments (#Env 01 - #Env 05)</span>
          </label>
          <span className="text-[10px] font-mono text-obsidian-muted">
            5 Core Narrative Locations
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {environments.map((env) => (
            <div
              key={env.code}
              className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-2.5 font-mono text-xs"
            >
              <div className="flex items-center justify-between border-b border-border/80 pb-2">
                <span className="font-bold text-amber-400">{env.code}</span>
                <span className="text-[11px] font-bold text-obsidian-primary font-sans truncate">
                  {env.name}
                </span>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-obsidian-muted uppercase">Architecture:</span>
                <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                  {env.architecture}
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-amber-500 uppercase">Atmosphere:</span>
                <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                  {env.atmosphere}
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-blue-400 uppercase">Lighting &amp; Audio:</span>
                <p className="text-[10px] text-obsidian-muted leading-tight font-sans">
                  {env.lighting} &bull; {env.audio}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Signature Props Section (#Prop 01 - 05) */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <div className="flex items-center justify-between">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
            <Package className="w-4 h-4 text-amber-500" />
            <span>Signature Hero Props (#Prop 01 - #Prop 05)</span>
          </label>
          <span className="text-[10px] font-mono text-obsidian-muted">
            Tactile Materiality Continuity
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {propsList.map((prp) => (
            <div
              key={prp.code}
              className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-2.5 font-mono text-xs"
            >
              <div className="flex items-center justify-between border-b border-border/80 pb-2">
                <span className="font-bold text-amber-400">{prp.code}</span>
                <span className="text-[11px] font-bold text-obsidian-primary font-sans truncate">
                  {prp.name}
                </span>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-obsidian-muted uppercase">Materiality:</span>
                <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                  {prp.material}
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-emerald-400 uppercase">Narrative Function:</span>
                <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                  {prp.weight}
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-amber-500 uppercase">Tactile Interaction:</span>
                <p className="text-[10px] text-obsidian-muted leading-tight font-sans">
                  {prp.action}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
