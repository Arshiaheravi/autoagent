# Skill: Slack GIF Creator

**When to use**: Creating animated GIFs for Slack — emoji reactions, announcement GIFs,
alert animations, celebration GIFs for milestones.

## Specs

| Type | Size | FPS | Duration |
|------|------|-----|----------|
| Emoji GIF | 128×128px | 10-15 | < 3 sec |
| Message GIF | 480×480px | 15-30 | < 5 sec |

Keep color palette to 48-128 colors — fewer = smaller file size.

## Dependencies

```bash
pip install pillow imageio numpy
```

## Basic animation loop

```python
import imageio
from PIL import Image, ImageDraw
import numpy as np

frames = []

for frame_num in range(30):  # 30 frames = 1 sec at 30fps
    img = Image.new('RGB', (128, 128), color=(10, 10, 15))
    draw = ImageDraw.Draw(img)

    # Animate — e.g. pulsing circle
    t = frame_num / 30
    radius = int(20 + 10 * np.sin(t * 2 * np.pi))
    draw.ellipse([64-radius, 64-radius, 64+radius, 64+radius], fill=(0, 200, 150))

    frames.append(np.array(img))

imageio.mimsave('output.gif', frames, fps=30, loop=0)
```

## Animation techniques

- **Pulse**: `sin(t * 2π)` for size/opacity oscillation
- **Bounce**: `abs(sin(t * π))` for bouncing motion
- **Shake**: random offset ±N pixels, decaying over time
- **Fade**: linear interpolation of alpha channel
- **Zoom**: scale transform from center outward

## Common GIF ideas

- Status change → card flips in with a glow
- Milestone GIF → counter animating up to the number
- Alert → bell ringing animation
- Event detected → arrow / burst launching

## Optimization

- Use `optimize=True` in imageio if available
- Reduce frame count (15fps often looks fine)
- Limit palette: `img = img.quantize(colors=64)`
