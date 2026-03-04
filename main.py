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

    def selectNext(self) -> None:
        s = self.source

        # Ignorar espaços em branco
        while self.position < len(s) and s[self.position].isspace():
            self.position += 1

        # EOF
        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        # PLUS
        if ch == "+":
            self.position += 1
            self.next = Token("PLUS", "+")
            return

        # MINUS
        if ch == "-":
            self.position += 1
            self.next = Token("MINUS", "-")
            return

        # INT (pode ter vários dígitos)
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
    def parseExpression() -> int:
        if Parser.lexer is None:
            raise RuntimeError("[Parser] Lexer not initialized")

        # Se o next token não é um número, ERRO
        if Parser.lexer.next.type != "INT":
            raise ValueError(f"[Parser] Expected INT, got {Parser.lexer.next.type}")

        # Resultado recebe o valor do next token INT
        result = Parser.lexer.next.value

        # Posicione no próximo token
        Parser.lexer.selectNext()

        # Enquanto o next token for PLUS ou MINUS
        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.type

            # Posicione no próximo token
            Parser.lexer.selectNext()

            # Se o next token não é um número, ERRO
            if Parser.lexer.next.type != "INT":
                raise ValueError(f"[Parser] Expected INT after {op}, got {Parser.lexer.next.type}")

            # Atualize o resultado conforme a operação indicada
            if op == "PLUS":
                result += Parser.lexer.next.value
            else:  # MINUS
                result -= Parser.lexer.next.value

            # Posicione no próximo token
            Parser.lexer.selectNext()

        # retorne o resultado
        return result

    @staticmethod
    def run(code: str) -> int:
        Parser.lexer = Lexer(code)

        # posiciona no primeiro token
        Parser.lexer.selectNext()

        # parseia expressão
        result = Parser.parseExpression()

        if Parser.lexer.next.type != "EOF":
            raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

        return result


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else input()
    try:
        print(Parser.run(code))
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()