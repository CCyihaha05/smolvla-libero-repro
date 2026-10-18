#!/usr/bin/env python3
"""从两个 eval run 中提取「A 成功但 B 失败」的配对视频。

LIBERO 使用固定初始状态，因此同一 task、同一 episode 编号在不同
`n_action_steps` 下是同一个初始条件，可以逐 episode 配对比较。

用法：
    python make_failure_pairs.py \
        --run-a outputs/eval/.../12-15-22_libero_smolvla \
        --run-b outputs/eval/.../12-29-49_libero_smolvla \
        --suite libero_spatial \
        --out failure_analysis

输出：
    <out>/<suite>_t<task>_ep<ep>_A_OK.mp4
    <out>/<suite>_t<task>_ep<ep>_B_FAIL.mp4
"""

import argparse
import json
import os
import shutil

import pandas as pd


def load_successes(run_dir: str) -> dict[int, list[bool]]:
    with open(os.path.join(run_dir, "eval_info.json")) as f:
        info = json.load(f)
    return {t["task_id"]: t["metrics"]["successes"] for t in info["per_task"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True, help="对照组 run（期望成功）")
    ap.add_argument("--run-b", required=True, help="实验组 run（期望失败）")
    ap.add_argument("--suite", required=True, help="例如 libero_spatial / libero_object")
    ap.add_argument("--out", default="failure_analysis")
    ap.add_argument("--tag-a", default="OK")
    ap.add_argument("--tag-b", default="FAIL")
    args = ap.parse_args()

    a = load_successes(args.run_a)
    b = load_successes(args.run_b)
    os.makedirs(args.out, exist_ok=True)

    rows = []
    for tid in sorted(a):
        for ep, (sa, sb) in enumerate(zip(a[tid], b[tid])):
            if not (sa and not sb):
                continue
            pa = os.path.join(args.run_a, "videos", f"{args.suite}_{tid}", f"eval_episode_{ep}.mp4")
            pb = os.path.join(args.run_b, "videos", f"{args.suite}_{tid}", f"eval_episode_{ep}.mp4")
            if not (os.path.exists(pa) and os.path.exists(pb)):
                print(f"[skip] missing video: task={tid} ep={ep}")
                continue
            base = f"{args.suite}_t{tid:02d}_ep{ep:02d}"
            shutil.copy(pa, os.path.join(args.out, f"{base}_A_{args.tag_a}.mp4"))
            shutil.copy(pb, os.path.join(args.out, f"{base}_B_{args.tag_b}.mp4"))
            rows.append({"suite": args.suite, "task_id": tid, "episode": ep,
                         "video_a": f"{base}_A_{args.tag_a}.mp4",
                         "video_b": f"{base}_B_{args.tag_b}.mp4"})

    df = pd.DataFrame(rows)
    csv_path = os.path.join(args.out, "pairs.csv")
    df.to_csv(csv_path, index=False)
    print(f"paired episodes: {len(df)}")
    print(f"manifest: {csv_path}")


if __name__ == "__main__":
    main()
