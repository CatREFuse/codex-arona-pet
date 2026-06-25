# OpenPlana 美术动作模组

## 资源标准

当前角色为 `plana-neo` 和 `arona-neo`。扩展动作帧统一使用 `256x256` 透明 PNG，运行时通过 `openplana-character.json` 的 `extraStates` 播放。

贴边睡觉模组是画风基准：3 头身 QQ 人比例，白发、黑色服装、红白光环、浅灰发丝阴影、干净透明边缘。贴边模组需要保留屏幕边界黑线：左贴边黑线贴齐画布左边，右贴边黑线贴齐画布右边；同一角色的外露比例、头顶光环和手部位置保持一致。

源图标准：

- 使用纯色抠图背景，优先 `#00ff00`，角色含绿色时改用 `#ff00ff`。
- 光环内部必须填充同一抠图背景色，不能保留白色内孔。
- 光环内孔必须在完整角色源图中由 imagegen 生成，不能在最终帧上单独抠除或局部修补光环。
- 帧与帧之间保留足够间距，角色、头发、手部、道具和光环不能进入相邻帧。
- 源图生成阶段就必须把每一帧放进 1:1 方型框架，不能先生成裁切图再靠本地脚本补救。
- 最终帧可见像素必须保留 8px 垂直安全边距；普通动作还必须保留 8px 水平安全边距；贴边动作只允许屏幕边界线贴住左边或右边。
- 贴边侧不做 8px 内移，但最外侧 4px 只能是黑色屏幕边界线；头发、光环、脸、手、道具、牌子、平板和身体色块不得被生成画布裁切。
- 半身裁切只在明确标记为贴边或半身的模组里使用；当前普通模组 `idle-read`、`idle-normal`、`idle-sleep`、`coding`、`checking`、`awaiting`、`rejected`、`success`、`pinched`、`carried` 全部必须完整进框。
- 同一循环里的脸宽、头部轮廓、外露身体宽度必须保持稳定，不能出现中间帧突然变窄或变宽。
- 循环动画固定 12 帧、每秒 6 帧，必须首尾相接，帧间动作自然过渡。
- 非循环动画每秒 6 帧，帧数不上限。
- 单张图无法稳定生成时，可以分成多张图生成，再整理为同一模组的连续帧。
- 最终帧四角 alpha 必须为 0。

## 当前模组

| 状态 | 模组目录 | 帧数 | 用途 | 状态 |
|---|---|---:|---|---|
| `carried` | `extra/carried` | 12 | 拖拽 | 已启用 |
| `pinched` | `extra/pinched` | 12 | 普通点击 | 已启用 |
| `edge-pinched-left` | `extra/edge-pinched-left` | 12 | 左贴边点击 | 已启用 |
| `edge-pinched-right` | `extra/edge-pinched-right` | 12 | 右贴边点击 | 已启用 |
| `edge-peek-left` | `extra/edge-peek-left` | 12 | 左贴边露出 | 已启用 |
| `edge-peek-right` | `extra/edge-peek-right` | 12 | 右贴边露出 | 已启用 |
| `idle-read` | `extra/idle-read` | 12 | 待机看书、运行态看书 | 已启用 |
| `idle-normal` | `extra/idle-normal` | 12 | 普通待机备用 | 资源可用 |
| `idle-sleep` | `extra/idle-sleep` | 12 | 待机睡觉 | 已启用 |
| `edge-idle-read-left` | `extra/edge-idle-read-left` | 12 | 左贴边看书 | 已启用 |
| `edge-idle-read-right` | `extra/edge-idle-read-right` | 12 | 右贴边看书 | 已启用 |
| `edge-idle-normal-left` | `extra/edge-idle-normal-left` | 12 | 左贴边待机备用 | 资源可用 |
| `edge-idle-normal-right` | `extra/edge-idle-normal-right` | 12 | 右贴边待机备用 | 资源可用 |
| `edge-idle-sleep-left` | `extra/edge-idle-sleep-left` | 12 | 左贴边睡觉 | 已启用 |
| `edge-idle-sleep-right` | `extra/edge-idle-sleep-right` | 12 | 右贴边睡觉 | 已启用 |
| `coding` | `extra/coding` | 12 | 运行态敲键盘 | 已启用 |
| `edge-coding-left` | `extra/edge-coding-left` | 12 | 左贴边运行态 | 已启用 |
| `edge-coding-right` | `extra/edge-coding-right` | 12 | 右贴边运行态 | 已启用 |
| `checking` | `extra/checking` | 12 | 检查、运行态检查 | 已启用 |
| `edge-checking-left` | `extra/edge-checking-left` | 12 | 左贴边检查 | 已启用 |
| `edge-checking-right` | `extra/edge-checking-right` | 12 | 右贴边检查 | 已启用 |
| `awaiting` | `extra/awaiting` | 12 | 等待输入 | 已启用 |
| `edge-awaiting-left` | `extra/edge-awaiting-left` | 12 | 左贴边等待输入 | 已启用 |
| `edge-awaiting-right` | `extra/edge-awaiting-right` | 12 | 右贴边等待输入 | 已启用 |
| `rejected` | `extra/rejected` | 12 | 失败 | 已启用 |
| `edge-rejected-left` | `extra/edge-rejected-left` | 12 | 左贴边失败 | 已启用 |
| `edge-rejected-right` | `extra/edge-rejected-right` | 12 | 右贴边失败 | 已启用 |
| `success` | `extra/success` | 12 | 完成 | 已启用 |
| `edge-success-left` | `extra/edge-success-left` | 12 | 左贴边完成 | 已启用 |
| `edge-success-right` | `extra/edge-success-right` | 12 | 右贴边完成 | 已启用 |

基础 spritesheet 使用 `3072x2304`、`12x9`、每格 `256x256` 的透明格式。扩展动作模组同样使用 `256x256` 连续帧，运行时 sprite 容器保持 1:1。

## 运行映射

| 运行状态 | 普通态 | 左贴边 | 右贴边 |
|---|---|---|---|
| 待机 | `idle-read` / `idle-sleep` | `edge-idle-read-left` / `edge-idle-sleep-left` | `edge-idle-read-right` / `edge-idle-sleep-right` |
| 运行 | `coding` / `idle-read` / `checking` | `edge-coding-left` / `edge-idle-read-left` / `edge-checking-left` | `edge-coding-right` / `edge-idle-read-right` / `edge-checking-right` |
| 等待 | `awaiting` | `edge-awaiting-left` | `edge-awaiting-right` |
| 检查 | `checking` | `edge-checking-left` | `edge-checking-right` |
| 失败 | `rejected` | `edge-rejected-left` | `edge-rejected-right` |
| 完成 | `success` | `edge-success-left` | `edge-success-right` |
| 拖拽 | `carried` | `carried` | `carried` |
| 点击 | `pinched` | `edge-pinched-left` | `edge-pinched-right` |

## 检查项

- `./script/process_neo_action_assets.py --character plana-neo --state <state>`
- `./script/validate_pet_assets.py`
- 第一轮视觉检查：查看 `.codex/tmp/asset-audit-after/all-contact-sheets.png`。
- 第二轮运行检查：执行 `./script/build_and_run.sh --verify`，再按待机、运行、等待、检查、失败、完成、拖拽、点击检查实际窗口。
