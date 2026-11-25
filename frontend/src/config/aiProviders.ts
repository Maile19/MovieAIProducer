export type ProviderCategory = 'core' | 'priority' | 'additional';

export interface AIProviderSpec {
  id: string;
  name: string;
  vendor: string;
  category: ProviderCategory;
  badge: string;
  supportsVisualAnchor: boolean;
  requiresProxy?: boolean;
  defaultBaseUrl: string;
  defaultModelId: string;
  modelOptions?: { id: string; label: string }[];
  apiKeyPlaceholder: string;
  requiresApiKey: boolean;
  portalUrl: string;
  portalLabel: string;
}

export interface UserProviderConfig {
  baseUrl: string;
  apiKey: string;
  modelId: string;
  customModelId?: string;
}

export interface FreePortalItem {
  id: string;
  name: string;
  url: string;
  note?: string;
}

export const AI_RENDER_PROVIDERS: AIProviderSpec[] = [
  // === 1. CORE ENGINE (Default: Google Flow Primary, Gemini/9Router Fallback) ===
  {
    id: 'google-flow',
    name: 'Google Flow',
    vendor: 'Google Labs',
    category: 'core',
    badge: 'PRIMARY • Free 6-Account Pool',
    supportsVisualAnchor: true,
    requiresProxy: true,
    defaultBaseUrl: 'https://labs.google/fx/api',
    defaultModelId: 'flow-imagen-anchor-pro',
    apiKeyPlaceholder: 'Otomatis via Sesi Akun PRO (1-6) / SOCKS5',
    requiresApiKey: false,
    portalUrl: 'https://labs.google/fx/tools/flow',
    portalLabel: 'Google Flow',
  },
  {
    id: 'gemini-direct',
    name: 'Gemini API (3.8 Flash)',
    vendor: 'Google AI Studio',
    category: 'core',
    badge: 'FALLBACK • Direct Key Fast',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    defaultModelId: 'gemini-3.8-flash',
    modelOptions: [
      { id: 'gemini-3.8-flash', label: 'gemini-3.8-flash (Default)' },
      { id: 'gemini-3.1-flash-image', label: 'gemini-3.1-flash-image' },
      { id: 'gemini-2.5-flash-image', label: 'gemini-2.5-flash-image (Fallback)' },
      { id: 'imagen-4.0-generate-001', label: 'imagen-4.0-generate-001' },
    ],
    apiKeyPlaceholder: 'AIzaSy... (Paste Gemini API Key)',
    requiresApiKey: true,
    portalUrl: 'https://aistudio.google.com/apikey',
    portalLabel: 'AI Studio',
  },
  {
    id: '9router',
    name: '9Router',
    vendor: 'Local VPS Router',
    category: 'core',
    badge: 'FALLBACK • Combo Pool',
    supportsVisualAnchor: false,
    defaultBaseUrl: 'http://127.0.0.1:8080/v1',
    defaultModelId: 'ag/gemini-3.8-flash',
    modelOptions: [
      { id: 'ag/gemini-3.8-flash', label: 'ag/gemini-3.8-flash (Recommended)' },
      { id: 'gemini-3.1-flash-image', label: 'gemini-3.1-flash-image' },
      { id: 'geminis', label: 'geminis (Combo Pool)' },
      { id: 'agy-high-speed', label: 'Agy (Antigravity High-Speed)' },
    ],
    apiKeyPlaceholder: 'sk-9router-... (Local Router Token)',
    requiresApiKey: true,
    portalUrl: 'http://127.0.0.1:8080',
    portalLabel: 'Router',
  },

  // === 2. PRIORITY CLOUD MODELS ===
  {
    id: 'qwen-image-3',
    name: 'Qwen Image 3.0',
    vendor: 'Alibaba Model Studio',
    category: 'priority',
    badge: 'Alibaba • High Detail',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://dashscope-intl.aliyuncs.com/api/v1',
    defaultModelId: 'qwen-image-3.0',
    modelOptions: [
      { id: 'qwen-image-3.0', label: 'qwen-image-3.0' },
      { id: 'qwen-mt-image-2.0', label: 'qwen-mt-image-2.0 (Fallback)' },
    ],
    apiKeyPlaceholder: 'sk-... (DashScope API Key)',
    requiresApiKey: true,
    portalUrl: 'https://modelstudio.console.alibabacloud.com/',
    portalLabel: 'Alibaba',
  },
  {
    id: 'seedream-5-5',
    name: 'Seedream 5.5',
    vendor: 'BytePlus ModelArk',
    category: 'priority',
    badge: 'BytePlus • 2K Cinematics',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://ark.ap-southeast.bytepluses.com/api/v3',
    defaultModelId: 'seedream-5.5',
    apiKeyPlaceholder: 'Paste BytePlus ModelArk API Key',
    requiresApiKey: true,
    portalUrl: 'https://console.byteplus.com/ark',
    portalLabel: 'BytePlus',
  },
  {
    id: 'gpt-2-6',
    name: 'GPT 2.6 Image',
    vendor: 'OpenAI',
    category: 'priority',
    badge: 'Prompt Accuracy',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://api.openai.com/v1',
    defaultModelId: 'gpt-image-2.6',
    modelOptions: [
      { id: 'gpt-image-2.6', label: 'gpt-image-2.6' },
      { id: 'gpt-image-1', label: 'gpt-image-1 (Fallback)' },
    ],
    apiKeyPlaceholder: 'sk-proj-... (OpenAI API Key)',
    requiresApiKey: true,
    portalUrl: 'https://platform.openai.com/api-keys',
    portalLabel: 'OpenAI',
  },
  {
    id: 'flux',
    name: 'FLUX',
    vendor: 'Black Forest Labs',
    category: 'priority',
    badge: 'Photorealistic',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://api.bfl.ai/v1',
    defaultModelId: 'flux-pro-1.1-ultra',
    modelOptions: [
      { id: 'flux-pro-1.1-ultra', label: 'flux-pro-1.1-ultra' },
      { id: 'flux-kontext-pro', label: 'flux-kontext-pro (Visual Ref)' },
    ],
    apiKeyPlaceholder: 'bfl_... (Black Forest Labs Key)',
    requiresApiKey: true,
    portalUrl: 'https://api.bfl.ai/',
    portalLabel: 'BFL Portal',
  },

  // === 3. 10 MODEL UNGGULAN TAMBAHAN ===
  {
    id: 'midjourney-v8-2',
    name: 'Midjourney V8.2',
    vendor: 'Midjourney / Proxy',
    category: 'additional',
    badge: 'Artistic • Proxy API',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://api.your-mj-proxy.com/v1',
    defaultModelId: 'mj-v8.2',
    apiKeyPlaceholder: 'Paste Midjourney Proxy API Key',
    requiresApiKey: true,
    portalUrl: 'https://www.midjourney.com/',
    portalLabel: 'Midjourney',
  },
  {
    id: 'nano-banana-2-1',
    name: 'Nano Banana 2.1',
    vendor: 'Google AI Studio',
    category: 'additional',
    badge: 'Consistent Character',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    defaultModelId: 'nano-banana-2.1',
    apiKeyPlaceholder: 'AIzaSy... (Gemini API Key)',
    requiresApiKey: true,
    portalUrl: 'https://aistudio.google.com/apikey',
    portalLabel: 'AI Studio',
  },
  {
    id: 'mai-image-2-6',
    name: 'MAI Image 2.6',
    vendor: 'Microsoft AI / Azure',
    category: 'additional',
    badge: 'Enterprise Photoreal',
    supportsVisualAnchor: false,
    defaultBaseUrl: 'https://models.inference.ai.azure.com',
    defaultModelId: 'mai-image-2.6',
    apiKeyPlaceholder: 'Paste Azure / MAI API Key',
    requiresApiKey: true,
    portalUrl: 'https://ai.azure.com/',
    portalLabel: 'Azure AI',
  },
  {
    id: 'ideogram-4-0',
    name: 'Ideogram 4.0',
    vendor: 'Ideogram',
    category: 'additional',
    badge: 'Typography & Poster',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://api.ideogram.ai/v1',
    defaultModelId: 'V_4_0',
    apiKeyPlaceholder: 'Paste Ideogram API Key',
    requiresApiKey: true,
    portalUrl: 'https://ideogram.ai/manage-api',
    portalLabel: 'Ideogram',
  },
  {
    id: 'adobe-firefly-4',
    name: 'Adobe Firefly Image 4',
    vendor: 'Adobe',
    category: 'additional',
    badge: 'Commercial Safe',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://firefly-api.adobe.io/v3',
    defaultModelId: 'firefly-image-4',
    apiKeyPlaceholder: 'client_id:access_token (Adobe Console)',
    requiresApiKey: true,
    portalUrl: 'https://developer.adobe.com/firefly-services/',
    portalLabel: 'Firefly',
  },
  {
    id: 'recraft-v4-pro',
    name: 'Recraft V4 Pro',
    vendor: 'Recraft',
    category: 'additional',
    badge: 'Design & Vector Style',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://external.api.recraft.ai/v1',
    defaultModelId: 'recraftv4_pro',
    apiKeyPlaceholder: 'Paste Recraft API Token',
    requiresApiKey: true,
    portalUrl: 'https://www.recraft.ai/docs',
    portalLabel: 'Recraft',
  },
  {
    id: 'kling-image-4-0',
    name: 'Kling Image 4.0',
    vendor: 'Kuaishou Kling',
    category: 'additional',
    badge: 'Donghua & Cinematic',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://api.klingai.com/v1',
    defaultModelId: 'kling-image-v4',
    apiKeyPlaceholder: 'access_key:secret_key (atau Bearer JWT)',
    requiresApiKey: true,
    portalUrl: 'https://klingai.com/global/dev',
    portalLabel: 'Kling Dev',
  },
  {
    id: 'grok-imagine-2-0',
    name: 'Grok Imagine 2.0',
    vendor: 'xAI',
    category: 'additional',
    badge: 'Unfiltered • Fast',
    supportsVisualAnchor: false,
    defaultBaseUrl: 'https://api.x.ai/v1',
    defaultModelId: 'grok-imagine-2.0',
    apiKeyPlaceholder: 'xai-... (xAI API Key)',
    requiresApiKey: true,
    portalUrl: 'https://console.x.ai/',
    portalLabel: 'xAI Console',
  },
  {
    id: 'luma-uni-1',
    name: 'Luma Uni-1',
    vendor: 'Luma Labs',
    category: 'additional',
    badge: 'Unified Image/Video',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://api.lumalabs.ai/dream-machine/v1',
    defaultModelId: 'luma-uni-1',
    apiKeyPlaceholder: 'luma-... (Luma API Key)',
    requiresApiKey: true,
    portalUrl: 'https://lumalabs.ai/dream-machine/api/keys',
    portalLabel: 'Luma AI',
  },
  {
    id: 'leonardo-phoenix',
    name: 'Leonardo Phoenix',
    vendor: 'Leonardo.ai',
    category: 'additional',
    badge: 'Concept Art • Assets',
    supportsVisualAnchor: true,
    defaultBaseUrl: 'https://cloud.leonardo.ai/api/rest/v1',
    defaultModelId: 'leonardo-phoenix-1.0',
    apiKeyPlaceholder: 'Paste Leonardo API Key',
    requiresApiKey: true,
    portalUrl: 'https://app.leonardo.ai/api-access',
    portalLabel: 'Leonardo',
  },
];

export const DEFAULT_FREE_PORTALS: FreePortalItem[] = [
  {
    id: 'free-ai-studio',
    name: 'Google AI Studio / Whisk',
    url: 'https://labs.google/fx/tools/whisk',
    note: 'Gratis kuota harian Google',
  },
  {
    id: 'free-leonardo',
    name: 'Leonardo.ai Free Tokens',
    url: 'https://app.leonardo.ai/',
    note: '150 token gratis per hari',
  },
  {
    id: 'free-ideogram',
    name: 'Ideogram Free Tier',
    url: 'https://ideogram.ai/',
    note: 'Kredit mingguan gratis',
  },
];
