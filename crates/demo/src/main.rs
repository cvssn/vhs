use image::io::Reader as ImageReader;
use ntscrs::ntsc::NtscEffect;

fn main() {
    let img = ImageReader::open("/home/va_erie/Pictures/ntsc-test-1.png")
        .unwrap()
        .decode()
        .unwrap();

    let img = img.as_rgb8().unwrap();

    println!("imagem decodificada");

    let filtered = NtscEffect::default().apply_effect(img, 0, 456);

    filtered
        .save("/home/va_erie/Pictures/ntsc-out.png")
        .unwrap();
}