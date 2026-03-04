import sys


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")

    def select_next(self) -> None:
        s = self.source

        # Ignora espaços em branco
        while self.position < len(s) and s[self.position].isspace():
            self.position += 1

        # EOF
        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        # Operadores
        if ch == "+":
            self.position += 1
            self.next = Token("PLUS", "+")
            return

        if ch == "-":
            self.position += 1
            self.next = Token("MINUS", "-")
            return

        if ch == "^":
            self.position += 1
            self.next = Token("XOR", "^")
            return

        # INT (múltiplos dígitos)
        if ch.isdigit():
            num = ""
            while self.position < len(s) and s[self.position].isdigit():
                num += s[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
            return

        # Símbolo inválido
        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


class Parser:
    lexer = None  # atributo estático

    @staticmethod
    def parse_expression() -> int:
        if Parser.lexer is None:
            raise RuntimeError("[Parser] Lexer not initialized")

        if Parser.lexer.next.type != "INT":
            raise ValueError(f"[Parser] Expected INT, got {Parser.lexer.next.type}")

        result = Parser.lexer.next.value
        Parser.lexer.select_next()

        # EXPR := INT ((PLUS|MINUS|XOR) INT)*
        while Parser.lexer.next.type in ("PLUS", "MINUS", "XOR"):
            op = Parser.lexer.next.type
            Parser.lexer.select_next()

            if Parser.lexer.next.type != "INT":
                raise ValueError(f"[Parser] Expected INT after {op}, got {Parser.lexer.next.type}")

            value = Parser.lexer.next.value
            if op == "PLUS":
                result += value
            elif op == "MINUS":
                result -= value
            else:  # XOR
                result ^= value  # XOR bitwise em Python

            Parser.lexer.select_next()

        return result

    @staticmethod
    def run(code: str) -> int:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()

        result = Parser.parse_expression()

        if Parser.lexer.next.type != "EOF":
            raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

        return result


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else input()
    try:
        print(Parser.run(code))
    except Exception as e:
        print(e)
        sys.exit(1)  # importante pro tester: erro => exit != 0


if __name__ == "__main__":
    main()