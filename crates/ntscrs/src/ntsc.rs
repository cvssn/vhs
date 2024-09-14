use std::collections::VecDeque;

use image::{Rgb, RgbImage};
use macros::FullSettings;
use nalgebra::{matrix, Matrix3, Vector3};
use rand::{rngs::SmallRng, Rng, RngCore, SeedableRng};
use simdnoise::NoiseBuilder;
use core::f64::consts::PI;

use crate::{
    filter::TransferFunction,
    random::{key_seed, Geometric},
    shift::{shift_row, BoundaryHandling}
};

const YIQ_MATRIX: Matrix3<f64> = matrix![
    0.299, 0.587, 0.114;
    0.5959, -0.2746, -0.3213;
    0.2115, -0.5227, 0.3112;
];

const RGB_MATRIX: Matrix3<f64> = matrix![
    1.0, 0.956, 0.619;
    1.0, -0.272, -0.647;
    1.0, -1.106, 1.703;
];

const NTSC_RATE: f64 = (315000000.00 / 88.0) * 4.0; // 315/88 mhz rate * 4

struct YiqPlanar {
    y: Vec<f64>,
    i: Vec<f64>,
    q: Vec<f64>,

    resolution: (usize, usize),
    field: YiqField
}

/// cria um filtro passa-baixo com os parâmetros fornecidos, que pode então ser usado para filtrar um sinal
pub fn make_lowpass(cutoff: f64, rate: f64) -> TransferFunction {
    let time_interval = 1.0 / rate;
    let tau = (cutoff * 2.0 * PI).recip();
    let alpha = time_interval / (tau + time_interval);

    TransferFunction::new(vec![alpha], vec![1.0, -(1.0 - alpha)])
}

/// cria um filtro passa-baixo com os parâmetros fornecidos, que pode então ser usado para filtrar um sinal
/// isso é equivalente a aplicar o mesmo filtro lowpass 3 vezes
pub fn make_lowpass_triple(cutoff: f64, rate: f64) -> TransferFunction {
    let time_interval = 1.0 / rate;
    let tau = (cutoff * 2.0 * PI).recip();
    let alpha = time_interval / (tau + time_interval);

    let tf = TransferFunction::new(vec![alpha], vec![1.0, -(1.0 - alpha)]);

    &(&tf * &tf) * &tf
}

pub fn make_notch_filter(freq: f64, quality: f64) -> TransferFunction {
    if freq > 1.0 || freq < 0.0 {
        panic!("frequência fora da faixa válida");
    }

    let bandwidth = (freq / quality) * PI;
    let freq = freq * PI;

    let beta = (bandwidth * 0.5).tan();

    let gain = (1.0 + beta).recip();

    let num = vec![gain, -2.0 * freq.cos() * gain, gain];
    let den = vec![1.0, -2.0 * freq.cos() * gain, 2.0 * gain - 1.0];

    TransferFunction::new(num, den)
}

/// filtra a condição inicial
enum InitialCondition {
    /// valor de conveniência – basta usar 0.
    Zero,

    /// define a condição inicial do filtro como uma constante.
    Constant(f64),

    /// define a condição de filtro inicial para a primeira amostra a ser filtrada.
    FirstSample
}

/// aplica o filtro fornecido para um plano de cor
fn filter_plane(
    plane: &mut Vec<f64>,
    width: usize,
    filter: &TransferFunction,
    initial: InitialCondition,
    scale: f64,
    delay: usize
) {
    plane.chunks_mut(width).for_each(|field| {
        let initial = match initial {
            InitialCondition::Zero => 0.0,
            InitialCondition::Constant(c) => c,
            InitialCondition::FirstSample => field[0]
        };

        filter.filter_signal_in_place(field, initial, scale, delay);
    });
}

#[derive(PartialEq, Eq)]
pub enum YiqField {
    Upper,
    Lower,
    Both
}

