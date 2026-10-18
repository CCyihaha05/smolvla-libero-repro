# SmolVLA + LIBERO 基准复现与偏差归因

> 在单卡 RTX 4090 上从零搭建 LeRobot + LIBERO 仿真环境，复现 SmolVLA-450M 的 LIBERO 基准，并通过消融实验、跨套件验证与失败行为分析定位复现偏差的来源。

**核心结论**

- 四套件平均成功率 **81.75%**，论文 87.3%（差 −5.55pp）
- 长时程套件几乎完全复现（70% vs 71%）
- LeRobot 默认的 `n_action_steps=50` 恰为论文消融中的最差配置；调至 10 后，Spatial 从 **64% 提升到 82%**（配对 McNemar 19:1, p<0.0001）
- 通过 11 对同初始状态的对照视频，把失效机制从"误差累积"修正为"**失去重试窗口**"

---

## 1. 结果

### 1.1 四套件基线（`n_action_steps=10`，共 400 episodes）

| 套件 | 本复现 | 95% CI | 论文 (SmolVLA-0.45B) | 差值 |
|---|---|---|---|---|
| LIBERO-Spatial | 82.0% | [73.3, 88.3] | 90% | −8.0 |
| LIBERO-Object | 88.0% | [80.2, 93.0] | 96% | −8.0 |
| LIBERO-Goal | 87.0% | [79.0, 92.2] | 92% | −5.0 |
| LIBERO-Long | 70.0% | [60.4, 78.1] | 71% | −1.0 |
| **平均** | **81.75%** | — | **87.3%** | **−5.55** |

评测协议：40 任务 × 10 episodes = 400 episodes，官方 checkpoint `lerobot/smolvla_libero`。

### 1.2 `n_action_steps` 消融（LIBERO-Spatial，每档 100 episodes）

| `n_action_steps` | 成功率 | 95% CI | 论文 |
|---|---|---|---|
| 1 | **83.0%** | [74.5, 89.1] | 80.3% |
| **10** | **82.0%** | [73.3, 88.3] | 82.8% |
| 25 | 77.0% | [67.8, 84.2] | ≈70.8%（论文 N=30） |
| 50 | **64.0%** | [54.2, 72.7] | 51.8% |

**`chunk_size` 固定为 50**（模型结构决定），只改变推理期的执行步数。

配对 McNemar（同一初始状态）：

| 比较 | 支持 A / 支持 B | exact p |
|---|---|---|
| N=10 vs N=50 | **19 : 1** | **< 0.0001** |
| N=25 vs N=50 | 17 : 4 | 0.0072 |
| N=10 vs N=25 | 7 : 2 | 0.180 |
| N=1 vs N=10 | 4 : 3 | 1.000 |

### 1.3 跨套件验证（LIBERO-Object）

| 套件 | N=10 | N=50 | 退化 | McNemar |
|---|---|---|---|---|
| Spatial | 82.0% | 64.0% | −18pp | 19:1, p<0.0001 |
| **Object** | **88.0%** | **59.0%** | **−29pp** | **31:2, p=1.3e-7** |

物体操作任务的退化幅度约为空间推理任务的 1.6 倍。

---

## 2. 关键发现

### 2.1 退化不是全局常数，而是与任务对闭环反馈的依赖程度相关

| 任务 | 描述 | N=1 | N=10 | N=25 | N=50 |
|---|---|---|---|---|---|
| Spatial-0 | 盘子与烤盅之间的碗 | 100 | 100 | 100 | 100 |
| Spatial-4 | **木柜最上层抽屉里的碗** | 90 | 70 | 60 | **50** |
| Spatial-5 | 烤盅上面的碗 | 0 | 10 | 0 | 0 |
| Spatial-8 | 盘子旁边的碗 | 80 | 70 | 80 | **40** |

- 短距离、无遮挡的任务完全不受影响
- 需要伸入遮挡区域的任务退化最严重
- Task 5 在所有配置下都只有 0–10% —— **这是策略能力上限，与控制视界无关**

### 2.2 机制修正：不是"误差累积"，而是"失去重试窗口"

对 11 对「同初始状态、N=10 成功 / N=50 失败」的配对视频做逐帧对比：

| 失败类型 | 涉及次数 |
|---|---|
| 定位偏差 | 9 / 11 |
| 动作滞后（继续执行失效动作块） | 6 / 11 |
| 抓取滑脱 | 1 / 11 |

