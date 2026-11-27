#!/usr/bin/env python3
"""Append measured job telemetry; unknown cash cost remains null, never guessed."""
import argparse,json,os,platform,time
from datetime import datetime,timezone
from pathlib import Path

def build_record(*,job_id,started_at,finished_at,output,video_data,hardware_report=None):
    data=json.loads(video_data.read_text(encoding="utf-8")) if video_data.exists() else {}
    scenes=data.get("scenes",[]) if isinstance(data.get("scenes"),list) else []
    media=[]
    for scene in scenes:
        if isinstance(scene,dict):
            media.extend(scene.get("mediaFiles") or ([scene["mediaFile"]] if scene.get("mediaFile") else []))
    size=output.stat().st_size if output.is_file() else 0
    hw=json.loads(hardware_report.read_text(encoding="utf-8")) if hardware_report and hardware_report.exists() else {}
    duration=round(max(0,finished_at-started_at),3)
    return {"job_id":job_id,"recorded_at":datetime.now(timezone.utc).isoformat(),
        "duration_seconds":duration,"video_file":str(output),"video_bytes":size,
        "source_asset_count":len(media),"scene_count":len(scenes),
        "voice_provider":data.get("voiceProvider","unknown"),
        "storyboard_provider":data.get("storyboardProvider","unknown"),
        "degraded_mode":bool(data.get("degradedMode")),"hardware_profile":hw.get("profile","unknown"),
        "runner_os":platform.platform(),"accounting":{"cash_cost_usd":None,
        "cash_cost_note":"Unknown: provider invoices, free quotas and electricity are not exposed to this process.",
        "compute_seconds":duration,"storage_bytes":size}}

def append_record(record,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f:f.write(json.dumps(record,ensure_ascii=False)+"\n")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",default="out/final.mp4");p.add_argument("--video-data",default="public/video_data.json")
    p.add_argument("--hardware-report",default="out/hardware_report.json");p.add_argument("--ledger",default="out/production_ledger.jsonl")
    p.add_argument("--job-id",default=os.environ.get("CINEMA_JOB_ID") or os.environ.get("GITHUB_RUN_ID","local"))
    p.add_argument("--started-at",type=float,default=float(os.environ.get("CINEMA_STARTED_AT","0") or 0))
    a=p.parse_args();now=time.time();start=a.started_at if a.started_at>0 else now
    record=build_record(job_id=a.job_id,started_at=start,finished_at=now,output=Path(a.output),
        video_data=Path(a.video_data),hardware_report=Path(a.hardware_report))
    append_record(record,Path(a.ledger));print(json.dumps(record,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
