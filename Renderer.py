import time
from alive_progress import alive_bar

import cv2
from PyQt5 import QtCore
import ffmpeg

from funcs import resize_to_height


class Renderer(QtCore.QObject):
    running = False
    mainEffect = True
    pause = False
    lineView = False
    newFrame = QtCore.pyqtSignal(object)
    frameMoved = QtCore.pyqtSignal(int)
    renderStateChanged = QtCore.pyqtSignal(bool)
    sendStatus = QtCore.pyqtSignal(str)
    render_data = {}
    
    def run(self):
        self.running = True
        
        ttmp_output = self.render_data['target_file'].parent / f'tmp_{self.render_data["target_file"].name}'
        
        orig_wh = (self.render_data["input_video"]["width"], self.render_data["input_video"]["height"])
        render_wh = resize_to_height(orig_wh, self.render_data["input_heigth"])
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(str(tmp_output.resolve()), fourcc, self.render_data["input_video"]["orig_fps"], render_wh)
        
        frame_index = 0
        self.renderStateChanged.emit(True)
        
        with alive_bar(self.render_data["input_video"]["frames_count"]) as progress_bar:
            while self.render_data["input_video"]["cap"].isOpened():
                if self.pause:
                    self.sendStatus.emit(f"{status_string} [P]")
                    time.sleep(0.3)
                    
                    continue

                # captura de frame por frame
                frame_index += 1
                self.render_data["input_video"]["cap"].set(1, frame_index)
                ret, frame = self.render_data["input_video"]["cap"].read()
                
                if not ret or not self.running:
                    break

                if orig_wh != render_wh:
                    frame = cv2.resize(frame, render_wh)

                if self.mainEffect:
                    frame = self.render_data["nt"].composite_layer(frame, frame, field=2, fieldno=2)
                    frame = cv2.convertScaleAbs(frame)
                    frame[1:-1:2] = frame[0:-2:2] / 2 + frame[2::2] / 2

                if frame_index % 10 == 0 or self.liveView:
                    self.frameMoved.emit(frame_index)
                    self.newFrame.emit(frame)

                progress_bar()
                status_string = f'progresso: {frame_index}/{self.render_data["input_video"]["frames_count"]}'
                
                self.sendStatus.emit(status_string)
                video.write(frame)

        video.release()

        audio_orig = (ffmpeg.input(str(self.render_data["input_video"]["path"].resolve())))
        self.sendStatus.emit('áudio original extraído')
        video = ffmpeg.input(str(tmp_output.resolve()))
        (ffmpeg.output(video.video, audio_orig.audio, str(self.render_data["target_file"].resolve()), shortest=None, vcodec='copy').overwrite_output().run())
        self.sendStatus.emit('cópia de áudio feita')
        tmp_output.unlink()
        self.renderStateChanged.emit(False)
        self.sendStatus.emit('renderiação feita')

    def stop(self):
        self.running = False