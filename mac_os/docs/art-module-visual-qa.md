# OpenPlana 动作模组视觉 QA

检查时间：2026-06-22

检查图：

- `.codex/tmp/qa-256/all-contact-sheets-256.png`

## 结构结果

- 基础 spritesheet：`3072x2304`，12 列 9 行，每格 `256x256`。
- 扩展动作：30 个模组，360 张帧图，全部为 `256x256` 透明 PNG。
- 播放速度：全部 `frameDuration = 0.1666666667`。
- 循环动作：12 帧，首尾像素闭合，帧间过渡连续。
- 非循环动作：12 帧，6fps，播放到最后一帧停住。
- 裁切规则：普通模组全部保留 8px 四向安全边距；贴边模组仅允许屏幕侧黑色边界线触边，贴边侧不做 8px 内移。
- 贴边边界：最外侧 4px 只允许黑色屏幕边界线，不允许头发、光环、脸、手、道具、牌子、平板或身体色块进入。
- 帧间稳定性：贴边循环检查上半身宽度、下半身深色像素和整体可见像素变化，脸宽或外露身体宽度明显跳变会失败。
- 资源目录：`extra` 下只允许清单引用的连续帧 PNG，QA contact sheet 不进入角色资源目录。

## 逐项结论

| 模组 | 帧数 | 结果 |
|---|---:|---|
| `awaiting` | 12 | 通过 |
| `carried` | 12 | 通过 |
| `checking` | 12 | 通过 |
| `coding` | 12 | 通过 |
| `edge-awaiting-left` | 12 | 通过 |
| `edge-awaiting-right` | 12 | 通过 |
| `edge-checking-left` | 12 | 通过 |
| `edge-checking-right` | 12 | 通过 |
| `edge-coding-left` | 12 | 通过 |
| `edge-coding-right` | 12 | 通过 |
| `edge-idle-normal-left` | 12 | 通过 |
| `edge-idle-normal-right` | 12 | 通过 |
| `edge-idle-read-left` | 12 | 通过 |
| `edge-idle-read-right` | 12 | 通过 |
| `edge-idle-sleep-left` | 12 | 通过 |
| `edge-idle-sleep-right` | 12 | 通过 |
| `edge-peek-left` | 12 | 通过 |
| `edge-peek-right` | 12 | 通过 |
| `edge-pinched-left` | 12 | 通过 |
| `edge-pinched-right` | 12 | 通过 |
| `edge-rejected-left` | 12 | 通过 |
| `edge-rejected-right` | 12 | 通过 |
| `edge-success-left` | 12 | 通过 |
| `edge-success-right` | 12 | 通过 |
| `idle-normal` | 12 | 通过 |
| `idle-read` | 12 | 通过 |
| `idle-sleep` | 12 | 通过 |
| `pinched` | 12 | 通过 |
| `rejected` | 12 | 通过 |
| `success` | 12 | 通过 |
