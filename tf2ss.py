from numpy import (r_, eye, atleast_2d, asarray, zeros, array, outer, ndarray)
import numpy as np

import math

from scipy.signal import butter, lfilter, lfiltic, dimpulse, dlti, lfilter_zi
from scipy import linalg


def tf2ss(num, den):
    r"""função de transferência para representação em espaço de estados.
    
    parâmetros
    ----------
    num, den : array_like
        sequências representando os coeficientes do numerador e
        polinômios denominadores, em ordem decrescente de grau. o
        o denominador precisa ser pelo menos tão longo quanto o numerador
        
    retorna
    -------
    a, b, c, d : ndarray
        representação em espaço de estados do sistema, em controlador
        canônico forma
        
    exemplos
    --------
    converte a função de transferência:
    
    .. math:: H(s) = \frac{s^2 + 3s + 3}{s^2 + 2s + 1}
    
    >>> num = [1, 3, 3]
    >>> den = [1, 2, 1]
    
    para a representação state-space:
    
    .. math::
    
        \dot{\textbf{x}}(t) =
        \begin{bmatrix} -2 & -1 \\ 1 & 0 \end{bmatrix} \textbf{x}(t) +
        \begin{bmatrix} 1 \\ 0 \end{bmatrix} \textbf{u}(t) \\
            
        \textbf{y}(t) = \begin{bmatrix} 1 & 2 \end{bmatrix} \textbf{x}(t) +
        \begin{bmatrix} 1 \end{bmatrix} \textbf{u}(t)
        
    >>> from scipy.signal import tf2ss
    >>> A, B, C, D = tf2ss(num, den)
    >>> A
    array([[-2., -1.],
           [ 1.,  0.]])
    >>> B
    array([[ 1.],
           [ 0.]])
    >>> C
    array([[ 1.,  2.]])
    >>> D
    array([[ 1.]])
    """
    
    # representação canônica do espaço de estados do controlador
    #     se M+1 = len(num) e K+1 = len(den) então devemos ter M <= K
    #     estados são encontrados afirmando que X(s) = U(s) / D(s)
    #     então Y(s) = N(s) * X(s)
    #
    #       a, b, c e d seguem naturalmente.
    nn = len(num.shape)
    
    if nn == 1:
        num = asarray([num], num.dtype)
        
    M = num.shape[1]
    K = len(den)
    
    if M > K:
        msg = "função de transferência inadequada. `num` é maior que `den`."
        
        raise ValueError(msg)
    
    if M == 0 or K == 0: # sistema nulo
        return (array([], float), array([], float), array([], float),
                array([], float))
        
    # numerador de bloco para ter o mesmo número de colunas tem denominador
    num = r_['-1', zeros((num.shape[0], K - M), num.dtype), num]

    print("num:", num, num.shape)

    if num.shape[-1] > 0:
        D = atleast_2d(num[:, 0])
        
        print("D:", D)
    else:
        D = array([[0]], float)
        
    if K == 1:
        D = D.reshape(num.shape)

        return (zeros((1, 1)), zeros((1, D.shape[1])),
                zeros((D.shape[0], 1)), D)

    frow = -array([den[1:]])
    A = r_[frow, eye(K - 2, K - 1)]
    B = eye(K - 1, 1)

    print("num den trimmed:", num[:, 0], den[1:])
    print("num 0:", num[0][0])
    print("sub:", num[0][0] * den[1:])

    C = num[:, 1:] - outer(num[:, 0], den[1:])
    print("alt C:", num[0][1:] - (num[0][0] * den[1:]), ", C:", C)
    D = D.reshape((C.shape[0], B.shape[1]))

    return A, B, C, D

