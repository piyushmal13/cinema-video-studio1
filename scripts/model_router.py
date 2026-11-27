#!/usr/bin/env python3
"""Conservative model admission: report what this host can attempt, never download weights."""
from __future__ import annotations
import argparse,json,re,subprocess
from pathlib import Path

REGISTRY = {
 "wan2.1-1.3b": {"family":"wan","min_vram_gb":8.2,"tier":"compact","weight_license":"verify-upstream","commercial_status":"review-required","note":"Official low-VRAM statement is hardware/configuration-specific; require benchmark."},
 "wan2.2-ti2v-5b": {"family":"wan","min_vram_gb":8.0,"tier":"worker","weight_license":"Apache-2.0","commercial_status":"verify-exact-weights","note":"8 GB is an optimistic ComfyUI offload community floor; upstream native path may require substantially more."},
 "wan2.2-a14b": {"family":"wan","min_vram_gb":80.0,"tier":"datacenter","weight_license":"Apache-2.0","commercial_status":"verify-exact-weights","note":"Treat as datacenter GPU workload."},
 "ltx-2.5-22b": {"family":"ltx","min_vram_gb":32.0,"tier":"datacenter","weight_license":"LTX-2.x Community License","commercial_status":"restricted-community-terms","note":"Code Apache-2.0 does not make model weights Apache-2.0."},
 "hunyuanvideo-1.5": {"family":"hunyuan","min_vram_gb":14.0,"tier":"high-memory","weight_license":"Tencent Hunyuan Community License","commercial_status":"territory-and-terms-review","note":"Confirm current model version and regional restrictions."}
}

def nvidia_vram_gb():
    try:
        p=subprocess.run(["nvidia-smi","--query-gpu=memory.total,memory.free","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=5,check=True)
        rows=[]
        for line in p.stdout.splitlines():
            values=re.findall(r"\d+",line)
            if len(values)>=2: rows.append({"total_gb":round(int(values[0])/1024,2),"free_gb":round(int(values[1])/1024,2)})
        return rows
    except (OSError,subprocess.SubprocessError): return []

def recommend(gpus, safety_margin_gb=1.5):
    if not gpus:
        return {"profile":"cpu-editorial","local_diffusion_allowed":False,"eligible_models":[],
            "reason":"No NVIDIA CUDA runtime detected. Use licensed media, stills, Remotion and FFmpeg; remote worker is a separate route."}
    free=max(g["free_gb"] for g in gpus)
    eligible=[name for name,item in REGISTRY.items() if free >= item["min_vram_gb"]+safety_margin_gb]
    return {"profile":"nvidia-worker","local_diffusion_allowed":bool(eligible),"free_vram_gb":free,
        "eligible_models":eligible,"reason":"Eligibility is a coarse VRAM gate only; run the exact model/workflow benchmark before production."}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",default="out/model_admission.json")
    p.add_argument("--safety-margin-gb",type=float,default=1.5);p.add_argument("--list-models",action="store_true")
    a=p.parse_args()
    if a.list_models: print(json.dumps(REGISTRY,indent=2));return 0
    report={"hardware":nvidia_vram_gb(),"admission":recommend(nvidia_vram_gb(),a.safety_margin_gb),"registry":REGISTRY}
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
