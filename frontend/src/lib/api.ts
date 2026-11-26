/**
 * MovieAIProducer API Client & Types
 * Configured for Hollywood Non-Linear AI Studio backend
 */

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface PipelineHeaderMetrics {
  current_working_stage: number;
  completed_stages_count: number;
  total_stages: number;
  current_working_step: number;
  completed_steps_count: number;
  total_steps: number;
  progress_percentage: number;
}

export interface StageStatusDetail {
  stage: number;
  name: string;
  phase: string;
  gate: string;
  step_ref?: number | null;
  status: "completed" | "in_progress" | "awaiting_gate" | "not_started";
  is_current: boolean;
  metrics?: Record<string, unknown>;
  gate_signoff?: {
    action: string;
    stage: number;
    notes?: string;
    signed_by?: string;
    revoked_by?: string;
    timestamp: string;
  } | null;
}

export interface StepStatusDetail {
  step: number;
  code: string;
  name: string;
  desc: string;
  status: "completed" | "in_progress" | "not_started";
  mapped_stages: string[];
  is_current: boolean;
}

export interface PipelineStatusResponse {
  project_id: string;
  header_metrics: PipelineHeaderMetrics;
  stages: Record<string, StageStatusDetail>;
  steps: Record<string, StepStatusDetail>;
}

export interface Project {
  id: string;
  title: string;
  slug: string;
  status: string;
  aspect_ratio: string;
  target_style_code: string;
  operational_stage: number;
  derived_stage?: number;
  stage_name: string;
  owner_id?: string | null;
  created_at: string;
  updated_at: string;
  settings?: Record<string, unknown>;
  pipeline_status?: PipelineStatusResponse;
  stats?: {
    scenes_count: number;
    bible_version: number;
    bible_locked: boolean;
  };
}

export interface EnvironmentItem {
  code: string;
  name: string;
  architecture: string;
  atmosphere: string;
  lighting_code?: string;
  lighting_and_audio?: string;
  linked_scenes?: string;
  lighting?: string;
  audio?: string;
}

export interface PropItem {
  code: string;
  name: string;
  owner_character?: string;
  material_and_wear?: string;
  narrative_utility?: string;
  description?: string;
  material?: string;
  weight?: string;
  action?: string;
}

export interface GenerationMeta {
  engine: "polya_ai_director_llm" | "procedural_fallback";
  model?: string | null;
  director_persona?: string;
  context_ingested?: {
    style_code?: string;
    characters_count?: number;
    scenes_count?: number;
    has_synopsis?: boolean;
  };
  generated_at?: string;
  fallback_reason?: string | null;
}

export interface RulesGenerationMeta {
  engine: "polya_ai_director_llm" | "procedural_fallback";
  model?: string | null;
  director_persona?: string;
  context_ingested?: {
    style_code?: string;
    characters_count?: number;
    environments_count?: number;
    props_count?: number;
    scenes_count?: number;
    has_synopsis?: boolean;
  };
  generated_at?: string;
  fallback_reason?: string | null;
}

export interface WorldPropVariation {
  variation_id: string;
  label: string;
  rationale: string;
  code: string;
  name: string;
  lighting_code?: string;
  visual_description?: string;
  ambient_foley?: string;
  dramatic_significance?: string;
  visual_details?: string;
}

export interface WorldPropVariationsResponse {
  status: string;
  project_id: string;
  item_type: "environment" | "prop";
  code: string;
  data: WorldPropVariation[];
}

export interface LookDevPaletteToken {
  role: string;
  hex: string;
  name: string;
}

export interface LookDevPreset {
  preset_id: string;
  label: string;
  mood_rationale: string;
  palette_tokens: LookDevPaletteToken[];
  film_stock_or_medium: string;
  default_lens_code: string;
  default_light_code: string;
  aesthetic_directives: string;
  color_grade_emulation: string;
  director_rag_cues?: string;
}

export interface LookDevPresetsResponse {
  status: string;
  project_id: string;
  style_code: string;
  style_label: string;
  director_rag_cues: string;
  count: number;
  data: LookDevPreset[];
}

export interface SheetOverrideInput {
  prompt_override?: string | null;
  negative_prompt_override?: string | null;
}

export interface ProjectCreateInput {
  title: string;
  slug?: string;
  aspect_ratio?: string;
  target_style_code?: string;
  settings?: Record<string, unknown>;
  preset_id?: string;
}

