import sys
import re
from abc import ABC, abstractmethod


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value


class PrePro:
    @staticmethod
    def filter(code: str) -> str:
        # Remove comentários inline: de "--" até "\n"
        # Mantém o \n para não perder a marcação de fim de linha
        return re.sub(r"--[^\n]*", "", code)


class Variable:
    def __init__(self, value: int):
        self.value = value


class SymbolTable:
    def __init__(self):
        self.table: dict = {}

    def get(self, name: str) -> Variable:
        if name not in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' not declared")
        return self.table[name]

    def set(self, name: str, variable: Variable) -> None:
        self.table[name] = variable


class Node(ABC):
    def __init__(self, value, children):
        self.value = value
        self.children = children

    @abstractmethod
    def evaluate(self, st: SymbolTable):
        pass


class IntVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        return self.value


class UnOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        child_val = self.children[0].evaluate(st)
        if self.value == "+":
            return +child_val
        elif self.value == "-":
            return -child_val
        raise ValueError(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        left_val = self.children[0].evaluate(st)
        right_val = self.children[1].evaluate(st)
        if self.value == "+":
            return left_val + right_val
        elif self.value == "-":
            return left_val - right_val
        elif self.value == "*":
            return left_val * right_val
        elif self.value == "/":
            if right_val == 0:
                raise ValueError("[Semantic] Division by zero")
            return int(left_val / right_val)
        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")


class Identifier(Node):
    """Nó folha que representa uma variável. value = nome da variável."""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        return st.get(self.value).value


class Assignment(Node):
    """
    Nó de atribuição. 2 filhos:
      children[0] = Identifier (nome da variável)
      children[1] = expressão (valor a ser atribuído)
    """
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        var_name = self.children[0].value  # nome da variável (string)
        var_value = self.children[1].evaluate(st)  # calcula a expressão
        st.set(var_name, Variable(var_value))


class Print(Node):
    """Nó de impressão. 1 filho (expressão a ser impressa)."""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        result = self.children[0].evaluate(st)
        print(result)


class Block(Node):
    """Nó raiz do programa. N filhos (uma instrução por filho)."""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        for child in self.children:
            child.evaluate(st)


class NoOp(Node):
    """Nó dummy — representa uma instrução vazia."""
    def __init__(self, value=None, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        pass


RESERVED_WORDS = {"print": "PRINT"}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")

    def select_next(self) -> None:
        s = self.source

        # Ignora espaços (mas NÃO \n, pois \n é um token)
        while self.position < len(s) and s[self.position] in (" ", "\t"):
            self.position += 1

        # EOF
        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        # Newline (\n) => token END
        if ch == "\n":
            self.position += 1
            self.next = Token("END", "\\n")
            return

        # Operadores e símbolos
        if ch == "+":
            self.position += 1
            self.next = Token("PLUS", "+")
            return

        if ch == "-":
            self.position += 1
            self.next = Token("MINUS", "-")
            return

        if ch == "*":
            self.position += 1
            self.next = Token("MULT", "*")
            return

        if ch == "/":
            self.position += 1
            self.next = Token("DIV", "/")
            return

        if ch == "(":
            self.position += 1
            self.next = Token("OPEN_PAR", "(")
            return

        if ch == ")":
            self.position += 1
            self.next = Token("CLOSE_PAR", ")")
            return

        if ch == "=":
            self.position += 1
            self.next = Token("ASSIGN", "=")
            return

        # Números inteiros
        if ch.isdigit():
            num = ""
            while self.position < len(s) and s[self.position].isdigit():
                num += s[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
            return

        # Identificadores e palavras reservadas
        if ch.isalpha():
            word = ""
            while self.position < len(s) and (
                s[self.position].isalpha()
                or s[self.position].isdigit()
                or s[self.position] == "_"
            ):
                word += s[self.position]
                self.position += 1
            # Verifica se é palavra reservada
            if word in RESERVED_WORDS:
                self.next = Token(RESERVED_WORDS[word], word)
            else:
                self.next = Token("IDEN", word)
            return

        # Símbolo inválido
        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


class Parser:
    lexer = None  

    @staticmethod
    def parse_factor() -> Node:
        token = Parser.lexer.next

        # Número inteiro
        if token.type == "INT":
            node = IntVal(token.value)
            Parser.lexer.select_next()
            return node

        # Operador unário (+ ou -)
        if token.type in ("PLUS", "MINUS"):
            op = token.value
            Parser.lexer.select_next()
            child = Parser.parse_factor()
            return UnOp(op, [child])

        # Parênteses
        if token.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return node

        # Identificador (variável)
        if token.type == "IDEN":
            node = Identifier(token.value)
            Parser.lexer.select_next()
            return node

        raise ValueError(f"[Parser] Unexpected token {token.type}")

    @staticmethod
    def parse_term() -> Node:
        result = Parser.parse_factor()

        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_factor()
            result = BinOp(op, [result, right])

        return result

    @staticmethod
    def parse_expression() -> Node:
        result = Parser.parse_term()

        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_term()
            result = BinOp(op, [result, right])

        return result

    @staticmethod
    def parse_statement() -> Node:
        token = Parser.lexer.next

        # Linha vazia (só tem \n ou EOF)
        if token.type in ("END", "EOF"):
            return NoOp()

        # Print: print ( EXPRESSION )
        if token.type == "PRINT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after print, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            expr = Parser.parse_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after print expression, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Print("print", [expr])

        # Atribuição: IDENTIFIER = EXPRESSION
        if token.type == "IDEN":
            iden_node = Identifier(token.value)
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise ValueError(
                    f"[Parser] Expected '=' after identifier, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            expr = Parser.parse_expression()
            return Assignment("=", [iden_node, expr])

        raise ValueError(f"[Parser] Unexpected token {token.type}")

    @staticmethod
    def parse_program() -> Node:
        statements = []

        while Parser.lexer.next.type != "EOF":
            stmt = Parser.parse_statement()
            statements.append(stmt)

            # Consome o \n (END) após cada instrução
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            elif Parser.lexer.next.type != "EOF":
                raise ValueError(
                    f"[Parser] Expected newline or EOF, got {Parser.lexer.next.type}"
                )

        return Block("block", statements)

    @staticmethod
    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()

        tree = Parser.parse_program()

        if Parser.lexer.next.type != "EOF":
            raise ValueError(
                f"[Parser] Unexpected token after program: {Parser.lexer.next.type}"
            )

        return tree


def main():
    if len(sys.argv) < 2:
        print("[Main] Usage: python3 main.py <filename.lua>")
        sys.exit(1)

    filename = sys.argv[1]

    with open(filename, "r") as f:
        code = f.read()
    code += "\n"  # adiciona \n no final

    # 2. Pré-processamento (remoção de comentários)
    code = PrePro.filter(code)

    # 3. Parsing (análise léxica + sintática → AST)
    tree = Parser.run(code)

    # 4. Execução (análise semântica)
    st = SymbolTable()
    tree.evaluate(st)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        sys.exit(1)