impl YiqPlanar {
    pub fn from_image(image: &RgbImage, field: YiqField) -> Self {
        let width = image.width() as usize;

        let height = match field {
            YiqField::Upper | YiqField::Lower => (image.height() + 1) / 2,
            YiqField::Both => image.height()
        } as usize;

        // se o índice da linha módulo 2 for igual a esse número, pule essa linha
        let skip_field: usize = match field {
            YiqField::Upper => 1,
            YiqField::Lower => 0,

            // o índice de linha módulo 2 nunca chega a 2, o que significa que não pulamos nenhum campo
            YiqField::Both => 2
        };

        let num_pixels = width * height;

        let mut y = vec![0f64; num_pixels];
        let mut i = vec![0f64; num_pixels];
        let mut q = vec![0f64; num_pixels];

        // let iter: &dyn Iterator<Item = (usize, Rows<'_, Rgb<u8>>)> = &image.rows().enumerate() as &dyn Iterator<Item = (usize, Rows<'_, Rgb<u8>>)>;
        let rows = image.rows().enumerate();

        let mut offset_out = 0usize;

        for (row_idx, row) in rows {
            if row_idx & 1 == skip_field {
                continue;
            }

            row.enumerate().for_each(|(index, Rgb(pixel))| {
                let yiq_pixel = YIQ_MATRIX
                    * Vector3::new(
                        (pixel[0] as f64) / 255.0,
                        (pixel[1] as f64) / 255.0,
                        (pixel[2] as f64) / 255.0
                    );

                y[offset_out + index] = yiq_pixel[0];
                i[offset_out + index] = yiq_pixel[1];
                q[offset_out + index] = yiq_pixel[2];
            });

            offset_out += width;
        }

        YiqPlanar {
            y,
            i,
            q,
            resolution: (width, height),
            field
        }
    }
}

impl From<&YiqPlanar> for RgbImage {
    fn from(image: &YiqPlanar) -> Self {
        let width = image.resolution.0;
        let output_height = image.resolution.1 * if image.field == YiqField::Both { 1 } else { 2 };
        let num_pixels = width * output_height;

        let mut dst = vec![0u8; num_pixels * 3];

        // se o índice da linha módulo 2 for igual a esse número, pular essa linha
        let skip_field: usize = match image.field {
            YiqField::Upper => 1,
            YiqField::Lower => 0,

            // o índice de linha módulo 2 nunca chega a 2, o que significa que não será pulado nenhum campo
            YiqField::Both => 2
        };

        let row_rshift = match image.field {
            YiqField::Both => 0,
            YiqField::Upper | YiqField::Lower => 1
        };

        dst.chunks_mut(width * 3)
            .enumerate()
            .for_each(|(row_idx, dst_row)| {
                // campos internos com linhas acima e abaixo deles. interpolar entre esses campos
                if (row_idx & 1) == skip_field && row_idx != 0 && row_idx != output_height - 1 {
                    for (pix_idx, pixel) in dst_row.chunks_mut(3).enumerate() {
                        let src_idx_lower = ((row_idx - 1) >> 1) * width + pix_idx;
                        let src_idx_upper = ((row_idx + 1) >> 1) * width + pix_idx;

                        let interp_pixel = Vector3::new(
                            (image.y[src_idx_lower] + image.y[src_idx_upper]) * 0.5,
                            (image.i[src_idx_lower] + image.i[src_idx_upper]) * 0.5,
                            (image.q[src_idx_lower] + image.q[src_idx_upper]) * 0.5
                        );

                        let rgb = RGB_MATRIX * interp_pixel;

                        pixel[0] = (rgb[0] * 255.0).clamp(0.0, 255.0) as u8;
                        pixel[1] = (rgb[1] * 255.0).clamp(0.0, 255.0) as u8;
                        pixel[2] = (rgb[2] * 255.0).clamp(0.0, 255.0) as u8;
                    }
                } else {
                    // copiar o campo diretamente
                    for (pix_idx, pixel) in dst_row.chunks_mut(3).enumerate() {
                        let src_idx = (row_idx >> row_rshift) * width + pix_idx;
                        
                        let rgb = RGB_MATRIX * Vector3::new(image.y[src_idx], image.i[src_idx], image.q[src_idx]);

                        pixel[0] = (rgb[0] * 255.0).clamp(0.0, 255.0) as u8;
                        pixel[1] = (rgb[1] * 255.0).clamp(0.0, 255.0) as u8;
                        pixel[2] = (rgb[2] * 255.0).clamp(0.0, 255.0) as u8;
                    }
                }
            });

        RgbImage::from_raw(width as u32, output_height as u32, dst).unwrap()
    }
}

