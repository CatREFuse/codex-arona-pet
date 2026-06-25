# OpenPlana Image2 / Imagegen 动作模板

## 模板变量

| 变量 | 内容 |
|---|---|
| `{character}` | 角色名称 |
| `{reference}` | 角色参考图或现有动作帧 |
| `{module}` | 动作模组名，例如 `edge-idle-sleep-left` |
| `{action}` | 动作描述 |
| `{frame_count}` | 循环动画固定 12 帧；非循环动画按动作时长决定，但每秒 6 帧 |
| `{side}` | `none`、`left`、`right` |
| `{key_color}` | `#00ff00` 或 `#ff00ff` |

## 通用提示词

```text
Use case: stylized-concept
Asset type: OpenPlana desktop pet action sprite source strip
Primary request: Create a {frame_count}-frame horizontal source strip for {character}, module {module}.
Input images: {reference} as the character and style reference.
Subject: one consistent 3-head chibi QQ person, matching the edge-idle-sleep OpenPlana style: oversized head, compact body, white hair, black outfit, red-white halo, clean anime linework, soft but crisp shading.
Action: {action}.
Scene/backdrop: perfectly flat solid {key_color} chroma-key background.
Composition/framing: one horizontal strip or multiple smaller images, {frame_count} separated frame slots total, one complete pose per slot, generous chroma-key gap between frames, no overlap between hair, hands, props, halo, or adjacent slots.
Frame rule: every generated frame must already fit a 1:1 256x256 square frame before local processing. Full-body and normal frames need 8px transparent padding on all sides. Edge frames keep the black screen-edge line exactly on the dock-side boundary with no 8px inward shift; the top, bottom, and opposite side still need 8px padding. The outermost 4px dock-side band may contain only the black screen-edge line and must not contain hair, halo, face, hands, props, signs, tablets, or colored body pixels. Half-body cropping is allowed only when the module name or action spec explicitly says edge or half-body. Current normal modules idle-read, idle-normal, idle-sleep, coding, checking, awaiting, rejected, success, pinched, and carried must not be cropped by the frame.
Timing rule: looping animations must have exactly 12 frames at 6 fps, the first and last frames must connect cleanly, and adjacent frames must transition naturally. Non-looping animations use 6 fps with no frame-count upper limit.
Face rule: non-sleep modules keep the visible eye or both eyes open and steady in every frame, with one small closed mouth shape; no blink, wink, squeezed-shut eye, open mouth, O-mouth, shout, gasp, or sudden smile change. Sleep modules keep closed eyes consistently in every frame, with no opening/closing change.
Output quality: high-resolution clean raster source, enough detail to preserve clear 256x256 final frames.
Transparency prep: fill every empty area with {key_color}; fill the inside of the halo with {key_color}; do not leave white inside the halo.
Generation rule: the halo center must be produced this way in the full source strip by imagegen; do not repair it later by locally erasing, masking, or cutting only the halo area in final frames.
Style lock: same face width, head silhouette, hair shape, halo size, outfit, proportions, palette, outline thickness, and lighting across all frames.
Avoid: white background, checkerboard, shadows, glow, motion blur, speed lines, floating effects, frame numbers, guide marks, text, watermark, scenery, cropped halo, cropped hands, cropped hair, cropped sign/tablet, cropped face, changing face width, blink, wink, closed-eye reaction in non-sleep modules, sudden open mouth, rear-facing carried pose, colored pixels on the edge boundary, touching adjacent frame slots.
```

## 贴边 offset

左贴边：

```text
Side constraint: left edge animation. Add one thin black vertical screen-edge line exactly on the left canvas boundary. The character peeks out from behind that line toward the right. Keep the line fixed at x=0 in every frame. The outermost left 4px may contain only that black line; keep the visible face, hair, hands, book/tablet/sign, and halo fully inside the frame without touching or being cut by the canvas edge. Keep the same exposed body width across all frames.
```

右贴边：

```text
Side constraint: right edge animation. Add one thin black vertical screen-edge line exactly on the right canvas boundary. The character peeks out from behind that line toward the left. Keep the line fixed at the rightmost canvas pixel in every frame. The outermost right 4px may contain only that black line; keep the visible face, hair, hands, book/tablet/sign, and halo fully inside the frame without touching or being cut by the canvas edge. Keep the same exposed body width across all frames.
```

普通态：

```text
Side constraint: normal animation. No screen-edge line. Keep the whole character or intended prop fully inside every frame slot with safe padding on all sides.
```

## 动作描述

```text
idle-read: calm reading loop, small head and book movement, no page text.
idle-normal: quiet standing loop, subtle breathing, hands close to body.
idle-sleep: sleeping loop, closed eyes, subtle head bob, halo stable.
coding: kneeling or sitting with keyboard and translucent tablet, small hand movement, no readable UI text.
checking: focused inspection pose with magnifier, subtle lean, eyes steady, no symbols.
awaiting: expectant waiting pose, quiet and patient, no waving.
rejected: holding a red rejection sign or paper shape, no readable text.
success: holding a green check sign shape, no readable text.
pinched: cheek-pinched reaction, visible eye kept open, redraw as a single integrated pose, no overlay layer look.
carried: front-facing carried pose, lifted by collar or nape-side upper clothing, dangling compact body, face visible, limbs hanging, no rear view.
edge-peek: peeking from the screen edge, curious expression, no prop.
```

## Imagegen built-in 用法

把通用提示词、贴边 offset 和动作描述合并成一次 `$imagegen` 提示词。贴边模组如果一张横向条带出现生成画布裁切、相邻帧挤压、脸宽跳变或 edge line 吞掉角色，必须分成逐帧或每 2-3 帧小批量生成，再整理为同一模组的连续帧。输出保存后放入对应模组目录，命名为 `source-strip-chroma.png`、`source-strip-magenta.png` 或逐帧 `00.png` 到 `11.png`，再运行：

```bash
./script/process_neo_action_assets.py --character plana --state <state>
```

脚本会把素材整理为 `256x256` 透明帧，清理抠图背景，重建接触表，并执行素材校验。脚本不得单独重画、擦除或局部抠除光环；发现光环内孔不是抠图背景色、贴边外侧 4px 出现非黑素材像素、源条带中任一帧被 canvas 或相邻 frame slot 裁切、脸宽明显变化或头部轮廓跳变时，退回 imagegen 重新生成源图。

## Image2 用法

推荐参数：

```text
model: gpt-image-2
quality: high
size: 3840x2160
background: use flat chroma-key in the prompt
```

生成透明 PNG 时仍优先使用纯色背景源条，再交给本地脚本抠图。只有在纯色抠图无法处理发丝、半透明材质或复杂光效时，才使用原生透明输出流程。
