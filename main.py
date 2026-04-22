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
        if self.value == "==":
            return 1 if left_val == right_val else 0
        if self.value == ">":
            return 1 if left_val > right_val else 0
        if self.value == "<":
            return 1 if left_val < right_val else 0
        if self.value == "and":
            return 1 if (left_val != 0 and right_val != 0) else 0
        if self.value == "or":
            return 1 if (left_val != 0 or right_val != 0) else 0
        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")


class Identifier(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        return st.get_value(self.value).value


class Assignment(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        var_name = self.children[0].value
        var_value = self.children[1].evaluate(st)
        st.set_value(var_name, Variable(var_value))


class Print(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        result = self.children[0].evaluate(st)
        print(result)


class Read(Node):
    def __init__(self, value="read", children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> int:
        return int(input().strip())


class If(Node):
    """2 ou 3 filhos: [cond, if_block, else_block?]"""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        if self.children[0].evaluate(st) != 0:
            self.children[1].evaluate(st)
        elif len(self.children) > 2:
            self.children[2].evaluate(st)


class While(Node):
    """2 filhos: [cond, block]"""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        while self.children[0].evaluate(st) != 0:
            self.children[1].evaluate(st)


class Block(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        for child in self.children:
            child.evaluate(st)


class NoOp(Node):
    def __init__(self, value=None, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        pass


RESERVED_WORDS = {
    "print": "PRINT",
    "if":    "IF",
    "else":  "ELSE",
    "while": "WHILE",
    "then":  "OPEN_IF_BRA",
    "do":    "OPEN_BRA",
    "end":   "CLOSE_BRA",
    "read":  "READ",
    "and":   "AND",
    "or":    "OR",
    "not":   "NOT",
}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")

    def select_next(self) -> None:
        s = self.source

        while self.position < len(s) and s[self.position] in (" ", "\t"):
            self.position += 1

        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        if ch == "\n":
            self.position += 1
            self.next = Token("EOL", "\\n")
            return

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

        if ch.isdigit():
            num = ""
            while self.position < len(s) and s[self.position].isdigit():
                num += s[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
            return

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

    # ------------------------------------------------------------------ FACTOR
    @staticmethod
    def parse_factor() -> Node:
        token = Parser.lexer.next

        if token.type == "INT":
            node = IntVal(token.value)
            Parser.lexer.select_next()
            return node

        if token.type in ("PLUS", "MINUS", "NOT"):
            op = token.value
            Parser.lexer.select_next()
            return UnOp(op, [Parser.parse_factor()])

        if token.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_bool_expression()
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
            return Read()

        raise ValueError(f"[Parser] Unexpected token in factor: {token.type}")

    # ------------------------------------------------------------------- TERM
    @staticmethod
    def parse_term() -> Node:
        result = Parser.parse_factor()
        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_factor()])
        return result

    # --------------------------------------------------------------- EXPRESSION
    @staticmethod
    def parse_expression() -> Node:
        result = Parser.parse_term()
        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_term()])
        return result

    # --------------------------------------------------------- REL EXPRESSION
    @staticmethod
    def parse_rel_expression() -> Node:
        result = Parser.parse_expression()
        while Parser.lexer.next.type in ("EQ", "GT", "LT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_expression()])
        return result

    # ---------------------------------------------------------- BOOL TERM (and)
    @staticmethod
    def parse_bool_term() -> Node:
        result = Parser.parse_rel_expression()
        while Parser.lexer.next.type == "AND":
            op = Parser.lexer.next.value          # "and"
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_rel_expression()])
        return result

    # ------------------------------------------------------- BOOL EXPRESSION (or)
    @staticmethod
    def parse_bool_expression() -> Node:
        result = Parser.parse_bool_term()
        while Parser.lexer.next.type == "OR":
            op = Parser.lexer.next.value          # "or"
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_bool_term()])
        return result

    # ------------------------------------------------------------------ BLOCK
    @staticmethod
    def parse_block() -> Node:
        """
        Análogo ao parseBlock() da linguagem C (que consumia '{' stmts '}').
        Para a sintaxe Lua, a abertura ('then'/'do') e o fechamento ('end')
        são consumidos pelo parse_statement; parse_block só organiza as
        statements internas até encontrar CLOSE_BRA ('end') ou ELSE.
        """
        stmts = []
        # Pula newlines iniciais dentro do bloco
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        while Parser.lexer.next.type not in ("CLOSE_BRA", "ELSE", "EOF"):
            stmt = Parser.parse_statement()
            stmts.append(stmt)
            if Parser.lexer.next.type == "EOL":
                while Parser.lexer.next.type == "EOL":
                    Parser.lexer.select_next()
            elif Parser.lexer.next.type not in ("CLOSE_BRA", "ELSE", "EOF"):
                raise ValueError(
                    f"[Parser] Expected newline inside block, "
                    f"got {Parser.lexer.next.type}"
                )
        return Block("block", stmts)

    # --------------------------------------------------------------- STATEMENT
    @staticmethod
    def parse_statement() -> Node:
        token = Parser.lexer.next

        # Linha vazia
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
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after print expr, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Print("print", [expr])

        # if ( BEXPR ) then BLOCK [else BLOCK] end
        if token.type == "IF":
            Parser.lexer.select_next()                      # consome 'if'
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after if, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome '('
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after if cond, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome ')'
            if Parser.lexer.next.type != "OPEN_IF_BRA":
                raise ValueError(
                    f"[Parser] Expected 'then', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome 'then'
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            if_block = Parser.parse_block()

            children = [cond, if_block]
            if Parser.lexer.next.type == "ELSE":
                Parser.lexer.select_next()                  # consome 'else'
                while Parser.lexer.next.type == "EOL":
                    Parser.lexer.select_next()
                children.append(Parser.parse_block())

            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close if, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome 'end'
            return If("if", children)

        # while ( BEXPR ) do BLOCK end
        if token.type == "WHILE":
            Parser.lexer.select_next()                      # consome 'while'
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after while, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome '('
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after while cond, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome ')'
            if Parser.lexer.next.type != "OPEN_BRA":
                raise ValueError(
                    f"[Parser] Expected 'do', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome 'do'
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close while, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome 'end'
            return While("while", [cond, body])

        # do BLOCK end
        if token.type == "OPEN_BRA":
            Parser.lexer.select_next()                      # consome 'do'
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close block, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()                      # consome 'end'
            return body

        # IDENTIFIER = BEXPR
        if token.type == "IDEN":
            iden_node = Identifier(token.value)
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise ValueError(
                    f"[Parser] Expected '=' after identifier, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Assignment("=", [iden_node, Parser.parse_bool_expression()])

        raise ValueError(f"[Parser] Unexpected token in statement: {token.type}")

    # --------------------------------------------------------------- PROGRAM
    @staticmethod
    def parse_program() -> Node:
        statements = []
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        while Parser.lexer.next.type != "EOF":
            stmt = Parser.parse_statement()
            statements.append(stmt)
            if Parser.lexer.next.type == "EOL":
                while Parser.lexer.next.type == "EOL":
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
    code += "\n"

    code = PrePro.filter(code)
    tree = Parser.run(code)

    st = SymbolTable()
    tree.evaluate(st)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)