fn composite_chroma_lowpass(frame: &mut YiqPlanar) {
    let i_filter = make_lowpass_triple(1300000.0, NTSC_RATE);
    let q_filter = make_lowpass_triple(600000.0, NTSC_RATE);

    let width = frame.resolution.0;

    filter_plane(&mut frame.i, width, &i_filter, InitialCondition::Zero, 1.0, 2);
    filter_plane(&mut frame.q, width, &q_filter, InitialCondition::Zero, 1.0, 4);
}

fn composite_chroma_lowpass_lite(frame: &mut YiqPlanar) {
    let filter = make_lowpass_triple(2600000.0, NTSC_RATE);

    let width = frame.resolution.0;

    filter_plane(&mut frame.i, width, &filter, InitialCondition::Zero, 1.0, 1);
    filter_plane(&mut frame.q, width, &filter, InitialCondition::Zero, 1.0, 1);
}

const I_MULT: [f64; 4] = [1.0, 0.0, -1.0, 0.0];
const Q_MULT: [f64; 4] = [0.0, 1.0, 0.0, -1.0];

fn chroma_luma_line_offset(
    scanline_phase_shift: PhaseShift,
    offset: i32,
    field_num: usize,
    line_num: usize
) -> usize {
    (match scanline_phase_shift {
        PhaseShift::Degrees90 | PhaseShift::Degrees270 => {
            (field_num as i32 + offset + ((line_num as i32) >> 1)) & 3
        }

        PhaseShift::Degrees180 => (((field_num + line_num) & 2) as i32 + offset) & 3,
        PhaseShift::Degrees0 => 0
    } & 3) as usize
}

fn chroma_into_luma_line(
    y: &mut [f64],
    i: &mut [f64],
    q: &mut [f64],

    xi: usize,
    subcarrier_amplitude: f64
) {
    y.into_iter()
        .zip(i.into_iter().zip(q.into_iter()))
        .enumerate()
        .for_each(|(index, (y, (i, q)))| {
            let offset = (index + (xi & 3)) & 3;

            *y += (*i * I_MULT[offset] + *q * Q_MULT[offset]) * subcarrier_amplitude / 50.0;
            
            // *i = 0.0;
            // *q = 0.0;
        });
}

fn luma_into_chroma_line(
    y: &mut [f64],
    i: &mut [f64],
    q: &mut [f64],

    xi: usize,
    subcarrier_amplitude: f64
) {
    let mut delay = VecDeque::<f64>::with_capacity(4);

    delay.push_back(16.0 / 255.0);
    delay.push_back(16.0 / 255.0);
    
    delay.push_back(y[0]);
    delay.push_back(y[1]);
    
    let mut sum: f64 = delay.iter().sum();
    let width = y.len();

    for index in 0..width {
        // desfoca o sinal para obter a luminância
        // todo: adicionar uma opção para usar um filtro passa-baixa real aqui?
        let c = y[usize::min(index + 2, width - 1)];

        sum -= delay.pop_front().unwrap();
        delay.push_back(c);
        sum += c;
        y[index] = sum * 0.25;
        
        let mut chroma = c - y[index];

        chroma = (chroma * 50.0) / subcarrier_amplitude;

        let offset = (index + (xi & 3)) & 3;

        let i_modulated = -(chroma * I_MULT[offset]);
        let q_modulated = -(chroma * Q_MULT[offset]);

        // todo: o ntscqt parece bagunçar tudo, dando ao croma uma aparência "irregular" que lembra o artefato "dot crawl".
        // vale a pena tentar replicar ou deveria simplesmente ficar assim?
        
        if index < width - 1 {
            i[index + 1] = i_modulated * 0.5;
            q[index + 1] = q_modulated * 0.5;
        }
        
        i[index] += i_modulated;
        q[index] += q_modulated;
        
        if index > 0 {
            i[index - 1] += i_modulated * 0.5;
            q[index - 1] += q_modulated * 0.5;
        }
    }
}

fn video_noise_line<R: Rng>(row: &mut [f64], rng: &mut R, frequency: f64, intensity: f64) {
    let width = row.len();
    let noise_seed = rng.next_u32();
    let offset = rng.gen::<f64>() * width as f64;

    let noise = NoiseBuilder::gradient_1d_offset(offset as f32, width)
        .with_seed(noise_seed as i32)
        .with_freq(frequency as f32)
        .generate()
        .0;

    row.iter_mut().enumerate().for_each(|(x, pixel)| {
        *pixel += noise[x] as f64 * 0.25 * intensity;
    });
}

