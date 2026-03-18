# logica-da-computacao

[![Compilation Status](https://compiler-tester.insper-comp.com.br/svg/roberta-barros/logica-da-computacao)](https://compiler-tester.insper-comp.com.br/svg/roberta-barros/logica-da-computacao)

This repository is monitored by Compiler Tester for automatic compilation status.

# EBNF
EXPRESSION = TERM, { ("+" | "-"), TERM } ;
TERM = FACTOR, { ("*" | "/"), FACTOR } ;
FACTOR = ("+" | "-"), FACTOR | "(", EXPRESSION, ")" | NUMBER ;
NUMBER = DIGIT, {DIGIT} ;
DIGIT = 0 | 1 | ... | 9 ;
