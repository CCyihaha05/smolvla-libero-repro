# 指标含义与置信区间

本文解释 `lerobot-eval` 输出中每个字段的含义，以及为什么 10 次评测的置信区间会那么宽。

---

## 单次评测的输出

```python
{'avg_sum_reward': 0.8,
 'avg_max_reward': 0.8,
 'pc_success': 80.0,
 'n_episodes': 10,
 'n_success': 8,
 'pc_success_ci95': [49.02, 94.33]}
```

| 字段 | 含义 |
|---|---|
| `avg_sum_reward` | 每个 episode 的累计奖励取平均。LIBERO 是二值奖励（成功=1，失败=0），所以等于成功率 |
| `avg_max_reward` | 每个 episode 的理论最大奖励取平均。二值奖励下与 `avg_sum_reward` 相同；密集奖励环境才会不同 |
| `n_episodes` | 总 episode 数。**汇总行是总数，不是每任务数** |
| `n_success` | 成功次数 |
| `pc_success` | 成功率百分比 = `n_success / n_episodes × 100` |
| `pc_success_ci95` | 成功率的 **95% 置信区间**（Wilson score interval） |

---

## ⚠️ `pc_success_ci95` 不是"95% 的成功概率"

| 说法 | 是否正确 |
|---|---|
| "成功率有 95% 的概率" | ❌ |
| "真实成功率的 95% 置信区间是 [49.0%, 94.3%]" | ✅ |

含义：**如果重复做同样的实验很多次，每次构造这样一个区间，约 95% 的区间会包含真实成功率。**

---

## 为什么区间这么宽

因为样本量小。

10 次里成功 8 次，无法区分真实成功率是 60%、80% 还是 95%。样本越小，估计越不确定。

正态近似下的误差：

```
误差 ≈ 1.96 × sqrt(p(1-p)/n)
     = 1.96 × sqrt(0.8 × 0.2 / 10)
     ≈ ±0.248
```

LeRobot 使用 **Wilson 区间**，在小样本和接近 0/100% 时更准确，且不对称。

### 样本量对照（假设真实成功率 80%）

| 每任务 episodes | 总 episodes（10 任务） | 典型 95% CI |
|---|---|---|
| 1 | 10 | [49%, 94%] |
| 10 | 100 | [71%, 87%] |
| 20 | 200 | [74%, 85%] |

---

## 置信区间重叠 ≠ 没有差异

比较两个配置时，**95% CI 重叠不代表差异不显著**。

更合适的做法是**配对检验**：LIBERO 使用固定初始状态，同一 task、同一 episode 编号在不同配置下是**同一个初始条件**，因此可以逐 episode 配对。

本文使用 **McNemar 精确检验**：

- b = A 成功且 B 失败的 episode 数
- c = A 失败且 B 成功的 episode 数
- 零假设下 b ~ Binomial(b+c, 0.5)

例：N=10 vs N=50 在 Spatial 上是 19:1，exact p < 0.0001。

---

## 复现时的记录规范

为了让他人能复现，每次实验至少记录：

```
模型 repo_id + commit sha
数据集 repo_id + commit sha
seed（默认 1000）
n_episodes × n_tasks
n_action_steps / chunk_size
硬件与框架版本
```

获取 commit sha：

```bash
python -c "from huggingface_hub import HfApi; a=HfApi(); \
print(a.model_info('lerobot/smolvla_libero').sha); \
print(a.dataset_info('lerobot/libero').sha)"
```