fn composite_noise(
    yiq: &mut YiqPlanar,
    seed: u64,
    frequency: f64,
    intensity: f64,
    frame_num: usize
) {
    let width = yiq.resolution.0;
    let mut rng = SmallRng::seed_from_u64(key_seed(seed, noise_seeds::VIDEO_COMPOSITE, frame_num));

    yiq.y.chunks_mut(width).for_each(|row| {
        video_noise_line(row, &mut rng, frequency, intensity);
    });
}

mod noise_seeds {
    pub const VIDEO_COMPOSITE: u64 = 0;
    pub const VIDEO_CHROMA: u64 = 1;
    pub const HEAD_SWITCHING: u64 = 2;
    pub const HEAD_SWITCHING_PHASE: u64 = 3;
    pub const VIDEO_CHROMA_PHASE: u64 = 4;
    pub const EDGE_WAVE: u64 = 5;
    pub const SNOW: u64 = 6;
}

fn chroma_noise(yiq: &mut YiqPlanar, seed: u64, frequency: f64, intensity: f64, frame_num: usize) {
    let width = yiq.resolution.0;
    let mut rng = SmallRng::seed_from_u64(key_seed(seed, noise_seeds::VIDEO_CHROMA, frame_num));

    yiq.i
        .chunks_mut(width)
        .zip(yiq.q.chunks_mut(width))
        .for_each(|(i, q)| {
            video_noise_line(i, &mut rng, frequency, intensity);
            video_noise_line(q, &mut rng, frequency, intensity);
        });
}

fn chroma_phase_noise(yiq: &mut YiqPlanar, seed: u64, intensity: f64, frame_num: usize) {
    let width = yiq.resolution.0;
    let mut rng = SmallRng::seed_from_u64(key_seed(seed, noise_seeds::VIDEO_CHROMA_PHASE, frame_num));

    yiq.i
        .chunks_mut(width)
        .zip(yiq.q.chunks_mut(width))
        .for_each(|(i, q)| {
            // ângulo de mudança de fase em radianos. Mapeado de forma que uma intensidade de 1,0 seja uma mudança de fase que varia de uma
            // rotação para a esquerda - uma rotação completa para a direita.
            let phase_shift = (rng.gen::<f64>() - 0.5) * PI * 4.0 * intensity;
            let (sin_angle, cos_angle) = phase_shift.sin_cos();

            for (i, q) in i.iter_mut().zip(q.iter_mut()) {
                // tratar (i, q) como um vetor 2D e gire-o pela quantidade de mudança de fase.
                let rotated_i = (*i * cos_angle) - (*q * sin_angle);
                let rotated_q = (*i * sin_angle) + (*q * cos_angle);

                *i = rotated_i;
                *q = rotated_q;
            }
        });
}

fn head_switching(
    yiq: &mut YiqPlanar,
    num_rows: usize,
    offset: usize,
    shift: f64,
    seed: u64,
    frame_num: usize
) {
    let (width, height) = yiq.resolution;
    let num_affected_rows = num_rows - offset;

    let mut rng = SmallRng::seed_from_u64(key_seed(seed, noise_seeds::HEAD_SWITCHING_PHASE, frame_num));

    for row_idx in 0..num_affected_rows {
        let dst_row_idx = height - 1 - row_idx;
        let row = &mut yiq.y[width * dst_row_idx..width * (dst_row_idx + 1)];

        let row_shift = shift * ((row_idx + offset) as f64 / num_rows as f64).powf(1.5);
        
        shift_row(
            row,
            row_shift + (rng.gen::<f64>() - 0.5),
            BoundaryHandling::Constant(0.0)
        );
    }
}

// 4 pixels entre os zeros do transiente do speckle
const SPECKLE_TRANSIENT_FREQUENCY: usize = 8;

