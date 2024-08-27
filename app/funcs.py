from pathlib import Path

import numpy
from PyQt5.QtWidgets import QFileDialog


def resize_to_height(wh, target_h):
    w, h = wh
    k = target_h / h
    
    return int(w * k) // 2 * 2, target_h


def pick_save_file(self, title='renderizar como', pre_path='', suffix: str = None) -> Path:
    pick_filter = f"arquivo {suffix} (*{suffix});;todos os arquivos (*)"
    target_file = QFileDialog.getSaveFileName(self, title, '', pick_filter)
    
    print(f"salvamento escolhido como: {target_file}")
    
    if not target_file[0]:
        return None
    
    path = Path(target_file[0])
    
    if path.suffix != suffix:
        path = path.parent / (path.name + suffix)
        
    # if target_file[1] == f'File {suffix} (*{suffix})' and target_file[0][-4:] != suffix:
    #     target_file = target_file[0] + suffix
    # else:
    #     target_file = target_file[0]
    
    return path


def trim_to_4width(img: numpy.ndarray) -> numpy.ndarray:
    """
    trabalhar com crash caso a imagem não seja dividida por 4
    """
    height, width, channels = img.shape
    
    print(f"┃ wh da imagem: {width}x{height} w % 4 = {width % 4}")
    
    if width % 4 != 0:
        img = img[:, :width % 4 * -1]
        height, width, channels = img.shape
        
        print(f"┗ corrigido para o wh: {width}x{height} w % 4 = {width % 4}")
        
    return img