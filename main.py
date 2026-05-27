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
    def __init__(self, value, type_):
        self.value = value
        self.type = type_


class SymbolTable:
    def __init__(self):
        self.table: dict[str, Variable] = {}

    def get_value(self, name: str) -> Variable:
        if name not in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' not declared")
        variable = self.table[name]
        if variable.value is None:
            raise ValueError(f"[Semantic] Variable '{name}' declared but not assigned")
        return Variable(variable.value, variable.type)

    def create_variable(self, name: str, type_: str) -> None:
        if name in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' already declared")
        self.table[name] = Variable(None, type_)

    def set_value(self, name: str, variable: Variable) -> None:
        if name not in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' not declared")
        current = self.table[name]

        # Promoção automática number -> float na atribuição
        if current.type == "float" and variable.type == "number":
            current.value = float(variable.value)
            return

        if current.type != variable.type:
            raise ValueError(
                f"[Semantic] Type mismatch in assignment to '{name}': "
                f"expected {current.type}, got {variable.type}"
            )
        current.value = variable.value


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

    def evaluate(self, st: SymbolTable) -> Variable:
        return Variable(self.value, "number")


class FloatVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return Variable(self.value, "float")


class BoolVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return Variable(self.value, "boolean")


class StringVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return Variable(self.value, "string")


class UnOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        child = self.children[0].evaluate(st)
        if self.value == "+":
            if child.type == "number":
                return Variable(+child.value, "number")
            if child.type == "float":
                return Variable(+child.value, "float")
            raise ValueError("[Semantic] Unary '+' expects number or float")
        if self.value == "-":
            if child.type == "number":
                return Variable(-child.value, "number")
            if child.type == "float":
                return Variable(-child.value, "float")
            raise ValueError("[Semantic] Unary '-' expects number or float")
        if self.value == "not":
            if child.type != "boolean":
                raise ValueError("[Semantic] Unary 'not' expects boolean")
            return Variable(not child.value, "boolean")
        raise ValueError(f"[Semantic] Unknown unary operator '{self.value}'")


class Cast(Node):
    """Operador unário de casting. self.value guarda o tipo destino."""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        child = self.children[0].evaluate(st)
        target = self.value

        if target == "number":
            if child.type == "number":
                return Variable(child.value, "number")
            if child.type == "float":
                # Arredonda para o inteiro mais próximo (1.6 -> 2)
                return Variable(int(round(child.value)), "number")
            if child.type == "boolean":
                return Variable(1 if child.value else 0, "number")
            if child.type == "string":
                try:
                    return Variable(int(child.value), "number")
                except ValueError:
                    raise ValueError(
                        f"[Semantic] Cannot cast string '{child.value}' to number"
                    )

        if target == "float":
            if child.type == "float":
                return Variable(child.value, "float")
            if child.type == "number":
                return Variable(float(child.value), "float")
            if child.type == "boolean":
                return Variable(1.0 if child.value else 0.0, "float")
            if child.type == "string":
                try:
                    return Variable(float(child.value), "float")
                except ValueError:
                    raise ValueError(
                        f"[Semantic] Cannot cast string '{child.value}' to float"
                    )

        if target == "string":
            if child.type == "boolean":
                return Variable("true" if child.value else "false", "string")
            if child.type == "string":
                return Variable(child.value, "string")
            return Variable(str(child.value), "string")

        if target == "boolean":
            if child.type == "boolean":
                return Variable(child.value, "boolean")
            if child.type in ("number", "float"):
                return Variable(child.value != 0, "boolean")
            if child.type == "string":
                if child.value == "true":
                    return Variable(True, "boolean")
                if child.value == "false":
                    return Variable(False, "boolean")
                raise ValueError(
                    f"[Semantic] Cannot cast string '{child.value}' to boolean"
                )

        raise ValueError(f"[Semantic] Invalid cast '{child.type}' -> '{target}'")


def _is_numeric(t: str) -> bool:
    return t in ("number", "float")


def _arith_result_type(a: str, b: str) -> str:
    return "float" if "float" in (a, b) else "number"


class BinOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        left = self.children[0].evaluate(st)
        right = self.children[1].evaluate(st)

        if self.value == "+":
            if _is_numeric(left.type) and _is_numeric(right.type):
                return Variable(left.value + right.value,
                                _arith_result_type(left.type, right.type))
            raise ValueError("[Semantic] Operator '+' expects numeric operands")

        if self.value == "..":
            def to_string(variable: Variable) -> str:
                if variable.type == "boolean":
                    return "true" if variable.value else "false"
                return str(variable.value)
            return Variable(to_string(left) + to_string(right), "string")

        if self.value == "-":
            if _is_numeric(left.type) and _is_numeric(right.type):
                return Variable(left.value - right.value,
                                _arith_result_type(left.type, right.type))
            raise ValueError("[Semantic] Operator '-' expects numeric operands")

        if self.value == "*":
            if _is_numeric(left.type) and _is_numeric(right.type):
                return Variable(left.value * right.value,
                                _arith_result_type(left.type, right.type))
            raise ValueError("[Semantic] Operator '*' expects numeric operands")

        if self.value == "/":
            if _is_numeric(left.type) and _is_numeric(right.type):
                if right.value == 0:
                    raise ValueError("[Semantic] Division by zero")
                # int/int continua sendo divisão inteira (truncamento),
                # qualquer envolvimento de float vira divisão real
                if "float" in (left.type, right.type):
                    return Variable(left.value / right.value, "float")
                return Variable(int(left.value / right.value), "number")
            raise ValueError("[Semantic] Operator '/' expects numeric operands")

        if self.value == "==":
            # Permite comparar number com float diretamente
            if _is_numeric(left.type) and _is_numeric(right.type):
                return Variable(left.value == right.value, "boolean")
            if left.type != right.type:
                raise ValueError("[Semantic] Operator '==' expects operands of the same type")
            return Variable(left.value == right.value, "boolean")

        if self.value == ">":
            if _is_numeric(left.type) and _is_numeric(right.type):
                return Variable(left.value > right.value, "boolean")
            if left.type == right.type == "string":
                return Variable(left.value > right.value, "boolean")
            raise ValueError("[Semantic] Operator '>' expects numeric or string operands")

        if self.value == "<":
            if _is_numeric(left.type) and _is_numeric(right.type):
                return Variable(left.value < right.value, "boolean")
            if left.type == right.type == "string":
                return Variable(left.value < right.value, "boolean")
            raise ValueError("[Semantic] Operator '<' expects numeric or string operands")

        if self.value == "and":
            if left.type == right.type == "boolean":
                return Variable(left.value and right.value, "boolean")
            raise ValueError("[Semantic] Operator 'and' expects boolean and boolean")

        if self.value == "or":
            if left.type == right.type == "boolean":
                return Variable(left.value or right.value, "boolean")
            raise ValueError("[Semantic] Operator 'or' expects boolean or boolean")

        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")