def lfilter_zi_alt(b, a):
    """
    constrói condições iniciais para lfilter para estado estacionário de resposta ao degrau.
    calcula um estado inicial `zi` para a função `lfilter` que corresponde ao estado
    estacionário da resposta ao degrau.
    um uso típico desta função é definir o estado inicial para que o
    a saída do filtro começa com o mesmo valor do primeiro elemento do
    o sinal a ser filtrado.
    
    parâmetros
    ----------
    b, a : array_like (1-d)
        os coeficientes do filtro iir. veja `lfilter` para mais
        informação.
        
    retorna
    -------
    zi : 1-d ndarray
        o estado inicial do filtro.
    
    veja também
    -----------
    lfilter, lfiltic, filtfilt
    
    notes
    -----
    um filtro linear de ordem m possui uma representação em espaço de estados
    (a, b, d, d), para o qual a saída y do filtro pode ser expressa como::
        z(n+1) = A*z(n) + B*x(n)
        y(n)   = C*z(n) + D*x(n)
    onde z(n) é um vetor de comprimento m, a tem forma (m, m), b tem forma
    (m, 1), c tem forma (1, m) e d tem forma (1, 1) (assumindo que x(n) é
    um escalar). lfilter_zi resolve::
        zi = A*zi + B
    em outras palavras, encontra a condição inicial para a qual a resposta
    para uma entrada de todos uns é uma constante.
    dados os coeficientes de filtro `a` e `b`, as matrizes de espaço de estados
    para a implementação da forma ii direta transposta do filtro linear,
    que é a implementação usada por scipy.signal.lfilter, são::
        A = scipy.linalg.companion(a).T
        B = b[1:] - a[1:]*b[0]
    assumindo que `a[0]` é 1,0; se `a[0]` não for 1, `a` e `b` são os
    primeiros dividido por a[0].
    
    exemplos
    --------
    o código a seguir cria um filtro butterworth passa-baixo. então
    aplica esse filtro a uma matriz cujos valores são todos 1,0; o
    a saída também é 1,0, conforme esperado para um filtro passa-baixa. se o
    o argumento `zi` de `lfilter` não tivesse sido fornecido, a saída teria
    mostrado o sinal transitório.
    
    >>> from numpy import array, ones
    >>> from scipy.signal import lfilter, lfilter_zi, butter
    >>> b, a = butter(5, 0.25)
    >>> zi = lfilter_zi(b, a)
    >>> y, zo = lfilter(b, a, ones(10), zi=zi)
    >>> y
    array([1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.])
    
    outro exemplo:
    >>> x = array([0.5, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0])
    >>> y, zf = lfilter(b, a, x, zi=zi*x[0])
    >>> y
    array([ 0.5       ,  0.5       ,  0.5       ,  0.49836039,  0.48610528,
        0.44399389,  0.35505241])
    """

    # poderíamos usar scipy.signal.normalize, mas ele usa avisos em
    # casos em que um valueerror é mais apropriado e permite
    # que b seja 2d.
    b = np.atleast_1d(b)
    
    if b.ndim != 1:
        raise ValueError("o numerador b deve ser 1-D.")
    
    a = np.atleast_1d(a)
    
    if a.ndim != 1:
        raise ValueError("o denominador a deve ser 1-D.")
    while len(a) > 1 and a[0] == 0.0:
        a = a[1:]
        
    if a.size < 1:
        raise ValueError("deve haver pelo menos um coeficiente `a` diferente de zero.")

    if a[0] != 1.0:
        # normaliza os coeficientes para que a[0] == 1.
        b = b / a[0]
        a = a / a[0]

    n = max(len(a), len(b))

    # preenche a ou b com zeros para que tenham o mesmo comprimento.
    if len(a) < n:
        a = np.r_[a, np.zeros(n - len(a), dtype=a.dtype)]
    elif len(b) < n:
        b = np.r_[b, np.zeros(n - len(b), dtype=b.dtype)]

    IminusA = np.eye(n - 1, dtype=np.result_type(a, b)) - linalg.companion(a).T
    B = b[1:] - a[1:] * b[0]

    print("num:", b)
    print("den:", a)

    '''print("a:", a)
    print("eye:", np.eye(n - 1, dtype=np.result_type(a, b)))
    print("companion:", linalg.companion(a).T)
    print("IminusA:", IminusA)
    print("IminusA sum:", IminusA[:,0].sum())
    print("a sum:", a.sum())'''
    
    print("B sum:", B.sum())
    print("B:", B)
    print(a[1:] * b[0])

    # print("IminusA:", IminusA[:,0], a)
    # print("B:", B)
    # Solve zi = A * zi + B
    # zi = np.linalg.solve(IminusA, B)

    # para referência futura: também poderíamos usar o seguinte
    # fórmulas explícitas para resolver o sistema linear:
    zi = np.zeros(n - 1)
    zi[0] = B.sum() / a.sum()
    asum = 1.0
    csum = 0.0
    
    for k in range(1,n-1):
        asum += a[k]
        csum += b[k] - a[k]*b[0]
        zi[k] = asum*zi[0] - csum

    return zi

filt = (
    array([0.5]),
    array([2.3, -1.2])
)

#filt = butter(3, 0.5)
print(filt)

data = [4, 1, 2, 0, 0, 0, 0]


def lowpassFilter(cutoff: float, reset: float, rate: float = 315000000.00 / 88 * 4):
    timeInterval = 1.0 / rate
    tau = 1 / (cutoff * 2.0 * math.pi)
    alpha = timeInterval / (tau + timeInterval)

    return array([alpha]), array([1, -(1.0 - alpha)])

# filter = lowpassFilter(600000.0, 0.0)
filter = butter(5, 0.5)
# filter = (filter[0], filter[1][1:])
# filter = (filter[0][2:], filter[1])
print("filter tf:", filter)
# state = tf2ss(filter[0], filter[1])
# print(state)

# ic = lfiltic(filter[0], filter[1], y=[16.0], x=lfilter_zi(filter[0], filter[1]))
ic = lfilter_zi(filter[0], filter[1])
ic_alt = lfilter_zi_alt(filter[0], filter[1])
# ic_better = lfiltic(filter[0], filter[1], [1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1])
filtered = lfilter(filter[0], filter[1], data, zi=ic * 4.0)
# filtered2 = lfilter(filter[0], filter[1], data, zi=ic_better)
print("filtered:", filtered)
# print("filtered2:", filtered2)
print("ic:", ic)
print("ic (ours):", ic_alt)
# print("ic (better):", ic_better)

'''impulse_data = lfilter(filter[0], filter[1], [1, 0, 0, 0, 0, 0, 0, 0, 0])
print("lfilter impulse:", impulse_data)
alt_impulse = dimpulse(dlti(filter[0], filter[1]), n = 9)
print("dimpulse impulse:", alt_impulse[1])'''