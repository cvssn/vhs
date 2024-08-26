import sys

from pathlib import Path
import cv2
import numpy
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QSlider, QHBoxLayout, QLabel, QCheckBox, QFileDialog
from numpy import ndarray

from Renderer import Renderer
from funcs import resize_to_height
from vhs import random_ntsc
from ui import mainWindow
from ui.DoubleSlider import DoubleSlider


class ExampleApp(QtWidgets.QMainWindow, mainWindow.Ui_MainWindow):
    def __init__(self):
        self.current_frame = False
        self.input_video = {}
        self.compareMode = False
        self.isRenderActive = False
        self.mainEffect = True
        self.nt_controls = {}
        
        super().__init__() # isso é necessário aqui para acessar variáveis, métodos etc. no arquivo design.py
        self.setupUi(self) # isso é necessário para inicializar nosso design
        
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
            "_color_bleed_horiz": self.tr("sangramento de cor horizontal"),
            "_color_bleed_vert": self.tr("sangramento de cor vertical"),
            "_video_chroma_noise": self.tr("ruído cromático de vídeo"),
            "_video_chroma_phase_noise": self.tr("Video chroma phase noise"),
            "_video_chroma_loss": self.tr("perda de croma de vídeo"),
            "_video_noise": self.tr("ruído de vídeo"),
            "_video_scanline_phase_shift": self.tr("mudança de fase da linha de varredura de vídeo"),
            "_video_scanline_phase_shift_offset": self.tr("mudança de fase da linha de varredura de vídeo"),
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
            "_output_ntsc": self.tr("output do ntsc")
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
        
        self.previewHeightBox.valueChanged.connect(self.set_current_frame)

        self.openFile.clicked.connect(self.open_video)
        self.renderVideoButton.clicked.connect(self.render)
        self.stopRenderButton.clicked.connect(self.stop_render)
        self.compareModeButton.stateChanged.connect(self.toggle_compare_mode)
        self.toggleMainEffect.stateChanged.connect(self.toggle_main_effect)
        self.pauseRenderButton.clicked.connect(self.toggle_pause_render)
        self.livePreviewCheckbox.stateChanged.connect(self.toggle_live_preview)

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
            print("configurando o primeiro renderizador")
            
        # criação de um tópico
        self.thread = QtCore.QThread()
        
        # criação de um objeto para executar código em outra thread
        self.videoRenderer = Renderer()
        
        # transferência do objeto para outra thread
        self.videoRenderer.moveToThread(self.thread)
        
        # conectar todos os sinais e slots
        self.videoRenderer.newFrame.connect(self.update_preview)
        self.videoRenderer.frameMoved.connect(self.videoTrackSlider.setValue)
        self.videoRenderer.renderStateChanged.connect(self.set_render_state)
        self.videoRenderer.sendStatus.connect(self.update_status)
        
        # conecta o sinal de início do thread ao método run do objeto que deve executar o código em outro thread
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

            print(f"configurar o slider {type(value)} {parameter_name} para {value}")
        
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
        
    def set_current_frame(self):
        preview_h = self.previewHeightBox.value()
        
        if not self.input_video or preview_h < 10:
            return None
        
        frame_no = self.videoTrackSlider.value()
        self.input_video["cap"].set(1, frame_no)
        ret, frame = self.input_video["cap"].read()

        orig_wh = (int(self.input_video["width"]), int(self.input_video["height"]))
        
        try:
            crop_wh = resize_to_height(orig_wh, preview_h)
            self.current_frame = cv2.resize(frame, crop_wh)
        except ZeroDivisionError:
            self.update_status("ZeroDivisionError :DDDDDD")
            
            pass
        
        self.nt_update_preview()
        
    def open_video(self):
        file = QtWidgets.QFileDialog.getOpenFileName(self, "selecione o arquivo")
        
        # abrir a caixa de diálogo de seleção de diretório e defina o valor da variável igual ao caminho para o diretório selecionado
        if file:
            norm_path = Path(file[0])
            print(f"arquivo: {norm_path}")
            
            cap = cv2.VideoCapture(str(norm_path))
            print(f"cap: {cap} isopened: {cap.isOpened()}")
            
            self.input_video = {
                "cap": cap,
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "frames_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "orig_fps": int(cap.get(cv2.CAP_PROP_FPS)),
                "path": norm_path
            }
            
            print(f"selfinput: {self.input_video}")
            
            self.set_current_frame()
            self.renderHeightBox.setValue(self.input_video["height"])
            self.videoTrackSlider.setMinimum(1)
            self.videoTrackSlider.setMaximum(self.input_video["frames_count"])
            self.videoTrackSlider.valueChanged.connect(self.set_current_frame)

    def render(self):
        # file_dialog = QtWidgets.QFileDialog()
        # file_dialog.setNameFilters([self.tr('arquivo mp4 (*.mp4)'), self.tr('todos os arquivos (*)')])
        # file_dialog.setDefaultSuffix('.mp4')
        target_file = QFileDialog.getSaveFileName(self, 'renderizar como', '', "vídeo mp4 (*.mp4);;todos os arquivos (*)")
        
        print(f"salvamento escolhido como: {target_file}")
        
        if not target_file[0]:
            return None
        
        if target_file[1] == 'vídeo mp4 (*.mp4)' and target_file[0][-4:] != '.mp4':
            target_file = target_file[0] + '.mp4'
        else:
            target_file = target_file[0]

        target_file = Path(target_file)
        
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

    def nt_update_preview(self):
        current_frame_valid = isinstance(self.current_frame, ndarray)
        render_on_pause = self.pauseRenderButton.isChecked()
        
        if not current_frame_valid or (self.isRenderActive and not render_on_pause):
            return None

        if not self.mainEffect:
            self.update_preview(self.current_frame)
            return None

        frame = self.nt.composite_layer(self.current_frame, self.current_frame, field=2, fieldno=2)
        norm_image = cv2.convertScaleAbs(frame)
        norm_image[1:-1:2] = norm_image[0:-2:2] / 2 + norm_image[2::2] / 2
        
        if self.compareMode:
            norm_image = numpy.concatenate((self.current_frame[:self.current_frame.shape[0] // 2], norm_image[norm_image.shape[0] // 2:]))

        self.update_preview(norm_image)

    @QtCore.pyqtSlot(object)
    def update_preview(self, img):
        image = QtGui.QImage(img.data, img.shape[1], img.shape[0], QtGui.QImage.Format_RGB888).rgbSwapped()
        self.image_frame.setPixmap(QtGui.QPixmap.fromImage(image))


def main():
    translator = QtCore.QTranslator()
    
    locale = QtCore.QLocale.system()
    
    if translator.load(locale + '.qm', 'translate'):
        print(f'localização carregada: {locale}') # nome, dir
    
    app = QtWidgets.QApplication(sys.argv) # nova instância qapplication
    app.installTranslator(translator)
    
    window = ExampleApp() # criação de um objeto da classe exampleapp
    window.show() # mostrando a janela
    app.exec_() # inicialização do aplicativo


if __name__ == '__main__': # se executarmos o arquivo diretamente em vez de importar
    main() # executar a função main()