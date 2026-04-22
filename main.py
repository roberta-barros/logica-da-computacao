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

    def get_value(self, name: str) -> Variable:
        if name not in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' not declared")
        return self.table[name]

    def set_value(self, name: str, variable: Variable) -> None:
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
        if self.value == "-":
            return -child_val
        if self.value == "not":
            return 1 if child_val == 0 else 0
        raise ValueError(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        left_val = self.children[0].evaluate(st)
        right_val = self.children[1].evaluate(st)
        if self.value == "+":
            return left_val + right_val
        if self.value == "-":
            return left_val - right_val
        if self.value == "*":
            return left_val * right_val
        if self.value == "/":
            if right_val == 0:
                raise ValueError("[Semantic] Division by zero")
            return int(left_val / right_val)
        # Relacionais → 0 ou 1
        if self.value == "==":
            return 1 if left_val == right_val else 0
        if self.value == ">":
            return 1 if left_val > right_val else 0
        if self.value == "<":
            return 1 if left_val < right_val else 0
        # Booleanos → 0 ou 1 (0 = falso, != 0 = verdadeiro)
        if self.value == "and":
            return 1 if (left_val != 0 and right_val != 0) else 0
        if self.value == "or":
            return 1 if (left_val != 0 or right_val != 0) else 0
        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")


class Identifier(Node):
    """Nó folha que representa uma variável. value = nome da variável."""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        return st.get_value(self.value).value


class Assignment(Node):
    """
    Nó de atribuição. 2 filhos:
      children[0] = Identifier (nome da variável)
      children[1] = expressão (valor a ser atribuído)
    """
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        var_name = self.children[0].value
        var_value = self.children[1].evaluate(st)
        st.set_value(var_name, Variable(var_value))


class Print(Node):
    """Nó de impressão. 1 filho (expressão a ser impressa)."""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        result = self.children[0].evaluate(st)
        print(result)


class Read(Node):
    """Nó de leitura do terminal. Retorna um inteiro lido do stdin."""
    def __init__(self, value="read", children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        line = input()
        return int(line.strip())


class If(Node):
    """
    Nó de condicional. 2 ou 3 filhos:
      children[0] = expressão booleana (condição)
      children[1] = bloco do if
      children[2] = bloco do else (opcional)
    """
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        cond = self.children[0].evaluate(st)
        if cond != 0:
            self.children[1].evaluate(st)
        elif len(self.children) > 2:
            self.children[2].evaluate(st)


class While(Node):
    """
    Nó de laço. 2 filhos:
      children[0] = expressão booleana (condição)
      children[1] = bloco do while
    """
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        while self.children[0].evaluate(st) != 0:
            self.children[1].evaluate(st)


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


RESERVED_WORDS = {
    "print": "PRINT",
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "then": "OPEN_IF_BRA",
    "do": "OPEN_BRA",
    "end": "CLOSE_BRA",
    "read": "READ",
    "and": "AND",
    "or": "OR",
    "not": "NOT",
}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")

    def select_next(self) -> None:
        s = self.source

        # Ignora espaços e tabs (mas NÃO \n, pois \n é um token)
        while self.position < len(s) and s[self.position] in (" ", "\t"):
            self.position += 1

        # EOF
        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        # Newline (\n) => token EOL
        if ch == "\n":
            self.position += 1
            self.next = Token("EOL", "\\n")
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
            # == → EQ
            if self.position < len(s) and s[self.position] == "=":
                self.position += 1
                self.next = Token("EQ", "==")
                return
            self.next = Token("ASSIGN", "=")
            return

        if ch == ">":
            self.position += 1
            self.next = Token("GT", ">")
            return

        if ch == "<":
            self.position += 1
            self.next = Token("LT", "<")
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
        if ch.isalpha() or ch == "_":
            word = ""
            while self.position < len(s) and (
                s[self.position].isalpha()
                or s[self.position].isdigit()
                or s[self.position] == "_"
            ):
                word += s[self.position]
                self.position += 1
            if word in RESERVED_WORDS:
                self.next = Token(RESERVED_WORDS[word], word)
            else:
                self.next = Token("IDEN", word)
            return

        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


class Parser:
    lexer = None

    # ---------- FACTOR ----------
    @staticmethod
    def parse_factor() -> Node:
        token = Parser.lexer.next

        if token.type == "INT":
            node = IntVal(token.value)
            Parser.lexer.select_next()
            return node

        # Unários: +, -, not
        if token.type in ("PLUS", "MINUS", "NOT"):
            op = token.value
            Parser.lexer.select_next()
            child = Parser.parse_factor()
            return UnOp(op, [child])

        # Parênteses envolvem BEXPR (não só EXPR)
        if token.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_bexpression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return node

        if token.type == "IDEN":
            node = Identifier(token.value)
            Parser.lexer.select_next()
            return node

        # read ( )
        if token.type == "READ":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after read, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after read(, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Read("read")

        raise ValueError(f"[Parser] Unexpected token {token.type}")

    # ---------- TERM ( *, / ) ----------
    @staticmethod
    def parse_term() -> Node:
        result = Parser.parse_factor()
        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_factor()
            result = BinOp(op, [result, right])
        return result

    # ---------- EXPR ( +, - ) ----------
    @staticmethod
    def parse_expression() -> Node:
        result = Parser.parse_term()
        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_term()
            result = BinOp(op, [result, right])
        return result

    # ---------- REXPR ( ==, >, < ) ----------
    @staticmethod
    def parse_relexpression() -> Node:
        result = Parser.parse_expression()
        while Parser.lexer.next.type in ("EQ", "GT", "LT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_expression()
            result = BinOp(op, [result, right])
        return result

    # ---------- BTERM ( and ) ----------
    @staticmethod
    def parse_bterm() -> Node:
        result = Parser.parse_relexpression()
        while Parser.lexer.next.type == "AND":
            op = Parser.lexer.next.value  # "and"
            Parser.lexer.select_next()
            right = Parser.parse_relexpression()
            result = BinOp(op, [result, right])
        return result

    # ---------- BEXPR ( or ) ----------
    @staticmethod
    def parse_bexpression() -> Node:
        result = Parser.parse_bterm()
        while Parser.lexer.next.type == "OR":
            op = Parser.lexer.next.value  # "or"
            Parser.lexer.select_next()
            right = Parser.parse_bterm()
            result = BinOp(op, [result, right])
        return result

    # ---------- Helpers de bloco ----------
    @staticmethod
    def skip_eols() -> None:
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

    @staticmethod
    def parse_block_until(terminators: tuple) -> Block:
        """Faz parse de múltiplas statements até encontrar um dos tokens em `terminators`."""
        stmts = []
        Parser.skip_eols()
        while Parser.lexer.next.type not in terminators:
            if Parser.lexer.next.type == "EOF":
                raise ValueError(
                    f"[Parser] Unexpected EOF, expected one of {terminators}"
                )
            stmt = Parser.parse_statement()
            stmts.append(stmt)
            # Após cada stmt dentro de um bloco: esperamos EOL ou um terminador
            if Parser.lexer.next.type == "EOL":
                Parser.skip_eols()
            elif Parser.lexer.next.type not in terminators:
                raise ValueError(
                    f"[Parser] Expected newline inside block, got {Parser.lexer.next.type}"
                )
        return Block("block", stmts)

    # ---------- IF ----------
    @staticmethod
    def parse_if() -> Node:
        # IF já é o próximo token quando chegamos aqui
        Parser.lexer.select_next()  # consome 'if'

        if Parser.lexer.next.type != "OPEN_PAR":
            raise ValueError(
                f"[Parser] Expected '(' after if, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        cond = Parser.parse_bexpression()

        if Parser.lexer.next.type != "CLOSE_PAR":
            raise ValueError(
                f"[Parser] Expected ')' after if condition, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "OPEN_IF_BRA":  # 'then'
            raise ValueError(
                f"[Parser] Expected 'then', got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        if_block = Parser.parse_block_until(("ELSE", "CLOSE_BRA"))

        children = [cond, if_block]

        if Parser.lexer.next.type == "ELSE":
            Parser.lexer.select_next()
            else_block = Parser.parse_block_until(("CLOSE_BRA",))
            children.append(else_block)

        if Parser.lexer.next.type != "CLOSE_BRA":  # 'end'
            raise ValueError(
                f"[Parser] Expected 'end' to close if, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()  # consome 'end'

        return If("if", children)

    # ---------- WHILE ----------
    @staticmethod
    def parse_while() -> Node:
        Parser.lexer.select_next()  # consome 'while'

        if Parser.lexer.next.type != "OPEN_PAR":
            raise ValueError(
                f"[Parser] Expected '(' after while, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        cond = Parser.parse_bexpression()

        if Parser.lexer.next.type != "CLOSE_PAR":
            raise ValueError(
                f"[Parser] Expected ')' after while condition, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "OPEN_BRA":  # 'do'
            raise ValueError(
                f"[Parser] Expected 'do', got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        body = Parser.parse_block_until(("CLOSE_BRA",))

        if Parser.lexer.next.type != "CLOSE_BRA":  # 'end'
            raise ValueError(
                f"[Parser] Expected 'end' to close while, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()  # consome 'end'

        return While("while", [cond, body])

    # ---------- STATEMENT ----------
    @staticmethod
    def parse_statement() -> Node:
        token = Parser.lexer.next

        # Linha vazia (por segurança; parse_program/parse_block_until já pulam EOLs)
        if token.type in ("EOL", "EOF"):
            return NoOp()

        # print ( BEXPR )
        if token.type == "PRINT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after print, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            expr = Parser.parse_bexpression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after print expression, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Print("print", [expr])

        # if
        if token.type == "IF":
            return Parser.parse_if()

        # while
        if token.type == "WHILE":
            return Parser.parse_while()

        # IDENTIFIER = BEXPR
        if token.type == "IDEN":
            iden_node = Identifier(token.value)
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise ValueError(
                    f"[Parser] Expected '=' after identifier, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            expr = Parser.parse_bexpression()
            return Assignment("=", [iden_node, expr])

        raise ValueError(f"[Parser] Unexpected token {token.type}")

    # ---------- PROGRAM ----------
    @staticmethod
    def parse_program() -> Node:
        statements = []
        Parser.skip_eols()

        while Parser.lexer.next.type != "EOF":
            stmt = Parser.parse_statement()
            statements.append(stmt)

            if Parser.lexer.next.type == "EOL":
                Parser.skip_eols()
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
    code += "\n"  # garante newline no final

    code = PrePro.filter(code)
    tree = Parser.run(code)

    st = SymbolTable()
    tree.evaluate(st)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        sys.exit(1)