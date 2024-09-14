import os
import sys
from pathlib import Path
import traceback

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QLibraryInfo
from PyQt5.QtCore import QFile, QTextStream
from PyQt5 import QtGui
import darkdetect

import colorama
# import qdarktheme

from app import VhsApp
from app import logger

import traceback
from halo import Halo


os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(QLibraryInfo.PluginsPath)

def crash_handler(etype, value, tb):
    logger.trace(value)
    
    traceback.print_exception(etype, value, tb)
    
    logger.error("exceção não detectada: {0}\n{1}".format(str(value), "\n".join(traceback.format_tb(tb))))
    
    sys.exit(1)
    
def cls():
    os.system('cls' if os.name=='vhs' else 'clear')

# instalar o manipulador de exceções
sys.excepthook = crash_handler

def main():
    translator = QtCore.QTranslator()
    locale = QtCore.QLocale.system().name()
    
    cls()
    
    print("vhs")
    # print(f"por cavassani)
    # print("")
    
    spinner = Halo(text='', color='white')
    spinner.start()

    # se executado pelo executável pyinstaller, o attr congelado será verdadeiro
    if getattr(sys, 'frozen', False):
        # _meipass contém o diretório temporário do pyinstaller
        base_dir = Path(sys._MEIPASS)
        locale_file = str((base_dir / 'translate' / f'{locale}.qm').resolve())
    else:
        base_dir = Path(__file__).absolute().parent
        locale_file = str((base_dir / 'translate' / f'{locale}.qm').resolve())

    # print(f"tente carregar o locale {locale}: {locale_file}")
    
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(QtGui.QPixmap("./icon.png")))
    app.installTranslator(translator)
    
    # qdarktheme.setup_theme("dark", corner_shape="sharp")
    
    spinner.stop()
    
    print("carregado.")
    
    if translator.load(locale_file):
        print(f'localização carregada: {locale}') # nome, diretório
    else:
        print("")
        print("usando tradução padrão")

    window = VhsApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()