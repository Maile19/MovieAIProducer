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

export interface Project {
  id: string;
  title: string;
  slug: string;
  status: string;
  aspect_ratio: string;
  target_style_code: string;
  operational_stage: number;
  stage_name: string;
  owner_id?: string | null;
  created_at: string;
  updated_at: string;
  settings?: Record<string, unknown>;
  stats?: {
    scenes_count: number;
    bible_version: number;
    bible_locked: boolean;
  };
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
  preview_url?: string | null;
  act_number: number;
  shots_count?: number;
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
  camera_code?: string;
  lens_code?: string;
  lighting_code?: string;
  action_code?: string;
  speed_code?: string;
  duration_seconds: number;
  prompt_compiled?: string;
  prompt_override?: string;
  preview_url?: string | null;
  status: string;
  created_at: string;
  updated_at?: string;
}

export interface CharacterState {
  id: string;
  character_id: string;
  scene_id?: string | null;
  state_code: string;
  wardrobe: string;
  injuries_and_wear?: string;
  expression_anchor?: string;
  image_url?: string | null;
  created_at?: string;
}

export interface CharacterSheetMeta {
  image_url?: string;
  prompt?: string;
  negative_prompt?: string;
  anchors_used?: string[];
  provider?: string;
  model?: string;
  seed?: number;
  aspect_ratio?: string;
  rendered_at?: string;
  updated_at?: string;
  source?: "ai_generated" | "manual_upload" | string;
  original_filename?: string;
  file_size?: number;
  width?: number;
  height?: number;
  status?: string;
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
  slot: string;
  character_id: string;
  width: number;
  height: number;
  sheet_metadata: CharacterSheetMeta;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  role: string;
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

export interface QCReport {
  id?: string;
  overall_score: number;
  passed?: boolean;
  biometric_score?: number;
  aesthetic_score?: number;
  acoustic_score?: number;
  status?: "PASSED" | "FLAGGED" | "FAILED";
  metrics?: {
    face_similarity_insightface?: number;
    clip_text_video_score?: number;
    aesthetic_score?: number;
    temporal_jitter_variance?: number;
    audio_snr_db?: number;
  };
  critical_defects?: string[];
  warnings?: string[];
  findings?: Array<{ category: string; severity: string; message: string; timestamp_code?: string }>;
  findings_json?: string[];
}

export interface QCEvaluateInput {
  shot_id?: string;
  asset_id?: string;
  face_similarity?: number;
  clip_score?: number;
  aesthetic_score?: number;
  temporal_jitter?: number;
  audio_snr_db?: number;
  prompt?: string;
}

export interface TranspileInput {
  provider_target: "veo" | "kling" | "runway" | "sora" | "comfyui" | "9router" | "sd35" | "flux" | string;
  style_code?: string;
  camera_code?: string;
  lens_code?: string;
  comp_code?: string;
  light_code?: string;
  act_code?: string;
  speed_code?: string;
  character_dna?: string;
  state_code?: string;
  wardrobe?: string;
  env_dna?: string;
  action_description?: string;
  fg_description?: string;
  bg_description?: string;
  dialogue?: string | null;
  transition_type?: string;
  aspect_ratio?: string;
  preset_rules?: Record<string, any>;
  is_non_verbal?: boolean;
  model?: string;
}

export interface TranspileResult {
  positive: string;
  negative: string;
  engine: string;
  metadata?: {
    target_engine?: string;
    aspect_ratio?: string;
    codes?: Record<string, string>;
    parameters?: Record<string, unknown>;
    prompt_tokens_est?: number;
    [key: string]: unknown;
  };
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
    let errorDetail = response.statusText;
    let errorCode = "UNKNOWN_ERROR";
    let errorExtra: any = undefined;
    try {
      const errJson = await response.json();
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
      // ignore json parse error on non-json body
    }
    throw new ApiError(response.status, errorDetail, errorCode, errorExtra);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null as unknown as T;
  }

