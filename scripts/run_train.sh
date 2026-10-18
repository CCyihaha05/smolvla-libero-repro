#!/usr/bin/env bash
# 统一的训练入口。
#
# 用法：
#   ./scripts/run_train.sh \
#     --policy.path=lerobot/smolvla_libero \
#     --policy.push_to_hub=false \
#     --dataset.repo_id=lerobot/libero \
#     --rename_map='{"observation.images.image": "observation.images.camera1", "observation.images.image2": "observation.images.camera2"}' \
#     --batch_size=2 \
#     --accelerator.mixed_precision=bf16 \
#     --accelerator.gradient_accumulation.steps=32 \
#     --steps=30000 --policy.scheduler_decay_steps=30000 \
#     --policy.device=cuda \
#     --output_dir=outputs/train/smolvla_libero_ft \
#     --job_name=smolvla_libero_ft

set -euo pipefail

export MUJOCO_GL="${MUJOCO_GL:-egl}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-0}"

if [[ -n "${LEROBOT_DIR:-}" ]]; then
  cd "$LEROBOT_DIR"
fi

exec lerobot-train "$@"
