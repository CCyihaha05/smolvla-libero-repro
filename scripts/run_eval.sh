#!/usr/bin/env bash
# 统一的评测入口：把环境变量固定下来，避免非交互 shell 丢失配置。
#
# 用法：
#   ./scripts/run_eval.sh --policy.path=lerobot/smolvla_libero \
#       --env.type=libero --env.task=libero_spatial \
#       --eval.batch_size=1 --eval.n_episodes=10 \
#       --policy.n_action_steps=10 \
#       --rename_map='{"observation.images.image": "observation.images.camera1", "observation.images.image2": "observation.images.camera2"}'
#
# 可以通过环境变量覆盖：
#   LEROBOT_DIR   LeRobot 仓库目录（输出会写到该目录下的 outputs/）
#   HF_HOME       HuggingFace 缓存目录

set -euo pipefail

export MUJOCO_GL="${MUJOCO_GL:-egl}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-0}"

if [[ -n "${LEROBOT_DIR:-}" ]]; then
  cd "$LEROBOT_DIR"
fi

exec lerobot-eval "$@"
