#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")] // esconde a janela do console no windows

use std::{
    path::{Path, PathBuf},
    time::SystemTime
};

use eframe::egui;
use image::{io::Reader as ImageReader, ImageError, RgbImage};
use ntscrs::ntsc::{ChromaLowpass, NtscEffect, NtscEffectFullSettings, VHSTapeSpeed};
use snafu::prelude::*;

fn main() -> Result<(), eframe::Error> {
    env_logger::init(); // log para stderr (caso seja rodado com `rust_log=debug`)

    let options = eframe::NativeOptions {
        initial_window_size: Some(egui::vec2(1200.0, 720.0)),

        ..Default::default()
    };

    eframe::run_native(
        "ntsc-rs",

        options,

        Box::new(|cc| {
            let mut app = Box::<NtscApp>::default();

            if let Some(storage) = cc.storage {
                let path = storage.get_string("image_path");

                if let Some(path) = path {
                    if path != "" {
                        let _ = app.load_image(&cc.egui_ctx, &PathBuf::from(path));
                    }
                }
            }

            app
        })
    )
}

struct PlayInfo {
    start_frame: usize,
    play_start: SystemTime
}

struct NtscApp {
    image_path: Option<String>,
    image: Option<RgbImage>,
    preview: Option<egui::TextureHandle>,
    seed: u64,
    frame: usize,
    play_info: Option<PlayInfo>,
    settings: NtscEffectFullSettings
}

impl Default for NtscApp {
    fn default() -> Self {
        Self {
            image_path: None,
            image: None,
            preview: None,
            seed: 0,
            frame: 0,
            play_info: None,
            settings: NtscEffectFullSettings::default()
        }
    }
}

#[derive(Debug, Snafu)]
enum LoadImageError {
    #[snafu()]
    IO { source: std::io::Error },

    #[snafu()]
    Image { source: ImageError }
}

impl NtscApp {
    fn load_image(&mut self, ctx: &egui::Context, path: &Path) -> Result<(), LoadImageError> {
        let image = ImageReader::open(path)
            .context(IOSnafu)?
            .decode()
            .context(ImageSnafu)?;

        let image = image.into_rgb8();

        self.image = Some(image);
        self.image_path = path.as_os_str().to_str().map(String::from);
        self.update_effect(ctx);

        Ok(())
    }

    fn update_effect(&mut self, ctx: &egui::Context) {
        if let Some(image) = &self.image {
            let result = NtscEffect::from(&self.settings).apply_effect(image, self.frame, self.seed);
            let egui_image = egui::ColorImage::from_rgb([result.width() as usize, result.height() as usize], result.as_raw());

            self.preview = Some(ctx.load_texture("preview", egui_image, egui::TextureOptions::LINEAR));
        }
    }

    fn update_frame(&mut self, ctx: &egui::Context) {
        if let Some(info) = &self.play_info {
            if let Ok(elapsed) = SystemTime::now().duration_since(info.play_start) {
                let frame = (elapsed.as_secs_f64() * 60.0) as usize + info.start_frame;

                if frame != self.frame {
                    self.frame = frame;
                    self.update_effect(ctx);
                }
            }

            ctx.request_repaint();
        }
    }
}