class Identifier(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return st.get_value(self.value)


class Assignment(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        var_name = self.children[0].value
        var_value = self.children[1].evaluate(st)
        st.set_value(var_name, var_value)


class VarDec(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        name = self.children[0].value
        st.create_variable(name, self.value)
        if len(self.children) > 1:
            st.set_value(name, self.children[1].evaluate(st))


class Print(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        result = self.children[0].evaluate(st)
        if result.type == "boolean":
            print("true" if result.value else "false")
        else:
            print(result.value)


class Read(Node):
    def __init__(self, value="read", children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        raw = input()
        if re.fullmatch(r"[+-]?\d+", raw):
            return Variable(int(raw), "number")
        if re.fullmatch(r"[+-]?\d+\.\d+", raw):
            return Variable(float(raw), "float")
        if raw == "true":
            return Variable(True, "boolean")
        if raw == "false":
            return Variable(False, "boolean")
        return Variable(raw, "string")


class If(Node):
    """2 ou 3 filhos: [cond, if_block, else_block?]"""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        cond = self.children[0].evaluate(st)
        if cond.type != "boolean":
            raise ValueError("[Semantic] If condition must be boolean")
        if cond.value:
            self.children[1].evaluate(st)
        elif len(self.children) > 2:
            self.children[2].evaluate(st)


class While(Node):
    """2 filhos: [cond, block]"""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        while True:
            cond = self.children[0].evaluate(st)
            if cond.type != "boolean":
                raise ValueError("[Semantic] While condition must be boolean")
            if not cond.value:
                break
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
    "local": "VAR",
    "true": "BOOL",
    "false": "BOOL",
    "string": "TYPE",
    "number": "TYPE",
    "boolean": "TYPE",
    "float": "TYPE",
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

        if ch == '"':
            self.position += 1
            string_value = ""
            while self.position < len(s) and s[self.position] != '"':
                if s[self.position] == "\n":
                    raise ValueError("[Lexer] Unterminated string literal")
                string_value += s[self.position]
                self.position += 1
            if self.position >= len(s):
                raise ValueError("[Lexer] Unterminated string literal")
            self.position += 1
            self.next = Token("STR", string_value)
            return

        if ch == ".":
            self.position += 1
            if self.position < len(s) and s[self.position] == ".":
                self.position += 1
                self.next = Token("CONCAT", "..")
                return
            raise ValueError(f"[Lexer] Invalid symbol '.' at position {self.position - 1}")

        if ch == ":":
            self.position += 1
            self.next = Token("COLON", ":")
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

            # Float literal: dígitos '.' dígitos (cuidado para não confundir com '..')
            if (
                self.position < len(s)
                and s[self.position] == "."
                and self.position + 1 < len(s)
                and s[self.position + 1].isdigit()
            ):
                num += "."
                self.position += 1
                while self.position < len(s) and s[self.position].isdigit():
                    num += s[self.position]
                    self.position += 1
                self.next = Token("FLOAT", float(num))
                return

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

    @staticmethod
    def parse_factor() -> Node:
        token = Parser.lexer.next

        if token.type == "INT":
            node = IntVal(token.value)
            Parser.lexer.select_next()
            return node

        if token.type == "FLOAT":
            node = FloatVal(token.value)
            Parser.lexer.select_next()
            return node

        if token.type == "BOOL":
            node = BoolVal(token.value == "true")
            Parser.lexer.select_next()
            return node

        if token.type == "STR":
            node = StringVal(token.value)
            Parser.lexer.select_next()
            return node

        if token.type in ("PLUS", "MINUS", "NOT"):
            op = token.value
            Parser.lexer.select_next()
            return UnOp(op, [Parser.parse_factor()])

        if token.type == "OPEN_PAR":
            Parser.lexer.select_next()

            # Cast: (TYPE) factor  -- maior prioridade depois dos parênteses
            if Parser.lexer.next.type == "TYPE":
                cast_type = Parser.lexer.next.value
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise ValueError(
                        f"[Parser] Expected ')' after cast type, got {Parser.lexer.next.type}"
                    )
                Parser.lexer.select_next()
                # cast aplica-se ao próximo fator (encadeia com outro cast/paren)
                operand = Parser.parse_factor()
                return Cast(cast_type, [operand])

            # Parênteses normais
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

    @staticmethod
    def parse_term() -> Node:
        result = Parser.parse_factor()
        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_factor()])
        return result

    @staticmethod
    def parse_expression() -> Node:
        result = Parser.parse_term()
        while Parser.lexer.next.type in ("PLUS", "MINUS", "CONCAT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_term()])
        return result

    @staticmethod
    def parse_rel_expression() -> Node:
        result = Parser.parse_expression()
        while Parser.lexer.next.type in ("EQ", "GT", "LT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_expression()])
        return result

    @staticmethod
    def parse_bool_term() -> Node:
        result = Parser.parse_rel_expression()
        while Parser.lexer.next.type == "AND":
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_rel_expression()])
        return result

    @staticmethod
    def parse_bool_expression() -> Node:
        result = Parser.parse_bool_term()
        while Parser.lexer.next.type == "OR":
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_bool_term()])
        return result

    @staticmethod
    def parse_block() -> Node:
        stmts = []
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
                    f"[Parser] Expected newline inside block, got {Parser.lexer.next.type}"
                )
        return Block("block", stmts)

    @staticmethod
    def parse_statement() -> Node:
        token = Parser.lexer.next

        if token.type in ("EOL", "EOF"):
            return NoOp()

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

        if token.type == "IF":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after if, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after if cond, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_IF_BRA":
                raise ValueError(
                    f"[Parser] Expected 'then', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            if_block = Parser.parse_block()

            children = [cond, if_block]
            if Parser.lexer.next.type == "ELSE":
                Parser.lexer.select_next()
                while Parser.lexer.next.type == "EOL":
                    Parser.lexer.select_next()
                children.append(Parser.parse_block())

            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close if, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return If("if", children)

        if token.type == "WHILE":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after while, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after while cond, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_BRA":
                raise ValueError(
                    f"[Parser] Expected 'do', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close while, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return While("while", [cond, body])

        if token.type == "OPEN_BRA":
            Parser.lexer.select_next()
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close block, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return body

        if token.type == "VAR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise ValueError(
                    f"[Parser] Expected identifier after local, got {Parser.lexer.next.type}"
                )
            iden_node = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()

            # Aceita 'local x number', 'local x: number' e 'local x::number'
            if Parser.lexer.next.type == "COLON":
                Parser.lexer.select_next()
                if Parser.lexer.next.type == "COLON":
                    Parser.lexer.select_next()

            if Parser.lexer.next.type != "TYPE":
                raise ValueError(
                    f"[Parser] Expected type after variable name, got {Parser.lexer.next.type}"
                )
            var_type = Parser.lexer.next.value
            Parser.lexer.select_next()

            children = [iden_node]
            if Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                children.append(Parser.parse_bool_expression())
            return VarDec(var_type, children)

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