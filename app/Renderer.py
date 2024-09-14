import abc
import time
import os
from collections import defaultdict
from typing import Tuple, TypedDict

import cv2
from PyQt5 import QtCore
import ffmpeg
from imutils.video import FileVideoStream
import numpy
from numpy import ndarray

from app.logs import logger
from app.funcs import resize_to_height, trim_to_4width, expand_to_4width
from app.vhs import Vhs


class Config(TypedDict):
    orig_wh: Tuple[int, int]
    render_wh: Tuple[int, int]
    container_wh: Tuple[int, int]
    
    upscale_2x: bool
    lossless: bool

    next_frame_context: bool

    audio_process: bool
    audio_sat_beforevol: float
    audio_lowpass: int
    audio_noise_volume: float

class AbstractRenderer(QtCore.QObject):
    @staticmethod
    @abc.abstractmethod
    def apply_main_effect(vhs: Vhs, frame1, frame2, frameno: int):
        raise NotImplementedError()

class DefaultRenderer(AbstractRenderer):
    running = False
    mainEffect = True
    pause = False
    liveView = False
    newFrame = QtCore.pyqtSignal(object)
    frameMoved = QtCore.pyqtSignal(int)
    renderStateChanged = QtCore.pyqtSignal(bool)
    sendStatus = QtCore.pyqtSignal(str)
    increment_progress = QtCore.pyqtSignal()
    render_data = {}
    current_frame_index = 0
    show_frame_index = 0
    cap = None
    interlaced = False
    lossless = True
    framecount: int = 0
    videoend: int = 0
    buffer: dict[int, ndarray] = defaultdict(lambda: None)

    @staticmethod
    def apply_main_effect(vhs: Vhs, frame1, frame2, frameno: int):
        if frame2 is None:
            frame2 = frame1

        frame1 = vhs.composite_layer(frame1, frame1, field=0, fieldno=0, frameno=frameno)
        frame1 = cv2.convertScaleAbs(frame1)
        
        frame2 = cv2.copyMakeBorder(frame2, 1, 0, 0, 0, cv2.BORDER_CONSTANT)
        frame2 = vhs.composite_layer(frame2, frame2, field=2, fieldno=2, frameno=frameno)
        frame2 = cv2.convertScaleAbs(frame2)
        
        frame = frame1
        frame[1::2,:] = frame2[2::2,:]
        
        return frame

    def update_buffer(self):
        buf = self.buffer
        current_index = self.current_frame_index

        if buf[current_index] is None:
            if self.interlaced:
                self.capdetect.set(1, current_index)
                
                _, cframe = self.capdetect.read()
                
                # print("frame atual - cap detect")
                
                current_frame = cframe
            else:
                current_frame = self.cap.read()
        else:
            current_frame = buf[current_index]
            
        # print("frame atual")
            
        if (self.framecount % 2 == 0):
            framefortwo = True
        else:
            framefortwo = False
            
        if self.interlaced:
            self.capdetect.set(1, current_index + 1)
            _, cframe = self.capdetect.read()
            
            #print("próximo frame - cap detect")
            
            next_frame = cframe
            
            self.capdetect.set(1, current_index)
        else:
            next_frame = self.cap.read()
            
        # print("próximo frame")
        #
        # if next_frame is None and self.interlaced and framefortwo != True and self.videoend == 0:
        #     next_frame = current_frame
        #
        #     self.videoend = 1
        
        if current_index > 0:
            del buf[current_index-1]
            
        buf[current_index] = current_frame
        # print("buf atual:")
        # print(buf[current_index])
        
        buf[current_index+1] = next_frame
        # print("próximo buf:")
        # print(buf[current_index+1])

    def prepare_frame(self, frame):
        orig_wh = self.config.get("orig_wh")
        render_wh = self.config.get("render_wh")

        if orig_wh != render_wh:
            try:
                frame = cv2.resize(frame, render_wh)
            except Exception as e:
                logger.exception(e)
                
                raise e

        # solução alternativa de crash
        if render_wh[0] % 4 != 0:
            frame = expand_to_4width(frame)

        return frame

    def produce_frame(self):
        frame = self.buffer[self.current_frame_index]
        
        if frame is None or not self.running:
            self.sendStatus.emit(f'renderização finalizada. ret(debug):')
            
            return False

        render_wh = self.config.get("render_wh")
        upscale_2x = self.config.get("upscale_2x")

        self.increment_progress.emit()

        frame1 = self.prepare_frame(frame)
        
        if self.config.get('next_frame_context'):
            fr = self.buffer[self.current_frame_index + 1]
            
            if fr is not None:
                frame2 = self.prepare_frame(fr)
            else:
                frame2 = None
        else:
            frame2 = None

        if self.mainEffect:
            frame = self.apply_main_effect(
                self.render_data.get("vhs"),
                
                frame1,
                frame2,
                
                self.show_frame_index
            )
        else:
            frame = frame1

        frame = frame[:, 0:render_wh[0]]

        if self.current_frame_index % 10 == 0 or self.liveView:
            self.frameMoved.emit(self.current_frame_index)
            self.newFrame.emit(frame)

        if upscale_2x:
            container_wh = self.config.get("container_wh")
            
            frame = cv2.resize(frame, dsize=container_wh, interpolation=cv2.INTER_NEAREST)

        return frame

    def set_up(self):
        orig_wh = (
            self.render_data["input_video"]["width"],
            self.render_data["input_video"]["height"]
        )
        
        render_wh = resize_to_height(orig_wh, self.render_data["input_heigth"])
        container_wh = render_wh

        upscale_2x = self.render_data["upscale_2x"]
        
        if upscale_2x:
            container_wh = (
                render_wh[0] * 2,
                render_wh[1] * 2
            )

        self.config = Config(
            upscale_2x=upscale_2x,
            container_wh=container_wh,
            render_wh=render_wh,
            orig_wh=orig_wh,

            lossless=self.render_data["lossless"],
            framecount=self.render_data["framecount"],
            next_frame_context=True,

            audio_process=False,
            audio_sat_beforevol=4.5,
            audio_lowpass=10896,
            audio_noise_volume=0.03
        )

    def update_check(self, cap, frameindex):
        cap.set(1, frameindex)
        checkframe1, _ = cap.read()
        
        # cap.set(1, frameindex+1)
        # checkframe2, _ = cap.read()
        # cap.set(1, frameindex)

        return checkframe1
    
    def check_frame_stops(self, frameindex, framecount):
        if((frameindex > framecount) or (frameindex+1 > framecount)):
            return framecount
        
        return frameindex
    
    def update_chromaencoding(self, vhs: Vhs, frameindex):
        if (frameindex % 2 != 0):
            vhs._video_scanline_phase_shift_offset = 2
        else:
            vhs._video_scanline_phase_shift_offset = 0

    def run(self):
        self.set_up()
        self.running = True

        suffix = '.mkv'
        
        # print(self.config.get("lossless"))

        tmp_output = self.render_data['target_file'].parent / f'tmp_{self.render_data["target_file"].stem}{suffix}'

        fourccs = [
            cv2.VideoWriter_fourcc(*'mp4v'), # não funciona em mac os
            cv2.VideoWriter_fourcc(*'H264')
        ]

        # if self.config.get("lossless"):
        #     fourcc_choice = cv2.VideoWriter_fourcc(*'FFV1')
        # else:
        #     fourcc_choice = fourccs.pop(0)
        
        # processar arquivo temporário sem perda para melhor compressão durante encoding
        
        fourcc_choice = cv2.VideoWriter_fourcc(*'FFV1')
        
        if (self.interlaced):
            framerate = self.render_data["input_video"]["orig_fps"] / 2
        else:
            framerate = self.render_data["input_video"]["orig_fps"]
        
        self.framecount = self.config.get("framecount")
        
        # print(self.framecount)

        video = cv2.VideoWriter()

        open_result = False
        
        while not open_result:
            open_result = video.open(
                filename=str(tmp_output.resolve()),
                fourcc=fourcc_choice,
                fps=framerate,
                frameSize=self.config.get("container_wh")
            )
            
            logger.debug(f'resultado aberto de saída de vídeo: {open_result}')

        logger.debug(f'vídeo de entrada: {str(self.render_data["input_video"]["path"].resolve())}')
        logger.debug(f'saída temporária: {str(tmp_output.resolve())}')
        logger.debug(f'vídeo de saída: {str(self.render_data["target_file"].resolve())}')
        # logger.debug(f'processo de áudio: {self.process_audio}')
        logger.debug(f'áudio de processo: {str(self.config.get("audio_process"))}')

        self.current_frame_index = 0
        self.show_frame_index = 0
        
        self.renderStateChanged.emit(True)
        
        self.cap = FileVideoStream(path=str(self.render_data["input_video"]["path"]), queue_size=322).start()
        self.capdetect = self.render_data["input_video"]["cap"]
        
        checkframe = self.update_check(self.capdetect,self.current_frame_index)

        while self.running:
            if self.pause:
                self.sendStatus.emit(f"{status_string} [p]")
                
                time.sleep(0.3)
                
                continue
            
            if checkframe is False:
                logger.info(f"fim de vídeo ou erro de renderização: {status_string}")
                
                break
            
            self.update_chromaencoding(self.render_data.get("vhs"),self.show_frame_index)

            self.update_buffer()
            frame = self.produce_frame()
            
            # print(frame)            

            status_string = '[cv2] progresso da renderização: {current_frame_index}/{total}'.format(
                current_frame_index=self.show_frame_index,
                total=(self.framecount)
            )
            
            # print("string de status")
            #
            # if frame is False:
            #     logger.info(f"fim de vídeo ou erro de renderização: {status_string}")
            #
            #     break
            
            if self.interlaced:
                self.current_frame_index += 2
            else:
                self.current_frame_index += 1
                
            self.show_frame_index += 1
            
            # print("alterar frames")

            self.sendStatus.emit(status_string)
            
            # print("escrevendo vídeo")
            
            video.write(frame)

            # self.current_frame_index = self.check_frame_stops(self.current_frame_index,self.framecount)

            checkframe = self.update_check(self.capdetect,self.current_frame_index)

        video.release()

        orig_path = str(self.render_data["input_video"]["path"].resolve())
        orig_suffix = self.render_data["input_video"]["suffix"]
        target_suffix = self.render_data["target_file"].suffix
        result_path = str(self.render_data["target_file"].resolve())

        # fixme embelezar a renderização de arquivos e a detecção de áudio

        # self.sendStatus.emit(f'[ffmpeg] copiando áudio para {result_path}')

        orig = ffmpeg.input(orig_path)

        final_audio = orig.audio

        if(self.config.get('audio_process')):
            self.sendStatus.emit(f'[ffmpeg] preparando filtragem de áudio')

            # tmp_audio = self.render_data['target_file'].parent / f'tmp_audio_{self.render_data["target_file"].stem}.wav'
            tmp_audio = f"{self.render_data['target_file'].parent}/tmp_audio_{self.render_data['target_file'].stem}.wav"

            aud_ff_probe = ffmpeg.probe(orig_path)

            # aud_ff_video_stream = next((stream for stream in aud_ff_probe['streams'] if stream['codec_type'] == 'video'), None)
            # aud_ff_duration = aud_ff_video_stream['duration']
            aud_ff_duration = aud_ff_probe["format"]["duration"]

            aud_ff_audio_stream = next((stream for stream in aud_ff_probe['streams'] if stream['codec_type'] == 'audio'), None)
            aud_ff_srate = aud_ff_audio_stream['sample_rate']
            aud_ff_clayout = aud_ff_audio_stream['channel_layout']

            aud_ff_noise = ffmpeg.input(f'aevalsrc=-2+random(0):sample_rate={aud_ff_srate}:channel_layout=mono',f="lavfi",t=aud_ff_duration)
            aud_ff_noise = ffmpeg.filter((aud_ff_noise, aud_ff_noise), 'join', inputs=2, channel_layout='stereo')
            aud_ff_noise = aud_ff_noise.filter('volume', self.audio_noise_volume)

            aud_ff_fx = final_audio.filter("volume",self.audio_sat_beforevol).filter("alimiter",limit="0.5").filter("volume",0.8)
            aud_ff_fx = aud_ff_fx.filter("firequalizer",gain=f'if(lt(f,{self.audio_lowpass}), 0, -INF)')

            aud_ff_mix = ffmpeg.filter([aud_ff_fx, aud_ff_noise], 'amix').filter("firequalizer",gain='if(lt(f,13301), 0, -INF)')

            aud_ff_command = aud_ff_mix.output(tmp_audio,acodec='pcm_s24le',shortest=None)

            self.sendStatus.emit(f'[ffmpeg] filtragem de áudio preparada')
            logger.debug(aud_ff_command)
            logger.debug(' '.join(aud_ff_command.compile()))

            self.sendStatus.emit(f'[ffmpeg] iniciando a filtragem de áudio em {tmp_audio}')
            aud_ff_command.overwrite_output().global_args('-v', 'verbose').run()

            final_audio = ffmpeg.input(tmp_audio)
            final_audio = final_audio.audio

            self.sendStatus.emit(f'[ffmpeg] filtragem de áudio finalizada')
        else:
            self.sendStatus.emit(f'[ffmpeg] copiando áudio para {result_path}')

        temp_video_stream = ffmpeg.input(str(tmp_output.resolve()))
        # render_streams.append(temp_video_stream.video)

        if self.config.get("audio_process"):
            acodec = 'flac' if target_suffix == '.mkv' else 'copy'
            
            if (self.config.get("lossless")):
                ff_command = ffmpeg.output(temp_video_stream.video, final_audio, result_path, shortest=None, vcodec='copy', acodec=acodec)
            else:
                ff_command = ffmpeg.output(temp_video_stream.video, final_audio, result_path, shortest=None, vcodec='libx264', preset='slow', crf=16, **{'vf': 'setfield=tff'}, **{'flags': '+ildct+ilme'}, acodec=acodec)
        else:
            acodec = 'copy' if target_suffix == '.mkv' else 'aac'
            
            if (self.config.get("lossless")):
                ff_command = ffmpeg.output(temp_video_stream.video, final_audio, result_path, shortest=None, vcodec='copy', acodec=acodec, **{'b:a': '320k'})
            else:
                ff_command = ffmpeg.output(temp_video_stream.video, final_audio, result_path, shortest=None, vcodec='libx264', preset='slow', crf=16, **{'vf': 'setfield=tff'}, **{'flags': '+ildct+ilme'}, acodec=acodec, **{'b:a': '320k'})

        logger.debug(ff_command)
        logger.debug(' '.join(ff_command.compile()))
        
        try:
            ff_command.overwrite_output().run()
        except ffmpeg.Error as e:
            if orig_suffix == '.gif':
                ff_command = ffmpeg.output(temp_video_stream.video, result_path, shortest=None)
            else:
                ff_command = ffmpeg.output(temp_video_stream.video, result_path, shortest=None, vcodec='copy')
                
            ff_command.overwrite_output().run()

        self.sendStatus.emit('[ffmpeg] cópia de áudio concluída')

        tmp_output.unlink()
        
        if self.config.get("audio_process"):
            if os.path.exists(tmp_audio):
                os.remove(tmp_audio)

        self.renderStateChanged.emit(False)
        self.sendStatus.emit('[feito] renderização completa')

    def stop(self):
        self.running = False