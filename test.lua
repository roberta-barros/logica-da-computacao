-- =============================================================
-- Programa de testes do compilador
-- Cobre, em um único programa, TODOS os elementos exigidos:
--   (1) Leitura do terminal .............. read()
--   (2) Condicional com and / or / not ... if / else
--   (3) Laço com and / or / not .......... while
-- =============================================================

-- (1) LEITURA DO TERMINAL: lê dois inteiros a e b
a = read()
b = read()

-- -------------------------------------------------------------
-- (2) CONDICIONAL com and, or e not
--     Classifica o par (a, b) e imprime um código:
--       1 -> ambos positivos e diferentes
--       2 -> pelo menos um é zero
--       3 -> demais casos (negativos, iguais, etc.)
-- -------------------------------------------------------------
if (a > 0 and b > 0 and not (a == b)) then
    print(1)
else
    if (a == 0 or b == 0) then
        print(2)
    else
        print(3)
    end
end

-- -------------------------------------------------------------
-- (3) LAÇO com and, or e not
--     Calcula a * b por somas repetidas, mas só se ambos >= 0.
--     A condição combina:
--        - um teste com or        : (i < b or i == b)
--        - dois testes com not    : not (a < 0), not (b < 0)
--        - ligados por and
--     TUDO entre os parênteses do while.
-- -------------------------------------------------------------
i = 0
produto = 0
while ((i < b or i == b) and not (a < 0) and not (b < 0)) do
    if (not (i == b)) then
        produto = produto + a
    end
    i = i + 1
end
print(produto)

-- -------------------------------------------------------------
-- Bônus: um segundo laço, também usando and/or/not,
-- para exibir o fatorial de a (quando a >= 1).
-- -------------------------------------------------------------
k = 1
f = 1
while ((k < a or k == a) and not (a < 1)) do
    f = f * k
    k = k + 1
end
print(f)