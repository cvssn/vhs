#!/usr/bin/env sh

case $1 in
"ui")
    echo atualizando py de ui
    pyuic5 ui/mainWindow.ui -o ui/mainWindow.py
    ;;
"translate")
    echo atualizando o arquivo de tradução para linguista
    pylupdate5 ui/mainWindow.py app/vhsQT.py -ts translate/pt_BR.ts
    ;;
"build")
    if [ ! -f 'ffmpeg.exe' ]; then
        echo 'baixando ffmpeg'
        echo 'windows x64'
        echo 'baixando de github.com'
        wget 'https://github.com/ShareX/FFmpeg/releases/download/v4.3.1/ffmpeg-4.3.1-win64.zip' -O "./win32-x64.zip"
        echo 'extraindo'
        unzip -o -d . -j win32-x64.zip 'ffmpeg.exe'
        echo 'remover arquivo'
        rm win32-x64.zip
    fi
    docker run --rm -v "$(pwd):/src/" cdrx/pyinstaller-windows
    ;;
esac