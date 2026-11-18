# AI Provider & Model Integration Matrix - MovieAIProducer

## 1. Vision
This matrix ensures MovieAIProducer remains provider-agnostic. By abstracting AI capabilities into a capability-driven registry, the platform can dynamically route production tasks to the best-suited model (Google Veo, Kling, Runway, etc.) based on capability verification, not vendor lock-in.

## 2. Integration Classification
- **Native API:** Direct, automated integration.
- **Assisted:** Platform prepares structured specifications/prompts for an external workflow.
- **Manual:** User-executed workflow with asset registration back into the platform.

## 3. Provider Categories
- **Text/Reasoning:** Creative dev, screenplay, analysis (OpenAI, Anthropic, Gemini, DeepSeek).
- **Image Gen:** Concept art, storyboards, DNA references (FLUX, OpenAI, Midjourney).
- **Video Gen:** Cinematic scene generation (Google Veo, Kling, Runway, Luma).
- **Audio:** Voice synthesis, SFX, music (ElevenLabs, OpenAI).
- **Vision/Analysis:** Consistency checks, motion analysis, QC (Gemini, GPT-4o).

## 4. Operational Protocols
- **Registry:** All providers/models must be registered with verified capabilities, constraints, and latency/cost benchmarks.
- **Adapter Pattern:** Domain layer interacts with a standardized `VideoProvider` interface. No vendor SDKs in the core logic.
- **Validation:** No provider is marked "ACTIVE" without live conformance testing (API auth, generation speed, asset integrity).
- **Security:** API keys strictly via environment/secret manager. No leaking of credentials into prompts or logs.

## 5. Strategic Evaluation Matrix
| Capability | Target Providers | Priority | Integration Level |
| :--- | :--- | :--- | :--- |
| **Reasoning** | Gemini, Claude, GPT-4o | P0 | Native |
| **Video Gen** | Google Veo, Kling, Runway | P0 | Native/Assisted |
| **Voice** | ElevenLabs | P1 | Native |
| **Analysis** | Gemini, GPT-4o | P1 | Native |

## 6. Implementation Strategy
1. **Registry Phase:** Implement `ProviderRegistry` and `CapabilityRegistry`.
2. **Adapter Phase:** Build standard `AIProviderAdapter` interface.
3. **Execution Phase:** Implement verified adapters for priority providers (e.g., Veo, Kling).
4. **Monitoring Phase:** Log latency, failure rates, and cost per shot.
