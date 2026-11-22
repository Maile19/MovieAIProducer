from typing import Any
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from backend.app.domain.transpiler import LivePromptTranspiler

router = APIRouter(tags=["Prompt Transpiler"])


class TranspileRequest(BaseModel):
    provider_target: str = Field(
        default="veo",
        description="Target engine: veo, kling, runway, sora, comfyui",
    )
    style_code: str = Field(default="#Style 01", description="#Style 01 to #Style 18")
    camera_code: str = Field(default="#Cam 01", description="#Cam 01 to #Cam 34")
    lens_code: str = Field(default="#Lens 01", description="#Lens 01 to #Lens 06")
    comp_code: str = Field(default="#Comp 01", description="#Comp 01 to #Comp 08")
    light_code: str = Field(default="#Light 01", description="#Light 01 to #Light 14")
    act_code: str = Field(default="#Act 01", description="#Act 01 to #Act 24")
    speed_code: str = Field(default="#Speed 01", description="#Speed 01 to #Speed 05")
    character_dna: str = Field(default="", description="Character visual descriptors")
    state_code: str = Field(default="#State 01", description="#State 01 to #State 05")
    wardrobe: str = Field(default="", description="Wardrobe description")
    env_dna: str = Field(default="", description="Environment architecture & atmosphere")
    action_description: str = Field(default="", description="Dynamic performance action")
    fg_description: str = Field(default="", description="Foreground particulate or depth layer")
    bg_description: str = Field(default="", description="Background atmosphere or moving scenery")
    dialogue: str | None = Field(default=None, description="Spoken dialogue text")
    transition_type: str = Field(default="NONE", description="NONE, J_CUT, L_CUT, HARD_CUT")
    aspect_ratio: str = Field(default="16:9", description="16:9 or 9:16")
    preset_rules: dict[str, Any] | None = Field(default=None, description="Preset rules dictionary")
    is_non_verbal: bool = Field(default=False, description="Whether non-verbal mode is active")


@router.post("/transpile", status_code=status.HTTP_200_OK)
async def transpile_prompt(payload: TranspileRequest) -> dict[str, Any]:
    """Transpile Hollywood cinematographic matrices into generative engine prompt."""
    result = LivePromptTranspiler.transpile(
        provider_target=payload.provider_target,
        style_code=payload.style_code,
        camera_code=payload.camera_code,
        lens_code=payload.lens_code,
        comp_code=payload.comp_code,
        light_code=payload.light_code,
        act_code=payload.act_code,
        speed_code=payload.speed_code,
        character_dna=payload.character_dna,
        state_code=payload.state_code,
        wardrobe=payload.wardrobe,
        env_dna=payload.env_dna,
        action_description=payload.action_description,
        fg_description=payload.fg_description,
        bg_description=payload.bg_description,
        dialogue=payload.dialogue,
        transition_type=payload.transition_type,
        aspect_ratio=payload.aspect_ratio,
        preset_rules=payload.preset_rules,
        is_non_verbal=payload.is_non_verbal,
    )
    return {"data": result}