export interface ProductionPreset {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  is_system: boolean;
  created_by_user_id?: string | null;
  preset_data: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface PresetCreateInput {
  name: string;
  slug?: string;
  description?: string;
  category?: string;
  preset_data: Record<string, any>;
}

export interface HermesCatalogItem {
  id: string;
  category: string;
  trend_tag: string;
  target_style_code: string;
  target_style_name: string;
  aspect_ratio: string;
  avg_retention_pacing: string;
  suggested_premise_seed: string;
  seo_keywords: string[];
}

export interface HermesTitleItem {
  rank: number;
  title: string;
  slug: string;
  trend_hook: string;
  target_keywords: string[];
  hook_score: number;
}

export interface HermesSynopsisItem {
  rank: number;
  angle_label: string;
  synopsis: string;
  retention_hook: string;
  target_audience: string;
}

export interface HermesTitlesResponse {
  status: string;
  source: "llm" | "procedural_fallback";
  context_summary: string;
  recommendations: HermesTitleItem[];
  seo_description_tags?: string[];
}

export interface HermesSynopsesResponse {
  status: string;
  source: "llm" | "procedural_fallback";
  locked_title: string;
  synopses: HermesSynopsisItem[];
}

export interface ProjectUpdateInput {
  title?: string;
  aspect_ratio?: string;
  target_style_code?: string;
  status?: string;
  settings?: Record<string, unknown>;
  operational_stage?: number;
}

export interface GateActionInput {
  action: "APPROVE" | "REVISE" | "LOCK";
  notes?: string;
  target_stage?: number;
}

export interface Scene {
  id: string;
  project_id: string;
  scene_number: number;
  slugline: string;
  narrative_goal: string;
  duration_target: number;
  status: string;
  dialogue?: string | null;
  speaking_character?: string | null;
  preview_url?: string | null;
  preview_provider?: string | null;
  act_number: number;
  shots_count?: number;
  camera_code?: string | null;
  lighting_code?: string | null;
  transition_type?: string | null;
  audio_lead_seconds?: number | null;
  // Compatibility fields
  slug?: string;
  title?: string;
  act?: "ACT_I" | "ACT_II_A" | "ACT_II_B" | "ACT_III" | string;
  narrative_beat?: string;
  dialogue_lines?: unknown[];
  audio_bridge_type?: string;
  target_duration_seconds?: number;
  created_at: string;
  updated_at?: string;
}

export interface Shot {
  id: string;
  scene_id: string;
  shot_number: number;
  composition_code?: string;
  comp_code?: string;
  camera_code?: string;
  lens_code?: string;
  lighting_code?: string;
  light_code?: string;
  action_code?: string;
  act_code?: string;
  speed_code?: string;
  duration_seconds: number;
  prompt_compiled?: string;
  prompt_override?: string;
  preview_url?: string | null;
  fg_bg_layers?: Record<string, any>;
  custom_background?: string | null;
  effective_background_url?: string | null;
  background_source?: "inherited" | "custom" | string;
  dialogue?: string | null;
  transition_type?: string;
  status: string;
  created_at: string;
  updated_at?: string;
}

export interface DirectorPolishTake {
  take_id: string;
  label: string;
  angle_rationale?: string;
  slugline: string;
  narrative_goal: string;
  dialogue?: string | null;
  camera_code: string;
  lighting_code: string;
  transition_type: string;
  director_notes: string;
  word_count?: number;
  estimated_duration_seconds?: number;
  passes_duration_limit?: boolean;
}

export interface DirectorPolishResult {
  scene_id: string;
  scene_number: number;
  original: {
    slugline: string;
    narrative_goal: string;
    dialogue?: string | null;
    camera_code?: string;
    lighting_code?: string;
  };
  suggestions: {
    slugline: string;
    narrative_goal: string;
    dialogue?: string | null;
    camera_code?: string;
    lighting_code?: string;
    transition_type?: string;
    director_notes: string;
  };
  options?: DirectorPolishTake[];
  message: string;
}

export interface DirectorAdvisorRecommendation {
  recommendation_id: string;
  axis: string;
  title: string;
  rationale: string;
  camera_code: string;
  lens_code: string;
  comp_code: string;
  light_code: string;
  act_code: string;
  speed_code: string;
  transition_type: string;
  continuity_warnings: string[];
}

export interface DirectorAdvisorResult {
  project_id: string;
  scene_id: string;
  shot_id?: string | null;
  style_code: string;
  style_family: string;
  source: "llm_rag" | "heuristic_rag" | string;
  director_rag_hits: number;
  bible_anchors: {
    matched_character?: string | null;
    active_state_code?: string | null;
    matched_environment?: string | null;
    matched_props: string[];
    applicable_laws: string[];
  };
  recommendations: DirectorAdvisorRecommendation[];
  shot_risk_flags: Array<{ code: string; severity: string; detail: string }>;
}

export interface ContinuityFinding {
  finding_id: string;
  pillar: "character_dna_states" | "world_props_lighting" | "optical_spatial" | "rules_invariants" | string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  scene_id?: string | null;
  scene_number?: number | null;
  act_number?: number | null;
  shot_id?: string | null;
  shot_number?: number | null;
  title: string;
  detail: string;
  remediation: string;
}

export interface ContinuityAuditResult {
  project_id: string;
  style_code: string;
  style_family: string;
  strict_mode: boolean;
  continuity_score: number;
  gate_status: "PASS" | "WARN" | "FAIL" | string;
  summary: {
    scenes_audited: number;
    shots_audited: number;
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
  };
  pillar_scores: {
    character_dna_states: number;
    world_props_lighting: number;
    optical_spatial: number;
    rules_invariants: number;
  };
  findings: ContinuityFinding[];
}

export interface CharacterState {
  id: string;
  character_id: string;
  scene_id?: string | null;
  state_code: string;
  state_label?: string | null;
  wardrobe: string;
  injuries_and_wear?: string;
  expression_anchor?: string;
  image_url?: string | null;
  source?: string | null;
  resolution_width?: number | null;
  resolution_height?: number | null;
  is_2k?: boolean;
  previous_1k_url?: string | null;
  created_at?: string;
}

export type CharacterMatrixSlotKey =
  | "closeup"
  | "expression"
  | "front"
  | "side"
  | "three_quarter"
  | "back"
  | "tpose"
  | "action";

export interface CharacterSheetMeta {
  image_url?: string;
  previous_1k_url?: string | null;
  prompt?: string;
  negative_prompt?: string;
  anchors_used?: string[];
  provider?: string;
  model?: string;
  seed?: number;
  aspect_ratio?: string;
  rendered_at?: string;
  updated_at?: string;
  upscaled_at?: string;
  source?: "ai_generated" | "manual_upload" | string;
  original_filename?: string;
  file_size?: number;
  width?: number;
  height?: number;
  resolution_width?: number | null;
  resolution_height?: number | null;
  is_2k?: boolean;
  status?: string;
}

export interface Upscale2KTarget {
  width: number;
  height: number;
  aspect_ratio: string;
}

export interface SheetPromptItem {
  slot: string;
  card_title: string;
  positive_prompt: string;
  negative_prompt: string;
  copy_ready_text: string;
  recommended_aspect_ratio: string;
  anchors_used: string[];
  dna_seed: number;
  width: number;
  height: number;
  preset_id?: string | null;
  routing_mode?: string;
  layers_applied?: string[];
  compiled_prompt?: string;
  prompt_override?: string | null;
  effective_prompt?: string;
  compiled_negative_prompt?: string;
  negative_prompt_override?: string | null;
  effective_negative_prompt?: string;
  has_override?: boolean;
  upscale_2k_prompt?: string;
  upscale_2k_negative_prompt?: string;
  upscale_2k_target?: Upscale2KTarget;
  style_gate_mode?: "full" | "light_override" | "strict_bypass" | string;
}

export interface Upscale2KPromptResponse {
  status: string;
  character_id: string;
  character_name: string;
  slot_key: CharacterMatrixSlotKey | "state" | string;
  state_id?: string | null;
  state_code?: string | null;
  state_label?: string | null;
  dna_seed: number;
  style_code: string;
  style_gate_mode: "full" | "light_override" | "strict_bypass" | string;
  upscale_2k_prompt: string;
  upscale_2k_negative_prompt: string;
  upscale_2k_target: Upscale2KTarget;
  has_override?: boolean;
}

export interface CharacterSheetPromptsResponse {
  data: {
    character_id: string;
    character_name: string;
    dna_seed: number;
    prompts: Record<string, SheetPromptItem>;
    states_prompts?: Record<string, SheetPromptItem>;
  };
}

export interface CharacterSheetUploadResponse {
  status: string;
  message: string;
  image_url: string;
  previous_1k_url?: string | null;
  slot: string;
  state_id?: string | null;
  state_code?: string | null;
  character_id: string;
  width: number;
  height: number;
  resolution_width?: number;
  resolution_height?: number;
  is_2k?: boolean;
  sheet_metadata: CharacterSheetMeta;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  role: string;
  narrative_summary?: string | null;
  voice_dna_profile?: string | null;
  base_prompt: string;
  face_ref_asset_id?: string | null;
  voice_ref_asset_id?: string | null;
  closeup_image_url?: string | null;
  front_image_url?: string | null;
  side_image_url?: string | null;
  three_quarter_image_url?: string | null;
  back_image_url?: string | null;
  tpose_image_url?: string | null;
  action_image_url?: string | null;
  expression_image_url?: string | null;
  dna_seed?: number | null;
  sheet_metadata?: Record<string, CharacterSheetMeta>;
  created_at?: string;
  states?: CharacterState[];
}

export interface MasterProductionBible {
  id: string;
  project_id: string;
  version: number;
  is_locked: boolean;
  locked_at?: string | null;
  locked_by_user_id?: string | null;
  style_parameters: Record<string, unknown>;
  world_rules: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MatrixCatalog {
  styles: Array<{ code: string; name: string; description: string; preview_url?: string; [key: string]: unknown }>;
  lighting: Array<{ code: string; name: string; description?: string; mood?: string; [key: string]: unknown }>;
  acting: Array<{ code: string; name?: string; cue?: string; intensity?: string; category?: string; [key: string]: unknown }>;
  cameras: Array<{ code: string; name: string; movement?: string; [key: string]: unknown }>;
  lenses: Array<{ code: string; name: string; focal_length?: string; bokeh?: string; [key: string]: unknown }>;
  compositions: Array<{ code: string; name: string; framing?: string; [key: string]: unknown }>;
  speeds: Array<{ code: string; name: string; fps?: number; timing?: string; [key: string]: unknown }>;
}

export interface QCSubScores {
  narrative_pacing: number;
  continuity_dna: number;
  optical_coverage: number;
  asset_readiness: number;
}

export interface QCIssue {
  category: string;
  severity: "CRITICAL" | "WARNING" | "INFO" | string;
  message: string;
  suggestion: string;
}

export interface QCReport {
  id?: string;
  scene_id?: string;
  scene_number?: number;
  overall_score: number;
  overall_score_100?: number;
  passed?: boolean;
  biometric_score?: number;
  aesthetic_score?: number;
  acoustic_score?: number;
  status?: "PASS" | "WARN" | "FAIL" | "PENDING" | "PASSED" | "FLAGGED" | "FAILED";
  asset_status?: "ready" | "partial" | "pending_asset" | string;
  sub_scores?: QCSubScores;
  issues?: QCIssue[];
  metrics?: {
    face_similarity_insightface?: number | null;
    clip_text_video_score?: number | null;
    aesthetic_score?: number | null;
    temporal_jitter_variance?: number | null;
    audio_snr_db?: number | null;
    asset_readiness_ratio?: number;
    dialogue_word_count?: number;
    dialogue_max_words?: number;
    shots_count?: number;
    shot_duration_total?: number;
    style_code?: string;
  };
  critical_defects?: string[];
  warnings?: string[];
  findings?: Array<{ category: string; severity: string; message: string; timestamp_code?: string }>;
  findings_json?: string[];
}

export interface ProjectQCSummary {
  project_id: string;
  continuum_score: number;
  total_scenes: number;
  pass_count: number;
  warn_count: number;
  fail_count: number;
  pending_asset_count: number;
  status: "PASS" | "WARN" | "FAIL" | "EMPTY" | string;
  top_gaps: Array<{ message: string; affected_scenes: number }>;
  scene_audits: Array<{
    scene_id: string;
    scene_number: number;
    overall_score_100: number;
    status: string;
    asset_status: string;
  }>;
}

export interface QCEvaluateInput {
  scene_id?: string;
  shot_id?: string;
  asset_id?: string;
  face_similarity?: number;
  clip_score?: number;
  aesthetic_score?: number;
  temporal_jitter?: number;
  audio_snr_db?: number;
  prompt?: string;
}

export interface AudioScriptCue {
  cue_number: number;
  scene_id: string;
  act_number: number;
  scene_number: number;
  slugline: string;
  shot_id?: string | null;
  shot_number: number;
  speaker: string;
  voice_profile: string;
  has_voice_dna: boolean;
  active_state_code: string;
  emotion_cue: string;
  text: string;
  is_sfx: boolean;
  word_count: number;
  estimated_duration_seconds: number;
  passes_duration_limit: boolean;
  transition_type: string;
  audio_lead_seconds: number;
  shot_start_seconds: number;
  shot_end_seconds: number;
  start_seconds: number;
  end_seconds: number;
  speaking_rate_wps: number;
  prosody_rate: string;
  prosody_pitch: string;
  pause_before_ms: number;
  pause_after_ms: number;
  ssml: string;
}

export interface AudioScriptData {
  project_id: string;
  project_title: string;
  total_scenes: number;
  total_cues: number;
  spoken_cues: number;
  sfx_cues: number;
  total_runtime_seconds: number;
  cues: AudioScriptCue[];
}

export interface TranspileInput {
  provider_target: "google_flow" | "veo" | "kling" | "seedance" | "runway" | "sora" | "comfyui" | "9router" | "flux" | string;
  project_id?: string;
  scene_id?: string;
  shot_id?: string;
  character_id?: string;
  state_number?: number;
  style_code?: string;
  camera_code?: string;
  lens_code?: string;
  comp_code?: string;
  light_code?: string;
  act_code?: string;
  speed_code?: string;
  character_dna?: string;
  character_name?: string;
  state_code?: string;
  wardrobe?: string;
  physical_damage?: string;
  emotional_anchor?: string;
  env_dna?: string;
  action_description?: string;
  slugline?: string;
  narrative_goal?: string;
  fg_description?: string;
  bg_description?: string;
  dialogue?: string | null;
  transition_type?: string;
  audio_lead_seconds?: number | null;
  aspect_ratio?: string;
  preset_rules?: Record<string, any>;
  is_non_verbal?: boolean;
  model?: string;
  genre?: string;
}

export interface TranspileResult {
  positive: string;
  negative: string;
  positive_prompt?: string;
  negative_prompt?: string;
  engine: string;
  compiled_engines?: Record<string, { engine: string; positive_prompt: string; negative_prompt: string }>;
  rag_references?: Array<Record<string, unknown>>;
  metadata?: {
    target_engine?: string;
    aspect_ratio?: string;
    codes?: Record<string, string>;
    engine_params?: Record<string, unknown>;
    audio_bridge?: Record<string, unknown>;
    continuity_sources?: {
      style_code?: string;
      character_name?: string | null;
      state_code?: string;
      has_character_dna?: boolean;
      has_wardrobe_dna?: boolean;
      director_rag_hits?: number;
      screenwriter_rag_hits?: number;
    };
    screenwriter_cues?: string | null;
    parameters?: Record<string, unknown>;
    prompt_tokens_est?: number;
    [key: string]: unknown;
  };
}

export interface DialogueAlternative {
  id: string;
  label: string;
  style_note?: string;
  dialogue: string;
  word_count: number;
  syllable_count?: number;
  estimated_duration_seconds: number;
  passes_duration_limit: boolean;
  max_allowed_words?: number;
  transition_type: string;
  audio_lead_seconds: number;
}

export interface DialogueCalibrationResult {
  scene_id: string;
  word_count: number;
  syllables_count?: number;
  syllable_count?: number;
  estimated_duration_seconds: number;
  passes_duration_limit?: boolean;
  passes_5s_limit: boolean;
  max_allowed_words?: number;
  max_seconds?: number;
  recommended_audio_bridge?: string;
  transition_type?: string;
  audio_lead_seconds: number;
  analysis?: string;
  trimmed_suggestion?: string | null;
  alternatives?: DialogueAlternative[];
}

export interface FlowAccount {
  id: number;
  label: string;
  profile_dir: string;
  status: "active" | "busy" | "cooldown" | "need_relogin" | "disabled" | string;
  cooldown_until?: string | null;
  daily_count: number;
  total_count: number;
  consecutive_failures: number;
  last_error?: string | null;
  last_used_at?: string | null;
  updated_at?: string | null;
}

export interface FlowSettings {
  socks5_proxy: string;
  batch_size_per_account: number;
  min_delay_sec: number;
  max_delay_sec: number;
  cooldown_minutes: number;
  worker_enabled: boolean;
  target_resolution?: "1k" | "2k" | "4k";
}

export interface FlowProxyStatus {
  healthy: boolean;
  status: "online" | "offline";
  host: string;
  port: number;
  proxy_url: string;
  latency_ms?: number | null;
  detail: string;
}

export interface FlowJob {
  id: string;
  project_id?: string | null;
  scene_id?: string | null;
  prompt: string;
  aspect_ratio: string;
  status: "queued" | "processing" | "completed" | "failed" | string;
  assigned_account_id?: number | null;
  output_filename?: string | null;
  image_url?: string | null;
  debug_screenshot_url?: string | null;
  error_message?: string | null;
  retry_count: number;
  max_retries: number;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface FlowJobCreateInput {
  prompt: string;
  aspect_ratio?: "16:9" | "9:16" | "1:1" | string;
  reference_image_paths?: string[];
  project_id?: string;
  scene_id?: string;
  preferred_account_id?: number;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: any;

  constructor(status: number, message: any, code?: string, detail?: any) {
    let resolvedMessage = "";
    if (typeof message === "string" && message !== "[object Object]") {
      resolvedMessage = message;
    } else if (message && typeof message === "object") {
      resolvedMessage =
        (typeof message.message === "string" && message.message !== "[object Object]"
          ? message.message
          : null) ||
        (typeof message.detail === "string" ? message.detail : null) ||
        JSON.stringify(message);
    } else {
      resolvedMessage = String(message || "Unknown error");
    }

    if (resolvedMessage === "[object Object]") {
      if (detail && typeof detail === "object" && typeof detail.message === "string") {
        resolvedMessage = detail.message;
      } else {
        resolvedMessage = "Unknown error";
      }
    }

    super(resolvedMessage);
    this.name = "ApiError";
    this.status = status;
    this.code =
      code ||
      (typeof message === "object" ? message?.error_code || message?.code : undefined);
    this.detail = detail || (typeof message === "object" ? message : undefined);
  }
}

export function getErrorMessage(err: unknown, fallback: string = "Terjadi kesalahan"): string {
  if (!err) return fallback;
  if (typeof err === "string" && err !== "[object Object]") return err;
  if (err instanceof ApiError) {
    if (err.message && err.message !== "[object Object]") return err.message;
    if (err.detail) {
      if (typeof err.detail === "string") return err.detail;
      if (typeof err.detail === "object" && typeof err.detail.message === "string") return err.detail.message;
    }
    return fallback;
  }
  if (typeof err === "object") {
    const e = err as any;
    if (typeof e.message === "string" && e.message !== "[object Object]") {
      return e.message;
    }
    if (typeof e.detail === "string" && e.detail !== "[object Object]") {
      return e.detail;
    }
    if (typeof e.error === "string" && e.error !== "[object Object]") {
      return e.error;
    }
    if (e.message && typeof e.message === "object") {
      const nested = getErrorMessage(e.message, "");
      if (nested) return nested;
    }
    if (e.detail && typeof e.detail === "object") {
      const nested = getErrorMessage(e.detail, "");
      if (nested) return nested;
    }
    if (e.error && typeof e.error === "object") {
      const nested = getErrorMessage(e.error, "");
      if (nested) return nested;
    }
  }
  return fallback;
}

export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("http://127.0.0.1:8090") || trimmed.startsWith("http://localhost:8090")) {
    return trimmed.replace(/^https?:\/\/(?:127\.0\.0\.1|localhost):8090/, "");
  }
  return trimmed;
}

const getApiBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    return "/api/v1";
  }
  return process.env.INTERNAL_API_URL ? `${process.env.INTERNAL_API_URL}/api/v1` : "http://127.0.0.1:8090/api/v1";
};