fn row_speckles<R: Rng>(row: &mut [f64], rng: &mut R, intensity: f64) {
    if intensity <= 0.0 {
        return;
    }

    // transforma cada pixel em "neve" com probabilidade snow_intensity * intensity_scale
    //
    // podemos simular a distância entre cada pixel de "neve" com uma distribuição geométrica que evita ter que
    // percorrer cada pixel
    let dist = Geometric::new(intensity);
    let mut pixel_idx = 0usize;

    loop {
        pixel_idx += rng.sample(&dist);

        if pixel_idx >= row.len() {
            break;
        }

        let transient_len = 2;

        for i in pixel_idx..(pixel_idx + (transient_len * SPECKLE_TRANSIENT_FREQUENCY)).min(row.len()) {
            let x = (i - pixel_idx) as f64;

            // simula o transitório com sin(pi*x / 4) * (1 - x/len)^2
            row[i] += ((x * PI) / SPECKLE_TRANSIENT_FREQUENCY as f64).sin()
                * (1.0 - x / (transient_len * SPECKLE_TRANSIENT_FREQUENCY) as f64).powi(2)
                * 2.0
                * rng.gen::<f64>();
        }

        // certifique-se de avançar o índice de pixels a cada vez. nossa distribuição geométrica nos dá o tempo entre
        // eventos sucessivos, que podem ser 0 para probabilidades muito altas.
        pixel_idx += 1;
    }
}

fn head_switching_noise(
    yiq: &mut YiqPlanar,
    seed: u64,
    height: usize,
    wave_intensity: f64,
    snow_intensity: f64,
    frame_num: usize
) {
    let width = yiq.resolution.0;

    let mut rng = SmallRng::seed_from_u64(key_seed(seed, noise_seeds::HEAD_SWITCHING, frame_num));
    let noise_seed = rng.next_u32();
    let offset = rng.gen::<f32>() * yiq.resolution.1 as f32;

    let shift_noise = NoiseBuilder::gradient_1d_offset(offset as f32, height)
        .with_seed(noise_seed as i32)
        .with_freq(0.5)
        .generate()
        .0;

    for row_idx in 0..height {
        // isso itera de cima para baixo. aumenta a intensidade à medida que nos aproximamos da parte inferior da imagem.
        let intensity_scale = 1.0 - (row_idx as f64 / height as f64);
        let dst_row_idx = yiq.resolution.1 - 1 - row_idx;
        let row = &mut yiq.y[width * dst_row_idx..width * (dst_row_idx + 1)];

        shift_row(
            row,
            shift_noise[row_idx] as f64 * intensity_scale * wave_intensity * 0.25,
            BoundaryHandling::Constant(0.0)
        );

        row_speckles(row, &mut rng, snow_intensity * intensity_scale);
    }
}

fn snow(yiq: &mut YiqPlanar, seed: u64, intensity: f64, frame_num: usize) {
    let mut rng = SmallRng::seed_from_u64(key_seed(seed, noise_seeds::SNOW, frame_num));

    for row in yiq.y.chunks_mut(yiq.resolution.0) {
        row_speckles(row, &mut rng, intensity);
    }
}

fn vhs_edge_wave(yiq: &mut YiqPlanar, seed: u64, intensity: f64, speed: f64, frame_num: usize) {
    let width = yiq.resolution.0;

    let mut rng = SmallRng::seed_from_u64(key_seed(seed, noise_seeds::EDGE_WAVE, 0));
    let noise_seed = rng.next_u32();

    // todo: amostrar o ruído perlin em domínio de tempo
    let offset = rng.gen::<f32>() * yiq.resolution.1 as f32;
    
    let noise = NoiseBuilder::gradient_2d_offset(
        offset as f32,
        width,
        (frame_num as f64 * speed) as f32,
        1
    ).with_seed(noise_seed as i32).with_freq(0.05).generate().0;

    for plane in [&mut yiq.y, &mut yiq.i, &mut yiq.q] {
        plane
            .chunks_mut(width)
            .enumerate()
            .for_each(|(index, row)| {
                let shift = (noise[index] as f64 / 0.022) * intensity * 0.5;

                shift_row(row, shift as f64, BoundaryHandling::Extend);
            })
    }
}

