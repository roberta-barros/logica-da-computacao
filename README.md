# logica-da-computacao

[![Compilation Status](https://compiler-tester.insper-comp.com.br/svg/roberta-barros/logica-da-computacao)](https://compiler-tester.insper-comp.com.br/svg/roberta-barros/logica-da-computacao)

This repository is monitored by Compiler Tester for automatic compilation status.

```ebnf
PROGRAM = { STATEMENT } ;
STATEMENT = ((IF, "(", BOOLEXPRESSION, ")", STATEMENT, ("ELSE", STATEMENT) | ε) | (WHILE, "(", BOOLEXPRESSION, ")", STATEMENT) | (IDENTIFIER, "=", BOOLEXPRESSION) | (PRINT, "(", BOOLEXPRESSION, ")") | ε), EOL ;
BOOLEXPRESSION = BOOLTERM, { "||", BOOLTERM } ;
BOOLTERM = RELEXPRESSION, { "&&", RELEXPRESSION } ;
RELEXPRESSION = EXPRESSION, ("==" | "<" | ">"), EXPRESSION ;
EXPRESSION = TERM, { ("+" | "-"), TERM } ;
TERM = FACTOR, { ("*" | "/"), FACTOR } ;
FACTOR = ("+" | "-"), FACTOR | "(", BOOLEXPRESSION, ")" | NUMBER | READ, "(", ")" ;
NUMBER = DIGIT, {DIGIT} ;
DIGIT = 0 | 1 | ... | 9 ;
IDENTIFIER = LETTER, {LETTER | DIGIT | "_"} ;
LETTER = a | b | ... | z | A | B | ... | Z ;
```