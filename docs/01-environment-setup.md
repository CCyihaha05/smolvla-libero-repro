# 环境搭建与 7 类问题的解决

> 记录在 Ubuntu 22.04 + RTX 4090 + Python 3.12 上搭建 LeRobot + LIBERO 时实际遇到的问题。每条都附报错原文与可复现的修复步骤。

---

## 0. 环境清单

| 项 | 版本 |
|---|---|
| GPU | RTX 4090 / 24564 MiB |
| 驱动 | 580.105.08 |
| OS | Ubuntu 22.04.5 LTS |
| Python | 3.12.3（miniconda base） |
| torch / torchvision | 2.8.0+cu128 / 0.23.0+cu128 |
| LeRobot | 0.6.2 |
| transformers / datasets | 5.5.4 / 4.8.5 |
| mujoco / robosuite | 3.8.1 / 1.4.0 |
| hf-libero | 0.1.4 |
| ffmpeg | 7.1.1（conda） |
| torchcodec | **已卸载**（走 PyAV 15.1.0） |

---

## 坑 1 · MuJoCo EGL 渲染失败：`libEGL.so.1` 缺失

**现象**

```
AttributeError: 'NoneType' object has no attribute 'eglQueryString'
```

或 `gladLoadGL error` / `Failed to initialize EGL display`。

**原因**：NVIDIA 的 `libEGL_nvidia.so.0` 和 `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` 都在，但缺少 GLVND 分发层 `libEGL.so.1`。

**诊断**

```bash
ldconfig -p | grep -E "libEGL\.so|libEGL_nvidia"
```

只有 `libEGL_nvidia.so.0`、没有 `libEGL.so.1` → 命中此问题。

**修复**

```bash
apt-get update
apt-get install -y libegl1 libegl-mesa0 libgles2
```

**验证**

```bash
MUJOCO_GL=egl python -c "
import mujoco
m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom type=\"box\" size=\".1 .1 .1\"/></worldbody></mujoco>')
d = mujoco.MjData(m); r = mujoco.Renderer(m, 240, 320)
mujoco.mj_forward(m, d); r.update_scene(d)
print('RENDER OK', r.render().shape)
"
```

> 析构时可能打印 `EGLError: <exception str() failed>`，属无害噪音；只要 stdout 有 `RENDER OK` 即成功。

---

## 坑 2 · LIBERO 首次导入阻塞在交互式提问

**现象**

```
EOFError: EOF when reading a line
```

指向 `libero/libero/__init__.py`：

```python
answer = input("Do you want to specify a custom path for the dataset folder? (Y/N): ")
```

**关键陷阱**：`import libero` 不会触发（外层包是空壳），必须 `from libero.libero import ...`。

**修复**

```bash
echo "N" | python -c "from libero.libero import benchmark"
```

生成 `~/.libero/config.yaml` 后不再提问。

---

## 坑 3 · 特征名不匹配：policy 期望 `camera1/camera2`

**现象**

```
ValueError: Feature mismatch between dataset/environment and policy config.
- Missing features: ['observation.images.camera1', 'observation.images.camera2']
- Extra features: ['observation.images.image', 'observation.images.image2']
```

**原因**：LIBERO 环境输出 `image` / `image2`，而 `lerobot/smolvla_libero` 训练时使用 `camera1` / `camera2`。

**修复**

```bash
--rename_map='{"observation.images.image": "observation.images.camera1", "observation.images.image2": "observation.images.camera2"}'
```

> 源码中 `make_policy` 有 `if not rename_map: validate_visual_features_consistency(...)` —— 传了 `rename_map` 就会跳过该校验。

---

## 坑 4 · hf-mirror 对多文件资源包限流 429

**现象**

```
HTTP Error 429 thrown while requesting HEAD https://hf-mirror.com/api/resolve-cache/...
Rate limited. Waiting 254.0s before retry [Retry 1/5].
```

`lerobot/libero-assets` 有 586 个文件，高并发下载触发限流。

**绕法**：用 git 协议拿文件树，再用 `resolve` 直链逐个下载实体文件。

