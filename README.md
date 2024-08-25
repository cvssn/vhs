# emulador de vídeo vhs

isso é uma reescrita de python 3.6 do repositório https://github.com/joncampbell123/composite-video-simulator

o objetivo final seria a reprodução de todos os artefatos descritos aqui
https://www.avartifactatlas.com/tags.html#video

a esse ponto, os artefatos simulados incluem:

## dot crawl

um artefato de vídeo composto, o dot crawl ocorre como resultado da multiplexação das informações de luminância e crominância transportadas no sinal. os sinais ntsc de banda base transportam esses componentes como frequências diferentes, mas quando são exibidos juntos, as informações de croma podem ser mal interpretadas como luma. o resultado é o aparecimento de uma linha móvel de pontos redondos. é mais aparente nas bordas horizontais entre objetos com altos níveis de saturação. usar um filtro comb para processar o vídeo pode reduzir a distração causada pelo rastreamento de pontos ao migrar fontes de vídeo composto, e o artefato pode ser eliminado através do uso de conexões s-video ou componentes. no entanto, se estiver presente numa transferência de fonte original, poderá ser agravado em gerações subsequentes de transferências de vídeo composto.

## ringing

em um sentido geral, o toque refere-se a uma oscilação indesejável exibida em um sinal. este artefato de vídeo é comum em gravações criadas usando câmeras de modelos anteriores e equipamentos vtr menos sofisticados (particularmente os primeiros equipamentos u-matic). pode ser acentuado pelo aprimoramento excessivo ou nitidez da imagem usando hardware de processamento ou controles de monitor crt. quando gravado no sinal da fita, ele passa a fazer parte da imagem.

## erro de delay chroma/luma (color bleeding)

quando o vídeo sofre de erro de atraso y/c, haverá uma incompatibilidade no tempo entre a luminância e/ou canais de cor, resultando num desalinhamento visível na forma como as cores aparecem no monitor. um desalinhamento de y/c mostra uma borda desfocada em torno de áreas com grande diferença de cores de contraste e será mais aparente em torno de bordas nítidas de objetos na imagem de vídeo.

## efeitos rainbow

os efeitos de arco-íris e o rastreamento de pontos são causados ​​pela separação imperfeita dos componentes luma e croma de um sinal de vídeo composto. este efeito é chamado de crosstalk de cores. é mais perceptível em imagens geradas por computador, como legendas, mapas meteorológicos, logotipos estacionários e imagens de vídeo onde há dados de alta frequência (como a foto de um arranha-céu à distância). sempre que você tiver padrões finos e alternados fortes (= altas frequências) em luma, você terá efeitos de arco-íris. Sempre que você tem uma grande mudança repentina no croma (normalmente gráficos gerados por computador, etc.), você tem rastreamento de pontos. os termos técnicos são os seguintes: efeitos de arco-íris são cores cruzadas (dados de luma de alta frequência perturbam o demodulador de croma) e rastreamento de pontos é luminância cruzada (sobras de croma no sinal y).

## chrominance noise

o ruído de crominância pode ser identificado como traços e manchas de cor em uma imagem nítida. é mais visível em áreas escuras e saturadas da imagem de vídeo. isso pode ser devido a limitações de sensibilidade do ccd em câmeras de vídeo (ou seja, condições de pouca iluminação durante a gravação da câmera), aumento excessivo da crominância no sinal de vídeo ou uso de processadores de vídeo de baixa qualidade. dublagens compostas de várias gerações podem sofrer altos níveis de ruído de crominância.

## head switching noise

o ruído de troca de cabeçote é comumente visto na parte inferior da tela de vídeo durante a reprodução de vhs. embora ocorra em outros formatos, muitas vezes é mascarado dependendo dos recursos de processamento e da calibração do vtr de reprodução. durante a reprodução da fita de vídeo, os cabeçotes de vídeo são ligados à medida que passam pela mídia e depois desligados para evitar a exibição de ruído que seria emitido quando não estivessem em contato com a fita. o ruído de troca de cabeçote é resultado desse intervalo de troca e ocorre antes do início da sincronização vertical. este artefato não é visível em overscan em um monitor de transmissão, mas é visível em underscan e em vídeo digitalizado full-raster e derivados digitais não cortados. alguns vtrs apresentam “mascaramento swp”, que mascara efetivamente as linhas criadas durante a troca de cabeçote com vídeo preto.

## long/extended play

o modo long play (lp), disponível para uma variedade de formatos de vídeo (veja a lista abaixo), torna possível estender o tempo potencial de gravação de uma fita diminuindo a velocidade da fita e alterando o ângulo e a proximidade das trilhas gravadas. para uma reprodução adequada, uma gravação feita no modo lp deve ser reproduzida no modo lp.

se reproduzida no modo standard play (sp), a imagem ainda é reconhecível, mas - dependendo do formato - pode ser reproduzida entre 1,5x e 2x muito rápido, exibindo faixas irregulares e horizontais de ruído semelhantes às que aparecem quando avanço rápido. o áudio na trilha longitudinal soará muito agudo e será reproduzido tão rápido que a fala parecerá incompreensível. se o áudio fm ou pcm for gravado nas trilhas helicoidais, ele desaparecerá completamente.
o modo lp foi efetivamente substituído por ep (“extended play”) ou slp (“super long play”). muitas vezes referidos em conjunto como “ep/slp”, este modo envolve uma velocidade de fita 3x mais lenta do que as velocidades de reprodução padrão.

nos casos em que a velocidade da fita é reduzida para economizar no uso da mídia, menos informações são gravadas para uma determinada imagem, resultando em uma qualidade de imagem visivelmente reduzida. de um modo geral, quando a velocidade da fita é reduzida, qualquer outra condição que aflija a fita, tal como aderência ou estiramento, é ainda mais exacerbada.

## luminance noise

o ruído de luminância se manifesta em uma imagem de vídeo como um leve ruído branco. pode ser o resultado de falha eletrônica, gravação em condições de pouca luz, fitas gastas ou mal revestidas, transmissão de um sinal de vídeo por cabos muito longos, aprimoramento excessivo do sinal de vídeo ou cabeçotes de gravação ou reprodução sujos. Vídeo colorido ou vídeo em preto e branco podem conter ruído de luminância.

## oversaturation

a supersaturação refere-se à alta amplitude de crominância em um sinal de vídeo, criando a aparência de cores muito intensas na imagem. Dependendo da gravidade da supersaturação, a cor da imagem pode parecer vazar para áreas fora dos limites aparentes de um objeto. a maioria dos padrões de transmissão ntsc exige que o sinal de vídeo composto não exceda 120 ire (plano). as barras coloridas de campo dividido smpte usam saturação de 75% como valor máximo para calibração, embora existam outros padrões usados ​​para testes que contêm valores de saturação de 100%.
