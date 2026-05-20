# logica-da-computacao

[![Compilation Status](https://compiler-tester.insper-comp.com.br/svg/roberta-barros/logica-da-computacao)](https://compiler-tester.insper-comp.com.br/svg/roberta-barros/logica-da-computacao)

This repository is monitored by Compiler Tester for automatic compilation status.

```ebnf
PROGRAM = { FUNCDEC | STATEMENT } ;
FUNCDEC = "function", IDENTIFIER, "(",(| IDENTIFIER, TYPE, {",", IDENTIFIER, TYPE}),")",(TYPE|), "\n", {STATEMENT}, "end";
BLOCK = "do", {STATEMENT, }, "end" ;
STATEMENT = (|"local", IDENTIFIER, TYPE, ( | "=", BOOLEXPRESSION )|(IDENTIFIER, ("=", BOOLEXPRESSION | "(",(BOOLEXPRESSION, {",", BOOLEXPRESSION} | ),")")) | ("print", "(", BOOLEXPRESSION, ")") | "return", BOOLEXPRESSION |), "\n"| ("if", BOOLEXPRESSION, "then", {STATEMENT}, (|"else", {STATEMENT})), "end" | ("while", BOOLEXPRESSION, "do", {STATEMENT}, "end") | BLOCK;
BOOLEXPRESSION = BOOLTERM, { "or", BOOLTERM } ;
BOOLTERM = RELEXPRESSION, { "and", RELEXPRESSION } ;
RELEXPRESSION = EXPRESSION, {("==" | "<" | ">"), EXPRESSION};
EXPRESSION = TERM, { ("+" | "-"), TERM } ;
TERM = FACTOR, { ("*" | "/"), FACTOR } ;
FACTOR = NUMBER | STRING | BOOLEAN | IDENTIFIER, ("(",(BOOLEXPRESSION, {",", BOOLEXPRESSION} | ),")"|) | ("+" | "-" |"not"), FACTOR | "(", BOOLEXPRESSION, ")" | "read", "(", ")" ;
TYPE = "number" | "string" | "boolean" ;
NUMBER = DIGIT, {DIGIT} ;
IDENTIFIER = LETTER, {LETTER | DIGIT | "_"} ;
STRING = '"..."' ;
DIGIT = "0" | "..." | "9";
LETTER = "a" | "..." | "z" | "A" | "..." | "Z" ;
BOOLEAN = "true" | "false" ;
```