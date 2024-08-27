from pathlib import Path
from typing import Tuple

import cv2
import numpy
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QSlider, QHBoxLayout, QLabel, QCheckBox, QInputDialog
from numpy import ndarray

from app.Renderer import Renderer
from app.funcs import resize_to_height, pick_save_file, trim_to_4width
from app.vhs import random_ntsc, Ntsc
from ui import mainWindow
from ui.DoubleSlider import DoubleSlider


class VhsApp(QtWidgets.QMainWindow, mainWindow.Ui_MainWindow):
    def __init__(self):
        self.current_frame: numpy.ndarray = False
        self.preview: numpy.ndarray = False
        self.scale_pixmap = False
        self.input_video = {}
        self.orig_wh: Tuple[int, int] = (0, 0)
        self.compareMode: bool = False
        self.isRenderActive: bool = False
        self.mainEffect: bool = True
        self.nt_controls = {}
        self.nt: Ntsc = None
        
        # necessário para acessar variáveis, métodos, etc. (design.py)
        super().__init__()
        
        self.supported_video_type = ['.mp4', '.mkv', '.avi', '.webm', '.mpg', '.gif']
        self.supported_image_type = ['.png', '.jpg', '.jpeg', '.webp']
        
        # necessário para inicializar o design
        self.setupUi(self)
        
        self.strings = {
            "_composite_preemphasis": self.tr("pré-ênfase composta"),
            "_vhs_out_sharpen": self.tr("vhs com nitidez"),
            "_vhs_edge_wave": self.tr("onda de borda"),
            "_output_vhs_tape_speed": self.tr("velocidade da fita vhs"),
            "_ringing": self.tr("ringing"),
            "_ringing_power": self.tr("poder de toque"),
            "_ringing_shift": self.tr("mudança de toque"),
            "_freq_noise_size": self.tr("tamanho do ruído de frequência"),
            "_freq_noise_amplitude": self.tr("amplitude de ruído de frequência"),
            "_color_bleed_horiz": self.tr("sangramento de cor horizontal"),
            "_color_bleed_vert": self.tr("sangramento de cor verde"),
            "_video_chroma_noise": self.tr("Video chroma noise"),
            "_video_chroma_phase_noise": self.tr("ruído de fase croma de vídeo"),
            "_video_chroma_loss": self.tr("perda de croma de vídeo"),
            "_video_noise": self.tr("ruído de vídeo"),
            "_video_scanline_phase_shift": self.tr("mudança de fase da linha de varredura de vídeo"),
            "_video_scanline_phase_shift_offset": self.tr("deslocamento de mudança de fase da linha de varredura de vídeo"),
            "_head_switching_speed": self.tr("velocidade de movimento do interruptor principal"),
            "_vhs_head_switching": self.tr("troca de cabeça"),
            "_color_bleed_before": self.tr("sangramento de cor antes"),
            "_enable_ringing2": self.tr("habilitar ringing2"),
            "_composite_in_chroma_lowpass": self.tr("composto em chroma lowpass"),
            "_composite_out_chroma_lowpass": self.tr("passagem baixa de croma composto"),
            "_composite_out_chroma_lowpass_lite": self.tr("composição chroma lowpass lite"),
            "_emulating_vhs": self.tr("emulação vhs"),
            "_nocolor_subcarrier": self.tr("subportadora nocolor"),
            "_vhs_chroma_vert_blend": self.tr("mistura vhs chroma vert"),
            "_vhs_svideo_out": self.tr("saída de vídeo vhs"),
            "_output_ntsc": self.tr("output do ntsc"),
        }
        
        self.add_slider("_composite_preemphasis", 0, 10, float)
        
        self.add_slider("_vhs_out_sharpen", 1, 5)
        self.add_slider("_vhs_edge_wave", 0, 10)
        
        # self.add_slider("_output_vhs_tape_speed", 0, 10)
        
        self.add_slider("_ringing", 0, 1, float)
        self.add_slider("_ringing_power", 0, 10)
        self.add_slider("_ringing_shift", 0, 3, float)
        
        self.add_slider("_freq_noise_size", 0, 2, float)
        self.add_slider("_freq_noise_amplitude", 0, 5)
        
        self.add_slider("_color_bleed_horiz", 0, 10)
        self.add_slider("_color_bleed_vert", 0, 10)
        
        self.add_slider("_video_chroma_noise", 0, 16384)
        self.add_slider("_video_chroma_phase_noise", 0, 50)
        self.add_slider("_video_chroma_loss", 0, 100_000)
        self.add_slider("_video_noise", 0, 4200)
        self.add_slider("_video_scanline_phase_shift", 0, 270)
        self.add_slider("_video_scanline_phase_shift_offset", 0, 3)

        self.add_slider("_head_switching_speed", 0, 100)

        self.add_checkbox("_vhs_head_switching", (1, 1))
        self.add_checkbox("_color_bleed_before", (1, 2))
        self.add_checkbox("_enable_ringing2", (2, 1))
        
        self.add_checkbox("_composite_in_chroma_lowpass", (2, 2))
        self.add_checkbox("_composite_out_chroma_lowpass", (3, 1))
        self.add_checkbox("_composite_out_chroma_lowpass_lite", (3, 2))
        
        self.add_checkbox("_emulating_vhs", (4, 1))
        self.add_checkbox("_nocolor_subcarrier", (4, 2))
        self.add_checkbox("_vhs_chroma_vert_blend", (5, 1))
        self.add_checkbox("_vhs_svideo_out", (5, 2))
        self.add_checkbox("_output_ntsc", (6, 1))

        self.previewHeightBox.valueChanged.connect(lambda: self.set_current_frame(self.current_frame))
        self.openFile.clicked.connect(self.open_file)
        self.renderVideoButton.clicked.connect(self.render_video)
        self.saveImageButton.clicked.connect(self.render_image)
        self.stopRenderButton.clicked.connect(self.stop_render)
        self.compareModeButton.stateChanged.connect(self.toggle_compare_mode)
        self.toggleMainEffect.stateChanged.connect(self.toggle_main_effect)
        self.pauseRenderButton.clicked.connect(self.toggle_pause_render)
        self.livePreviewCheckbox.stateChanged.connect(self.toggle_live_preview)
        self.refreshFrameButton.clicked.connect(self.nt_update_preview)
        self.openImageUrlButton.clicked.connect(self.open_image_by_url)

        self.seedSpinBox.valueChanged.connect(self.update_seed)
        self.seedSpinBox.setValue(3)
        
    def setup_renderer(self):
        try:
            self.update_status("encerrando o renderizador anterior")
            print("encerrando o renderizador anterior")
            self.thread.quit()
            self.update_status("aguardando renderização anterior")
            print("aguardando renderização anterior")
            self.thread.wait()
        except AttributeError:
            print("configure o primeiro renderizador")
            
        # criação de um tópico
        self.thread = QtCore.QThread()
        
        # criação de um objeto para executar código em outro thread
        self.videoRenderer = Renderer()
        
        # transferência de um objeto para outro thread
        self.videoRenderer.moveToThread(self.thread)
        
        # conectar todos os sinais e slots
        self.videoRenderer.newFrame.connect(self.render_preview)
        self.videoRenderer.frameMoved.connect(self.videoTrackSlider.setValue)
        self.videoRenderer.renderStateChanged.connect(self.set_render_state)
        self.videoRenderer.sendStatus.connect(self.update_status)
        
        # conectar o sinal de início do thread ao método run do objeto que deve executar o código em outro thread
        self.thread.started.connect(self.videoRenderer.run)

    @QtCore.pyqtSlot()
    def stop_render(self):
        self.videoRenderer.stop()

    @QtCore.pyqtSlot()
    def toggle_compare_mode(self):
        state = self.sender().isChecked()
        
        self.compareMode = state
        self.nt_update_preview()

    @QtCore.pyqtSlot()
    def toggle_pause_render(self):
        button = self.sender()
        
        if not self.isRenderActive:
            self.update_status("renderização não está em execução")
            
            button.setChecked(False)
            
            return None
        
        state = button.isChecked()
        
        self.videoRenderer.pause = state

    def toggle_live_preview(self):
        button = self.sender()
        state = button.isChecked()
        
        try:
            self.videoRenderer.liveView = state
        except AttributeError:
            pass

    @QtCore.pyqtSlot()
    def toggle_main_effect(self):
        state = self.toggleMainEffect.isChecked()
        self.mainEffect = state
        
        try:
            self.videoRenderer.mainEffect = state
        except AttributeError:
            pass
        
        self.nt_update_preview()

    @QtCore.pyqtSlot(int)
    def update_seed(self, seed):
        self.nt = random_ntsc(seed)
        self.nt._enable_ringing2 = True
        self.sync_nt_to_sliders()

    @QtCore.pyqtSlot(str)
    def update_status(self, string):
        self.statusLabel.setText(string)

    @QtCore.pyqtSlot(bool)
    def set_render_state(self, is_render_active):
        self.isRenderActive = is_render_active

        self.videoTrackSlider.blockSignals(is_render_active)

        self.openFile.setEnabled(not is_render_active)
        self.renderVideoButton.setEnabled(not is_render_active)
        self.stopRenderButton.setEnabled(is_render_active)

        # todo: reatribuir parâmetros durante a renderização
        self.seedSpinBox.setEnabled(not is_render_active)

    def sync_nt_to_sliders(self):
        for parameter_name, element in self.nt_controls.items():
            value = getattr(self.nt, parameter_name)

            element.blockSignals(True)
            
            if isinstance(value, bool):
                element.setChecked(value)
            elif isinstance(value, (int, float)):
                element.setValue(value)
                
            element.blockSignals(False)

            related_label = element.parent().findChild(QLabel, parameter_name)
            
            if related_label:
                related_label.setText(str(value)[:7])

            print(f"configurar slider {type(value)} {parameter_name} para {value}")
            
        self.nt_update_preview()

    def value_changed_slot(self):
        element = self.sender()
        parameter_name = element.objectName()
        
        if isinstance(element, (QSlider, DoubleSlider)):
            value = element.value()
            related_label = element.parent().findChild(QLabel, parameter_name)
            
            if related_label:
                related_label.setText(str(value)[:7])
        elif isinstance(element, QCheckBox):
            value = element.isChecked()

        self.update_status(f"configurar {parameter_name} para {value}")
        print(f"configurar {parameter_name} para {value}")
        setattr(self.nt, parameter_name, value)
        self.nt_update_preview()

    def add_checkbox(self, param_name, pos):
        checkbox = QCheckBox()
        checkbox.setText(self.strings[param_name])
        checkbox.setObjectName(param_name)
        checkbox.stateChanged.connect(self.value_changed_slot)
        # checkbox.mouseReleaseEvent(lambda: self.controls_set())
        
        self.nt_controls[param_name] = checkbox
        self.checkboxesLayout.addWidget(checkbox, pos[0], pos[1])

    def add_slider(self, param_name, min_val, max_val, slider_value_type=int):
        slider_layout = QHBoxLayout()
        
        if slider_value_type is int:
            slider = QSlider()
            # box = QSpinBox()
            slider.valueChanged.connect(self.value_changed_slot)
        elif slider_value_type is float:
            # box = QDoubleSpinBox()
            # box.setSingleStep(0.1)
            slider = DoubleSlider()
            slider.mouseRelease.connect(self.value_changed_slot)

        slider.blockSignals(True)
        slider.setEnabled(True)
        slider.setMaximum(max_val)
        slider.setMinimum(min_val)
        slider.setMouseTracking(False)
        
        if max_val < 100 and slider_value_type == int:
            slider.setTickPosition(QSlider.TicksLeft)
            
        slider.setOrientation(QtCore.Qt.Horizontal)
        slider.setObjectName(f"{param_name}")
        slider.blockSignals(False)

        label = QLabel()
        # label.setText(descrição ou nome)
        label.setText(self.strings[param_name])

        # todo: fazer um randomizador em vez de uma caixa
        # box.setMinimum(min_val)
        # box.setMaximum(max_val)
        # box.valueChanged.connect(slider.setValue)
        # slider.valueChanged.connect(box.setValue)
        
        value_label = QLabel()
        value_label.setObjectName(param_name)
        
        # slider.valueChanged.connect(lambda intval: value_label.setText(str(intval)))

        slider_layout.addWidget(label)
        slider_layout.addWidget(slider)
        # slider_layout.addWidget(box)
        slider_layout.addWidget(value_label)

        self.nt_controls[param_name] = slider
        self.controlLayout.addLayout(slider_layout)

    def get_current_video_frame(self):
        preview_h = self.previewHeightBox.value()
        
        if not self.input_video or preview_h < 10:
            return None
        
        frame_no = self.videoTrackSlider.value()
        self.input_video["cap"].set(1, frame_no)
        ret, frame = self.input_video["cap"].read()
        
        return frame

    def set_current_frame(self, frame):
        current_frame_valid = isinstance(frame, ndarray)
        preview_h = self.previewHeightBox.value()
        
        if not current_frame_valid or preview_h < 10:
            self.update_status("tentando definir o quadro atual inválido")
            
            return None

        self.current_frame = frame
        
        try:
            crop_wh = resize_to_height(self.orig_wh, preview_h)
            self.preview = cv2.resize(frame, crop_wh)
        except ZeroDivisionError:
            self.update_status("ZeroDivisionError :DDDDDD")
            
            pass
        
        if self.preview.shape[1] % 4 != 0:
            self.preview = trim_to_4width(self.preview)
        
        self.nt_update_preview()
        
    @QtCore.pyqtSlot()
    def open_image_by_url(self):
        url, ok = QInputDialog.getText(self, self.tr('abrir imagem por url'), self.tr('url da imagem:'))
        
        if ok:
            cap = cv2.VideoCapture(url)
            
            if cap.isOpened():
                ret, img = cap.read()
                
                self.set_image_mode()
                self.open_image(img)
            else:
                self.update_status(self.tr('erro ao abrir o url da imagem :('))
                
                return None

    def open_file(self):
        file = QtWidgets.QFileDialog.getOpenFileName(self, "selecionar arquivo")
        
        if file:
            path = Path(file[0])
        else:
            return None
        
        file_suffix = path.suffix.lower()
        
        if file_suffix in self.supported_video_type:
            self.set_video_mode()
            self.open_video(path)
        elif file_suffix in self.supported_image_type:
            img = cv2.imread(str(path.resolve()))
            
            self.open_image(img)
        else:
            self.update_status(f"tipo de arquivo não compatível: {file_suffix}")

    def set_video_mode(self):
        self.videoTrackSlider.blockSignals(False)
        self.videoTrackSlider.show()
        self.pauseRenderButton.show()
        self.stopRenderButton.show()
        self.livePreviewCheckbox.show()
        self.renderVideoButton.show()

    def set_image_mode(self):
        self.videoTrackSlider.blockSignals(True)
        self.videoTrackSlider.hide()
        self.pauseRenderButton.hide()
        self.stopRenderButton.hide()
        self.livePreviewCheckbox.hide()
        self.renderVideoButton.hide()

    def open_image(self, img: numpy.ndarray):
        height, width, channels = img.shape
        self.orig_wh = width, height
        
        if height > 1337:
            self.renderHeightBox.setValue(600)
            self.update_status(self.tr('a resolução da imagem é grande. para obter o melhor efeito, a altura de saída é definida como 600'))
        else:
            self.renderHeightBox.setValue(height // 120 * 120)
            
        self.set_current_frame(img)

    def open_video(self, path: Path):
        print(f"arquivo: {path}")
        cap = cv2.VideoCapture(str(path))
        print(f"cap: {cap} isOpened: {cap.isOpened()}")
        
        self.input_video = {
            "cap": cap,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "frames_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "orig_fps": int(cap.get(cv2.CAP_PROP_FPS)),
            "path": path
        }
        
        print(f"selfinput: {self.input_video}")
        self.orig_wh = (int(self.input_video["width"]), int(self.input_video["height"]))
        self.set_current_frame(self.get_current_video_frame())
        self.renderHeightBox.setValue(self.input_video["height"])
        self.videoTrackSlider.setMinimum(1)
        self.videoTrackSlider.setMaximum(self.input_video["frames_count"])
        self.videoTrackSlider.valueChanged.connect(lambda: self.set_current_frame(self.get_current_video_frame()))

    def render_image(self):
        target_file = pick_save_file(self, title='salvar frame como', suffix='.png')
        
        if not target_file and not self.current_frame:
            return None
        
        render_h = self.renderHeightBox.value()
        crop_wh = resize_to_height(self.orig_wh, render_h)
        image = cv2.resize(self.current_frame, crop_wh)
        
        if image.shape[1] % 4 != 0:
            image = trim_to_4width(image)
        
        image = self.nt_process(image)
        
        cv2.imwrite(str(target_file.resolve()), image)

    def render_video(self):
        target_file = pick_save_file(self, title='renderizar vídeo como', suffix='.mp4')

        render_data = {
            "target_file": target_file,
            "nt": self.nt,
            "input_video": self.input_video,
            "input_heigth": self.renderHeightBox.value()
        }
        
        self.setup_renderer()
        self.toggle_main_effect()
        self.videoRenderer.render_data = render_data
        self.thread.start()

    def nt_process(self, frame) -> ndarray:
        _ = self.nt.composite_layer(frame, frame, field=2, fieldno=2)
        
        ntsc_out_image = cv2.convertScaleAbs(_)
        ntsc_out_image[1:-1:2] = ntsc_out_image[0:-2:2] / 2 + ntsc_out_image[2::2] / 2
        
        return ntsc_out_image

    def nt_update_preview(self):
        current_frame_valid = isinstance(self.current_frame, ndarray)
        render_on_pause = self.pauseRenderButton.isChecked()
        
        if not current_frame_valid or (self.isRenderActive and not render_on_pause):
            return None

        if not self.mainEffect:
            self.render_preview(self.preview)
            
            return None

        ntsc_out_image = self.nt_process(self.preview)

        if self.compareMode:
            ntsc_out_image = numpy.concatenate((self.preview[:self.preview.shape[0] // 2], ntsc_out_image[ntsc_out_image.shape[0] // 2:]))

        self.render_preview(ntsc_out_image)

    @QtCore.pyqtSlot(object)
    def render_preview(self, img):
        image = QtGui.QImage(img.data.tobytes(), img.shape[1], img.shape[0], QtGui.QImage.Format_RGB888)\
            .rgbSwapped()
            
        if self.scale_pixmap:
            self.image_frame.setPixmap(QtGui.QPixmap.fromImage(image).scaledToHeight(480))
        else:
            self.image_frame.setPixmap(QtGui.QPixmap.fromImage(image))