```bash
mkdir -p /root/.cache/libero && cd /root/.cache/libero

# 1) 只拉文件树
GIT_LFS_SKIP_SMUDGE=1 git clone https://hf-mirror.com/datasets/lerobot/libero-assets assets-git

# 2) 逐个覆盖 LFS 指针
cd assets-git
grep -rl "git-lfs.github.com/spec" . | sed 's|^\./||' | while read -r f; do
  curl -sL --retry 3 --retry-delay 3 --max-time 300 \
    -o "$f" "https://hf-mirror.com/datasets/lerobot/libero-assets/resolve/main/$f"
done

# 3) 放到 LIBERO 默认查找位置
cd /root/.cache/libero
rm -rf assets && mv assets-git assets
```

**实测**：177 个 LFS 文件、约 470MB，4 并发约 4 分钟完成。

**验证**

```bash
for d in articulated_objects stable_scanned_objects turbosquid_objects stable_hope_objects scenes; do
  [ -d "/root/.cache/libero/assets/$d" ] && echo "OK   $d" || echo "MISS $d"
done
grep -rl "git-lfs.github.com/spec" /root/.cache/libero/assets 2>/dev/null | wc -l   # 应为 0
```

---

## 坑 5 · torchcodec 与 torch 2.8.0 ABI 不匹配

**现象（第一次）**

```
OSError: libavdevice.so.58: cannot open shared object file
```

`libavdevice.so.58` 是 ffmpeg 4.x 的 soname，而 conda 装的是 ffmpeg 7.1.1（`.so.61`）。

装系统 ffmpeg 4.x 后又变成：

```
OSError: .../libtorchcodec_core4.so: undefined symbol: torch_dtype_float4_e2m1fn_x2
```

（该符号是 torch 2.11 才有的）

**原因**：pip 默认装 torchcodec 0.11.1，需要 torch ≥ 2.11；本机 torch 2.8.0。

**修复**：卸载 torchcodec，走 PyAV 回退。

```bash
pip uninstall -y torchcodec
```

**实测**：`lerobot-info` 恢复正常；`lerobot-eval` 仍能正常生成 MP4，速度不受影响。

**版本对应参考**

| torch | torchcodec |
|---|---|
| 2.8 | 0.8.x |
| 2.9 | 0.9.x |
| 2.10 | 0.10.x |
| 2.11 | 0.11.x |

---

## 坑 6 · 非交互 shell 环境变量丢失 → 直连 HF 报 `Errno 99`

**现象**

```
'[Errno 99] Cannot assign requested address' thrown while requesting HEAD
https://huggingface.co/lerobot/smolvla_libero/resolve/main/config.json
huggingface_hub.errors.LocalEntryNotFoundError
```

**关键线索**：URL 是 `huggingface.co` 而不是 `hf-mirror.com` → `HF_ENDPOINT` 未生效。

**根因**：非交互 shell（`ssh host "cmd"`、脚本、部分 IDE 终端）不加载 `/etc/profile`，且 `~/.bashrc` 开头有 `[ -z "$PS1" ] && return`。

**修复**：用包装脚本，env 写死。

```bash
cat > run_eval.sh <<'EOF'
#!/bin/bash
export MUJOCO_GL=egl
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=/root/autodl-tmp/hf
export HF_HUB_ENABLE_HF_TRANSFER=0
cd "$(dirname "$0")/../lerobot" || exit 1
exec lerobot-eval "$@"
EOF
chmod +x run_eval.sh
```

---

## 坑 7 · 训练一启动报 `'repo_id' argument missing`

**现象**

```
ValueError: 'repo_id' argument missing. Please specify it to push the model to the hub.
```

**原因**：`PoliciesConfig` 中 `push_to_hub: bool = True` 而 `repo_id: str | None = None`，`validate()` 直接抛错。

**修复**

```bash
--policy.push_to_hub=false
# 或
--policy.repo_id=你的用户名/仓库名
```

---

## 附 · 训练有效 batch 的陷阱

训练是**按 step 迭代的离线监督学习**，episode 只存在于评测。

```
总样本数 = steps × batch_size × gradient_accumulation.steps
```

官方配方：20k steps × batch 64 = 1.28M 样本 ≈ 4.7 epoch（数据集 273,465 帧）。

**常见错误**：`batch_size=1, steps=30000` → 仅 30k 样本，不到一个 epoch 的 11%。

24GB 显存推荐配置：

```bash
--batch_size=2 \
--accelerator.mixed_precision=bf16 \
--accelerator.gradient_accumulation.steps=32 \
--steps=30000
# 有效 batch = 2 × 32 = 64
```

显存不足时降级（乘积保持 64）：`4×16` → `2×32` → `1×64`。
