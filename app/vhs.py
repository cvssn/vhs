import math
import random
import sys
from enum import Enum
from pathlib import Path
from typing import List, Union

import numpy
from scipy.signal import lfilter, lfiltic
from scipy.ndimage.interpolation import shift

import cv2


M_PI = math.pi

Int_MIN_VALUE = -2147483648
Int_MAX_VALUE = 2147483647

ring_pattern_real_path = 'app/ringPattern.npy'

if getattr(sys, 'frozen', False):
    ring_pattern_real_path = f'{sys._MEIPASS}/app/ringPattern.npy'

ring_pattern_path = Path(ring_pattern_real_path)
RingPattern = numpy.load(str(ring_pattern_path.resolve()))

def ringing(img2d, alpha=0.5, noiseSize=0, noiseValue=2, clip=True, seed=None):
    dft = cv2.dft(numpy.float32(img2d), flags=cv2.DFT_COMPLEX_OUTPUT)
    dft_shift = numpy.fft.fftshift(dft)

    rows, cols = img2d.shape
    crow, ccol = int(rows / 2), int(cols / 2)
    
    mask = numpy.zeros((rows, cols, 2), numpy.uint8)
    maskH = min(crow, int(1 + alpha * crow))
    mask[:, ccol - maskH:ccol + maskH] = 1

    if noiseSize > 0:
        noise = numpy.ones((mask.shape[0], mask.shape[1], mask.shape[2])) * noiseValue - noiseValue / 2.
        
        start = int(ccol - ((1 - noiseSize) * ccol))
        stop = int(ccol + ((1 - noiseSize) * ccol))
        
        noise[:, start:stop, :] = 0
        rnd = numpy.random.RandomState(seed)
        
        mask = mask.astype(numpy.float) + rnd.rand(mask.shape[0], mask.shape[1], mask.shape[2]) * noise - noise / 2.

    img_back = cv2.idft(numpy.fft.ifftshift(dft_shift * mask), flags=cv2.DFT_SCALE)
    
    if clip:
        _min, _max = img2d.min(), img2d.max()
        
        return numpy.clip(img_back[:, :, 0], _min, _max)
    else:
        return img_back[:, :, 0]

