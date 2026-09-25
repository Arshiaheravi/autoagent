# Skill: Algorithmic Art (p5.js)

**When to use**: Creating generative/interactive visual artifacts — pattern visualizations,
animated charts, procedural backgrounds, data art.

## Two-phase workflow

### Phase 1 — Philosophy (write a manifesto first)

Before coding, write a 4-6 paragraph computational aesthetic philosophy:
- What mathematical/algorithmic system drives the work?
- What emergent behavior is being expressed?
- What does seeded variation reveal about the system?

### Phase 2 — Code (p5.js HTML artifact)

Self-contained single HTML file using p5.js via CDN:

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js"></script>
</head>
<body>
<script>
let seed = 42;

function setup() {
  createCanvas(800, 600);
  randomSeed(seed);
  noLoop();
}

function draw() {
  background(10, 10, 15);
  // 90% algorithmic generation, 10% parameter tweaking
  for (let i = 0; i < 200; i++) {
    let x = random(width);
    let y = random(height);
    let sz = random(2, 20);
    fill(0, 200, 150, 180);
    ellipse(x, y, sz);
  }
}
</script>
</body>
</html>
```

## Required elements

- **Seeded randomness**: `randomSeed(seed)` for reproducibility
- **Real-time parameters**: sliders for quantities, scales, probabilities
- **Seed navigation**: previous/next/random seed buttons
- **Single file**: all JS embedded, no external assets

## Design principle

90% algorithmic generation, 10% parameter adjustment.
Beauty must emerge from the system — not from manually placing elements.
Each seed reveals a different facet of the same underlying algorithm.

## Project usage
- Animated concept explainers (a process or pattern forming step by step)
- Data-strength visualizer
- Mood/atmosphere art (a metric expressed as generative noise)
