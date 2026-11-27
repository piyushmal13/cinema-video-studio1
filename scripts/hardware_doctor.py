#!/usr/bin/env python3
"""Read-only host preflight; does not install packages, download weights or change drivers."""
import json, os, platform, re, shutil, subprocess
from pathlib import Path

def cmd(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=8,check=False)
        return p.stdout.strip() if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired): return None

def inspect_hardware():
    ram=None
    try:
        if Path("/proc/meminfo").exists():
            m=re.search(r"MemTotal:\s+(\d+) kB",Path("/proc/meminfo").read_text())
            if m: ram=round(int(m.group(1))/1024/1024,2)
    except OSError: pass
    nvidia=cmd(["nvidia-smi","--query-gpu=name,memory.total,memory.free","--format=csv,noheader"])
    amd=cmd(["rocm-smi","--showproductname","--showmeminfo","vram"])
    profile="gpu-worker" if nvidia else "amd-experimental" if amd else "cpu-editorial"
    notes=[]
    if not nvidia and not amd: notes.append("No supported GPU runtime detected; do not schedule diffusion inference here.")
    if ram is not None and ram<16: notes.append("Under 16 GB RAM: reduce concurrency and avoid large model loading.")
    if not shutil.which("ffmpeg"): notes.append("FFmpeg missing from PATH.")
    if nvidia: notes.append("NVIDIA detected; validate free VRAM against exact model and resolution.")
    if amd: notes.append("AMD detected; support depends on OS, ROCm/DirectML and model kernels.")
    return {"os":platform.platform(),"cpu":platform.processor() or platform.machine(),
        "logical_cpu_count":os.cpu_count() or 1,"system_ram_gb":ram,"nvidia_smi":nvidia,
        "rocm_smi":amd,"ffmpeg":shutil.which("ffmpeg"),"ffprobe":shutil.which("ffprobe"),
        "profile":profile,"recommendations":notes,
        "model_policy":{"local_llm":"Use quantized models only after measuring memory.",
        "video_diffusion":"Use an explicitly provisioned GPU worker; free notebooks are opportunistic.",
        "rendering":"Use FFmpeg for simple assembly and Remotion for React motion graphics."}}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",default="out/hardware_report.json")
    a=p.parse_args();report=inspect_hardware();target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report,indent=2));return 0
if __name__=="__main__": raise SystemExit(main())