impl eframe::App for NtscApp {
    fn update(&mut self, ctx: &egui::Context, frame: &mut eframe::Frame) {
        self.update_frame(ctx);

        egui::TopBottomPanel::top("menu_bar").show(ctx, |ui| {
            ui.with_layout(egui::Layout::left_to_right(egui::Align::Center), |ui| {
                ui.heading("ntsc-rs");

                ui.menu_button("arquivo", |ui| {
                    if ui.button("abrir").clicked() {
                        if let Some(path) = rfd::FileDialog::new().pick_file() {
                            ui.close_menu();

                            let _ = self.load_image(ctx, &path);
                        }
                    }

                    if ui.button("fechar").clicked() {
                        frame.close();

                        ui.close_menu();
                    }
                });
            });
        });

        egui::SidePanel::left("controls")
            .resizable(true)
            .default_width(400.0)
            .width_range(200.0..=800.0)
            .show(ctx, |ui| {
                egui::ScrollArea::vertical()
                    .auto_shrink([false, true])
                    .show(ui, |ui| {
                        ui.heading("controles");
                        ui.style_mut().spacing.slider_width = 200.0;

                        // ui.checkbox(&mut self.settings.chroma_lowpass_in, "Chroma low-pass in");

                        egui::ComboBox::from_label("passagem baixa de croma")
                            .selected_text(match &self.settings.chroma_lowpass_in {
                                ChromaLowpass::Full => "completa",
                                ChromaLowpass::Light => "moderada",
                                ChromaLowpass::None => "nenhuma"
                            }).show_ui(ui, |ui| {
                                if ui
                                    .selectable_value(
                                        &mut self.settings.chroma_lowpass_in,
                                        ChromaLowpass::Full,
                                        
                                        "completa"
                                    ).changed()
                                {
                                    self.update_effect(ctx);
                                };
                                
                                if ui
                                    .selectable_value(
                                        &mut self.settings.chroma_lowpass_in,
                                        ChromaLowpass::Light,
                                        
                                        "moderada"
                                    ).changed()
                                {
                                    self.update_effect(ctx);
                                };

                                if ui
                                    .selectable_value(
                                        &mut self.settings.chroma_lowpass_in,
                                        ChromaLowpass::None,
                                        
                                        "nenhuma"
                                    ).changed()
                                {
                                    self.update_effect(ctx);
                                };
                            });

                        if ui
                            .add(
                                egui::Slider::new(
                                    &mut self.settings.composite_preemphasis,
                                    0f64..=2f64,
                                ).text("pré-ênfase composta")
                            ).changed()
                        {
                            self.update_effect(ctx);
                        }

                        if ui
                            .add(
                                egui::Slider::new(
                                    &mut self.settings.composite_noise_intensity,
                                    0f64..=0.1f64,
                                ).text("ruído composto")
                            ).changed()
                        {
                            self.update_effect(ctx);
                        }

                        if ui
                            .add(
                                egui::Slider::new(&mut self.settings.snow_intensity, 0.0..=1.0)
                                    .logarithmic(true)
                                    .text("neve")
                            ).changed()
                        {
                            self.update_effect(ctx);
                        }

                        ui.group(|ui| {
                            if ui
                                .checkbox(
                                    &mut self.settings.head_switching_noise.enabled,

                                    "ruído de troca de cabeça"
                                ).changed()
                            {
                                self.update_effect(ctx);
                            }

                            ui.set_enabled(self.settings.head_switching_noise.enabled);

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.head_switching_noise.settings.height,

                                        1..=48
                                    ).text("altura")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self
                                            .settings
                                            .head_switching_noise
                                            .settings
                                            .wave_intensity,

                                        0.0..=50.0
                                    ).text("intensidade da onda")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self
                                            .settings
                                            .head_switching_noise
                                            .settings
                                            .snow_intensity,

                                        0.0..=1.0
                                    )
                                    .logarithmic(true)
                                    .text("intensidade de neve")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }
                        });

                        ui.group(|ui| {
                            if ui
                                .checkbox(
                                    &mut self.settings.head_switching.enabled,

                                    "troca de cabeça"
                                ).changed()
                            {
                                self.update_effect(ctx);
                            }

                            ui.set_enabled(self.settings.head_switching.enabled);

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.head_switching.settings.height,
                                        1..=24,
                                    ).text("altura")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.head_switching.settings.offset,
                                        0..=self.settings.head_switching.settings.height
                                    ).text("desvio")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.head_switching.settings.horiz_shift,
                                        
                                        -100.0..=100.0
                                    ).text("mudança horizontal")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }
                        });

                        ui.group(|ui| {
                            if ui
                                .checkbox(&mut self.settings.ringing.enabled, "toque")
                                .changed()
                            {
                                self.update_effect(ctx);
                            }

                            ui.set_enabled(self.settings.ringing.enabled);

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.ringing.settings.frequency,
                                        
                                        0.0..=1.0
                                    ).text("frequência")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.ringing.settings.power,
                                        
                                        1.0..=10.0
                                    ).text("poder")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.ringing.settings.intensity,
                                        
                                        0.0..=10.0
                                    ).text("escala")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }
                        });

                        if ui
                            .add(
                                egui::Slider::new(
                                    &mut self.settings.chroma_noise_intensity,

                                    0.0..=1.0
                                )
                                .logarithmic(true)
                                .text("ruído cromático")
                            ).changed()
                        {
                            self.update_effect(ctx);
                        }

                        if ui
                            .add(
                                egui::Slider::new(
                                    &mut self.settings.chroma_phase_noise_intensity,
                                    
                                    0.0..=1.0
                                )
                                .logarithmic(true)
                                .text("ruído de fase cromática")
                            ).changed()
                        {
                            self.update_effect(ctx);
                        }

                        ui.group(|ui| {
                            if ui
                                .checkbox(&mut self.settings.vhs_settings.enabled, "Emulate VHS")
                                .changed()
                            {
                                self.update_effect(ctx);
                            }

                            ui.set_enabled(self.settings.vhs_settings.enabled);

                            egui::ComboBox::from_label("velocidade da fita")
                                .selected_text(
                                    match &self.settings.vhs_settings.settings.tape_speed {
                                        Some(VHSTapeSpeed::SP) => "sp (reprodução inicial)",
                                        Some(VHSTapeSpeed::LP) => "lp (reprodução longa)",
                                        Some(VHSTapeSpeed::EP) => "ep (reprodução estendida)",
                                        
                                        None => "desligada",
                                    },
                                )
                                .show_ui(ui, |ui| {
                                    if ui
                                        .selectable_value(
                                            &mut self.settings.vhs_settings.settings.tape_speed,
                                            Some(VHSTapeSpeed::SP),

                                            "sp (reprodução inicial)"
                                        ).changed()
                                    {
                                        self.update_effect(ctx);
                                    };

                                    if ui
                                        .selectable_value(
                                            &mut self.settings.vhs_settings.settings.tape_speed,
                                            Some(VHSTapeSpeed::LP),

                                            "lp (reprodução longa)"
                                        ).changed()
                                    {
                                        self.update_effect(ctx);
                                    };

                                    if ui
                                        .selectable_value(
                                            &mut self.settings.vhs_settings.settings.tape_speed,
                                            Some(VHSTapeSpeed::EP),

                                            "ep (reprodução estendida)"
                                        ).changed()
                                    {
                                        self.update_effect(ctx);
                                    };

                                    if ui
                                        .selectable_value(
                                            &mut self.settings.vhs_settings.settings.tape_speed,
                                            None,
                                            
                                            "desligado"
                                        ).changed()
                                    {
                                        self.update_effect(ctx);
                                    };
                                });

                            if ui
                                .checkbox(
                                    &mut self.settings.vhs_settings.settings.chroma_vert_blend,
                                    
                                    "mistura vertical de croma"
                                ).changed()
                            {
                                self.update_effect(ctx);
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.vhs_settings.settings.sharpen,
                                        
                                        0.0..=5.0
                                    ).text("afiado")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.vhs_settings.settings.edge_wave,
                                        
                                        0.0..=10.0
                                    ).text("intensidade da onda de borda")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }

                            if ui
                                .add(
                                    egui::Slider::new(
                                        &mut self.settings.vhs_settings.settings.edge_wave_speed,
                                        
                                        0.0..=10.0
                                    ).text("velocidade da onda de borda")
                                ).changed()
                            {
                                self.update_effect(ctx)
                            }
                        });

                        egui::ComboBox::from_label("passagem baixa do croma")
                            .selected_text(match &self.settings.chroma_lowpass_out {
                                ChromaLowpass::Full => "completa",
                                ChromaLowpass::Light => "moderada",
                                ChromaLowpass::None => "nenhuma"
                            })
                            .show_ui(ui, |ui| {
                                if ui
                                    .selectable_value(
                                        &mut self.settings.chroma_lowpass_out,
                                        ChromaLowpass::Full,

                                        "completa"
                                    ).changed()
                                {
                                    self.update_effect(ctx);
                                };

                                if ui
                                    .selectable_value(
                                        &mut self.settings.chroma_lowpass_out,
                                        ChromaLowpass::Light,

                                        "moderada"
                                    ).changed()
                                {
                                    self.update_effect(ctx);
                                };

                                if ui
                                    .selectable_value(
                                        &mut self.settings.chroma_lowpass_out,
                                        ChromaLowpass::None,

                                        "nenhuma"
                                    ).changed()
                                {
                                    self.update_effect(ctx);
                                };
                            });
                    });
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("visualização");

            if let Some(preview_texture) = &self.preview {
                ui.image(preview_texture, preview_texture.size_vec2());
            }

            ui.horizontal(|ui| {
                ui.label("seed:");

                if ui.add(egui::DragValue::new(&mut self.seed)).changed() {
                    self.update_effect(ctx);
                }
                
                ui.separator();
                
                ui.label("frame:");
                
                if ui.add(egui::DragValue::new(&mut self.frame)).changed() {
                    self.update_effect(ctx);
                }

                ui.separator();

                if ui
                    .button(if let Some(_) = self.play_info {
                        "⏸"
                    } else {
                        "▶"
                    }).clicked()
                {
                    if let Some(_) = self.play_info {
                        self.play_info = None;
                    } else {
                        self.play_info = Some(PlayInfo {
                            start_frame: self.frame,

                            play_start: SystemTime::now()
                        });
                    }
                }
            })
        });
    }

    fn save(&mut self, storage: &mut dyn eframe::Storage) {
        storage.set_string(
            "image_path",

            match &self.image_path {
                Some(path) => path.clone(),

                None => String::from("")
            }
        )
    }
}