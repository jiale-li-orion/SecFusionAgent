/** Procedural studio lighting and category sculptures; no product or runtime state. */
export const artifactVertex = `attribute vec2 position;
void main() { gl_Position = vec4(position, 0., 1.); }`

export const artifactFragment = `precision highp float;
uniform vec2 resolution;
uniform vec2 pointer;
uniform float time;
uniform float model;
mat2 rotation(float a) { return mat2(cos(a), -sin(a), sin(a), cos(a)); }
float roundedBox(vec3 p, vec3 b, float radius) {
  vec3 q = abs(p) - b;
  return length(max(q, 0.)) + min(max(q.x, max(q.y, q.z)), 0.) - radius;
}
float torus(vec3 p, float radius, float tube) {
  return length(vec2(length(p.xz) - radius, p.y)) - tube;
}
vec2 closer(vec2 a, vec2 b) { return a.x < b.x ? a : b; }
vec3 pose(vec3 p) {
  p.xz = rotation(.46 + sin(time * .13) * .10 + pointer.x * .16) * p.xz;
  p.yz = rotation(.32 + pointer.y * .12) * p.yz;
  return p;
}
// Surface IDs: platinum, ceramic, optical glass, copper.
vec2 scene(vec3 position, bool glass) {
  vec3 p = pose(position);
  vec2 result = vec2(20., 0.);
  if (model < .5) {
    result = vec2(length(p) - .59, 1.);
    vec3 q = p; q.xy = rotation(.58) * q.xy;
    result = closer(result, vec2(torus(q, .92, .042), 0.));
    q = p; q.yz = rotation(1.15) * q.yz; q.xy = rotation(-.4) * q.xy;
    result = closer(result, vec2(torus(q, .76, .026), 3.));
    result = closer(result, vec2(length(p - vec3(.82, .35, 0.)) - .07, 0.));
    return result;
  }
  if (model < 1.5) {
    p.yz = rotation(1.26) * p.yz;
    result = vec2(torus(p, .69, .105), 0.);
    result = closer(result, vec2(torus(p - vec3(0., .12, 0.), .64, .028), 3.));
    result = closer(result, vec2(torus(p + vec3(0., .11, 0.), .59, .035), 1.));
    if (glass) result = closer(result, vec2((length(p * vec3(1., 3.8, 1.)) - .42) / 3.8, 2.));
    for (int i = 0; i < 8; i++) {
      vec3 q = p; q.xz = rotation(float(i) * .785398) * q.xz;
      q -= vec3(.25, -.03, .33); q.xz = rotation(.65) * q.xz;
      result = closer(result, vec2(roundedBox(q, vec3(.08, .025, .21), .015), 1.));
    }
    return result;
  }
  if (model < 2.5) {
    for (int i = 0; i < 4; i++) {
      vec3 q = p; q.y -= float(i) * .24 - .36;
      q.xz = rotation(float(i) * .11 - .17) * q.xz;
      float outer = roundedBox(q, vec3(.65, .018, .49), .032);
      float inner = roundedBox(q, vec3(.59, .07, .43), .03);
      result = closer(result, vec2(max(outer, -inner), i == 3 ? 3. : 0.));
      if (glass) result = closer(result, vec2(roundedBox(q, vec3(.57, .015, .41), .018), 2.));
    }
    result = closer(result, vec2(roundedBox(p, vec3(.10, .48, .10), .025), 0.));
    return closer(result, vec2(length(p - vec3(0., .53, 0.)) - .105, 3.));
  }
  if (model < 3.5) {
    for (int i = 0; i < 3; i++) {
      vec3 q = p; q.x -= float(i) * .45 - .45; q.y -= float(i) * .12 - .12;
      q.xy = rotation(float(i) * .20 - .20) * q.xy;
      float outer = roundedBox(q, vec3(.28, .56, .09), .055);
      float inner = roundedBox(q, vec3(.17, .44, .20), .06);
      result = closer(result, vec2(max(outer, -inner), i == 1 ? 3. : 0.));
    }
    return result;
  }
  if (model < 4.5) {
    float diamond = (abs(p.x) + abs(p.y) + abs(p.z) - 1.28) * .57735;
    float bevel = max(max(abs(p.x), abs(p.z)) - .73, abs(p.y) - .9);
    if (glass) result = vec2(max(diamond, bevel), 2.);
    vec3 q = p; q.xy = rotation(.3) * q.xy;
    return closer(result, vec2(torus(q, .8, .02), 3.));
  }
  vec3 q = p; q.xy = rotation(-.2) * q.xy;
  result = vec2(roundedBox(q - vec3(-.29, 0., 0.), vec3(.21, .72, .34), .045), 1.);
  result = closer(result, vec2(roundedBox(q - vec3(.30, .12, -.04), vec3(.21, .62, .34), .045), 0.));
  return closer(result, vec2(roundedBox(q - vec3(.01, -.02, 0.), vec3(.015, .65, .27), .012), 3.));
}
vec2 scene(vec3 p) { return scene(p, true); }
vec3 normalAt(vec3 p) {
  vec2 e = vec2(.0018, 0.);
  return normalize(vec3(scene(p + e.xyy).x - scene(p - e.xyy).x,
    scene(p + e.yxy).x - scene(p - e.yxy).x,
    scene(p + e.yyx).x - scene(p - e.yyx).x));
}
vec3 environment(vec3 r) {
  vec3 color = mix(vec3(.025, .038, .035), vec3(.32, .38, .36), smoothstep(-.5, .8, r.y));
  float panel = smoothstep(-.65, -.55, r.x) * (1. - smoothstep(.15, .23, r.x));
  panel *= smoothstep(.25, .32, r.y) * (1. - smoothstep(.80, .86, r.y));
  float ribbon = exp(-pow((r.x + .62) / .065, 2.)) * smoothstep(-.4, .7, r.y);
  float rim = pow(max(dot(r, normalize(vec3(2., .4, -2.))), 0.), 18.);
  color += vec3(3.8, 3.85, 3.55) * panel;
  color += vec3(2.5, 2.8, 2.75) * ribbon;
  return color + vec3(1.8, .86, .40) * rim;
}
float ambientOcclusion(vec3 p, vec3 n) {
  float value = 0.;
  for (int i = 1; i <= 3; i++) {
    float distance = float(i) * .08;
    value += (distance - scene(p + n * distance).x) / pow(2., float(i));
  }
  return clamp(1. - value * 2.6, .30, 1.);
}
void main() {
  vec2 uv = (gl_FragCoord.xy - .5 * resolution) / resolution.y;
  vec3 origin = vec3(0., .14, 4.4);
  vec3 ray = normalize(vec3(uv, -2.0 * min(1., resolution.x / resolution.y)));
  float projection = dot(origin, ray);
  float discriminant = projection * projection - dot(origin, origin) + 1.70;
  float travel = discriminant > 0. ? max(0., -projection - sqrt(discriminant)) : 9.;
  vec3 p = origin; vec2 surface = vec2(20., 0.);
  for (int i = 0; i < 88; i++) {
    if (travel > 7.) break;
    p = origin + ray * travel; surface = scene(p);
    if (surface.x < .0015) break;
    travel += surface.x * .78;
  }
  if (travel > 7. || surface.x >= .004) {
    float shadow = exp(-pow(uv.x * 3.6, 2.) - pow((uv.y + .34) * 19., 2.)) * .20;
    gl_FragColor = vec4(vec3(.025, .04, .03), shadow); return;
  }
  vec3 n = normalAt(p);
  float facing = max(dot(n, -ray), 0.);
  float fresnel = pow(1. - facing, 5.);
  float diffuse = max(dot(n, normalize(vec3(-2., 4., 3.))), 0.);
  vec3 reflection = environment(reflect(ray, n));
  vec3 color;
  float alpha = 1.;
  if (surface.y < .5) {
    color = vec3(.58, .67, .64) * (.06 + diffuse * .16) + reflection * vec3(.87, .92, .90);
  } else if (surface.y < 1.5) {
    color = vec3(.014, .025, .024) * (.4 + diffuse) + reflection * (.11 + fresnel * .72);
    float etch = smoothstep(.92, 1., sin(pose(p).y * 95.));
    color *= 1. - etch * .13;
  } else if (surface.y < 2.5) {
    vec3 through = normalize(mix(ray, refract(ray, n, .80), .35));
    float depth = .03;
    vec2 inner = vec2(20., 0.);
    vec3 innerPoint = p;
    for (int i = 0; i < 32; i++) {
      innerPoint = p + through * depth;
      inner = scene(innerPoint, false);
      if (inner.x < .002 || depth > 2.3) break;
      depth += max(inner.x * .8, .006);
    }
    float reflectance = .10 + fresnel * .75;
    color = vec3(.075, .16, .12) + reflection * reflectance;
    alpha = .32 + reflectance * .60;
    if (inner.x < .004 && depth < 2.3) {
      vec2 e = vec2(.002, 0.);
      vec3 innerNormal = normalize(vec3(
        scene(innerPoint + e.xyy, false).x - scene(innerPoint - e.xyy, false).x,
        scene(innerPoint + e.yxy, false).x - scene(innerPoint - e.yxy, false).x,
        scene(innerPoint + e.yyx, false).x - scene(innerPoint - e.yyx, false).x));
      vec3 transmitted = environment(reflect(through, innerNormal));
      transmitted *= inner.y > 2.5 ? vec3(.90, .58, .29) : inner.y > .5 ? vec3(.04, .065, .045) : vec3(.69, .79, .71);
      color = mix(transmitted, reflection, reflectance);
      alpha = 1.;
    }
  } else {
    color = reflection * vec3(.90, .58, .29) + vec3(.19, .09, .035) * diffuse;
  }
  color *= ambientOcclusion(p, n);
  color = color / (vec3(1.) + color);
  gl_FragColor = vec4(pow(max(color, 0.), vec3(.4545)), alpha);
}`
