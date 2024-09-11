import os
import sys
from pathlib import Path

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QLibraryInfo

from app.logs import logger
from app.VhsApp import VhsApp

os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(
    QLibraryInfo.PluginsPath
)


def crash_handler(type, value, tb):
    logger.exception("excessão não capturada: {0}".format(str(value)))
    
    exit(1)
    
# instalar handler de excessão
sys.excepthook = crash_handler

def main():
    translator = QtCore.QTranslator()
    locale = QtCore.QLocale.system().name()
    
    # caso seja rodado pelo executável pyinstaller, attr congelado será verdadeiro
    if getattr(sys, 'frozen', False):
        # _meipass contém o diretório de pyinstaller temporário
        base_dir = Path(sys._MEIPASS)
        
        locale_file = str((base_dir / 'translate' / f'{locale}.qm').resolve())
    else:
        base_dir = Path(__file__).absolute().parent
        
        locale_file = str((base_dir / 'translate' / f'{locale}.qm').resolve())
        
    print(f"tente carregar o locale {locale}: {locale_file}")
    
    if translator.load(locale_file):
        print(f'localização carregada: {locale}') # nome, diretório
    else:
        print("utilizando tradução padrão")
        
    app = QtWidgets.QApplication(sys.argv)
    app.installTranslator(translator)
    
    window = VhsApp()
    window.show()
    
    sys.exit(app.exec_())
    
    
if __name__ == '__main__':
    main()