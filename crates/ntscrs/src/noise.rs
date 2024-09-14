use crate::random::Seeder;

const JITTER_SEED: u64 = 1;
const VALUE_SEED: u64 = 2;

/// amostra de ruído de valor instável em um determinado momento. útil para variar coisas ao longo do tempo.
/// `t` é o tempo dessa amostra.
/// `jitter` é a quantidade de movimentação em torno dos pontos que são interpolados para gerar ruído de valor.
/// útil para evitar artefatos periódicos.
/// `seed` é a seed aleatória.
pub fn sample_noise(t: f64, jitter: f64, seed: u64) -> f64 {
    let left_coord = t as u64;
    let cellspace_coord = t.fract();

    let mut left_jitter = (Seeder::new(left_coord)
        .mix_u64(seed)
        .mix_u64(JITTER_SEED)
        .finalize::<f64>()
        - 0.5)
        * jitter;

    let mut right_jitter = (Seeder::new(left_coord.wrapping_add(1))
        .mix_u64(seed)
        .mix_u64(JITTER_SEED)
        .finalize::<f64>()
        - 0.5)
        * jitter;

    let (dist_offset, rand_coord) = if cellspace_coord < left_jitter {
        right_jitter = left_jitter;

        left_jitter = (Seeder::new(left_coord.wrapping_sub(1))
            .mix_u64(seed)
            .mix_u64(JITTER_SEED)
            .finalize::<f64>()
            - 0.5)
            * jitter;
        
        (-1.0, left_coord.wrapping_sub(1))
    } else if cellspace_coord > right_jitter + 1.0 {
        left_jitter = right_jitter;
        
        right_jitter = (Seeder::new(left_coord.wrapping_add(2))
            .mix_u64(seed)
            .mix_u64(JITTER_SEED)
            .finalize::<f64>()
            - 0.5)
            * jitter;

        (1.0, left_coord.wrapping_add(1))
    } else {
        (0.0, left_coord)
    };
    
    let mut dist = (cellspace_coord - (left_jitter + dist_offset)) / (right_jitter + 1.0 - left_jitter);

    let left_rand: f64 = Seeder::new(rand_coord)
        .mix_u64(seed)
        .mix_u64(VALUE_SEED)
        .finalize();
    
        let right_rand: f64 = Seeder::new(rand_coord.wrapping_add(1))
        .mix_u64(seed)
        .mix_u64(VALUE_SEED)
        .finalize();

    // passo suave
    dist = dist * dist * (3.0 - 2.0 * dist);

    (left_rand * (1.0 - dist)) + (right_rand * dist)
}