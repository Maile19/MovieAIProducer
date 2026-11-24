export interface MpbVersionDisplay {
  label: string;
  tag: string;
  isLocked: boolean;
}

/**
 * Formats Master Production Bible version reflecting actual production lifecycle:
 * - Unlocked / Mutable: "Draft v0.1 (MUTABLE)" (or "Draft v1.2" for unlocked post-v1 revisions)
 * - Locked / Frozen: "Version 1.0.0 (DNA FROZEN)"
 */
export function formatMpbVersion(
  version: number = 1,
  isLocked: boolean = false
): MpbVersionDisplay {
  if (!isLocked) {
    const draftMinor = version > 1 ? `${version - 1}.${version}` : `0.${version}`;
    return {
      label: `Draft v${draftMinor}`,
      tag: "MUTABLE",
      isLocked: false,
    };
  }
  return {
    label: `Version ${version}.0.0`,
    tag: "DNA FROZEN",
    isLocked: true,
  };
}
