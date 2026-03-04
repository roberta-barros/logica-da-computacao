import sys


class Token:
    def __init__(self, type_, value):
        # atributos exigidos: type (string) e value (int|string)
        self.type = type_
        self.value = value


class Lexer:
    def __init__(self, source: str):
        # atributos exigidos: source (string), position (int), next (Token)
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")  # placeholder

    def select_next(self) -> None:
        s = self.source

        # ignora espaços
        while self.position < len(s) and s[self.position].isspace():
            self.position += 1

        # EOF
        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        if ch == "+":
            self.position += 1
            self.next = Token("PLUS", "+")
            return

        if ch == "-":
            self.position += 1
            self.next = Token("MINUS", "-")
            return

        if ch.isdigit():
            start = self.position
            while self.position < len(s) and s[self.position].isdigit():
                self.position += 1
            number_str = s[start:self.position]
            self.next = Token("INT", int(number_str))
            return


        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")

    def selectNext(self) -> None:
        self.select_next()


class Parser:
    lexer = None | None

    @staticmethod
    def parse_expression() -> int:
        if Parser.lexer is None:
            raise RuntimeError("[Parser] Lexer not initialized")

        # EXPR := INT ((PLUS|MINUS) INT)*
        if Parser.lexer.next.type != "INT":
            raise ValueError(f"[Parser] Expected INT, got {Parser.lexer.next.type}")

        result = Parser.lexer.next.value
        Parser.lexer.selectNext()

        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.type
            Parser.lexer.selectNext()

            if Parser.lexer.next.type != "INT":
                raise ValueError(f"[Parser] Expected INT after {op}, got {Parser.lexer.next.type}")

            if op == "PLUS":
                result += Parser.lexer.next.value
            else:  # MINUS
                result -= Parser.lexer.next.value

            Parser.lexer.selectNext()

        return result

    @staticmethod
    def run(code: str) -> int:
        Parser.lexer = Lexer(code)
        Parser.lexer.selectNext()

        result = Parser.parse_expression()

        if Parser.lexer.next.type != "EOF":
            raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

        return result

    @staticmethod
    def parseExpression() -> int:
        return Parser.parse_expression()


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else input()
    try:
        print(Parser.run(code))
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()