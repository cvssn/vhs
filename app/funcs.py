from pathlib import Path
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
    
    if target_file[1] == f'arquivo {suffix} (*{suffix})' and target_file[0][-4:] != suffix:
        target_file = target_file[0] + suffix
    else:
        target_file = target_file[0]
        
    return Path(target_file)