from __future__ import annotations

import hashlib
import re
from typing import Any


VISUAL_TREATMENTS = frozenset({
    "hero_full_bleed",
    "documentary_lower_third",
    "editorial_split",
    "editorial_cover",
    "kinetic_typography",
    "vertical_timeline",
    "process_blueprint",
    "comparative_split",
    "data_stage",
    "market_chart",
    "orbit_stage",
    "cinema_end_frame",
    "immersive_photo",
    "photo_essay",
    "cinematic_side_caption",
})

CAMERA_MOTIONS = (
    "zoom_in", "zoom_out", "pan_left", "pan_right", "dolly_push",
    "tilt_up", "tilt_down", "drift_diagonal", "handheld", "static",
)

TRANSITIONS = ("dissolve", "push", "wipe", "flash")


_TYPE_TREATMENTS = {
    "cinema_hero": (
        "hero_full_bleed", "editorial_cover", "documentary_lower_third",
        "cinematic_side_caption", "immersive_photo",
    ),
    "editorial_montage": (
        "immersive_photo", "photo_essay", "editorial_split",
        "documentary_lower_third", "editorial_cover",
    ),
    "three_d_globe": ("orbit_stage", "hero_full_bleed", "cinematic_side_caption"),
    "three_d_bars": ("data_stage", "market_chart"),
    "data_viz": ("data_stage", "market_chart"),
    "candlestick_chart": ("market_chart", "data_stage"),
    "split_compare": (
        "comparative_split", "editorial_split", "kinetic_typography",
        "documentary_lower_third", "editorial_cover",
    ),
    "step_list": (
        "vertical_timeline", "kinetic_typography", "editorial_cover",
        "documentary_lower_third", "photo_essay",
    ),
    "process_diagram": (
        "process_blueprint", "kinetic_typography", "editorial_split",
        "documentary_lower_third", "editorial_cover",
    ),
    "kinetic_type": ("kinetic_typography", "editorial_cover"),
    "cinema_outro": ("cinema_end_frame", "hero_full_bleed"),
}

_GENERIC_TREATMENTS = (
    "hero_full_bleed",
    "documentary_lower_third",
    "editorial_split",
    "editorial_cover",
    "kinetic_typography",
    "immersive_photo",
    "photo_essay",
    "cinematic_side_caption",
)


def _hash_int(*parts: object) -> int:
    raw = "\0".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def _shot_size(query: str, index: int, seed: int) -> str:
    text = query.casefold()
    if re.search(r"\b(?:macro|microscopic|texture|detail|close[- ]?up)\b", text):
        return "macro"
    if re.search(r"\b(?:aerial|drone|overhead|bird.?s.?eye)\b", text):
        return "aerial"
    if re.search(r"\b(?:wide|panorama|landscape|establishing)\b", text):
        return "wide"
    if re.search(r"\b(?:person|people|worker|analyst|crowd|human|hands)\b", text):
        return "human"
    return ("wide", "medium", "closeup", "overhead", "low_angle", "detail")[(seed + index) % 6]


def _caption_style(treatment: str, topic_kind: str) -> str:
    if topic_kind == "market_update":
        return "ticker"
    if treatment in {"kinetic_typography", "hero_full_bleed", "cinema_end_frame"}:
        return "minimal"
    if treatment in {"documentary_lower_third", "photo_essay", "immersive_photo"}:
        return "documentary"
    return "karaoke"


def assign_visual_language(
    scenes: list[dict[str, Any]],
    topic_kind: str,
    job_id: str,
    orientation: str = "vertical",
) -> list[dict[str, Any]]:
    """Give every scene an authored composition, camera grammar and transition.

    The language layer is deliberately separate from scene meaning: the AI still
    chooses what each shot depicts, while this director ensures the finished film
    does not become one repeated headline-card template.
    """
    if not scenes:
        return scenes

    recent_treatments: list[str] = []
    recent_motions: list[str] = []
    previous_transition = ""
    for index, scene in enumerate(scenes):
        scene_type = str(scene.get("type", "editorial_montage"))
        options = _TYPE_TREATMENTS.get(scene_type, _GENERIC_TREATMENTS)
        seed = _hash_int(job_id, topic_kind, index, scene.get("headline", ""))
        requested = str(scene.get("visualTreatment", "")).strip()
        if requested not in VISUAL_TREATMENTS:
            requested = ""

        ranked = list(options)
        offset = seed % len(ranked)
        ranked = ranked[offset:] + ranked[:offset]
        ranked.extend(item for item in _GENERIC_TREATMENTS if item not in ranked)

        chosen = requested or next(
            (item for item in ranked if item not in recent_treatments[-2:]),
            ranked[0],
        )
        if chosen in recent_treatments[-2:]:
            chosen = next(
                (item for item in ranked if item not in recent_treatments[-2:]),
                chosen,
            )
        scene["visualTreatment"] = chosen
        recent_treatments.append(chosen)

        scene["shotSize"] = _shot_size(
            str(scene.get("visualQuery", "")), index, seed
        )
        scene["textSide"] = "right" if (seed + index) % 2 else "left"
        scene["captionStyle"] = _caption_style(chosen, topic_kind)

        current_motion = scene.get("cameraMotion")
        if current_motion not in CAMERA_MOTIONS:
            current_motion = ""
        motion_offset = seed % len(CAMERA_MOTIONS)
        motion_order = CAMERA_MOTIONS[motion_offset:] + CAMERA_MOTIONS[:motion_offset]
        if not current_motion or current_motion in recent_motions[-2:]:
            current_motion = next(
                (item for item in motion_order if item not in recent_motions[-2:]),
                motion_order[0],
            )
        scene["cameraMotion"] = current_motion
        recent_motions.append(current_motion)

        transition_offset = (seed // 7 + index) % len(TRANSITIONS)
        transition_order = TRANSITIONS[transition_offset:] + TRANSITIONS[:transition_offset]
        transition = next(
            (item for item in transition_order if item != previous_transition),
            transition_order[0],
        )
        scene["transitionStyle"] = transition
        previous_transition = transition

        # A landscape film benefits from side-by-side information; a portrait cut
        # should reserve vertical space and favour stacked / tall-safe compositions.
        scene["composition"] = (
            "widescreen" if orientation == "landscape" else "portrait"
        )
    return scenes