def ringing2(img2d, power=4, shift=0, clip=True):
    dft = cv2.dft(numpy.float32(img2d), flags=cv2.DFT_COMPLEX_OUTPUT)
    dft_shift = numpy.fft.fftshift(dft)

    rows, cols = img2d.shape

    scalecols = int(cols * (1 + shift))
    mask = cv2.resize(RingPattern[numpy.newaxis, :], (scalecols, 1), interpolation=cv2.INTER_LINEAR)[0]

    mask = mask[(scalecols // 2) - (cols // 2):(scalecols // 2) + (cols // 2)]
    mask = mask ** power
    
    img_back = cv2.idft(numpy.fft.ifftshift(dft_shift * mask[None, :, None]), flags=cv2.DFT_SCALE)
    
    if clip:
        _min, _max = img2d.min(), img2d.max()
        
        return numpy.clip(img_back[:, :, 0], _min, _max)
    else:
        return img_back[:, :, 0]

def fmod(x: float, y: float) -> float:
    return x % y

class NumpyRandom:
    def __init__(self, seed=None):
        self.rnd = numpy.random.RandomState(seed)

    def nextInt(self, _from: int = Int_MIN_VALUE, until: int = Int_MAX_VALUE) -> int:
        return self.rnd.randint(_from, until)

    def nextIntArray(self, size: int, _from: int = Int_MIN_VALUE, until: int = Int_MAX_VALUE) -> numpy.ndarray:
        return self.rnd.randint(_from, until, size, dtype=numpy.int32)

class XorWowRandom:
    def __init__(self, seed1: int, seed2: int):
        self.x: int = numpy.int32(seed1)
        self.y: int = numpy.int32(seed2)
        
        self.z: int = numpy.int32(0)
        self.w: int = numpy.int32(0)
        
        self.v: int = -numpy.int32(seed1) - 1
        
        self.addend: int = numpy.int32((numpy.int32(seed1) << 10) ^ (numpy.uint32(seed2) >> 4))
        
        [self._nextInt() for _ in range(0, 64)]

    def _nextInt(self) -> int:
        t = self.x
        t = numpy.int32(t ^ (numpy.uint32(t) >> 2))
        
        self.x = numpy.int32(self.y)
        self.y = numpy.int32(self.z)
        self.z = numpy.int32(self.w)
        
        v0 = numpy.int32(self.v)
        self.w = numpy.int32(v0)
        
        t = (t ^ (t << 1)) ^ v0 ^ (v0 << 4)
        
        self.v = numpy.int32(t)
        self.addend += 362437
        
        return t + numpy.int32(self.addend)

    def nextInt(self, _from: int = Int_MIN_VALUE, until: int = Int_MAX_VALUE) -> numpy.int32:
        n = until - _from
        
        if n > 0 or n == Int_MIN_VALUE:
            if (n & -n) == n:
                assert False, "não implementado"
            else:
                v: int = 0
                
                while True:
                    bits = numpy.uint32(self._nextInt()) >> 1
                    
                    v = bits % n
                    
                    if bits - v + (n - 1) >= 0:
                        break
                    
                return numpy.int32(_from + v)
        else:
            r = range(_from, until)
            
            while True:
                rnd = self._nextInt()
                
                if rnd in r:
                    return numpy.int32(rnd)

    def nextIntArray(self, size: int, _from: int = Int_MIN_VALUE, until: int = Int_MAX_VALUE) -> numpy.ndarray:
        zeros = numpy.zeros(size, dtype=numpy.int32)
        
        for i in range(0, size):
            zeros[i] = self.nextInt(_from=_from, until=until)
            
        return zeros

# interleaved uint8 HWC BGR to -> planar int32 CHW YIQ
def bgr2yiq(bgrimg: numpy.ndarray) -> numpy.ndarray:
    planar = numpy.transpose(bgrimg, (2, 0, 1))
    b, g, r = planar
    dY = 0.30 * r + 0.59 * g + 0.11 * b

    Y = (dY * 256).astype(numpy.int32)
    I = (256 * (-0.27 * (b - dY) + 0.74 * (r - dY))).astype(numpy.int32)
    Q = (256 * (0.41 * (b - dY) + 0.48 * (r - dY))).astype(numpy.int32)
    return numpy.stack([Y, I, Q], axis=0).astype(numpy.int32)

# um campo de planar int32 chw yiq -> um campo de uint8 hwc bgr intercalado para
def yiq2bgr(yiq: numpy.ndarray, dst_bgr: numpy.ndarray = None, field: int = 0) -> numpy.ndarray:
    c, h, w = yiq.shape
    dst_bgr = dst_bgr if dst_bgr is not None else numpy.zeros((h, w, c))
    
    Y, I, Q = yiq
    
    if field == 0:
        Y, I, Q = Y[::2], I[::2], Q[::2]
    else:
        Y, I, Q = Y[1::2], I[1::2], Q[1::2]

    r = ((1.000 * Y + 0.956 * I + 0.621 * Q) / 256).astype(numpy.int32)
    g = ((1.000 * Y + -0.272 * I + -0.647 * Q) / 256).astype(numpy.int32)
    b = ((1.000 * Y + -1.106 * I + 1.703 * Q) / 256).astype(numpy.int32)
    
    r = numpy.clip(r, 0, 255)
    g = numpy.clip(g, 0, 255)
    b = numpy.clip(b, 0, 255)
    
    planarBGR = numpy.stack([b, g, r])
    interleavedBGR = numpy.transpose(planarBGR, (1, 2, 0))
    
    if field == 0:
        dst_bgr[::2] = interleavedBGR
    else:
        dst_bgr[1::2] = interleavedBGR
        
    return dst_bgr

class LowpassFilter:
    def __init__(self, rate: float, hz: float, value: float = 0.0):
        self.timeInterval: float = 1.0 / rate
        self.tau: float = 1 / (hz * 2.0 * M_PI)
        self.alpha: float = self.timeInterval / (self.tau + self.timeInterval)
        self.prev: float = value

    def lowpass(self, sample: float) -> float:
        stage1 = sample * self.alpha
        stage2 = self.prev - self.prev * self.alpha
        
        self.prev = stage1 + stage2
        
        return self.prev

    def highpass(self, sample: float) -> float:
        stage1 = sample * self.alpha
        stage2 = self.prev - self.prev * self.alpha
        
        self.prev = stage1 + stage2
        
        return sample - self.prev

    def lowpass_array(self, samples: numpy.ndarray) -> numpy.ndarray:
        if self.prev == 0.0:
            return lfilter([self.alpha], [1, -(1.0 - self.alpha)], samples)
        else:
            ic = scipy.signal.lfiltic([self.alpha], [1, -(1.0 - self.alpha)], [self.prev])
            return lfilter([self.alpha], [1, -(1.0 - self.alpha)], samples, zi=ic)[0]

    def highpass_array(self, samples: numpy.ndarray) -> numpy.ndarray:
        f = self.lowpass_array(samples)
        return samples - f


def cut_black_line_border(image: numpy.ndarray, bordersize: int = None) -> None:
    h, w, _ = image.shape
    
    if bordersize is None:
        line_width = int(w * 0.017) # 1.7%
    else:
        line_width = bordersize # todo: valor para configurações

    image[:, -1*line_width:] = 0 # 0 configurado para preto


def composite_lowpass(yiq: numpy.ndarray, field: int, fieldno: int):
    _, height, width = yiq.shape
    fY, fI, fQ = yiq
    
    for p in range(1, 3):
        cutoff = 1300000.0 if p == 1 else 600000.0
        delay = 2 if (p == 1) else 4
        
        P = fI if (p == 1) else fQ
        P = P[field::2]
        
        lp = lowpassFilters(cutoff, reset=0.0)
        
        for i, f in enumerate(P):
            f = lp[0].lowpass_array(f)
            f = lp[1].lowpass_array(f)
            f = lp[2].lowpass_array(f)
            
            P[i, 0:width - delay] = f.astype(numpy.int32)[delay:]

# filtragem mais leve, provavelmente o que seu crt antigo faz para reduzir um pouco as franjas de cores
def composite_lowpass_tv(yiq: numpy.ndarray, field: int, fieldno: int):
    _, height, width = yiq.shape
    fY, fI, fQ = yiq
    
    for p in range(1, 3):
        delay = 1
        
        P = fI if (p == 1) else fQ
        P = P[field::2]
        
        lp = lowpassFilters(2600000.0, reset=0.0)
        
        for i, f in enumerate(P):
            f = lp[0].lowpass_array(f)
            f = lp[1].lowpass_array(f)
            f = lp[2].lowpass_array(f)
            
            P[i, 0:width - delay] = f.astype(numpy.int32)[delay:]

def composite_preemphasis(yiq: numpy.ndarray, field: int, composite_preemphasis: float, composite_preemphasis_cut: float):
    fY, fI, fQ = yiq
    
    pre = LowpassFilter(Vhs.VHS_RATE, composite_preemphasis_cut, 16.0)
    
    fields = fY[field::2]
    
    for i, samples in enumerate(fields):
        filtered = samples + pre.highpass_array(samples) * composite_preemphasis
        fields[i] = filtered.astype(numpy.int32)

class VHSSpeed(Enum):
    VHS_SP = (2400000.0, 320000.0, 9)
    VHS_LP = (1900000.0, 300000.0, 12)
    VHS_EP = (1400000.0, 280000.0, 14)

    def __init__(self, luma_cut: float, chroma_cut: float, chroma_delay: int):
        self.luma_cut = luma_cut
        self.chroma_cut = chroma_cut
        self.chroma_delay = chroma_delay

class Vhs:
    VHS_RATE = 315000000.00 / 88 * 4 # 315/88 mhz rate * 4

    def __init__(self, precise=False, random=None):
        self.precise = precise
        self.random = random if random is not None else XorWowRandom(31374242, 0)
        self._composite_preemphasis_cut = 1000000.0
        
        # artefatos analógicos relacionados a qualquer coisa que afete o sinal composto bruto, ou seja, modulação catv
        self._composite_preemphasis = 0.0 # valores 0..8 parecem realistas

        self._vhs_out_sharpen = 1.5 # 1.0..5.0
        self._vhs_edge_wave = 0 # 0..10

        self._vhs_head_switching = False # ative esta opção apenas em quadros com altura de 486 pixels ou mais
        self._head_switching_speed = 0 # 0..100 este é o incremento de /1000 para _vhs_head_switching_point 0 é estático
        self._vhs_head_switching_point = 1.0 - (4.5 + 0.01) / 262.5 # 4 linhas de scan vhs a partir do vsync
        self._vhs_head_switching_phase = (1.0 - 0.01) / 262.5 # 4 linhas de scan vhs a partir do vsync
        self._vhs_head_switching_phase_noise = 1.0 / 500 / 262.5 # 1/500 de uma linha de varredura

        self._color_bleed_before = True # o sangramento de cor vem antes de outras degradações se for Verdadeiro ou depois de outra forma
        self._color_bleed_horiz = 0 # sangramento de cor horizontal 0 = sem sangramento de cor, 1..10 valores sensatos
        self._color_bleed_vert = 0 # sangramento de cor vertical 0 = sem sangramento de cor, 1..10 valores sensatos
        self._ringing = 1.0 # 1 = sem toque, 0.3..0.99 = valores sensatos
        self._enable_ringing2 = False
        self._ringing_power = 2
        self._ringing_shift = 0
        self._freq_noise_size = 0 # (0-1) o valor ideal é 0,5..0,99 se noisesize=0 - sem ruído
        self._freq_noise_amplitude = 2 # amplitude de ruído (0-5) os valores ideais são 0,5-2
        self._composite_in_chroma_lowpass = True # aplique chroma lowpass antes da codificação composta
        self._composite_out_chroma_lowpass = True
        self._composite_out_chroma_lowpass_lite = True

        self._video_chroma_noise = 0 # 0..16384
        self._video_chroma_phase_noise = 0 # 0..50
        self._video_chroma_loss = 0 # 0..100_000
        self._video_noise = 2 # 0..4200
        self._subcarrier_amplitude = 50
        self._subcarrier_amplitude_back = 50
        self._emulating_vhs = False
        self._nocolor_subcarrier = False # se definido, emula a subportadora, mas não decodifica de volta para a cor (depuração)
        self._vhs_chroma_vert_blend = True # se definido, e vhs, misture verticalmente as linhas de varredura de croma (como faz o formato VHS)
        self._vhs_svideo_out = False # se não estiver definido, e vhs, o vídeo será recombinado como se fosse composto em um videocassete

        self._output_vhs = True # emulação de subportadora de cores vhs
        self._video_scanline_phase_shift = 180
        self._video_scanline_phase_shift_offset = 0 # 0..4
        self._output_vhs_tape_speed = VHSSpeed.VHS_SP

        self._black_line_cut = False # adicionada falha na linha preta

    def rand(self) -> numpy.int32:
        return self.random.nextInt(_from=0)

    def rand_array(self, size: int) -> numpy.ndarray:
        return self.random.nextIntArray(size, 0, Int_MAX_VALUE)

    def video_noise(self, yiq: numpy.ndarray, field: int, video_noise: int):
        _, height, width = yiq.shape
        fY, fI, fQ = yiq
        noise_mod = video_noise * 2 + 1
        fields = fY[field::2]
        fh, fw = fields.shape
        
        if not self.precise: # isto funciona rápido
            lp = LowpassFilter(1, 1, 0)
            lp.alpha = 0.5
            
            rnds = self.rand_array(fw * fh) % noise_mod - video_noise
            noises = shift(lp.lowpass_array(rnds).astype(numpy.int32), 1)
            fields += noises.reshape(fields.shape)
        else: # este funciona exatamente como o código original
            noise = 0
            
            for field1 in fields:
                rnds = self.rand_array(fw) % noise_mod - video_noise
                
                for x in range(0, fw):
                    field1[x] += noise
                    
                    noise += rnds[x]
                    noise = int(noise / 2)

    def video_chroma_noise(self, yiq: numpy.ndarray, field: int, video_chroma_noise: int):
        _, height, width = yiq.shape
        fY, fI, fQ = yiq

        noise_mod = video_chroma_noise * 2 + 1
        
        U = fI[field::2]
        V = fQ[field::2]
        
        fh, fw = U.shape
        
        if not self.precise:
            lp = LowpassFilter(1, 1, 0)
            lp.alpha = 0.5
            
            rndsU = self.rand_array(fw * fh) % noise_mod - video_chroma_noise
            noisesU = shift(lp.lowpass_array(rndsU).astype(numpy.int32), 1)

            rndsV = self.rand_array(fw * fh) % noise_mod - video_chroma_noise
            noisesV = shift(lp.lowpass_array(rndsV).astype(numpy.int32), 1)

            U += noisesU.reshape(U.shape)
            V += noisesV.reshape(V.shape)
        else:
            noiseU = 0
            noiseV = 0
            
            for y in range(0, fh):
                for x in range(0, fw):
                    U[y][x] += noiseU
                    
                    noiseU += self.rand() % noise_mod - video_chroma_noise
                    noiseU = int(noiseU / 2)

                    V[y][x] += noiseV
                    
                    noiseV += self.rand() % noise_mod - video_chroma_noise
                    noiseV = int(noiseV / 2)

    def video_chroma_phase_noise(self, yiq: numpy.ndarray, field: int, video_chroma_phase_noise: int):
        _, height, width = yiq.shape
        fY, fI, fQ = yiq
        
        noise_mod = video_chroma_phase_noise * 2 + 1
        
        U = fI[field::2]
        V = fQ[field::2]
        
        fh, fw = U.shape
        noise = 0
        
        for y in range(0, fh):
            noise += self.rand() % noise_mod - video_chroma_phase_noise
            noise = int(noise / 2)
            
            pi = noise * M_PI / 100
            
            sinpi = math.sin(pi)
            cospi = math.cos(pi)
            
            u = U[y] * cospi - V[y] * sinpi
            v = U[y] * sinpi + V[y] * cospi
            
            U[y, :] = u
            V[y, :] = v

    def vhs_head_switching(self, yiq: numpy.ndarray, field: int = 0):
        _, height, width = yiq.shape
        
        fY, fI, fQ = yiq
        twidth = width + width // 10
        
        shy = 0
        noise = 0.0
        
        if self._vhs_head_switching_phase_noise != 0.0:
            x = numpy.int32(random.randint(1, 2000000000))
            
            noise = x / 1000000000.0 - 1.0
            noise *= self._vhs_head_switching_phase_noise

        t = twidth * (262.5 if self._output_vhs else 312.5)
        p = int(fmod(self._vhs_head_switching_point + noise, 1.0) * t)
        
        self._vhs_head_switching_point += self._head_switching_speed / 1000
        
        y = int(p // twidth * 2) + field
        p = int(fmod(self._vhs_head_switching_phase + noise, 1.0) * t)
        x = p % twidth
        y -= (262 - 240) * 2 if self._output_vhs else (312 - 288) * 2
        
        tx = x
        
        ishif = x - twidth if x >= twidth // 2 else x
        
        shif = 0
        
        while y < height:
            if y >= 0:
                Y = fY[y]
                
                if shif != 0:
                    tmp = numpy.zeros(twidth)
                    x2 = (tx + twidth + shif) % twidth
                    tmp[:width] = Y

                    x = tx
                    
                    while x < width:
                        Y[x] = tmp[x2]
                        
                        x2 += 1
                        
                        if x2 == twidth:
                            x2 = 0
                            
                        x += 1

            shif = ishif if shy == 0 else int(shif * 7 / 8)
            
            tx = 0
            y += 2
            shy += 1

    _Umult = numpy.array([1, 0, -1, 0], dtype=numpy.int32)
    _Vmult = numpy.array([0, 1, 0, -1], dtype=numpy.int32)

    def _chroma_luma_xi(self, fieldno: int, y: int):
        if self._video_scanline_phase_shift == 90:
            return int(fieldno + self._video_scanline_phase_shift_offset + (y >> 1)) & 3
        elif self._video_scanline_phase_shift == 180:
            return int(((((fieldno + y) & 2) + self._video_scanline_phase_shift_offset) & 3))
        elif self._video_scanline_phase_shift == 270:
            return int(((fieldno + self._video_scanline_phase_shift_offset) & 3))
        else:
            return int(self._video_scanline_phase_shift_offset & 3)

    def chroma_into_luma(self, yiq: numpy.ndarray, field: int, fieldno: int, subcarrier_amplitude: int):
        _, height, width = yiq.shape
        
        fY, fI, fQ = yiq
        y = field
        
        umult = numpy.tile(Vhs._Umult, int((width / 4) + 1))
        vmult = numpy.tile(Vhs._Vmult, int((width / 4) + 1))
        
        while y < height:
            Y = fY[y]
            I = fI[y]
            Q = fQ[y]
            
            xi = self._chroma_luma_xi(fieldno, y)

            chroma = I * subcarrier_amplitude * umult[xi:xi + width]
            chroma += Q * subcarrier_amplitude * vmult[xi:xi + width]
            
            Y[:] = Y + chroma.astype(numpy.int32) // 50
            I[:] = 0
            Q[:] = 0
            
            y += 2

    def chroma_from_luma(self, yiq: numpy.ndarray, field: int, fieldno: int, subcarrier_amplitude: int):
        _, height, width = yiq.shape
        
        fY, fI, fQ = yiq
        chroma = numpy.zeros(width, dtype=numpy.int32)
        
        for y in range(field, height, 2):
            Y = fY[y]
            I = fI[y]
            Q = fQ[y]
            
            sum: int = Y[0] + Y[1]
            
            y2 = numpy.pad(Y[2:], (0, 2))
            yd4 = numpy.pad(Y[:-2], (2, 0))
            
            sums = y2 - yd4
            sums0 = numpy.concatenate([numpy.array([sum], dtype=numpy.int32), sums])
            
            acc = numpy.add.accumulate(sums0, dtype=numpy.int32)[1:]
            acc4 = acc // 4
            
            chroma = y2 - acc4
            
            Y[:] = acc4

            xi = self._chroma_luma_xi(fieldno, y)

            x = 4 - xi & 3
            # inverta a parte da onda senoidal que corresponderia aos valores negativos de u e v
            chroma[x + 2::4] = -chroma[x + 2::4]
            chroma[x + 3::4] = -chroma[x + 3::4]

            chroma = (chroma * 50 / subcarrier_amplitude)

            # decodificar a cor da subportadora que geramos
            cxi = -chroma[xi::2]
            cxi1 = -chroma[xi + 1::2]
            
            I[::2] = numpy.pad(cxi, (0, width // 2 - cxi.shape[0]))
            Q[::2] = numpy.pad(cxi1, (0, width // 2 - cxi1.shape[0]))

            I[1:width - 2:2] = (I[:width - 2:2] + I[2::2]) >> 1
            Q[1:width - 2:2] = (Q[:width - 2:2] + Q[2::2]) >> 1
            
            I[width - 2:] = 0
            Q[width - 2:] = 0

    def vhs_luma_lowpass(self, yiq: numpy.ndarray, field: int, luma_cut: float):
        _, height, width = yiq.shape
        
        fY, fI, fQ = yiq
        
        for Y in fY[field::2]:
            pre = LowpassFilter(Vhs.VHS_RATE, luma_cut, 16.0)
            lp = lowpassFilters(cutoff=luma_cut, reset=16.0)
            
            f0 = lp[0].lowpass_array(Y)
            f1 = lp[1].lowpass_array(f0)
            f2 = lp[2].lowpass_array(f1)
            f3 = f2 + pre.highpass_array(f2) * 1.6
            
            Y[:] = f3

    def vhs_chroma_lowpass(self, yiq: numpy.ndarray, field: int, chroma_cut: float, chroma_delay: int):
        _, height, width = yiq.shape
        
        fY, fI, fQ = yiq
        
        for U in fI[field::2]:
            lpU = lowpassFilters(cutoff=chroma_cut, reset=0.0)
            
            f0 = lpU[0].lowpass_array(U)
            f1 = lpU[1].lowpass_array(f0)
            f2 = lpU[2].lowpass_array(f1)
            
            U[:width - chroma_delay] = f2[chroma_delay:]

        for V in fQ[field::2]:
            lpV = lowpassFilters(cutoff=chroma_cut, reset=0.0)
            
            f0 = lpV[0].lowpass_array(V)
            f1 = lpV[1].lowpass_array(f0)
            f2 = lpV[2].lowpass_array(f1)
            
            V[:width - chroma_delay] = f2[chroma_delay:]

    def vhs_chroma_vert_blend(self, yiq: numpy.ndarray, field: int):
        _, height, width = yiq.shape
        fY, fI, fQ = yiq
        
        U2 = fI[field + 2::2, ]
        V2 = fQ[field + 2::2, ]
        
        delayU = numpy.pad(U2[:-1, ], [[1, 0], [0, 0]])
        delayV = numpy.pad(V2[:-1, ], [[1, 0], [0, 0]])
        
        fI[field + 2::2, ] = (delayU + U2 + 1) >> 1
        fQ[field + 2::2, ] = (delayV + V2 + 1) >> 1

    def vhs_sharpen(self, yiq: numpy.ndarray, field: int, luma_cut: float):
        _, height, width = yiq.shape
        
        fY, fI, fQ = yiq
        
        for Y in fY[field::2]:
            lp = lowpassFilters(cutoff=luma_cut * 4, reset=0.0)
            
            s = Y
            
            ts = lp[0].lowpass_array(Y)
            ts = lp[1].lowpass_array(ts)
            ts = lp[2].lowpass_array(ts)
            
            Y[:] = (s + (s - ts) * self._vhs_out_sharpen * 2.0)

    def color_bleed(self, yiq: numpy.ndarray, field: int):
        _, height, width = yiq.shape
        fY, fI, fQ = yiq

        field_ = fI[field::2]
        h, w = field_.shape
        fI[field::2] = numpy.pad(field_, ((self._color_bleed_vert, 0), (self._color_bleed_horiz, 0)))[0:h, 0:w]

        field_ = fQ[field::2]
        h, w = field_.shape
        fQ[field::2] = numpy.pad(field_, ((self._color_bleed_vert, 0), (self._color_bleed_horiz, 0)))[0:h, 0:w]

    def vhs_edge_wave(self, yiq: numpy.ndarray, field: int):
        _, height, width = yiq.shape
        
        fY, fI, fQ = yiq
        rnds = self.random.nextIntArray(height // 2, 0, self._vhs_edge_wave)
        lp = LowpassFilter(Vhs.VHS_RATE, self._output_vhs_tape_speed.luma_cut, 0) # nenhum propósito real para inicializá-lo com valores vhs
        rnds = lp.lowpass_array(rnds).astype(numpy.int32)

        for y, Y in enumerate(fY[field::2]):
            if rnds[y] != 0:
                shift = rnds[y]
                Y[:] = numpy.pad(Y, (shift, 0))[:-shift]
                
        for y, I in enumerate(fI[field::2]):
            if rnds[y] != 0:
                shift = rnds[y]
                I[:] = numpy.pad(I, (shift, 0))[:-shift]
                
        for y, Q in enumerate(fQ[field::2]):
            if rnds[y] != 0:
                shift = rnds[y]
                Q[:] = numpy.pad(Q, (shift, 0))[:-shift]

    def vhs_chroma_loss(self, yiq: numpy.ndarray, field: int, video_chroma_loss: int):
        _, height, width = yiq.shape
        fY, fI, fQ = yiq
        
        for y in range(field, height, 2):
            U = fI[y]
            V = fQ[y]
            
            if self.rand() % 100000 < video_chroma_loss:
                U[:] = 0
                V[:] = 0

    def emulate_vhs(self, yiq: numpy.ndarray, field: int, fieldno: int):
        vhs_speed = self._output_vhs_tape_speed
        
        if self._vhs_edge_wave != 0:
            self.vhs_edge_wave(yiq, field)

        self.vhs_luma_lowpass(yiq, field, vhs_speed.luma_cut)
        self.vhs_chroma_lowpass(yiq, field, vhs_speed.chroma_cut, vhs_speed.chroma_delay)

        if self._vhs_chroma_vert_blend and self._output_vhs:
            self.vhs_chroma_vert_blend(yiq, field)

        if True: # todo: fazer opção
            self.vhs_sharpen(yiq, field, vhs_speed.luma_cut)

        if not self._vhs_svideo_out:
            self.chroma_into_luma(yiq, field, fieldno, self._subcarrier_amplitude)
            self.chroma_from_luma(yiq, field, fieldno, self._subcarrier_amplitude)

    def composite_layer(self, dst: numpy.ndarray, src: numpy.ndarray, field: int, fieldno: int):
        assert dst.shape == src.shape, "imagens dst e src devem ter o mesmo formato"

        if self._black_line_cut:
            cut_black_line_border(src)

        yiq = bgr2yiq(src)
        
        if self._color_bleed_before and (self._color_bleed_vert != 0 or self._color_bleed_horiz != 0):
            self.color_bleed(yiq, field)

        if self._composite_in_chroma_lowpass:
            composite_lowpass(yiq, field, fieldno)

        if self._ringing != 1.0:
            self.ringing(yiq, field)

        self.chroma_into_luma(yiq, field, fieldno, self._subcarrier_amplitude)

        if self._composite_preemphasis != 0.0 and self._composite_preemphasis_cut > 0:
            composite_preemphasis(yiq, field, self._composite_preemphasis, self._composite_preemphasis_cut)

        if self._video_noise != 0:
            self.video_noise(yiq, field, self._video_noise)

        if self._vhs_head_switching:
            self.vhs_head_switching(yiq, field)

        if not self._nocolor_subcarrier:
            self.chroma_from_luma(yiq, field, fieldno, self._subcarrier_amplitude_back)

        if self._video_chroma_noise != 0:
            self.video_chroma_noise(yiq, field, self._video_chroma_noise)

        if self._video_chroma_phase_noise != 0:
            self.video_chroma_phase_noise(yiq, field, self._video_chroma_phase_noise)

        if self._emulating_vhs:
            self.emulate_vhs(yiq, field, fieldno)

        if self._video_chroma_loss != 0:
            self.vhs_chroma_loss(yiq, field, self._video_chroma_loss)

        if self._composite_out_chroma_lowpass:
            if self._composite_out_chroma_lowpass_lite:
                composite_lowpass_tv(yiq, field, fieldno)
            else:
                composite_lowpass(yiq, field, fieldno)

        if not self._color_bleed_before and (self._color_bleed_vert != 0 or self._color_bleed_horiz != 0):
            self.color_bleed(yiq, field)

        # if self._ringing != 1.0:
        #     self.ringing(yiq, field)

        Y, I, Q = yiq

        # simula 2x menos largura de banda para componentes cromáticos, assim como o yuv420
        I[field::2] = self._blur_chroma(I[field::2])
        Q[field::2] = self._blur_chroma(Q[field::2])

        return yiq2bgr(yiq)

    def _blur_chroma(self, chroma: numpy.ndarray) -> numpy.ndarray:
        h, w = chroma.shape
        down2 = cv2.resize(chroma.astype(numpy.float32), (w // 2, h // 2), interpolation=cv2.INTER_LANCZOS4)
        
        return cv2.resize(down2, (w, h), interpolation=cv2.INTER_LANCZOS4).astype(numpy.int32)

    def ringing(self, yiq: numpy.ndarray, field: int):
        Y, I, Q = yiq
        
        sz = self._freq_noise_size
        amp = self._freq_noise_amplitude
        shift = self._ringing_shift
        
        if not self._enable_ringing2:
            Y[field::2] = ringing(Y[field::2], self._ringing, noiseSize=sz, noiseValue=amp, clip=False)
            I[field::2] = ringing(I[field::2], self._ringing, noiseSize=sz, noiseValue=amp, clip=False)
            Q[field::2] = ringing(Q[field::2], self._ringing, noiseSize=sz, noiseValue=amp, clip=False)
        else:
            Y[field::2] = ringing2(Y[field::2], power=self._ringing_power, shift=shift, clip=False)
            I[field::2] = ringing2(I[field::2], power=self._ringing_power, shift=shift, clip=False)
            Q[field::2] = ringing2(Q[field::2], power=self._ringing_power, shift=shift, clip=False)

def random_vhs(seed=None) -> Vhs:
    rnd = random.Random(seed)
    
    vhs = Vhs(random=NumpyRandom(seed))
    
    vhs._composite_preemphasis = rnd.triangular(0, 8, 0)
    vhs._vhs_out_sharpen = rnd.triangular(1, 5, 1.5)
    vhs._composite_in_chroma_lowpass = rnd.random() < 0.8  # lean towards default value
    vhs._composite_out_chroma_lowpass = rnd.random() < 0.8  # lean towards default value
    vhs._composite_out_chroma_lowpass_lite = rnd.random() < 0.8  # lean towards default value
    vhs._video_chroma_noise = int(rnd.triangular(0, 16384, 2))
    vhs._video_chroma_phase_noise = int(rnd.triangular(0, 50, 2))
    vhs._video_chroma_loss = int(rnd.triangular(0, 800, 10))
    vhs._video_noise = int(rnd.triangular(0, 4200, 2))
    vhs._emulating_vhs = rnd.random() < 0.2  # lean towards default value
    vhs._vhs_edge_wave = int(rnd.triangular(0, 5, 0))
    vhs._video_scanline_phase_shift = rnd.choice([0, 90, 180, 270])
    vhs._video_scanline_phase_shift_offset = rnd.randint(0, 3)
    vhs._output_vhs_tape_speed = rnd.choice([VHSSpeed.VHS_SP, VHSSpeed.VHS_LP, VHSSpeed.VHS_EP])
    enable_ringing = rnd.random() < 0.8
    
    if enable_ringing:
        vhs._ringing = rnd.uniform(0.3, 0.7)
        enable_freq_noise = rnd.random() < 0.8
        
        if enable_freq_noise:
            vhs._freq_noise_size = rnd.uniform(0.5, 0.99)
            vhs._freq_noise_amplitude = rnd.uniform(0.5, 2.0)
            
        vhs._enable_ringing2 = rnd.random() < 0.5
        vhs._ringing_power = rnd.randint(2, 7)
        
    vhs._color_bleed_before = 1 == rnd.randint(0, 1)
    vhs._color_bleed_horiz = int(rnd.triangular(0, 8, 0))
    vhs._color_bleed_vert = int(rnd.triangular(0, 8, 0))
    
    return vhs

def lowpassFilters(cutoff: float, reset: float, rate: float = Vhs.VHS_RATE) -> List[LowpassFilter]:
    return [LowpassFilter(rate, cutoff, reset) for x in range(0, 3)]