  return response.json();
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
    list: async (params?: { search?: string; limit?: number; offset?: number }): Promise<{ data: Project[]; pagination: { limit?: number; offset?: number; count?: number; [key: string]: unknown } }> => {
      const query = new URLSearchParams();
      if (params?.search) query.set("search", params.search);
      if (params?.limit) query.set("limit", params.limit.toString());
      if (params?.offset) query.set("offset", params.offset.toString());
      const qs = query.toString();
      return apiRequest<{ data: Project[]; pagination: { limit?: number; offset?: number; count?: number; [key: string]: unknown } }>(`/projects${qs ? `?${qs}` : ""}`);
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
    listCharacters: async (projectId: string): Promise<{ data: Character[] }> => {
      return apiRequest<{ data: Character[] }>(`/projects/${projectId}/characters`);
    },
    createCharacter: async (
      projectId: string,
      payload: {
        name: string;
        role: string;
        base_prompt: string;
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
          base_visual_prompt?: string;
          dna_seed?: number;
        };
      }
    ): Promise<{
      data: {
        name: string;
        role_suggestion: string;
        archetype_and_bio: string;
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
    }> => {
      return apiRequest(`/projects/${projectId}/characters/preview/attach`, {
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
      payload: { scene_id?: string; state_code: string; wardrobe: string; injuries_and_wear?: string; expression_anchor?: string }
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
        provider?: "ag_gemini_flash" | "9router" | "sd35_large_hf" | "google_flow" | string;
        model?: string;
        prompt_override?: string;
        aspect_ratio?: string;
      }
    ): Promise<{
      status: "completed" | "queued";
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
      return apiRequest<CharacterSheetPromptsResponse>(`/characters/${characterId}/sheet-prompts`);
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
      maxSeconds: number = 5.0
    ): Promise<{ data: DialogueCalibrationResult }> => {
      return apiRequest<{ data: DialogueCalibrationResult }>(`/scenes/${sceneId}/calibrate-dialogue`, {
        method: "POST",
        body: JSON.stringify({ raw_text: rawText, max_seconds: maxSeconds }),
      });
    },
    autoSplit: async (
      sceneId: string,
      targetDuration?: number
    ): Promise<{
      data: {
        scene_id: string;
        target_duration: number;
        shots_count: number;
        message: string;
        shots: Shot[];
      };
    }> => {
      return apiRequest<{
        data: {
          scene_id: string;
          target_duration: number;
          shots_count: number;
          message: string;
          shots: Shot[];
        };
      }>(`/scenes/${sceneId}/auto-split`, {
        method: "POST",
        body: JSON.stringify({ target_duration: targetDuration }),
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
    generatePreview: async (
      sceneId: string,
      payload?: {
        prompt?: string;
        negative_prompt?: string;
        steps?: number;
        aspect_ratio?: string;
        provider?: "9router" | "sd35_large_hf" | "mock" | string;
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
    generateShotPreview: async (
      shotId: string,
      payload?: {
        prompt?: string;
        negative_prompt?: string;
        steps?: number;
        aspect_ratio?: string;
        provider?: "9router" | "sd35_large_hf" | "mock" | string;
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
        provider?: "9router" | "sd35_large_hf" | "mock" | string;
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

  // Staged / Batching Hollywood Blueprint Writer API
  blueprint: {
    generateTreatment: async (
      projectId: string,
      payload: {
        total_scenes: number;
        duration_mode?: string;
        premise?: string;
        clear_existing?: boolean;
      }
    ): Promise<{ data: any }> => {
      return apiRequest<{ data: any }>(`/projects/${projectId}/blueprint/treatment`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    generateAct: async (
      projectId: string,
      payload: {
        act_number: number;
        total_scenes: number;
        duration_mode?: string;
        auto_split_shots?: boolean;
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

  // Automated QC Scorecard
  qc: {
    evaluate: async (payload: {
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
  },

  // Export
  export: {
    getProjectPackage: async (projectId: string, format: "json" | "markdown" = "json"): Promise<unknown> => {
      return apiRequest(`/projects/${projectId}/export?format=${format}`);
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
    ): Promise<{ status: string; preview_url: string; width: number; height: number; provider: string; model?: string }> => {
      return apiRequest(`/previews/projects/${projectId}/generate-preview`, {
        method: "POST",
        body: JSON.stringify(payload || {}),
      });
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
