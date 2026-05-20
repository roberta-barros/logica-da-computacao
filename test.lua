local b number = 5 -- Variável Global
function soma(x number, y number) number
local a number -- Variável Local
a = x + y
print(a) -- Imprime 7
return a
end
function main()
local a number
do
local b number
a = 3
b = soma(a, 4)
print(b) -- Imprime 7
end
print(a) -- Imprime 3
print(b) -- Imprime 5
end
main()