export async function apiRequest<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = endpoint.startsWith("http")
    ? endpoint
    : endpoint.startsWith("/api/")
    ? endpoint
    : `${baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const defaultHeaders: Record<string, string> = {
    Accept: "application/json",
  };

  if (!(options.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const statusLabel = response.statusText ? `${response.status} ${response.statusText}` : `HTTP ${response.status}`;
    let errorDetail =
      response.status === 504
        ? `Gateway Timeout (${statusLabel}): proses render upstream melebihi batas waktu.`
        : response.status === 502
        ? `Bad Gateway (${statusLabel}): server backend atau provider upstream gagal merespons.`
        : statusLabel;
    let errorCode = "UNKNOWN_ERROR";
    let errorExtra: any = undefined;
    try {
      const rawText = await response.text();
      if (rawText) {
        try {
          const errJson = JSON.parse(rawText);
          if (errJson?.error) {
            if (typeof errJson.error === "string") {
              errorDetail = errJson.error;
            } else if (typeof errJson.error === "object" && errJson.error !== null) {
              errorExtra = errJson.error;
              errorCode = errJson.error.code || errJson.error.error_code || errorCode;
              if (typeof errJson.error.message === "string") {
                errorDetail = errJson.error.message;
              } else if (typeof errJson.error.message === "object" && errJson.error.message !== null) {
                const nested = errJson.error.message;
                errorCode = nested.error_code || nested.code || errorCode;
                errorDetail = nested.message || nested.detail || JSON.stringify(nested);
                errorExtra = nested;
              } else if (errJson.error.detail) {
                errorDetail =
                  typeof errJson.error.detail === "string"
                    ? errJson.error.detail
                    : JSON.stringify(errJson.error.detail);
              } else {
                errorDetail = JSON.stringify(errJson.error);
              }
            }
          } else if (errJson?.detail) {
            if (Array.isArray(errJson.detail)) {
              errorDetail = errJson.detail.map((e: any) => e.msg || JSON.stringify(e)).join(", ");
              errorCode = "VALIDATION_ERROR";
            } else if (typeof errJson.detail === "object" && errJson.detail !== null) {
              errorDetail = errJson.detail.message || errJson.detail.detail || JSON.stringify(errJson.detail);
              errorCode = errJson.detail.error_code || errJson.detail.code || errorCode;
              errorExtra = errJson.detail;
            } else {
              errorDetail = typeof errJson.detail === "string" ? errJson.detail : String(errJson.detail);
            }
          }
          if (errJson?.error_code) {
            errorCode = errJson.error_code;
          }
        } catch {
          // Non-JSON error body (e.g. Nginx HTML error page)
          const cleanText = rawText.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
          if (cleanText) {
            errorDetail = `${statusLabel}: ${cleanText.slice(0, 180)}`;
          }
        }
      }
    } catch {
      // ignore body read error
    }
    throw new ApiError(response.status, errorDetail, errorCode, errorExtra);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null as unknown as T;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return (await response.text()) as unknown as T;
}

/* =====================================================================
 * API SDK Methods
 * ===================================================================== */

export const api = {
  // Auth
  auth: {
    me: async (): Promise<{ data: User }> => {
      return apiRequest<{ data: User }>("/auth/me");
    },
    logout: async (): Promise<{ data: { message: string } }> => {
      return apiRequest<{ data: { message: string } }>("/auth/logout", {
        method: "POST",
      });
    },
    getGoogleLoginUrl: (): string => {
      return "/api/v1/auth/google/login";
    },
  },

  // Projects
  projects: {
    list: async (params?: { search?: string; limit?: number; offset?: number }): Promise<{
      data: Project[];
      pagination: { limit?: number; offset?: number; count?: number; total?: number; [key: string]: unknown };
      metrics?: { total: number; pre_production: number; generation: number; post_master: number };
    }> => {
      const query = new URLSearchParams();
      if (params?.search) query.set("search", params.search);
      if (params?.limit) query.set("limit", params.limit.toString());
      if (params?.offset) query.set("offset", params.offset.toString());
      const qs = query.toString();
      return apiRequest<{
        data: Project[];
        pagination: { limit?: number; offset?: number; count?: number; total?: number; [key: string]: unknown };
        metrics?: { total: number; pre_production: number; generation: number; post_master: number };
      }>(`/projects${qs ? `?${qs}` : ""}`);
    },
    get: async (id: string): Promise<{ data: Project }> => {
      return apiRequest<{ data: Project }>(`/projects/${id}`);
    },
    create: async (payload: ProjectCreateInput): Promise<{ data: Project }> => {
      return apiRequest<{ data: Project }>("/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    update: async (id: string, payload: ProjectUpdateInput): Promise<{ data: Project }> => {
      return apiRequest<{ data: Project }>(`/projects/${id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    delete: async (id: string): Promise<{ data: { id: string; title: string; message: string } }> => {
      return apiRequest<{ data: { id: string; title: string; message: string } }>(`/projects/${id}`, {
        method: "DELETE",
      });
    },
    advanceStage: async (id: string, notes?: string): Promise<{ data: Project }> => {
      return apiRequest<{ data: Project }>(`/projects/${id}/advance-stage`, {
        method: "POST",
        body: JSON.stringify({ notes }),
      });
    },
    gateAction: async (id: string, payload: GateActionInput): Promise<{ data: Project }> => {
      return apiRequest<{ data: Project }>(`/projects/${id}/gate`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    getPipelineStatus: async (id: string): Promise<{ data: PipelineStatusResponse }> => {
      return apiRequest<{ data: PipelineStatusResponse }>(`/projects/${id}/pipeline-status`);
    },
    gateSignoff: async (
      id: string,
      payload: { stage: number; action: "APPROVE" | "REVOKE"; notes?: string }
    ): Promise<{ data: PipelineStatusResponse }> => {
      return apiRequest<{ data: PipelineStatusResponse }>(`/projects/${id}/gate-signoff`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },

  // Master Production Bible
  bible: {
    get: async (projectId: string): Promise<{ data: MasterProductionBible }> => {
      return apiRequest<{ data: MasterProductionBible }>(`/projects/${projectId}/bible`);
    },
    update: async (projectId: string, payload: Partial<MasterProductionBible>): Promise<{ data: MasterProductionBible }> => {
      return apiRequest<{ data: MasterProductionBible }>(`/projects/${projectId}/bible`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    lock: async (projectId: string, payload?: { approval_notes?: string; confirm_dna_freeze?: boolean }): Promise<{ data: MasterProductionBible }> => {
      return apiRequest<{ data: MasterProductionBible }>(`/projects/${projectId}/bible/lock`, {
        method: "POST",
        body: JSON.stringify(payload || { approval_notes: "Master DNA Freeze", confirm_dna_freeze: true }),
      });
    },
    generateWorldPropVariations: async (
      projectId: string,
      payload: {
        item_type: "environment" | "prop";
        code: string;
        current_item?: Record<string, any> | null;
        additional_notes?: string | null;
      }
    ): Promise<WorldPropVariationsResponse> => {
      return apiRequest<WorldPropVariationsResponse>(
        `/projects/${projectId}/bible/world-props/variations`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );
    },
    lookDevPresets: async (
      projectId: string,
      params?: { style_code?: string; include_rag_cues?: boolean }
    ): Promise<LookDevPresetsResponse> => {
      const query = new URLSearchParams();
      if (params?.style_code) query.set("style_code", params.style_code);
      if (params?.include_rag_cues !== undefined) {
        query.set("include_rag_cues", String(params.include_rag_cues));
      }
      const suffix = query.toString() ? `?${query.toString()}` : "";
      return apiRequest<LookDevPresetsResponse>(
        `/projects/${projectId}/bible/look-dev-presets${suffix}`
      );
    },
    saveSheetOverride: async (
      projectId: string,
      characterId: string,
      slotKey: string,
      payload: SheetOverrideInput
    ): Promise<{
      status: string;
      character_id: string;
      slot_key: string;
      has_override: boolean;
      overrides: Record<string, any>;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/${characterId}/sheet-overrides`, {
        method: "PUT",
        body: JSON.stringify({ slot_key: slotKey, ...payload }),
      });
    },
    generateWorldProps: async (
      projectId: string,
      payload?: { additional_notes?: string | null }
    ): Promise<{
      status: string;
      project_id: string;
      environments: EnvironmentItem[];
      props: PropItem[];
      generation_meta?: GenerationMeta;
      data: {
        id: string;
        project_id: string;
        version: number;
        is_locked: boolean;
        world_rules: Record<string, any>;
        updated_at: string;
      };
    }> => {
      return apiRequest(`/projects/${projectId}/bible/generate-world-props`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    generateRulesInvariants: async (
      projectId: string,
      payload?: { additional_notes?: string | null }
    ): Promise<{
      status: string;
      project_id: string;
      continuity_rules: string[];
      continuity_laws: string[];
      negative_prompts: string[];
      prompt_negatives: string[];
      rules_generation_meta?: RulesGenerationMeta;
      data: {
        id: string;
        project_id: string;
        version: number;
        is_locked: boolean;
        world_rules: Record<string, any>;
        updated_at: string;
      };
    }> => {
      return apiRequest(`/projects/${projectId}/bible/generate-rules-invariants`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    listCharacters: async (projectId: string): Promise<{ data: Character[] }> => {
      return apiRequest<{ data: Character[] }>(`/projects/${projectId}/characters`);
    },
    generateCast: async (
      projectId: string,
      payload?: {
        replace_existing?: boolean;
        preferred_count?: number | null;
        additional_notes?: string | null;
      }
    ): Promise<{
      status: string;
      cast_rationale: string;
      count: number;
      data: Character[];
    }> => {
      return apiRequest(`/projects/${projectId}/characters/generate-cast`, {
        method: "POST",
        body: JSON.stringify(payload || { replace_existing: true }),
      });
    },
    generateOneCharacter: async (
      projectId: string,
      payload?: {
        preferred_role?: string | null;
        custom_directive?: string | null;
      }
    ): Promise<{
      status: string;
      data: Character;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/generate-one`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    regenerateCharacter: async (
      projectId: string,
      characterId: string,
      payload?: {
        preserve_role?: boolean;
        custom_directive?: string | null;
      }
    ): Promise<{
      status: string;
      data: Character;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/${characterId}/regenerate`, {
        method: "POST",
        body: JSON.stringify(payload || { preserve_role: true }),
      });
    },
    updateCharacter: async (
      projectId: string,
      characterId: string,
      payload: {
        name?: string;
        role?: string;
        base_prompt?: string;
        voice_dna_profile?: string;
        narrative_summary?: string;
        dna_seed?: number;
      }
    ): Promise<{
      status: string;
      data: Character;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/${characterId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    deleteCharacter: async (
      projectId: string,
      characterId: string
    ): Promise<{ status: string; message: string }> => {
      return apiRequest(`/projects/${projectId}/characters/${characterId}`, {
        method: "DELETE",
      });
    },
    createCharacter: async (
      projectId: string,
      payload: {
        name: string;
        role: string;
        base_prompt: string;
        narrative_summary?: string;
        voice_dna_profile?: string;
        face_ref_asset_id?: string;
        voice_ref_asset_id?: string;
        dna_seed?: number;
        preview_token?: string;
      }
    ): Promise<{ data: Character }> => {
      return apiRequest<{ data: Character }>(`/projects/${projectId}/characters`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    autoGenerateCharacter: async (
      projectId: string,
      payload: {
        llm_provider?: string;
        mode?: "all" | "name" | "suggestion" | "visual_prompt";
        current_draft?: {
          name?: string;
          role?: string;
          archetype_and_bio?: string;
          voice_dna_profile?: string;
          base_visual_prompt?: string;
          dna_seed?: number;
        };
      }
    ): Promise<{
      data: {
        name: string;
        role_suggestion: string;
        archetype_and_bio: string;
        voice_dna_profile?: string;
        base_visual_prompt: string;
      };
    }> => {
      return apiRequest(`/projects/${projectId}/characters/auto-generate`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    previewCharacter: async (
      projectId: string,
      payload: {
        name: string;
        role: string;
        base_visual_prompt: string;
        dna_seed?: number;
        image_provider?: string;
        model?: string;
        target?: "closeup" | "expression" | "front" | "both" | "all";
        aspect_ratio?: string;
        preview_token?: string;
        respect_provider_override?: boolean;
      }
    ): Promise<{
      status: "completed" | "queued";
      preview_token: string;
      closeup_url?: string;
      expression_url?: string;
      front_url?: string;
      job_id?: string;
      slot?: "closeup" | "expression" | "front";
      dna_seed: number;
      provider: string;
      slot_dimensions?: Record<string, { resolution_width?: number; resolution_height?: number; is_2k?: boolean }>;
      message?: string;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/preview`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    attachCharacterPreviewJob: async (
      projectId: string,
      payload: {
        preview_token: string;
        job_id: string;
        slot: "closeup" | "expression" | "front";
      }
    ): Promise<{
      status: string;
      preview_token: string;
      slot: string;
      image_url: string;
      resolution_width?: number | null;
      resolution_height?: number | null;
      is_2k?: boolean;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/preview/attach`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    upscaleCharacterPreview: async (
      projectId: string,
      payload: {
        preview_token: string;
        slot: "closeup" | "expression" | "front";
        name?: string;
        role?: string;
        base_visual_prompt?: string;
        dna_seed?: number;
        provider_override?: string;
      }
    ): Promise<{
      status: string;
      preview_token: string;
      slot: "closeup" | "expression" | "front";
      image_url: string;
      previous_1k_url?: string | null;
      resolution_width: number;
      resolution_height: number;
      is_2k: boolean;
      provider: string;
      model?: string;
      message?: string;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/preview/upscale`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    revertCharacterPreview: async (
      projectId: string,
      payload: {
        preview_token: string;
        slot: "closeup" | "expression" | "front";
      }
    ): Promise<{
      status: string;
      preview_token: string;
      slot: "closeup" | "expression" | "front";
      image_url: string;
      resolution_width: number;
      resolution_height: number;
      is_2k: boolean;
    }> => {
      return apiRequest(`/projects/${projectId}/characters/preview/revert`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    cleanupCharacterPreview: async (
      projectId: string,
      previewToken: string
    ): Promise<{ status: string; preview_token: string }> => {
      return apiRequest(`/projects/${projectId}/characters/preview/${previewToken}`, {
        method: "DELETE",
      });
    },
    createCharacterState: async (
      characterId: string,
      payload: { scene_id?: string; state_code: string; state_label?: string | null; wardrobe: string; injuries_and_wear?: string; expression_anchor?: string }
    ): Promise<{ data: CharacterState }> => {
      return apiRequest<{ data: CharacterState }>(`/characters/${characterId}/states`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    suggestCharacterState: async (
      characterId: string,
      payload: {
        state_code: string;
        target_field?: "all" | "wardrobe" | "injuries" | "expression";
        current_values?: {
          wardrobe?: string;
          injuries_and_wear?: string;
          expression_anchor?: string;
        };
        previous_value?: string;
        is_regeneration?: boolean;
        llm_provider?: string;
      },
      signal?: AbortSignal
    ): Promise<{
      status: string;
      data: {
        state_code: string;
        target_field: string;
        wardrobe: string | null;
        injuries_and_wear: string | null;
        expression_anchor: string | null;
      };
    }> => {
      return apiRequest(`/characters/${characterId}/states/suggest`, {
        method: "POST",
        body: JSON.stringify(payload),
        signal,
      });
    },
    updateCharacterState: async (
      characterId: string,
      stateId: string,
      payload: {
        scene_id?: string;
        state_code?: string;
        state_label?: string | null;
        wardrobe?: string;
        injuries_and_wear?: string;
        expression_anchor?: string;
      }
    ): Promise<{ data: CharacterState }> => {
      return apiRequest<{ data: CharacterState }>(`/characters/${characterId}/states/${stateId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    deleteCharacterState: async (
      characterId: string,
      stateId: string
    ): Promise<{ status: string; message: string; id: string }> => {
      return apiRequest(`/characters/${characterId}/states/${stateId}`, {
        method: "DELETE",
      });
    },
    generateCharacterAsset: async (
      characterId: string,
      payload: {
        target_type: "turnaround" | "sheet" | "state" | string;
        angle?: "front" | "side" | "three_quarter" | "back" | "tpose" | "action" | "expression" | string;
        state_id?: string;
        provider?: "ag_gemini_flash" | "9router" | "google_flow" | string;
        model?: string;
        prompt_override?: string;
        aspect_ratio?: string;
        skip_existing?: boolean;
      }
    ): Promise<{
      status: "completed" | "queued" | "skipped";
      skipped?: boolean;
      job_id?: string;
      image_url?: string;
      provider: string;
      model?: string;
      target_type: string;
      angle?: string;
      state_id?: string;
      anchors_used?: string[];
      dna_seed?: number;
      compiled_prompt?: string;
      message?: string;
    }> => {
      return apiRequest(`/characters/${characterId}/generate-asset`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    attachCharacterJobResult: async (
      characterId: string,
      payload: {
        job_id: string;
        target_type: "turnaround" | "sheet" | "state" | string;
        angle?: "front" | "side" | "three_quarter" | "back" | "tpose" | "action" | "expression" | string;
        state_id?: string;
      }
    ): Promise<{
      status: string;
      message: string;
      image_url: string;
      angle?: string;
      target_type?: string;
    }> => {
      return apiRequest(`/characters/${characterId}/attach-job-result`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    getActiveJobs: async (
      characterId: string
    ): Promise<{
      status: string;
      character_id: string;
      count: number;
      jobs: Array<{
        job_id: string;
        character_id: string;
        asset_slot: string;
        target_type: string;
        state_id: string | null;
        status: string;
        started_at: string | null;
        created_at: string | null;
      }>;
    }> => {
      return apiRequest(`/characters/${characterId}/active-jobs`);
    },
    getSheetPrompts: async (
      characterId: string
    ): Promise<CharacterSheetPromptsResponse> => {
      return apiRequest<CharacterSheetPromptsResponse>(`/bible/characters/${characterId}/sheet-prompts`);
    },
    getUpscalePrompt: async (
      characterId: string,
      slotKey: CharacterMatrixSlotKey | "state" | string,
      stateId?: string
    ): Promise<Upscale2KPromptResponse> => {
      const qs = new URLSearchParams();
      if (stateId) {
        qs.set("slot_key", "state");
        qs.set("state_id", stateId);
      } else {
        qs.set("slot_key", slotKey);
      }
      return apiRequest<Upscale2KPromptResponse>(
        `/bible/characters/${characterId}/upscale-prompt?${qs.toString()}`
      );
    },
    downloadCharacterAsset: async (
      characterId: string,
      slotKey: CharacterMatrixSlotKey | "state" | string,
      characterName?: string,
      stateId?: string
    ): Promise<string> => {
      const baseUrl = getApiBaseUrl();
      const qs = new URLSearchParams();
      if (stateId) {
        qs.set("slot_key", "state");
        qs.set("state_id", stateId);
      } else {
        qs.set("slot_key", slotKey);
      }
      const url = `${baseUrl}/bible/characters/${characterId}/download-asset?${qs.toString()}`;
      const response = await fetch(url, {
        method: "GET",
        credentials: "include",
      });
      if (!response.ok) {
        let errorDetail = response.statusText || "Gagal mengunduh aset.";
        try {
          const errJson = await response.json();
          errorDetail = getErrorMessage(errJson, errorDetail);
        } catch {
          // ignore
        }
        throw new ApiError(response.status, errorDetail, "DOWNLOAD_ASSET_FAILED");
      }
      const cd = response.headers.get("Content-Disposition") || "";
      const fnMatch = cd.match(/filename="?([^";\n]+)"?/i);
      const fallbackSlug =
        (characterName || "character")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-+|-+$/g, "") || "character";
      const fallbackToken = stateId ? `state_${stateId.slice(0, 8)}` : slotKey;
      const filename = fnMatch?.[1]?.trim() || `${fallbackSlug}_${fallbackToken}_1k.png`;
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = filename;
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1500);
      return filename;
    },
    uploadCharacterSheet: async (
      characterId: string,
      slot: string,
      file: File
    ): Promise<CharacterSheetUploadResponse> => {
      const formData = new FormData();
      formData.append("slot", slot);
      formData.append("file", file);
      return apiRequest<CharacterSheetUploadResponse>(`/characters/${characterId}/upload-sheet`, {
        method: "POST",
        body: formData,
      });
    },
    uploadCharacterStateImage: async (
      characterId: string,
      stateId: string,
      file: File
    ): Promise<CharacterSheetUploadResponse> => {
      const formData = new FormData();
      formData.append("file", file);
      return apiRequest<CharacterSheetUploadResponse>(
        `/bible/characters/${characterId}/states/${stateId}/upload-image`,
        {
          method: "POST",
          body: formData,
        }
      );
    },
    upscaleCharacterAsset: async (
      characterId: string,
      payload: {
        slot_key?: string;
        state_id?: string;
        provider_override?: string;
        model_override?: string;
      }
    ): Promise<{
      status: string;
      character_id: string;
      slot_key: string;
      state_id?: string | null;
      image_url: string;
      previous_1k_url?: string | null;
      resolution_width: number;
      resolution_height: number;
      is_2k: boolean;
      provider: string;
      model?: string;
      auto_routed_from?: string | null;
      message: string;
    }> => {
      return apiRequest(`/bible/characters/${characterId}/upscale-asset`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    revertCharacterAsset: async (
      characterId: string,
      payload: {
        slot_key?: string;
        state_id?: string;
      }
    ): Promise<{
      status: string;
      character_id: string;
      slot_key: string;
      state_id?: string | null;
      image_url: string;
      resolution_width: number;
      resolution_height: number;
      is_2k: boolean;
      message: string;
    }> => {
      return apiRequest(`/bible/characters/${characterId}/revert-asset`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },

  // 50-Scene Storyboard & Shots
  scenes: {
    list: async (projectId: string): Promise<{ data: Scene[]; total_scenes?: number }> => {
      return apiRequest<{ data: Scene[]; total_scenes?: number }>(`/projects/${projectId}/scenes`);
    },
    get: async (projectId: string, sceneId: string): Promise<{ data: Scene }> => {
      // Backend supports GET /scenes/{scene_id}
      return apiRequest<{ data: Scene }>(`/scenes/${sceneId}`);
    },
    create: async (projectId: string, payload: Partial<Scene>): Promise<{ data: Scene }> => {
      return apiRequest<{ data: Scene }>(`/projects/${projectId}/scenes`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    generateBlueprint: async (
      projectId: string,
      options?:
        | {
            total_scenes?: number;
            duration_mode?: "dynamic" | "flat_10s" | "flat_15s" | "flat_5s";
            auto_split_shots?: boolean;
            clear_existing?: boolean;
            title?: string;
            styleCode?: string;
          }
        | string,
      legacyStyleCode?: string
    ): Promise<{
      data: {
        message: string;
        scenes_generated: number;
        shots_generated?: number;
        total_scenes?: number;
        duration_mode?: string;
      };
    }> => {
      const payload: Record<string, unknown> = { generate_blueprint: true };
      if (typeof options === "string") {
        payload.title = options;
        if (legacyStyleCode) payload.style_code = legacyStyleCode;
      } else if (options) {
        if (options.total_scenes !== undefined) payload.total_scenes = options.total_scenes;
        if (options.duration_mode !== undefined) payload.duration_mode = options.duration_mode;
        if (options.auto_split_shots !== undefined) payload.auto_split_shots = options.auto_split_shots;
        if (options.clear_existing !== undefined) payload.clear_existing = options.clear_existing;
        if (options.title) payload.title = options.title;
        if (options.styleCode) payload.style_code = options.styleCode;
      }
      return apiRequest<{
        data: {
          message: string;
          scenes_generated: number;
          shots_generated?: number;
          total_scenes?: number;
          duration_mode?: string;
        };
      }>(`/projects/${projectId}/scenes`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    update: async (sceneId: string, payload: Partial<Scene>): Promise<{ data: Scene }> => {
      return apiRequest<{ data: Scene }>(`/scenes/${sceneId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    delete: async (sceneId: string): Promise<{ data: { message: string } }> => {
      return apiRequest<{ data: { message: string } }>(`/scenes/${sceneId}`, {
        method: "DELETE",
      });
    },
    calibrateDialogue: async (
      sceneId: string,
      rawText: string,
      maxSeconds: number = 5.0,
      characterName?: string | null
    ): Promise<{ data: DialogueCalibrationResult }> => {
      return apiRequest<{ data: DialogueCalibrationResult }>(`/scenes/${sceneId}/calibrate-dialogue`, {
        method: "POST",
        body: JSON.stringify({
          raw_text: rawText,
          max_seconds: maxSeconds,
          ...(characterName ? { character_name: characterName } : {}),
        }),
      });
    },
    autoSplit: async (
      sceneId: string,
      targetDuration?: number,
      coverageStyle: string = "classic_coverage"
    ): Promise<{
      data: {
        scene_id: string;
        target_duration: number;
        coverage_style?: string;
        shots_count: number;
        message: string;
        shots: Shot[];
      };
    }> => {
      return apiRequest<{
        data: {
          scene_id: string;
          target_duration: number;
          coverage_style?: string;
          shots_count: number;
          message: string;
          shots: Shot[];
        };
      }>(`/scenes/${sceneId}/auto-split`, {
        method: "POST",
        body: JSON.stringify({ target_duration: targetDuration, coverage_style: coverageStyle }),
      });
    },
    listShots: async (sceneId: string): Promise<{ data: Shot[] }> => {
      return apiRequest<{ data: Shot[] }>(`/scenes/${sceneId}/shots`);
    },
    createShot: async (sceneId: string, payload: Partial<Shot>): Promise<{ data: Shot }> => {
      return apiRequest<{ data: Shot }>(`/scenes/${sceneId}/shots`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    updateShot: async (shotId: string, payload: Partial<Shot>): Promise<{ data: Shot }> => {
      return apiRequest<{ data: Shot }>(`/shots/${shotId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    deleteShot: async (shotId: string): Promise<{ data: { message: string } }> => {
      return apiRequest<{ data: { message: string } }>(`/shots/${shotId}`, {
        method: "DELETE",
      });
    },
    resetShotBackground: async (
      shotId: string
    ): Promise<{ status: string; background_source: string; message: string }> => {
      return apiRequest(`/shots/${shotId}/reset-background`, { method: "POST" });
    },
    setShotCustomBackground: async (
      shotId: string,
      customBackground: string
    ): Promise<{ status: string; custom_background: string; message: string }> => {
      return apiRequest(`/shots/${shotId}/custom-background`, {
        method: "POST",
        body: JSON.stringify({ custom_background: customBackground }),
      });
    },
    directorPolish: async (
      sceneId: string,
      payload?: {
        slugline?: string;
        narrative_goal?: string;
        dialogue?: string;
        style_code?: string;
        camera_code?: string;
        lighting_code?: string;
      }
    ): Promise<{ status: string; data: DirectorPolishResult }> => {
      return apiRequest(`/scenes/${sceneId}/director-polish`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    directorAdvisor: async (
      projectId: string,
      sceneId: string,
      payload?: {
        shot_id?: string | null;
        focus?: "staging" | "optics" | "lighting" | "continuity" | "all";
        intent_notes?: string | null;
        include_rag?: boolean;
      }
    ): Promise<{ status: string; data: DirectorAdvisorResult }> => {
      return apiRequest(`/projects/${projectId}/scenes/${sceneId}/director-advisor`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    generatePreview: async (
      sceneId: string,
      payload?: {
        prompt?: string;
        negative_prompt?: string;
        steps?: number;
        aspect_ratio?: string;
        provider?: "9router" | "mock" | string;
        model?: string;
        enable_fallback?: boolean;
      }
    ): Promise<{
      data: {
        scene_id: string;
        shot_id?: string | null;
        preview_url: string;
        seed: number;
        prompt: string;
        width: number;
        height: number;
        steps: number;
        provider: string;
        model?: string | null;
        rate_limit_info?: Record<string, any> | null;
        created_at: string;
      };
    }> => {
      return apiRequest(`/scenes/${sceneId}/generate-preview`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    attachPreview: async (
      sceneId: string,
      payload: {
        preview_url: string;
        preview_provider?: string;
        job_id?: string | null;
      }
    ): Promise<{
      status: string;
      scene_id: string;
      shot_id: string;
      preview_url: string;
      preview_provider: string;
      fg_bg_layers: Record<string, unknown>;
    }> => {
      return apiRequest(`/scenes/${sceneId}/attach-preview`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    generateShotPreview: async (
      shotId: string,
      payload?: {
        prompt?: string;
        negative_prompt?: string;
        steps?: number;
        aspect_ratio?: string;
        provider?: "9router" | "mock" | string;
        model?: string;
        enable_fallback?: boolean;
      }
    ): Promise<{
      data: {
        shot_id: string;
        scene_id: string;
        preview_url: string;
        seed: number;
        prompt: string;
        width: number;
        height: number;
        steps: number;
        provider: string;
        model?: string | null;
        rate_limit_info?: Record<string, any> | null;
        created_at: string;
      };
    }> => {
      return apiRequest(`/shots/${shotId}/generate-preview`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    generateProjectPreview: async (
      projectId: string,
      payload?: {
        prompt?: string;
        negative_prompt?: string;
        steps?: number;
        aspect_ratio?: string;
        provider?: "9router" | "mock" | string;
        model?: string;
        enable_fallback?: boolean;
      }
    ): Promise<{
      data: {
        project_id: string;
        scene_id?: string | null;
        preview_url: string;
        seed: number;
        prompt: string;
        width: number;
        height: number;
        steps: number;
        provider: string;
        model?: string | null;
        rate_limit_info?: Record<string, any> | null;
        created_at: string;
      };
    }> => {
      return apiRequest(`/projects/${projectId}/generate-preview`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    getPreviewProviders: async (): Promise<{
      data: {
        default_provider: string;
        fallback_chain: string[];
        providers: Array<{
          id: string;
          name: string;
          status: string;
          default_model?: string;
          combo_models?: string[];
          rate_limits?: any;
          features?: string[];
        }>;
      };
    }> => {
      return apiRequest("/previews/providers", { method: "GET" });
    },
  },

  // Staged / Batching Hollywood Blueprint Writer API (Polya AI)
  blueprint: {
    recommendStructure: async (
      projectId: string,
      payload?: { total_scenes?: number }
    ): Promise<{
      data: {
        recommended_structure: "3_act" | "4_act" | "youtube_viral" | "5_act";
        strategic_rationale: string;
        options: Array<{
          structure_type: "3_act" | "4_act" | "youtube_viral" | "5_act";
          label: string;
          acts_count: number;
          description: string;
          act_labels: Array<{ act_number: number; title: string; percentage: string }>;
        }>;
      };
    }> => {
      return apiRequest(`/projects/${projectId}/blueprint/recommend-structure`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
    generateTreatment: async (
      projectId: string,
      payload: {
        total_scenes: number;
        duration_mode?: string;
        premise?: string;
        clear_existing?: boolean;
        structure_type?: string;
        enable_cold_open?: boolean;
        selected_treatment?: any;
      }
    ): Promise<{ data: any }> => {
      return apiRequest<{ data: any }>(`/projects/${projectId}/blueprint/treatment`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    generateTreatmentVariants: async (
      projectId: string,
      payload: {
        total_scenes: number;
        duration_mode?: string;
        premise?: string;
        clear_existing?: boolean;
        structure_type?: string;
        enable_cold_open?: boolean;
      }
    ): Promise<{ data: { variants: any[]; structure_type: string; total_scenes: number } }> => {
      return apiRequest<{ data: { variants: any[]; structure_type: string; total_scenes: number } }>(
        `/projects/${projectId}/blueprint/treatment-variants`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );
    },
    generateAct: async (
      projectId: string,
      payload: {
        act_number: number;
        total_scenes: number;
        duration_mode?: string;
        auto_split_shots?: boolean;
        structure_type?: string;
        enable_cold_open?: boolean;
      }
    ): Promise<{
      data: {
        act_number: number;
        scenes_generated: number;
        shots_generated: number;
        start_scene: number;
        end_scene: number;
        act_summary: string;
        total_saved_for_project: number;
        used_fallback?: boolean;
        generator_type?: string;
      };
    }> => {
      return apiRequest<{
        data: {
          act_number: number;
          scenes_generated: number;
          shots_generated: number;
          start_scene: number;
          end_scene: number;
          act_summary: string;
          total_saved_for_project: number;
          used_fallback?: boolean;
          generator_type?: string;
        };
      }>(`/projects/${projectId}/blueprint/generate-act`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    getStatus: async (
      projectId: string
    ): Promise<{
      data: {
        project_id: string;
        has_treatment: boolean;
        treatment?: any;
        total_scenes: number;
        total_shots: number;
        act_counts: Record<number, number>;
        act_summaries: Record<string, string>;
        act_fallbacks?: Record<string, boolean>;
        completed_acts: number[];
      };
    }> => {
      return apiRequest<{
        data: {
          project_id: string;
          has_treatment: boolean;
          treatment?: any;
          total_scenes: number;
          total_shots: number;
          act_counts: Record<number, number>;
          act_summaries: Record<string, string>;
          completed_acts: number[];
        };
      }>(`/projects/${projectId}/blueprint/status`);
    },
    batchWrite: async (
      projectId: string,
      payload: {
        total_scenes: number;
        duration_mode?: string;
        premise?: string;
        auto_split_shots?: boolean;
        clear_existing?: boolean;
        structure_type?: string;
        enable_cold_open?: boolean;
      }
    ): Promise<{ data: any }> => {
      return apiRequest<{ data: any }>(`/projects/${projectId}/blueprint/batch-write`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },

  // Shots API
  shots: {
    list: async (sceneId: string): Promise<{ data: Shot[] }> => {
      return apiRequest<{ data: Shot[] }>(`/scenes/${sceneId}/shots`);
    },
    create: async (sceneId: string, payload: Partial<Shot>): Promise<{ data: Shot }> => {
      return apiRequest<{ data: Shot }>(`/scenes/${sceneId}/shots`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    update: async (shotId: string, payload: Partial<Shot>): Promise<{ data: Shot }> => {
      return apiRequest<{ data: Shot }>(`/shots/${shotId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    delete: async (shotId: string): Promise<{ data: { message: string } }> => {
      return apiRequest<{ data: { message: string } }>(`/shots/${shotId}`, {
        method: "DELETE",
      });
    },
  },

  // Matrix Catalog (#Style, #Light, #Act, #Cam, etc.)
  catalog: {
    getMatrix: async (category?: string): Promise<{ data: MatrixCatalog }> => {
      const q = category ? `?category=${encodeURIComponent(category)}` : "";
      return apiRequest<{ data: MatrixCatalog }>(`/catalog/matrix${q}`);
    },
  },

  // Live Prompt Transpiler
  transpile: {
    execute: async (payload: {
      prompt?: string;
      target_engine?: string;
      scene_context?: Record<string, unknown>;
    }): Promise<{ data: { compiled_prompt: string; engine: string; tokens_count: number } }> => {
      return apiRequest("/transpile", {
        method: "POST",
        body: JSON.stringify({
          provider_target: (payload.target_engine || "veo").toLowerCase(),
          action_description: payload.prompt || "",
        }),
      });
    },
    transpilePrompt: async (payload: TranspileInput): Promise<{ data: TranspileResult }> => {
      return apiRequest<{ data: TranspileResult }>("/transpile", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },

  // Automated QC Scorecard & Real Continuity Audits
  qc: {
    evaluate: async (payload: {
      scene_id?: string;
      shot_id?: string;
      asset_id?: string;
      face_similarity?: number;
      clip_score?: number;
      aesthetic_score?: number;
      temporal_jitter?: number;
      audio_snr_db?: number;
      prompt?: string;
    }): Promise<{ data: QCReport }> => {
      return apiRequest<{ data: QCReport }>("/qc/evaluate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    auditScene: async (sceneId: string): Promise<{ data: QCReport }> => {
      return apiRequest<{ data: QCReport }>(`/qc/audit-scene/${sceneId}`, {
        method: "POST",
      });
    },
    getProjectSummary: async (projectId: string): Promise<{ data: ProjectQCSummary }> => {
      return apiRequest<{ data: ProjectQCSummary }>(`/projects/${projectId}/qc/summary`);
    },
    continuityAudit: async (
      projectId: string,
      payload?: {
        scene_id?: string | null;
        act_number?: number | null;
        strict_mode?: boolean;
      }
    ): Promise<{ status: string; data: ContinuityAuditResult }> => {
      return apiRequest(`/projects/${projectId}/continuity-audit`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
  },

  // Export & Stage S13-S15 Audio/Subtitle Script Engine
  export: {
    getProjectPackage: async (projectId: string, format: "json" | "markdown" = "json"): Promise<unknown> => {
      return apiRequest(`/projects/${projectId}/export?format=${format}`);
    },
    getAudioScript: async (
      projectId: string,
      format: "json" | "ssml" | "markdown" = "json"
    ): Promise<{ data: AudioScriptData } | string> => {
      return apiRequest(`/projects/${projectId}/audio-script?format=${format}`);
    },
    getSubtitles: async (
      projectId: string,
      format: "srt" | "vtt" = "srt",
      includeSfx: boolean = false
    ): Promise<string> => {
      return apiRequest<string>(
        `/projects/${projectId}/subtitles?format=${format}&include_sfx=${includeSfx ? "true" : "false"}`
      );
    },
  },

  // Reusable Production Presets
  presets: {
    list: async (params?: { category?: string; search?: string }): Promise<{ data: ProductionPreset[] }> => {
      const searchParams = new URLSearchParams();
      if (params?.category) searchParams.append("category", params.category);
      if (params?.search) searchParams.append("search", params.search);
      const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
      return apiRequest<{ data: ProductionPreset[] }>(`/presets${query}`);
    },
    get: async (presetId: string): Promise<{ data: ProductionPreset }> => {
      return apiRequest<{ data: ProductionPreset }>(`/presets/${presetId}`);
    },
    create: async (payload: PresetCreateInput): Promise<{ data: ProductionPreset }> => {
      return apiRequest<{ data: ProductionPreset }>("/presets", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    update: async (presetId: string, payload: Partial<PresetCreateInput>): Promise<{ data: ProductionPreset }> => {
      return apiRequest<{ data: ProductionPreset }>(`/presets/${presetId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    delete: async (presetId: string): Promise<{ data: { message: string } }> => {
      return apiRequest<{ data: { message: string } }>(`/presets/${presetId}`, {
        method: "DELETE",
      });
    },
    saveFromProject: async (
      projectId: string,
      payload: { name: string; slug?: string; description?: string; category?: string }
    ): Promise<{ data: ProductionPreset }> => {
      return apiRequest<{ data: ProductionPreset }>(`/projects/${projectId}/save-as-preset`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    applyToProject: async (
      projectId: string,
      presetId: string
    ): Promise<{ data: Record<string, any> }> => {
      return apiRequest<{ data: Record<string, any> }>(`/projects/${projectId}/apply-preset`, {
        method: "POST",
        body: JSON.stringify({ preset_id: presetId }),
      });
    },
  },

  // Google Flow Automation Pool
  flow: {
    getAccounts: async (): Promise<{
      worker_service: { name: string; status: string; healthy: boolean };
      accounts: FlowAccount[];
    }> => {
      return apiRequest("/api/flow/accounts");
    },
    patchAccount: async (
      accountId: number,
      payload: { label?: string; status?: string }
    ): Promise<{ status: string; account: Partial<FlowAccount> }> => {
      return apiRequest(`/api/flow/accounts/${accountId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    resetAccount: async (
      accountId: number
    ): Promise<{ status: string; message: string; account: Partial<FlowAccount> }> => {
      return apiRequest(`/api/flow/accounts/${accountId}/reset`, {
        method: "POST",
      });
    },
    testAccount: async (
      accountId: number
    ): Promise<{ status: string; message: string; job_id: string; preferred_account_id: number }> => {
      return apiRequest(`/api/flow/accounts/${accountId}/test`, {
        method: "POST",
      });
    },
    getSettings: async (): Promise<{ settings: FlowSettings }> => {
      return apiRequest("/api/flow/settings");
    },
    updateSettings: async (
      payload: Partial<FlowSettings>
    ): Promise<{ status: string; settings: FlowSettings }> => {
      return apiRequest("/api/flow/settings", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    getProxyStatus: async (): Promise<FlowProxyStatus> => {
      return apiRequest("/api/flow/proxy/status");
    },
    generateImage: async (
      payload: FlowJobCreateInput
    ): Promise<{ status: string; job_id: string; job_status: string; message: string }> => {
      return apiRequest("/api/flow/images/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    getJob: async (jobId: string): Promise<FlowJob> => {
      return apiRequest(`/api/flow/images/jobs/${jobId}`);
    },
    cancelJob: async (jobId: string): Promise<{ status: string; message?: string }> => {
      return apiRequest(`/api/flow/images/jobs/${jobId}/cancel`, {
        method: "POST",
      });
    },
    listJobs: async (limit: number = 30): Promise<{ jobs: FlowJob[] }> => {
      return apiRequest(`/api/flow/images/jobs?limit=${limit}`);
    },
  },

  // Hermes Nova (Polya AI) YouTube Trend Engine
  hermesNova: {
    getCatalog: async (): Promise<{ status: string; total: number; data: HermesCatalogItem[] }> => {
      return apiRequest<{ status: string; total: number; data: HermesCatalogItem[] }>("/hermes-nova/catalog");
    },
    ideateTitles: async (payload: {
      preset_name?: string;
      category?: string;
      target_style_code?: string;
      target_style_desc?: string;
      aspect_ratio?: string;
      seed_premise?: string;
    }): Promise<HermesTitlesResponse> => {
      return apiRequest<HermesTitlesResponse>("/hermes-nova/ideate-titles", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    ideateSynopses: async (payload: {
      locked_title: string;
      preset_name?: string;
      target_style_code?: string;
      aspect_ratio?: string;
      seed_premise?: string;
      trend_keywords?: string[];
    }): Promise<HermesSynopsesResponse> => {
      return apiRequest<HermesSynopsesResponse>("/hermes-nova/ideate-synopses", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },

  // 360p Previews Engine (Point 8 & Refinement 4)
  previews: {
    generateProjectPreview: async (
      projectId: string,
      payload?: { aspect_ratio?: string; provider?: string; model?: string; prompt?: string }
    ): Promise<{
      status: string;
      preview_url: string;
      width: number;
      height: number;
      provider: string;
      model?: string;
      seed?: number;
      data?: any;
    }> => {
      const res = await apiRequest<{
        status?: string;
        preview_url?: string;
        width?: number;
        height?: number;
        provider?: string;
        model?: string;
        seed?: number;
        data?: any;
      }>(`/projects/${projectId}/generate-preview`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
      const data = res?.data || res || {};
      return {
        status: res?.status || "success",
        preview_url: data.preview_url || res?.preview_url || "",
        width: data.width || res?.width || 640,
        height: data.height || res?.height || 360,
        provider: data.provider || res?.provider || "9router",
        model: data.model || res?.model,
        seed: data.seed ?? res?.seed,
        data: res?.data || data,
      };
    },
    generateScenePreview: async (
      projectId: string,
      sceneId: string,
      payload?: { aspect_ratio?: string; provider?: string }
    ): Promise<{ status: string; preview_url: string; width: number; height: number; provider: string }> => {
      return apiRequest(`/previews/projects/${projectId}/scenes/${sceneId}/generate`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
    },
  },
};
