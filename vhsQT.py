import sys
from pathlib import Path

from PyQt5 import QtCore, QtWidgets

from app.VhsApp import VhsApp


def main():
    translator = QtCore.QTranslator()
    locale = QtCore.QLocale.system().name()
    
    # caso seja rodado pelo executável pyinstaller, attr congelado será verdadeiro
    if getattr(sys, 'frozen', False):
        # _meipass contém o diretório de pyinstaller temporário
        locale_file = str((Path(sys._MEIPASS) / 'translate' / f'{locale}.qm').resolve())
    else:
        locale_file = str((Path(__file__).absolute().parent / 'translate' / f'{locale}.qm').resolve())
        
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