**关键观察**：11 个 N=10 成功样本中，至少 4 个本身就是「抓空 → 重新观测 → 重试 → 成功」。

> 这说明 N=10 与 N=50 的**单步定位精度没有本质差异**——两者的第一次抓取都有相当比例是失准的。
>
> 差别在于：N=10 每 10 步重新观测一次，**抓空后能在下一个窗口立刻重试并成功**；N=50 在抓空后还要继续执行几十步已经失效的计划，要么带着空夹爪完成后续动作，要么在错误位置反复重试。
>
> **开环执行的核心代价不是"精度下降"，而是"剥夺了从错误中恢复的机会"。**

典型失败行为：

| 行为 | 含义 |
|---|---|
| 抓空后直接移向篮子 | 它"以为"已经抓到了 |
| 同一位置反复抓取 | 重新观测了，但位置没变，仍然抓空 |
| 抓错物体（篮子 / 另一个罐子） | 动作方向对，目标定位失准 |
| 抬起时打滑 | 真正抓到但滑脱（少数） |

**在线对照播放器**：[`failure_analysis/index.html`](failure_analysis/index.html)（GitHub Pages 或本地打开）

---

## 3. 复现方法

### 3.1 环境

| 项 | 版本 |
|---|---|
| GPU | RTX 4090 24GB |
| OS | Ubuntu 22.04.5 LTS |
| Python | 3.12.3 |
| PyTorch | 2.8.0+cu128 |
| LeRobot | 0.6.2 |
| transformers | 5.5.4 |
| datasets | 4.8.5 |
| mujoco | 3.8.1 |
| hf-libero | 0.1.4 |
| 视频解码 | PyAV 15.1.0（torchcodec 已卸载） |

### 3.2 命令

```bash
# 四套件基线（每个套件单独跑，避免已知挂起问题）
for S in libero_spatial libero_object libero_goal libero_10; do
  ./scripts/run_eval.sh \
    --policy.path=lerobot/smolvla_libero \
    --env.type=libero --env.task=$S \
    --eval.batch_size=1 --eval.n_episodes=10 \
    --policy.n_action_steps=10 \
    --rename_map='{"observation.images.image": "observation.images.camera1", "observation.images.image2": "observation.images.camera2"}'
done
```

完整环境搭建与 7 类问题的解决方案见 [`docs/01-environment-setup.md`](docs/01-environment-setup.md)。

---

## 4. 仓库结构

```
.
├── README.md
├── LICENSE                     Apache-2.0
├── docs/
│   ├── 01-environment-setup.md 环境搭建与 7 类问题的解决
│   ├── 02-metrics-explained.md 指标含义与置信区间
│   ├── 03-ablation.md          n_action_steps 消融完整分析
│   └── 04-failure-analysis.md  11 对配对视频的行为归因
├── scripts/
│   ├── run_eval.sh
│   └── run_train.sh
├── results/
│   ├── ablation_spatial.csv
│   ├── cross_suite_object.csv
│   ├── baseline_four_suites.csv
│   └── failure_pairs.csv
└── failure_analysis/
    ├── index.html              左右对照播放器
    └── *.mp4                   50 对（N=10 成功 / N=50 失败）
```

---

## 5. 已知问题

| 问题 | 现象 | 规避 |
|---|---|---|
| 多套件评测挂起 | 四套件一起跑时在 `libero_goal` task 6 永久卡住；CPU 空闲、线程全 sleeping、`eval_info.json` 不生成 | 按套件分开跑 |
| `torchcodec` ABI 不匹配 | torch 2.8 与 torchcodec 0.11 的符号不兼容 | 卸载 torchcodec，走 PyAV |
| 特征名不匹配 | 环境输出 `image/image2`，checkpoint 期望 `camera1/camera2` | 使用 `--rename_map` |

---

## 6. 局限

- **只做了定性失败分析**（11 / 50 对），未做逐帧定量标注
- 两个套件的任务结构不同，**不能把退化幅度直接归因于"接触密度"**
- 论文数字与本次复现的差异来源未能完全隔离（评测协议 / checkpoint 配方 / 初始状态集合）
- 未在真机上验证，全部结果来自仿真

---

## 7. 致谢与许可

- 模型与框架：[Hugging Face LeRobot](https://github.com/huggingface/lerobot)、[SmolVLA](https://arxiv.org/abs/2506.01844)
- 仿真基准：[LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)
- 本仓库代码与分析采用 [Apache-2.0](LICENSE)
- 未分发模型权重与 LIBERO 资源文件；视频为本地评测产物
