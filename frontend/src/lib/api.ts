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
  created_at?: string;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  role: string;
  base_prompt: string;
  face_ref_asset_id?: string | null;
  voice_ref_asset_id?: string | null;
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
  provider_target: "veo" | "kling" | "runway" | "sora" | "comfyui" | string;
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
  syllables_count: number;
  estimated_duration_seconds: number;
  passes_5s_limit: boolean;
  recommended_audio_bridge: string;
  audio_lead_seconds: number;
  analysis: string;
}

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
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
  const url = endpoint.startsWith("http") ? endpoint : `${baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

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
    try {
      const errJson = await response.json();
      if (errJson?.error) {
        errorDetail = errJson.error.message || errorDetail;
        errorCode = errJson.error.code || errorCode;
      } else if (errJson?.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse error on non-json body
    }
    throw new ApiError(response.status, errorDetail, errorCode);
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
      payload: { name: string; role: string; base_prompt: string; face_ref_asset_id?: string; voice_ref_asset_id?: string }
    ): Promise<{ data: Character }> => {
      return apiRequest<{ data: Character }>(`/projects/${projectId}/characters`, {
        method: "POST",
        body: JSON.stringify(payload),
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
    generateBlueprint: async (projectId: string, title?: string, styleCode?: string): Promise<{ data: Scene[]; count?: number }> => {
      return apiRequest<{ data: Scene[]; count?: number }>(`/projects/${projectId}/scenes`, {
        method: "POST",
        body: JSON.stringify({ generate_blueprint: true, title, style_code: styleCode }),
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
};
