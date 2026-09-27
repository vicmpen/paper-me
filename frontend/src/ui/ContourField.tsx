function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Closed contour lines around a few seeded hills; the same seed gives the same terrain. */
export function contourPaths(seed: number, width = 600, height = 200): string[] {
  const rand = mulberry32(seed + 1);
  const paths: string[] = [];
  for (let hill = 0; hill < 3; hill++) {
    const cx = rand() * width;
    const cy = rand() * height;
    const phase = rand() * Math.PI * 2;
    const levels = 5 + Math.floor(rand() * 4);
    for (let level = 1; level <= levels; level++) {
      const base = level * 14;
      const points: string[] = [];
      for (let step = 0; step < 48; step++) {
        const t = (step / 48) * Math.PI * 2;
        const r = base * (1 + 0.18 * Math.sin(3 * t + phase + level * 0.4) + 0.08 * Math.sin(5 * t - phase));
        points.push(`${(cx + r * Math.cos(t)).toFixed(1)},${(cy + r * 0.7 * Math.sin(t)).toFixed(1)}`);
      }
      paths.push(`M${points.join("L")}Z`);
    }
  }
  return paths;
}

/** Decorative contour texture for the masthead; never behind body text. */
export function ContourField({ seed, className }: { seed: number; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 600 200" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      {contourPaths(seed).map((d, i) => <path key={i} d={d} />)}
    </svg>
  );
}