fn chroma_vert_blend(yiq: &mut YiqPlanar) {
    let width = yiq.resolution.0;

    let mut delay_i = vec![0f64; width];
    let mut delay_q = vec![0f64; width];

    yiq.i
        .chunks_mut(width)
        .zip(yiq.q.chunks_mut(width))
        .for_each(|(i_row, q_row)| {
            // todo: verifique se isso é mais rápido que intercalado (acho que a localidade do cache é melhor assim)
            i_row.iter_mut().enumerate().for_each(|(index, i)| {
                let c_i = *i;
                
                *i = (delay_i[index] + c_i) * 0.5;

                delay_i[index] = c_i;
            });

            q_row.iter_mut().enumerate().for_each(|(index, q)| {
                let c_q = *q;

                *q = (delay_q[index] + c_q) * 0.5;
                
                delay_q[index] = c_q;
            });
        });
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum PhaseShift {
    Degrees0,
    Degrees90,
    Degrees180,
    Degrees270
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum VHSTapeSpeed {
    SP,
    LP,
    EP
}

struct VHSTapeParams {
    luma_cut: f64,
    chroma_cut: f64,
    chroma_delay: usize
}

impl VHSTapeSpeed {
    fn filter_params(&self) -> VHSTapeParams {
        match self {
            VHSTapeSpeed::SP => VHSTapeParams {
                luma_cut: 2400000.0,
                chroma_cut: 320000.0,

                chroma_delay: 4
            },

            VHSTapeSpeed::LP => VHSTapeParams {
                luma_cut: 1900000.0,
                chroma_cut: 300000.0,

                chroma_delay: 5
            },

            VHSTapeSpeed::EP => VHSTapeParams {
                luma_cut: 1400000.0,
                chroma_cut: 280000.0,

                chroma_delay: 6
            }
        }
    }
}

#[derive(Clone, PartialEq)]
pub struct VHSSettings {
    pub tape_speed: Option<VHSTapeSpeed>,
    pub chroma_vert_blend: bool,
    pub sharpen: f64,
    
    pub edge_wave: f64,
    pub edge_wave_speed: f64
}

impl Default for VHSSettings {
    fn default() -> Self {
        Self {
            tape_speed: Some(VHSTapeSpeed::LP),
            chroma_vert_blend: true,
            sharpen: 1.0,
            edge_wave: 1.0,
            edge_wave_speed: 4.0
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum ChromaLowpass {
    None,
    Light,
    Full
}

#[derive(Clone, PartialEq)]
pub struct HeadSwitchingSettings {
    pub height: usize,
    pub offset: usize,

    pub horiz_shift: f64
}

impl Default for HeadSwitchingSettings {
    fn default() -> Self {
        Self {
            height: 8,
            offset: 3,
            horiz_shift: 72.0
        }
    }
}

#[derive(Clone, PartialEq)]
pub struct HeadSwitchingNoiseSettings {
    pub height: usize,

    pub wave_intensity: f64,
    pub snow_intensity: f64
}

impl Default for HeadSwitchingNoiseSettings {
    fn default() -> Self {
        Self {
            height: 24,
            wave_intensity: 5.0,
            snow_intensity: 0.005
        }
    }
}

#[derive(Clone, PartialEq)]
pub struct RingingSettings {
    pub frequency: f64,
    pub power: f64,
    pub intensity: f64
}

impl Default for RingingSettings {
    fn default() -> Self {
        Self { frequency: 0.45, power: 4.0, intensity: 4.0 }
    }
}

pub struct SettingsBlock<T> {
    pub enabled: bool,
    pub settings: T
}

impl<T: Default + Clone> From<&Option<T>> for SettingsBlock<T> {
    fn from(opt: &Option<T>) -> Self {
        Self {
            enabled: opt.is_some(),

            settings: match opt {
                Some(v) => v.clone(),

                None => T::default()
            }
        }
    }
}

impl<T: Default> From<Option<T>> for SettingsBlock<T> {
    fn from(opt: Option<T>) -> Self {
        Self {
            enabled: opt.is_some(),

            settings: opt.unwrap_or_else(T::default)
        }
    }
}

impl<T> From<SettingsBlock<T>> for Option<T> {
    fn from(value: SettingsBlock<T>) -> Self {
        if value.enabled {
            Some(value.settings)
        } else {
            None
        }
    }
}

impl<T: Clone> From<&SettingsBlock<T>> for Option<T> {
    fn from(value: &SettingsBlock<T>) -> Self {
        if value.enabled {
            Some(value.settings.clone())
        } else {
            None
        }
    }
}

impl<T: Default> Default for SettingsBlock<T> {
    fn default() -> Self {
        Self { enabled: true, settings: T::default() }
    }
}

#[derive(FullSettings)]
pub struct NtscEffect {
    pub chroma_lowpass_in: ChromaLowpass,
    pub composite_preemphasis: f64,

    pub video_scanline_phase_shift: PhaseShift,
    pub video_scanline_phase_shift_offset: i32,
    
    #[settings_block]
    pub head_switching: Option<HeadSwitchingSettings>,

    #[settings_block]
    pub head_switching_noise: Option<HeadSwitchingNoiseSettings>,
    pub composite_noise_intensity: f64,

    #[settings_block]
    pub ringing: Option<RingingSettings>,

    pub chroma_noise_intensity: f64,
    pub snow_intensity: f64,
    pub chroma_phase_noise_intensity: f64,

    #[settings_block]
    pub vhs_settings: Option<VHSSettings>,
    pub chroma_lowpass_out: ChromaLowpass
}

impl Default for NtscEffect {
    fn default() -> Self {
        Self {
            chroma_lowpass_in: ChromaLowpass::Full,
            chroma_lowpass_out: ChromaLowpass::Full,
            
            composite_preemphasis: 1.0,
            
            video_scanline_phase_shift: PhaseShift::Degrees90,
            video_scanline_phase_shift_offset: 0,

            head_switching: Some(HeadSwitchingSettings::default()),
            head_switching_noise: Some(HeadSwitchingNoiseSettings::default()),

            ringing: Some(RingingSettings::default()),
            snow_intensity: 0.00001,
            composite_noise_intensity: 0.01,
            
            chroma_noise_intensity: 0.1,
            chroma_phase_noise_intensity: 0.001,

            vhs_settings: Some(VHSSettings::default())
        }
    }
}

impl NtscEffect {
    pub fn apply_effect(&self, input_frame: &RgbImage, frame_num: usize, seed: u64) -> RgbImage {
        let mut yiq = YiqPlanar::from_image(input_frame, YiqField::Lower);

        let (width, _) = yiq.resolution;

        match self.chroma_lowpass_in {
            ChromaLowpass::Full => {
                composite_chroma_lowpass(&mut yiq);
            }

            ChromaLowpass::Light => {
                composite_chroma_lowpass_lite(&mut yiq);
            }

            ChromaLowpass::None => {}
        };

        self.chroma_into_luma(&mut yiq, 50.0, 1);

        if self.composite_preemphasis > 0.0 {
            let preemphasis_filter = make_lowpass(315000000.0 / 88.0 / 2.0, NTSC_RATE);

            filter_plane(
                &mut yiq.y,
                width,
                &preemphasis_filter,
                InitialCondition::Zero,
                -self.composite_preemphasis,
                0
            );
        }

        if self.composite_noise_intensity > 0.0 {
            composite_noise(
                &mut yiq,
                seed,
                0.25,
                self.composite_noise_intensity,
                frame_num
            );
        }

        if self.snow_intensity > 0.0 {
            snow(&mut yiq, seed, self.snow_intensity, frame_num);
        }

        if let Some(HeadSwitchingNoiseSettings {
            height,
            wave_intensity,
            snow_intensity
        }) = self.head_switching_noise
        {
            head_switching_noise(
                &mut yiq,

                seed,
                height,

                wave_intensity,
                snow_intensity,

                frame_num
            );
        }

        if let Some(HeadSwitchingSettings {
            height,
            offset,
            horiz_shift
        }) = self.head_switching
        {
            head_switching(&mut yiq, height, offset, horiz_shift, seed, frame_num);
        }

        self.luma_into_chroma(&mut yiq, 50.0, 1);

        if let Some(ringing) = &self.ringing {
            let notch_filter = make_notch_filter(ringing.frequency, ringing.power);

            filter_plane(&mut yiq.y, width, &notch_filter, InitialCondition::FirstSample, ringing.intensity, 1);
        }

        if self.chroma_noise_intensity > 0.0 {
            chroma_noise(&mut yiq, seed, 0.05, self.chroma_noise_intensity, frame_num);
        }

        if self.chroma_phase_noise_intensity > 0.0 {
            chroma_phase_noise(&mut yiq, seed, self.chroma_phase_noise_intensity, frame_num);
        }

        if let Some(vhs_settings) = &self.vhs_settings {
            if vhs_settings.edge_wave > 0.0 {
                vhs_edge_wave(
                    &mut yiq,

                    seed,

                    vhs_settings.edge_wave,
                    vhs_settings.edge_wave_speed,

                    frame_num
                );
            }

            if let Some(tape_speed) = &vhs_settings.tape_speed {
                let VHSTapeParams {
                    luma_cut,
                    chroma_cut,
                    chroma_delay,
                } = tape_speed.filter_params();

                // todo: implementar a redefinição do filtro e tente corrigir a linha preta à esquerda
                // todo: utilizar um filtro melhor! a saída deste efeito parece muito mais manchada do que o vhs real
                let luma_filter = make_lowpass_triple(luma_cut, NTSC_RATE);
                let chroma_filter = make_lowpass_triple(chroma_cut, NTSC_RATE);
                
                filter_plane(&mut yiq.y, width, &luma_filter, InitialCondition::Zero, 1.0, 0);
                filter_plane(&mut yiq.i, width, &chroma_filter, InitialCondition::Zero, 1.0, chroma_delay);
                filter_plane(&mut yiq.q, width, &chroma_filter, InitialCondition::Zero, 1.0, chroma_delay);
                
                let luma_filter_single = make_lowpass(luma_cut, NTSC_RATE);
                
                filter_plane(&mut yiq.y, width, &luma_filter_single, InitialCondition::Zero, -1.6, 0);
            }

            if vhs_settings.chroma_vert_blend {
                chroma_vert_blend(&mut yiq);
            }

            if vhs_settings.sharpen > 0.0 {
                if let Some(tape_speed) = &vhs_settings.tape_speed {
                    let VHSTapeParams { luma_cut, .. } = tape_speed.filter_params();
                    let luma_sharpen_filter = make_lowpass_triple(luma_cut * 4.0, NTSC_RATE);
                    // let chroma_sharpen_filter = make_lowpass_triple(chroma_cut * 4.0, 0.0, NTSC_RATE);
                    
                    filter_plane(
                        &mut yiq.y,

                        width,
                        &luma_sharpen_filter,
                        InitialCondition::Zero,
                        -vhs_settings.sharpen * 2.0,
                        0
                    );

                    // filter_plane_scaled(&mut yiq.i, width, &chroma_sharpen_filter, -vhs_settings.sharpen * 0.85);
                    // filter_plane_scaled(&mut yiq.q, width, &chroma_sharpen_filter, -vhs_settings.sharpen * 0.85);
                }
            }
        }

        match self.chroma_lowpass_out {
            ChromaLowpass::Full => {
                composite_chroma_lowpass(&mut yiq);
            }

            ChromaLowpass::Light => {
                composite_chroma_lowpass_lite(&mut yiq);
            }

            ChromaLowpass::None => {}
        };

        RgbImage::from(&yiq)
    }

    // modular o sinal de crominância no plano de luminância
    fn chroma_into_luma(&self, yiq: &mut YiqPlanar, subcarrier_amplitude: f64, fieldno: usize) {
        let width = yiq.resolution.0;

        let y_lines = yiq.y.chunks_mut(width);
        let i_lines = yiq.i.chunks_mut(width);
        let q_lines = yiq.q.chunks_mut(width);

        y_lines
            .zip(i_lines.zip(q_lines))
            .enumerate()
            .for_each(|(index, (y, (i, q)))| {
                let xi = chroma_luma_line_offset(
                    self.video_scanline_phase_shift,
                    self.video_scanline_phase_shift_offset,
                    
                    fieldno,
                    index * 2
                );

                chroma_into_luma_line(y, i, q, xi, subcarrier_amplitude);
            });
    }

    fn luma_into_chroma(&self, yiq: &mut YiqPlanar, subcarrier_amplitude: f64, fieldno: usize) {
        let width = yiq.resolution.0;

        let y_lines = yiq.y.chunks_mut(width);
        let i_lines = yiq.i.chunks_mut(width);
        let q_lines = yiq.q.chunks_mut(width);

        y_lines
            .zip(i_lines.zip(q_lines))
            .enumerate()
            .for_each(|(index, (y, (i, q)))| {
                let xi = chroma_luma_line_offset(
                    self.video_scanline_phase_shift,
                    self.video_scanline_phase_shift_offset,
                    
                    fieldno,
                    index * 2
                );

                luma_into_chroma_line(y, i, q, xi, subcarrier_amplitude);
            });
    }
}