from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import requests


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    """Run user-owned ComfyUI API workflows without hard-coding model/node packs."""

    def __init__(self, base_url: str, *, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CinemaVideoStudio/1.0"})

    @staticmethod
    def _load_workflow(path: str | Path) -> dict[str, Any]:
        workflow_path = Path(path)
        if not workflow_path.is_file():
            raise ComfyUIError(f"ComfyUI workflow file does not exist: {workflow_path}")
        try:
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ComfyUIError(f"Cannot read ComfyUI API workflow: {error}") from error
        if not isinstance(workflow, dict) or not workflow:
            raise ComfyUIError("ComfyUI API workflow must be a non-empty JSON object.")
        return workflow

    @staticmethod
    def _patch_workflow(
        workflow: dict[str, Any],
        prompt: str,
        negative_prompt: str,
        *,
        seed: int,
        mapping_path: str | Path | None = None,
    ) -> dict[str, Any]:
        graph = json.loads(json.dumps(workflow))
        mapping: dict[str, Any] = {}
        if mapping_path:
            try:
                mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise ComfyUIError(f"Invalid ComfyUI node mapping file: {error}") from error

        positive_ids = [str(value) for value in mapping.get("positive_prompt_nodes", [])]
        negative_ids = [str(value) for value in mapping.get("negative_prompt_nodes", [])]
        seed_ids = [str(value) for value in mapping.get("seed_nodes", [])]

        if not positive_ids:
            positive_ids = [
                str(node_id) for node_id, node in graph.items()
                if isinstance(node, dict)
                and node.get("class_type") in {"CLIPTextEncode", "CLIPTextEncodeSDXL"}
                and isinstance(node.get("inputs"), dict)
                and isinstance(node["inputs"].get("text"), str)
            ][:1]
        if not negative_ids:
            all_text_nodes = [
                str(node_id) for node_id, node in graph.items()
                if isinstance(node, dict)
                and node.get("class_type") in {"CLIPTextEncode", "CLIPTextEncodeSDXL"}
                and isinstance(node.get("inputs"), dict)
                and isinstance(node["inputs"].get("text"), str)
            ]
            negative_ids = all_text_nodes[1:2]

        patched_prompts = 0
        for node_id in positive_ids:
            node = graph.get(node_id)
            if isinstance(node, dict) and isinstance(node.get("inputs"), dict):
                node["inputs"]["text"] = prompt
                patched_prompts += 1
        for node_id in negative_ids:
            node = graph.get(node_id)
            if isinstance(node, dict) and isinstance(node.get("inputs"), dict):
                node["inputs"]["text"] = negative_prompt

        if patched_prompts == 0:
            raise ComfyUIError(
                "No positive prompt node was patched. Add its node ID to the workflow mapping JSON."
            )

        if not seed_ids:
            seed_ids = [
                str(node_id) for node_id, node in graph.items()
                if isinstance(node, dict)
                and node.get("class_type") in {"KSampler", "KSamplerAdvanced"}
                and isinstance(node.get("inputs"), dict)
                and ("seed" in node["inputs"] or "noise_seed" in node["inputs"])
            ]
        for node_id in seed_ids:
            node = graph.get(node_id)
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                continue
            inputs = node["inputs"]
            if "seed" in inputs:
                inputs["seed"] = int(seed)
            if "noise_seed" in inputs:
                inputs["noise_seed"] = int(seed)
        return graph

    def _get(self, path: str, **kwargs):
        try:
            response = self.session.get(
                f"{self.base_url}{path}", timeout=kwargs.pop("timeout", self.timeout), **kwargs
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            raise ComfyUIError(f"ComfyUI GET {path} failed: {error}") from error

    def _post(self, path: str, **kwargs):
        try:
            response = self.session.post(
                f"{self.base_url}{path}", timeout=kwargs.pop("timeout", self.timeout), **kwargs
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            detail = getattr(error.response, "text", "")[:500] if error.response is not None else ""
            raise ComfyUIError(f"ComfyUI POST {path} failed: {error}; {detail}") from error

    def generate(
        self,
        workflow_path: str | Path,
        prompt: str,
        output_dir: str | Path,
        *,
        negative_prompt: str = "blurry, low quality, malformed, flicker, subtitles, watermark, logo",
        seed: int = 1,
        mapping_path: str | Path | None = None,
        timeout_seconds: int = 240,
    ) -> list[Path]:
        workflow = self._load_workflow(workflow_path)
        workflow = self._patch_workflow(
            workflow, prompt, negative_prompt, seed=seed, mapping_path=mapping_path
        )
        client_id = str(uuid.uuid4())
        queued = self._post(
            "/prompt",
            json={"prompt": workflow, "client_id": client_id},
        ).json()
        prompt_id = queued.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyUIError(f"ComfyUI did not return a prompt_id: {queued}")

        deadline = time.monotonic() + max(10, timeout_seconds)
        history: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                result = self._get(f"/history/{prompt_id}").json()
                item = result.get(prompt_id) if isinstance(result, dict) else None
                if isinstance(item, dict) and item.get("outputs"):
                    history = item
                    break
                if isinstance(item, dict) and item.get("status", {}).get("status_str") == "error":
                    raise ComfyUIError(f"ComfyUI workflow failed: {item.get('status')}")
            except (ValueError, ComfyUIError):
                raise
            time.sleep(1.5)

        if history is None:
            raise ComfyUIError(f"ComfyUI workflow timed out after {timeout_seconds}s.")

        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        outputs = history.get("outputs", {})
        for node_id, node_output in outputs.items():
            if not isinstance(node_output, dict):
                continue
            for category in ("images", "videos", "gifs"):
                for item in node_output.get(category, []) or []:
                    if not isinstance(item, dict) or not item.get("filename"):
                        continue
                    filename = str(item["filename"])
                    subfolder = str(item.get("subfolder", ""))
                    media_type = str(item.get("type", "output"))
                    response = self._get(
                        "/view",
                        params={
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": media_type,
                        },
                        timeout=90,
                    )
                    suffix = Path(filename).suffix or (".mp4" if category == "videos" else ".png")
                    target = destination / f"comfy_{prompt_id[:8]}_{node_id}_{len(saved)}{suffix}"
                    max_bytes = 180 * 1024 * 1024
                    if len(response.content) > max_bytes:
                        raise ComfyUIError("ComfyUI output exceeded the 180 MB safety limit.")
                    target.write_bytes(response.content)
                    if target.stat().st_size > 5_000:
                        saved.append(target)
        if not saved:
            raise ComfyUIError("ComfyUI finished but returned no downloadable image/video outputs.")
        return saved


def generate_from_environment(
    prompt: str,
    output_dir: str | Path,
    *,
    media_kind: str,
    seed: int,
) -> list[Path]:
    base_url = os.environ.get("COMFYUI_BASE_URL", "").strip()
    workflow_path = os.environ.get(
        "COMFYUI_VIDEO_WORKFLOW" if media_kind == "video" else "COMFYUI_IMAGE_WORKFLOW", ""
    ).strip()
    if not base_url or not workflow_path:
        return []
    mapping_path = os.environ.get(
        "COMFYUI_VIDEO_MAPPING" if media_kind == "video" else "COMFYUI_IMAGE_MAPPING", ""
    ).strip() or None
    client = ComfyUIClient(base_url, timeout=20)
    return client.generate(
        workflow_path,
        prompt,
        output_dir,
        seed=seed,
        mapping_path=mapping_path,
        timeout_seconds=int(os.environ.get("COMFYUI_TIMEOUT_SECONDS", "240")),
    )
