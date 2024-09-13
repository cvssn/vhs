import json
from pathlib import Path
from random import randint
from typing import Tuple, Union, List, Dict
import requests
import cv2
import numpy
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QSlider, QHBoxLayout, QLabel, QCheckBox, QInputDialog, QPushButton
from numpy import ndarray

from app.InterlacedRenderer import InterlacedRenderer
from app.config_dialog import ConfigDialog
from app.logs import logger
from app.Renderer import DefaultRenderer
from app.funcs import resize_to_height, pick_save_file, trim_to_4width, set_ui_element
from app.vhs import random_vhs, Vhs
from ui import mainWindow
from ui.DoubleSlider import DoubleSlider


class VhsApp(QtWidgets.QMainWindow, mainWindow.Ui_MainWindow):
    def __init__(self):
        self.videoRenderer: DefaultRenderer = None
        self.current_frame: numpy.ndarray = False
        self.next_frame: numpy.ndarray = False
        self.scale_pixmap = False
        self.input_video = {}
        self.templates = {}
        self.orig_wh: Tuple[int, int] = (0, 0)
        self.compareMode: bool = False
        self.isRenderActive: bool = False
        self.mainEffect: bool = True
        self.loss_less_mode: bool = False
        self.__video_output_suffix = ".mp4" # ou .mkv para ffv1
        self.ProcessAudio: bool = False
        self.vhs_controls = {}
        self.vhs: Vhs = None
        self.pro_mode_elements = []
        
        # necessário para acessar variáveis, métodos, etc. no arquivo design.py
        super().__init__()
        
        self.supported_video_type = ['.mp4', '.mkv', '.avi', '.webm', '.mpg', '.gif']
        self.supported_image_type = ['.png', '.jpg', '.jpeg', '.webp']
        
        self.setupUi(self) # necessário para inicializar nosso design
        
        self.strings = {
            "_composite_preemphasis": self.tr("pré-ênfase composta"),
            "_vhs_out_sharpen": self.tr("vhs com nitidez"),
            "_vhs_edge_wave": self.tr("onda de borda"),
            "_output_vhs_tape_speed": self.tr("velocidade da fita vhs"),
            "_ringing": self.tr("ringing"),
            "_ringing_power": self.tr("poder de ringing"),
            "_ringing_shift": self.tr("mudança de ringing"),
            "_freq_noise_size": self.tr("tamanho do ruído de frequência"),
            "_freq_noise_amplitude": self.tr("amplitude de ruído de frequência"),
            "_color_bleed_horiz": self.tr("bleed de cor horizontal"),
            "_color_bleed_vert": self.tr("bleed de cor vertical"),
            "_video_chroma_noise": self.tr("ruído de croma de vídeo"),
            "_video_chroma_phase_noise": self.tr("ruído de fase croma de vídeo"),
            "_video_chroma_loss": self.tr("perda de croma de vídeo"),
            "_video_noise": self.tr("ruído de vídeo"),
            "_video_scanline_phase_shift": self.tr("mudança de fase da linha de varredura de vídeo"),
            "_video_scanline_phase_shift_offset": self.tr("mudança de fase da linha de varredura de vídeo"),
            "_head_switching_speed": self.tr("velocidade de movimento do interruptor principal"),
            "_vhs_head_switching": self.tr("troca de cabeça"),
            "_color_bleed_before": self.tr("sangramento de cor anterior"),
            "_enable_ringing2": self.tr("habilitar ringing2"),
            "_composite_in_chroma_lowpass": self.tr("composto em chroma lowpass"),
            "_composite_out_chroma_lowpass": self.tr("passagem baixa de croma composto"),
            "_composite_out_chroma_lowpass_lite": self.tr("composição chroma lowpass lite"),
            "_emulating_vhs": self.tr("emulação vhs"),
            "_nocolor_subcarrier": self.tr("subportadora nocolor"),
            "_vhs_chroma_vert_blend": self.tr("misturar vhs chroma vert"),
            "_vhs_svideo_out": self.tr("saída de vídeo vhs"),
            "_output_vhs": self.tr("output de vhs"),
            "_black_line_cut": self.tr("cortar 2% da linha preta")
        }
        
        self.add_slider("_composite_preemphasis", 0, 10, float)
        self.add_slider("_vhs_out_sharpen", 1, 5)
        self.add_slider("_vhs_edge_wave", 0, 10)
        # self.add_slider("_output_vhs_tape_speed", 0, 10)
        self.add_slider("_ringing", 0, 1, float, pro=True)
        self.add_slider("_ringing_power", 0, 10)
        self.add_slider("_ringing_shift", 0, 3, float, pro=True)
        self.add_slider("_freq_noise_size", 0, 2, float, pro=True)
        self.add_slider("_freq_noise_amplitude", 0, 5, pro=True)
        self.add_slider("_color_bleed_horiz", 0, 10)
        self.add_slider("_color_bleed_vert", 0, 10)
        self.add_slider("_video_chroma_noise", 0, 16384)
        self.add_slider("_video_chroma_phase_noise", 0, 50)
        self.add_slider("_video_chroma_loss", 0, 800)
        self.add_slider("_video_noise", 0, 4200)
        self.add_slider("_video_scanline_phase_shift", 0, 270, pro=True)
        self.add_slider("_video_scanline_phase_shift_offset", 0, 3, pro=True)

        self.add_slider("_head_switching_speed", 0, 100)

        self.add_checkbox("_vhs_head_switching", (1, 1))
        self.add_checkbox("_color_bleed_before", (1, 2), pro=True)
        self.add_checkbox("_enable_ringing2", (2, 1), pro=True)
        self.add_checkbox("_composite_in_chroma_lowpass", (2, 2), pro=True)
        self.add_checkbox("_composite_out_chroma_lowpass", (3, 1), pro=True)
        self.add_checkbox("_composite_out_chroma_lowpass_lite", (3, 2), pro=True)
        self.add_checkbox("_emulating_vhs", (4, 1))
        self.add_checkbox("_nocolor_subcarrier", (4, 2), pro=True)
        self.add_checkbox("_vhs_chroma_vert_blend", (5, 1), pro=True)
        self.add_checkbox("_vhs_svideo_out", (5, 2), pro=True)
        self.add_checkbox("_output_vhs", (6, 1), pro=True)
        self.add_checkbox("_black_line_cut", (1, 2), pro=False)
        
        self.renderHeightBox.valueChanged.connect(lambda: self.set_current_frames(*self.get_current_video_frames()))
        self.openFile.clicked.connect(self.open_file)
        self.renderVideoButton.clicked.connect(self.render_video)
        self.saveImageButton.clicked.connect(self.render_image)
        self.stopRenderButton.clicked.connect(self.stop_render)
        self.compareModeButton.stateChanged.connect(self.toggle_compare_mode)
        self.toggleMainEffect.stateChanged.connect(self.toggle_main_effect)
        self.LossLessCheckBox.stateChanged.connect(self.lossless_exporting)
        # self.ProcessAudioCheckBox.stateChanged.connect(self.audio_filtering)
        self.pauseRenderButton.clicked.connect(self.toggle_pause_render)
        self.livePreviewCheckbox.stateChanged.connect(self.toggle_live_preview)
        self.refreshFrameButton.clicked.connect(self.nt_update_preview)
        self.openImageUrlButton.clicked.connect(self.open_image_by_url)
        self.exportImportConfigButton.clicked.connect(self.export_import_config)
        
        # self.ProcessAudioCheckBox.hide()
        
        # aguardando por outra branch
        
        self.ProMode.clicked.connect(
            lambda: self.set_pro_mode(self.ProMode.isChecked())
        )
        
        self.seedSpinBox.valueChanged.connect(self.update_seed)
        presets = [18, 31, 38, 44]
        self.seedSpinBox.setValue(presets[randint(0, len(presets) - 1)])

        self.progressBar.setValue(0)
        self.progressBar.setMinimum(1)
        self.progressBar.hide()

        self.add_builtin_templates()
        
    def add_builtin_templates(self):
        try:
            # todo: se online não estiver disponível, carregue a partir do arquivo (é necessário que o arquivo seja incluído nas especificações de construção)
            res = requests.get('https://raw.githubusercontent.com/cvssn/vhs/master/builtin_templates.json')
            
            if not res.ok:
                return
            
            self.templates = json.loads(res.content)
        except Exception as e:
            logger.exception(f'json não foi carregado: {e}')
            
        for name, values in self.templates.items():
            button = QPushButton()
            button.setText(name)
            
            set_values = (
                lambda v: lambda: self.vhs_set_config(v)
            )(values)
            
            button.clicked.connect(set_values)
            
            self.templatesLayout.addWidget(button)
            
    def get_render_class(self):
        is_interlaced = False # obter estado da escolha ui
        
        if is_interlaced:
            return InterlacedRenderer
        else:
            return DefaultRenderer
        
    def setup_renderer(self):
        try:
            self.update_status("encerrando o renderizador anterior")
            logger.debug("encerrando o renderizador anterior")
            
            self.thread.quit()
            
            self.update_status("aguardando renderização anterior")
            logger.debug("aguardando renderização anterior")
            
            self.thread.wait()
        except AttributeError:
            logger.debug("configurar primeira renderização")
            
        # criação de um tópico
        self.thread = QtCore.QThread()
        
        # criação de um objeto para executar código em outro thread
        RendererClass = self.get_render_class()
        self.videoRenderer = RendererClass()
        
        # transferência de objeto para outra thread
        self.videoRenderer.moveToThread(self.thread)
        
        # após o qual conectaremos todos os sinais e slots
        self.videoRenderer.newFrame.connect(self.render_preview)
        self.videoRenderer.frameMoved.connect(self.videoTrackSlider.setValue)
        self.videoRenderer.renderStateChanged.connect(self.set_render_state)
        self.videoRenderer.sendStatus.connect(self.update_status)
        self.videoRenderer.increment_progress.connect(self.increment_progress)
        
        # conectar o sinal de início da thread ao método run do objeto que deve executar o código em outra thread
        self.thread.started.connect(self.videoRenderer.run)
        
    @QtCore.pyqtSlot()
    def stop_render(self):
        self.videoRenderer.stop()
        
    @QtCore.pyqtSlot()
    def increment_progress(self):
        self.progressBar.setValue(self.progressBar.value() + 1)
        
    @QtCore.pyqtSlot()
    def toggle_compare_mode(self):
        state = self.sender().isChecked()
        
        self.compareMode = state
        self.vhs_update_preview()

    @QtCore.pyqtSlot()
    def toggle_pause_render(self):
        button = self.sender()
        
        if not self.isRenderActive:
            self.update_status("a renderização não está em execução")
            
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
        
        self.vhs_update_preview()

    @QtCore.pyqtSlot()
    def lossless_exporting(self):
        lossless_state = self.LossLessCheckBox.isChecked()

        self.loss_less_mode = lossless_state
        self.__video_output_suffix = '.mkv' if lossless_state else '.mp4'
        
        try:
            self.videoRenderer.lossless = lossless_state
            
            logger.debug(f"lossless: {str(lossless_state)}")
        except AttributeError:
            pass

    def audio_filtering(self):
        # state = self.ProcessAudioCheckBox.isChecked()
        
        state = False # solução alternativa
        
        self.ProcessAudio = state
        
        try:
            self.videoRenderer.audio_process = state
            
            logger.debug(f"processar áudio: {str(state)}")
        except AttributeError:
            pass

    @QtCore.pyqtSlot(int)
    def update_seed(self, seed):
        self.vhs = random_vhs(seed)
        self.vhs._enable_ringing2 = True
        
        self.sync_vhs_to_sliders()

    @QtCore.pyqtSlot(str)
    def update_status(self, string):
        logger.info('[STATUS DE GUI] ' + string)
        
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

        if is_render_active:
            self.progressBar.show()
        else:
            self.progressBar.hide()

        self.NearestUpScale.setEnabled(not is_render_active)

    def sync_nt_to_sliders(self):
        for parameter_name, element in self.nt_controls.items():
            value = getattr(self.nt, parameter_name)

            # necessário porque alguns parâmetros que possuem um tipo float real, mas na interface,
            # o slide é simplificado para int. No entanto, ao definir os parâmetros iniciais que
            # ocorrem aqui, você precisa definir a partir dos parâmetros iniciais que flutuam
            if isinstance(element, QSlider) and isinstance(value, float):
                value = int(value)

            set_ui_element(element, value)

            related_label = element.parent().findChild(QLabel, parameter_name)
            
            if related_label:
                related_label.setText(str(value)[:7])

            logger.debug(f"configurar o slider {type(value)} {parameter_name} para {value}")
            
        self.vhs_update_preview()

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

        logger.debug(f"configurar {parameter_name} para {value}")
        
        setattr(self.vhs, parameter_name, value)
        
        self.vhs_update_preview()

    def add_checkbox(self, param_name, pos, pro=False):
        checkbox = QCheckBox()
        checkbox.setText(self.strings[param_name])
        checkbox.setObjectName(param_name)
        checkbox.stateChanged.connect(self.value_changed_slot)
        # checkbox.mouseReleaseEvent(lambda: self.controls_set())
        
        self.vhs_controls[param_name] = checkbox
        self.checkboxesLayout.addWidget(checkbox, pos[0], pos[1])

        if pro:
            self.pro_mode_elements.append(checkbox)
            
            checkbox.hide()

    @QtCore.pyqtSlot(bool)
    def set_pro_mode(self, state):
        for frame in self.pro_mode_elements:
            if state:
                frame.show()
            else:
                frame.hide()

    def add_slider(self, param_name, min_val, max_val, slider_value_type: Union[int, float] = int, pro=False):
        ly = QHBoxLayout()
        
        slider_frame = QtWidgets.QFrame()
        slider_frame.setLayout(ly)

        if pro:
            self.pro_mode_elements.append(slider_frame)
            
            slider_frame.hide()

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
        # label.setText(description or name)
        label.setText(self.strings[param_name])

        # todo: faça um randomizador em vez de boxe
        # box.setMinimum(min_val)
        # box.setMaximum(max_val)
        # box.valueChanged.connect(slider.setValue)
        
        # slider.valueChanged.connect(box.setValue)
        
        value_label = QLabel()
        value_label.setObjectName(param_name)
        
        # slider.valueChanged.connect(lambda intval: value_label.setText(str(intval)))

        ly.addWidget(label)
        ly.addWidget(slider)
        # slider_layout.addWidget(box)
        ly.addWidget(value_label)

        self.nt_controls[param_name] = slider
        self.slidersLayout.addWidget(slider_frame)

    def get_current_video_frames(self):
        preview_h = self.renderHeightBox.value()
        
        if not self.input_video or preview_h < 10:
            return None, None
        
        frame_no = self.videoTrackSlider.value()
        self.input_video["cap"].set(1, frame_no)
        ret, frame1 = self.input_video["cap"].read()

        # ler o próximo quadro
        ret, frame2 = self.input_video["cap"].read()
        
        if not ret:
            frame2 = frame1

        return frame1, frame2

    def resize_to_preview_frame(self, frame):
        preview_h = self.renderHeightBox.value()
        
        try:
            crop_wh = resize_to_height(self.orig_wh, preview_h)
            
            frame = cv2.resize(frame, crop_wh)
        except ZeroDivisionError:
            self.update_status("zerodivisionerror :)")

        if frame.shape[1] % 4 != 0:
            frame = trim_to_4width(frame)

        return frame

    def set_current_frames(self, frame1: ndarray, frame2=None):
        current_frame_valid = isinstance(frame1, ndarray)
        
        preview_h = self.renderHeightBox.value()
        
        if not current_frame_valid or preview_h < 10:
            self.update_status("tentando definir o quadro atual inválido")
            
            return None

        if frame2 is None:
            frame2 = frame1.copy()

        self.current_frame = self.resize_to_preview_frame(frame1)
        self.next_frame = self.resize_to_preview_frame(frame2)

        self.vhs_update_preview()

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
            img = cv2.imdecode(numpy.fromfile(path, dtype=numpy.uint8), cv2.IMREAD_COLOR)
            
            self.set_image_mode()
            self.open_image(img)
        else:
            self.update_status(f"tipo de arquivo não suportado: {file_suffix}")

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

    def set_render_heigth(self, height):
        if height > 600:
            self.renderHeightBox.setValue(600)
            
            self.update_status(
                self.tr('a resolução da imagem é grande. para obter o melhor efeito, a altura de saída é definida como 600'))
        else:
            self.renderHeightBox.setValue(height // 120 * 120)

    def open_image(self, img: numpy.ndarray):
        self.setup_renderer()
        
        height, width, channels = img.shape
        
        self.orig_wh = width, height

        self.set_render_heigth(height)

        self.set_current_frames(img)

    def vhs_get_config(self):
        values = {}
        
        element: Union[QCheckBox, QSlider, DoubleSlider]
        
        for parameter_name, element in self.nt_controls.items():
            if isinstance(element, QCheckBox):
                value = element.isChecked()
            elif isinstance(element, (QSlider, DoubleSlider)):
                value = element.value()

            values[parameter_name] = value

        return values

    def vhs_set_config(self, values: List[Dict[str, Union[int, float]]]):
        for parameter_name, value in values.items():
            setattr(self.vhs, parameter_name, value)

        self.sync_vhs_to_sliders()

    def open_video(self, path: Path):
        self.setup_renderer()
        logger.debug(f"arquivo: {path}")
        
        cap = cv2.VideoCapture(str(path.resolve()))
        logger.debug(f"cap: {cap} isopened: {cap.isOpened()}")
        
        self.input_video = {
            "cap": cap,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "frames_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "orig_fps": cap.get(cv2.CAP_PROP_FPS),
            "path": path,
            "suffix": path.suffix.lower()
        }
        
        logger.debug(f"selfinput: {self.input_video}")
        
        self.orig_wh = (int(self.input_video["width"]), int(self.input_video["height"]))
        self.set_render_heigth(self.input_video["height"])
        self.set_current_frames(*self.get_current_video_frames())
        self.videoTrackSlider.setMinimum(1)
        self.videoTrackSlider.setMaximum(self.input_video["frames_count"])
        
        self.videoTrackSlider.valueChanged.connect(
            lambda: self.set_current_frames(*self.get_current_video_frames())
        )
        
        self.progressBar.setMaximum(self.input_video["frames_count"])

    def render_image(self):
        target_file = pick_save_file(self, title='salvar frame como', suffix='.png')
        
        if target_file is None or not isinstance(self.current_frame, ndarray):
            return None
        
        render_h = self.renderHeightBox.value()
        crop_wh = resize_to_height(self.orig_wh, render_h)
        image = cv2.resize(self.current_frame, crop_wh)
        
        if image.shape[1] % 4 != 0:
            image = trim_to_4width(image)
            
        image = self.videoRenderer.apply_main_effect(self.nt, frame1=image)
        is_success, im_buf_arr = cv2.imencode(".png", image)
        
        if not is_success:
            self.update_status("erro ao salvar (!is_success)")
            
            return None
        
        im_buf_arr.tofile(target_file)

    def render_video(self):
        if self.input_video['suffix'] == ".gif":
            suffix = self.input_video['suffix']
        else:
            suffix = self.__video_output_suffix
            
        target_file = pick_save_file(self, title='renderizar vídeo como', suffix=suffix)
        
        if not target_file:
            return None
        
        render_data = {
            "target_file": target_file,
            "vhs": self.vhs,
            "input_video": self.input_video,
            
            "input_heigth": self.renderHeightBox.value(),
            "upscale_2x": self.NearestUpScale.isChecked()
        }
        
        self.setup_renderer()
        self.toggle_main_effect()
        self.lossless_exporting()
        self.audio_filtering()
        
        self.progressBar.setValue(1)
        self.videoRenderer.render_data = render_data
        self.thread.start()

    def vhs_process(self, frame) -> ndarray:
        _ = self.vhs.composite_layer(frame, frame, field=2, fieldno=2)
        
        vhs_out_image = cv2.convertScaleAbs(_)
        vhs_out_image[1:-1:2] = vhs_out_image[0:-2:2] / 2 + vhs_out_image[2::2] / 2
        
        return vhs_out_image

    def vhs_update_preview(self):
        current_frame_valid = isinstance(self.current_frame, ndarray)
        
        render_on_pause = self.pauseRenderButton.isChecked()
        
        if not current_frame_valid or (self.isRenderActive and not render_on_pause):
            return None

        if not self.mainEffect:
            self.render_preview(self.current_frame)
            
            return None

        vhs_out_image = self.videoRenderer.apply_main_effect(self.nt, self.current_frame, self.next_frame)

        if self.compareMode:
            vhs_out_image = numpy.concatenate(
                (self.current_frame[:self.current_frame.shape[0] // 2], vhs_out_image[vhs_out_image.shape[0] // 2:])
            )

        self.render_preview(vhs_out_image)

    def export_import_config(self):
        config = self.vhs_get_config()
        config_json = json.dumps(config, indent=2)

        dialog = ConfigDialog()
        dialog.configJsonTextField.setPlainText(config_json)
        dialog.configJsonTextField.selectAll()

        code = dialog.exec_()
        
        if code:
            config_json = dialog.configJsonTextField.toPlainText()
            config = json.loads(config_json)
            
            self.nt_set_config(config)

    @QtCore.pyqtSlot(object)
    def render_preview(self, img: ndarray):
        # https://stackoverflow.com/questions/41596940/qimage-skews-some-images-but-not-others

        height, width, _ = img.shape
        
        # calcular o número total de bytes no quadro
        totalBytes = img.nbytes
        
        # divida pelo número de linhas
        bytesPerLine = int(totalBytes / height)

        image = QtGui.QImage(img.tobytes(), width, height, bytesPerLine, QtGui.QImage.Format_RGB888) \
            .rgbSwapped()

        max_h = self.image_frame.height()
        
        if height > max_h:
            self.image_frame.setPixmap(QtGui.QPixmap.fromImage(image).scaledToHeight(max_h))
        else:
            self.image_frame.setPixmap(QtGui.QPixmap.fromImage(image))