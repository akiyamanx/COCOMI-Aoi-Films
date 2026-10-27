HASH = '''
float fr(float x){ return x - floor(x); }
float ss(float a, float b, float x){ float tt = clamp((x-a)/(b-a), 0.0, 1.0); return tt*tt*(3.0-2.0*tt); }
float h21(float x, float y){
  float fx = fr(x*0.1031), fy = fr(y*0.1031);
  float d = fx*(fy+33.33) + fy*(fx+33.33) + fx*(fx+33.33);
  return fr((fx + d + fy + d)*(fx + d));
}
'''
FOG = HASH + '''
shader fog(point Pin = point(0,0,0), float t = 0.0, float swirl = 0.0, float ring_r = 0.0, float ring_amt = 0.0,
           float dust = 0.0, float dust_r = 20.0, float base = 0.0065, float scale_h = 17.0, float haze = 0.00035,
           float clear_r = 0.0,
           output float Density = 0.0)
{
  float x = Pin[0], y = Pin[1], z = Pin[2];
  float zz = max(z, 0.0);
  float r = sqrt(x*x + y*y);
  float ang = swirl * exp(-r*r/(2.0*70.0*70.0)) * exp(-zz/110.0);
  float c = cos(ang), s = sin(ang);
  point q = point(c*x - s*y, s*x + c*y, z) + vector(-4.0, 1.5, 0.0) * t;
  float n1 = noise("snoise", point(q[0]/60.0, q[1]/60.0, q[2]/22.0));
  float n2 = noise("snoise", point(q[0]/19.0 + 7.0, q[1]/19.0, q[2]/9.0 + t*0.15));
  float n3 = noise("snoise", point(q[0]/7.0, q[1]/7.0 - 3.0, q[2]/4.0 - t*0.2));
  float cov = ss(-0.35, 0.65, 0.62*n1 + 0.30*n2 + 0.12*n3 + 0.05);
  float hf = exp(-zz/scale_h);
  float d = base * hf * (0.18 + 1.25*cov);
  // shock ring pushes mist outward, thinning behind it
  float behind = ss(ring_r, ring_r*0.35 + 1.0, r);
  d *= 1.0 - 0.75*ring_amt*behind;
  float rg = exp(-pow((r - ring_r)/26.0, 2.0));
  d += ring_amt * 0.055 * rg * exp(-zz/38.0) * (0.35 + 1.2*cov);
  // dust plume
  float dd = exp(-(r*r)/(dust_r*dust_r) - (zz*zz)/(dust_r*dust_r*2.0));
  d += dust * dd * (0.4 + 1.0*ss(-0.4,0.7,0.6*n2+0.4*n3));
  d += haze * exp(-zz/170.0);
  Density = d;
}
'''
CLOUD = '''
float ss(float a, float b, float x){ float tt = clamp((x-a)/(b-a), 0.0, 1.0); return tt*tt*(3.0-2.0*tt); }
shader cloud(point Pin = point(0,0,0), float t = 0.0, float z0 = 95.0, float z1 = 165.0, float cover = 0.66, float dens = 0.055,
             output float Density = 0.0)
{
  float x = Pin[0] - 6.0*t, y = Pin[1] + 2.0*t, z = Pin[2];
  float wx = noise("snoise", point(x/300.0, y/300.0, 3.0))*70.0;
  float wy = noise("snoise", point(x/300.0 + 9.0, y/300.0, 5.0))*70.0;
  float a = noise("snoise", point((x+wx)/240.0, (y+wy)/240.0, z/90.0));
  float b = noise("snoise", point((x+wx)/95.0, (y+wy)/95.0, z/38.0 + 3.0));
  float cc = noise("snoise", point((x+wx)/38.0, (y+wy)/38.0, z/16.0 + 7.0));
  float vh = clamp((z - z0)/(z1 - z0), 0.0, 1.0);
  float prof = ss(0.0, 0.3, vh) * ss(1.0, 0.45, vh);
  float f = 0.58*a + 0.30*b + 0.14*cc;
  float m = ss(0.02, 0.42, f + (cover - 0.5)*1.2 - 0.05 + (prof-0.5)*0.15);
  Density = dens * m * prof;
}
'''
GROUND = HASH + '''
shader ground(point Pin = point(0,0,0), float t = 0.0, float reveal = 0.0, float width = 0.3, float glow = 1.0, float cell = 9.0,
              output float Emit = 0.0, output float Mask = 0.0)
{
  float px = Pin[0], py = Pin[1];
  float qx = px + 1.7*sin(py*0.31 + 1.1) + 0.8*sin(py*0.83 + px*0.17);
  float qy = py + 1.7*sin(px*0.29 + 0.3) + 0.8*sin(px*0.71 - py*0.2);
  float uu = qx/cell, vv = qy/cell;
  float iu = floor(uu), iv = floor(vv);
  float d1 = 1e9, d2 = 1e9;
  for (int a = -1; a <= 1; a++) for (int b = -1; b <= 1; b++) {
    float cu = iu + a, cv = iv + b;
    float fx = cu + 0.5 + 0.8*(h21(cu, cv) - 0.5);
    float fy = cv + 0.5 + 0.8*(h21(cu + 57.1, cv - 23.7) - 0.5);
    float d = sqrt((uu-fx)*(uu-fx) + (vv-fy)*(vv-fy))*cell;
    if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
  }
  float de = 0.5*(d2 - d1);
  float r = sqrt(px*px + py*py);
  float rv = ss(reveal, reveal*0.55, r);
  float jag = 0.6 + 0.4*noise("snoise", point(px/1.7, py/1.7, 0.0));
  float m = ss(width*jag, 0.0, de) * rv;
  Mask = m;
  Emit = m * glow * (0.6 + 0.4*noise("snoise", point(px/3.0, py/3.0, t*2.0)));
}
'''
