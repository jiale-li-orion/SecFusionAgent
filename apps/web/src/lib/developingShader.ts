/** Pigment deposits on a fixed grain surface. No waves, bloom, or simulated task progress. */
export const developingVertex = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`

export const developingFragment = `
precision highp float;
uniform vec2 resolution;
uniform float time;
uniform float arrival;
uniform float focus;
uniform float direction;
uniform float impulse;
uniform float variant;
uniform vec4 depositLeft;
uniform vec4 depositMiddle;
uniform vec4 depositRight;
uniform vec4 motion;
uniform vec2 origin;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1., 0.)), f.x),
             mix(hash(i + vec2(0., 1.)), hash(i + 1.), f.x), f.y);
}
float grainField(vec2 p) {
  return noise(p) * .57 + noise(p * 2.07 + 8.3) * .28 + noise(p * 4.17 + 12.8) * .15;
}
float stain(vec2 p, vec2 center, vec2 radius) {
  vec2 d = (p - center) / radius;
  return exp(-dot(d, d) * 1.6);
}
void main() {
  vec2 uv = gl_FragCoord.xy / resolution;
  float aspect = resolution.x / resolution.y;
  vec2 p = (uv - .5) * vec2(aspect, 1.0);
  float drift = time * .045;
  vec2 offset = vec2(grainField(p * 3.3 + vec2(drift * motion.x, variant)),
                     grainField(p * 3.1 + vec2(variant + 17., drift * motion.y))) - .5;
  vec2 q = p + offset * (.37 - focus * .08);
  float spread = 1.0 + impulse * .24 - focus * .16;
  float shift = direction * .22;
  // Slow, non-periodic migration: distinct deposits meet and separate without waves.
  vec2 migration = (vec2(noise(vec2(drift * 1.8, variant)),
                         noise(vec2(variant + 5., drift * 1.4))) - .5) * motion.z;
  float gathering = 1.0 - focus * motion.w;
  vec2 displacement = vec2(shift, 0.);
  float left = stain(q, depositLeft.xy * gathering + displacement + migration, depositLeft.zw * spread);
  float middle = stain(q, depositMiddle.xy * gathering + displacement - migration.yx, depositMiddle.zw * spread);
  float right = stain(q, depositRight.xy * gathering + displacement - migration, depositRight.zw * spread);
  float body = max(max(left, middle * .86), right * .82);
  float mottling = grainField(p * 12. + offset * 2. + variant);
  float deposit = smoothstep(.08, .67, body + (mottling - .5) * .30);
  float edge = smoothstep(.01, .28, body) * (1.0 - deposit);
  float grit = hash(floor(gl_FragCoord.xy / 1.15));
  float fleck = hash(floor(gl_FragCoord.xy / 2.1) + 92.);
  // A local exposure develops outward once; interaction causes a separate spreading deposit.
  float distanceFromSeed = length((p - origin - vec2(shift, 0.)) * vec2(.72, 1.));
  float front = 1.0 - smoothstep(arrival * 1.45 - .18, arrival * 1.45 + .18,
                               distanceFromSeed + (mottling - .5) * .25);
  float fiber = smoothstep(.10, .68, grit + deposit * .30);
  float opacity = (deposit * (.30 + fiber * .57) + edge * step(.80, fleck) * .28) * front;
  // Restrained overprinting: charcoal, mineral green, oxidised ochre.
  vec3 ink = mix(vec3(.22, .29, .27), vec3(.49, .55, .44), smoothstep(.20, .95, left));
  ink = mix(ink, vec3(.64, .43, .27), smoothstep(.18, .85, right) * .76);
  ink = mix(ink, vec3(.75, .72, .60), (1.0 - deposit) * .52);
  opacity *= smoothstep(0., .16, uv.y) * (1.0 - smoothstep(.86, 1., uv.y));
  opacity *= smoothstep(0., .10, uv.x) * (1.0 - smoothstep(.90, 1., uv.x));
  gl_FragColor = vec4(ink, opacity * .78);
}
`
