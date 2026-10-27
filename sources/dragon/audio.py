import numpy as np, wave
from scipy import signal
SR=48000; D=7.6; N=int(SR*D); t=np.arange(N)/SR
rng=np.random.RandomState(3)
def bp(x,lo,hi,o=2):
    sos=signal.butter(o,[lo,hi],'bandpass',fs=SR,output='sos'); return signal.sosfilt(sos,x)
def lp(x,f,o=2): return signal.sosfilt(signal.butter(o,f,'low',fs=SR,output='sos'),x)
def hp(x,f,o=2): return signal.sosfilt(signal.butter(o,f,'high',fs=SR,output='sos'),x)
def env(pts):  # piecewise linear (time,val)
    a=np.array(pts); return np.interp(t,a[:,0],a[:,1])
def ss(a,b,x): u=np.clip((x-a)/(b-a),0,1); return u*u*(3-2*u)
TC=1.9
# wind bed (stereo-decorrelated)
def wind(seed,lo,hi):
    r=np.random.RandomState(seed); n=r.randn(N)
    w=bp(n,lo,hi,2)
    mod=1+0.5*lp(r.randn(N),0.6,1)*8
    return w*np.clip(mod,0.2,2)
wL=wind(1,150,900); wR=wind(2,150,900)
wenv=env([(0,0.25),(1.5,0.4),(2.0,0.9),(4,0.7),(5.5,1.0),(7.6,0.55)])
# rumble: sub sines with beating + filtered noise
rum_env=env([(0,0.15),(0.3,0.35),(1.7,0.9),(1.88,1.0),(2.0,0.5),(3.0,0.55),(5,0.4),(7.6,0.25)])
rum=sum(np.sin(2*np.pi*f*t+rng.rand()*6) for f in (28,33.5,41,47))/4
rum+=0.7*lp(rng.randn(N),70,3)
rum*=rum_env*(1+0.25*np.sin(2*np.pi*6.5*t))
# crack impact
imp=np.zeros(N); i0=int(TC*SR)
n=rng.randn(N)
crack=hp(n,800)*np.exp(-np.maximum(t-TC,0)/0.05)*(t>=TC)
thump=np.sin(2*np.pi*(55*np.exp(-np.maximum(t-TC,0)/0.35)+22)*np.maximum(t-TC,0))*np.exp(-np.maximum(t-TC,0)/0.7)*(t>=TC)
rocks=bp(n,90,1500)*np.exp(-np.maximum(t-TC,0)/1.2)*(t>=TC)*(0.4+0.6*(rng.rand(N)>0.992)*3)
rocks=lp(rocks,2500)
pre=bp(rng.randn(N),200,1800)*ss(0.9,1.88,t)*(1-ss(1.88,1.9,t))*(rng.rand(N)>0.9985)*6  # small cracks pings
pre=lp(pre,3000)
# roar: pitch contour, harsh harmonic + formants + growl AM
rt=np.clip((t-2.25)/(4.3-2.25),0,1)
f0=60+70*np.sin(np.pi*np.clip(rt*1.15,0,1))**1.2 - 18*rt + 6*np.sin(2*np.pi*3.1*t)
ph=2*np.pi*np.cumsum(f0)/SR
saw=sum(np.sin(k*ph)/k**0.8 for k in range(1,28))
roar_n=saw*(0.7+0.3*np.sign(np.sin(2*np.pi*27*t)+0.3))+0.5*bp(rng.randn(N),200,2500)
form=bp(roar_n,350,900,2)+0.8*bp(roar_n,900,1700,2)+0.5*bp(roar_n,60,300,2)
renv=ss(2.25,3.1,t)*(1-ss(3.7,4.5,t))*(1+0.35*np.sin(2*np.pi*4.2*t))
roar=form*renv
roar=np.tanh(2.2*roar/ (np.std(roar)+1e-9))*renv
# whoosh as it rises
who=bp(rng.randn(N),300,2500,2)*env([(2.5,0),(4.5,0.4),(6.2,1.0),(7.6,0.6)])
# mix
def mono_mix():
    return 0.55*rum+0.9*(thump+0.5*crack+0.5*rocks+0.4*pre)+0.65*roar
base=mono_mix()
L=base+0.22*wL*wenv/np.std(wL)+0.12*who*1.0
R=base+0.22*wR*wenv/np.std(wR)+0.12*np.roll(who,200)
# haas/stereo width for roar
R=R+0.15*np.roll(roar,int(0.012*SR)); L=L+0.15*np.roll(roar,int(0.019*SR))
# reverb
ir=rng.randn(int(1.8*SR))*np.exp(-np.arange(int(1.8*SR))/SR/0.55); ir=lp(ir,4500)
def rev(x): return signal.fftconvolve(x,ir)[:N]*0.012
L=L+rev(L)*8; R=R+rev(R)*8
st=np.stack([L,R],1)
fade=np.minimum(1,t/0.25)*np.minimum(1,(D-t)/0.9)
st*=fade[:,None]
st=hp(st.T,22).T
st/=np.max(np.abs(st))*1.12
w=wave.open('audio.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((st*32767).astype('<i2').tobytes()); w.close()
print('ok', np.sqrt((st**2).mean()))
