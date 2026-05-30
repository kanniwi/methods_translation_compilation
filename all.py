"""
Компилятор C++ (учебный)
Модули: препроцессор → лексический анализ → синтаксический анализ → семантический анализ
Запуск: python all.py test.cpp
"""

import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# =============================================================================
# МОДУЛЬ 1: ПРЕПРОЦЕССОР
# =============================================================================

class CodeCleaner:
    """Очистка исходного кода от комментариев и лишних символов."""

    def __init__(self):
        self.single_comment = re.compile(r'//.*$', re.MULTILINE)
        self.multi_comment  = re.compile(r'/\*.*?\*/', re.DOTALL)
        self.trim_spaces    = re.compile(r'^\s+|\s+$', re.MULTILINE)
        self.multiple_spaces = re.compile(r'\s+')
        self.empty_lines    = re.compile(r'\n\s*\n')
        self.invalid_chars  = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')

    def clean(self, code: str):
        errors = []

        # 1. Проверка недопустимых символов
        for line_num, line in enumerate(code.split('\n'), 1):
            invalid = self.invalid_chars.findall(line)
            if invalid:
                errors.append(f"Строка {line_num}: недопустимые символы {invalid}")

        # 2. Незакрытые многострочные комментарии
        if code.count('/*') != code.count('*/'):
            errors.append("ОШИБКА: незакрытый многострочный комментарий")
            return "", errors

        # 3. Удаление комментариев
        cleaned = self.multi_comment.sub('', code)
        cleaned = self.single_comment.sub('', cleaned)

        # 4–7. Нормализация пробелов и пустых строк
        cleaned = self.trim_spaces.sub('', cleaned)
        cleaned = self.multiple_spaces.sub(' ', cleaned)
        cleaned = self.empty_lines.sub('\n', cleaned)
        cleaned = cleaned.strip('\n')

        return cleaned, errors


# =============================================================================
# МОДУЛЬ 2: ЛЕКСИЧЕСКИЙ АНАЛИЗ
# =============================================================================

class TokenType(Enum):
    KEYWORD         = "KEYWORD"
    IDENTIFIER      = "IDENTIFIER"
    CONSTANT_INT    = "CONSTANT_INT"
    CONSTANT_FLOAT  = "CONSTANT_FLOAT"
    CONSTANT_STRING = "CONSTANT_STRING"
    CONSTANT_BOOL   = "CONSTANT_BOOL"
    OPERATOR        = "OPERATOR"
    DELIMITER       = "DELIMITER"
    ERROR           = "ERROR"


class Token:
    def __init__(self, type_: TokenType, value: str, line: int, column: int):
        self.type   = type_
        self.value  = value
        self.line   = line
        self.column = column

    def __repr__(self):
        return f"({self.type.value}, {self.value})"


class LexicalAnalyzer:
    def __init__(self, source: str):
        self.source = source
        self.pos    = 0
        self.line   = 1
        self.column = 1
        self.errors: List[str] = []

        self.keywords = {
            "int", "bool", "if", "else", "for", "while", "return",
            "using", "namespace", "include", "iostream", "endl", "main", "cout"
        }
        self.identifiers = {
            "add", "x", "y", "result", "isPositive",
            "i", "j", "a", "b", "std"
        }
        self.boolean_constants = {"true", "false"}
        self.operators = {
            "=", "+", "-", "*", "/", ">", "<", ">=", "<=", "==", "!=",
            "&&", "||", "!", "++", "--", "+=", "-=", "*=", "/=", "<<", ">>"
        }
        self.delimiters = {';', ',', '(', ')', '{', '}', ':', '[', ']', '#', '<', '>'}

    def _is_keyword(self, word):         return word in self.keywords
    def _is_identifier(self, word):      return word in self.identifiers
    def _is_boolean_constant(self, word): return word in self.boolean_constants
    def _is_operator_start(self, char):  return char in "=+-*/><&|!%"
    def _is_delimiter(self, char):       return char in self.delimiters

    def _skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos].isspace():
            if self.source[self.pos] == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def _read_identifier(self) -> Token:
        start_col = self.column
        value = ""
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            value += self.source[self.pos]
            self.pos += 1
            self.column += 1

        if self._is_keyword(value):
            return Token(TokenType.KEYWORD, value, self.line, start_col)
        elif self._is_boolean_constant(value):
            return Token(TokenType.CONSTANT_BOOL, value, self.line, start_col)
        elif self._is_identifier(value):
            return Token(TokenType.IDENTIFIER, value, self.line, start_col)
        else:
            if value[0].isdigit():
                self.errors.append(f"Лексическая ошибка: идентификатор не может начинаться с цифры '{value}' на строке {self.line}")
            else:
                self.errors.append(f"Лексическая ошибка: неизвестный идентификатор '{value}' на строке {self.line}")
            return Token(TokenType.ERROR, value, self.line, start_col)

    def _read_number(self) -> Token:
        start_col = self.column
        value = ""
        has_decimal = False
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == '.'):
            if self.source[self.pos] == '.':
                if has_decimal:
                    self.errors.append(f"Лексическая ошибка: некорректное число (две точки подряд) на строке {self.line}")
                    return Token(TokenType.ERROR, value, self.line, start_col)
                has_decimal = True
            value += self.source[self.pos]
            self.pos += 1
            self.column += 1

        if self.pos < len(self.source) and self.source[self.pos].isalpha():
            next_char = self.source[self.pos]
            self.errors.append(f"Лексическая ошибка: буква в числовой константе '{value}{next_char}' на строке {self.line}")
            return Token(TokenType.ERROR, value + next_char, self.line, start_col)

        return Token(TokenType.CONSTANT_FLOAT if has_decimal else TokenType.CONSTANT_INT, value, self.line, start_col)

    def _read_string(self) -> Token:
        start_col = self.column
        value = ""
        quote = self.source[self.pos]
        self.pos += 1
        self.column += 1
        closed = False
        while self.pos < len(self.source):
            if self.source[self.pos] == quote:
                closed = True
                self.pos += 1
                self.column += 1
                break
            if self.source[self.pos] == '\n':
                break
            value += self.source[self.pos]
            self.pos += 1
            self.column += 1

        if not closed:
            self.errors.append(f"Лексическая ошибка: незакрытая строковая константа на строке {self.line}")
            return Token(TokenType.ERROR, value, self.line, start_col)
        return Token(TokenType.CONSTANT_STRING, value, self.line, start_col)

    def _read_operator(self) -> Token:
        start_col = self.column
        if self.pos + 1 < len(self.source):
            two_char = self.source[self.pos:self.pos + 2]
            if two_char in self.operators:
                self.pos += 2
                self.column += 2
                return Token(TokenType.OPERATOR, two_char, self.line, start_col)
        value = self.source[self.pos]
        if value in self.operators:
            self.pos += 1
            self.column += 1
            return Token(TokenType.OPERATOR, value, self.line, start_col)
        self.errors.append(f"Лексическая ошибка: неизвестный оператор '{value}' на строке {self.line}")
        self.pos += 1
        self.column += 1
        return Token(TokenType.ERROR, value, self.line, start_col)

    def tokenize(self) -> List[Token]:
        tokens = []
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break
            current = self.source[self.pos]

            if current.isalpha() or current == '_':
                token = self._read_identifier()
            elif current.isdigit():
                token = self._read_number()
            elif current in ('"', "'"):
                token = self._read_string()
            elif self._is_operator_start(current):
                token = self._read_operator()
            elif self._is_delimiter(current):
                token = Token(TokenType.DELIMITER, current, self.line, self.column)
                self.pos += 1
                self.column += 1
            else:
                self.errors.append(f"Лексическая ошибка: недопустимый символ '{current}' на строке {self.line}")
                token = Token(TokenType.ERROR, current, self.line, self.column)
                self.pos += 1
                self.column += 1

            tokens.append(token)
        return tokens

    def get_errors(self) -> List[str]:
        return self.errors

    def print_token_table(self, tokens: List[Token]):
        print(f"{'Лексема':<35} | Тип")
        print("-" * 35 + "+" + "-" * 20)
        for token in tokens:
            display = token.value.replace('\n', '\\n').replace('\r', '\\r')
            print(f"{display:<35} | {token.type.value}")

    def print_token_sequence(self, tokens: List[Token]):
        print("\n[", end="")
        for i, token in enumerate(tokens):
            display = token.value.replace('\n', '\\n').replace('\r', '\\r')
            print(f"({token.type.value}, {display})", end="")
            if i < len(tokens) - 1:
                print(", ", end="")
        print("]")


# =============================================================================
# МОДУЛЬ 3: СИНТАКСИЧЕСКИЙ АНАЛИЗ
# =============================================================================

@dataclass
class ASTNode:
    kind: str
    attrs: dict = field(default_factory=dict)
    children: List["ASTNode"] = field(default_factory=list)

    def add(self, child: "ASTNode") -> "ASTNode":
        self.children.append(child)
        return self


def _tree_lines(node: ASTNode, prefix: str = "", is_last: bool = True, *, is_root: bool = False) -> List[str]:
    connector = "`-- " if is_last else "|-- "
    head = node.kind
    if node.attrs:
        attrs_str = ", ".join(f"{k}={v}" for k, v in node.attrs.items())
        head = f"{node.kind} [{attrs_str}]"
    lines = [head] if is_root else [f"{prefix}{connector}{head}"]
    child_prefix = prefix + ("    " if is_last else "|   ")
    for i, ch in enumerate(node.children):
        lines.extend(_tree_lines(ch, child_prefix, i == len(node.children) - 1))
    return lines


def print_ast(node: ASTNode) -> None:
    for line in _tree_lines(node, is_root=True):
        print(line)


class ParseError(Exception):
    pass


class Parser:
    TYPE_KEYWORDS = {"int", "bool", "double", "char", "void", "float"}

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.errors: List[str] = []

    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def peek(self, k: int = 0) -> Optional[Token]:
        i = self.pos + k
        return self.tokens[i] if 0 <= i < len(self.tokens) else None

    def advance(self) -> Optional[Token]:
        tok = self.peek()
        if tok is not None:
            self.pos += 1
        return tok

    def match(self, typ: TokenType, value: str = None) -> Optional[Token]:
        tok = self.peek()
        if tok is None or tok.type != typ:
            return None
        if value is not None and tok.value != value:
            return None
        self.pos += 1
        return tok

    def expect(self, typ: TokenType, value: str = None, what: str = None) -> Token:
        tok = self.peek()
        expected = what or (f"{typ.value} '{value}'" if value else typ.value)
        if tok is None:
            raise ParseError(f"Конец потока токенов: ожидалось {expected}")
        if tok.type != typ or (value is not None and tok.value != value):
            raise ParseError(
                f"Строка {tok.line}, столбец {tok.column}: "
                f"ожидалось {expected}, получено {tok.type.value} '{tok.value}'"
            )
        self.pos += 1
        return tok

    def sync_to(self, stop_values: set) -> None:
        while True:
            tok = self.peek()
            if tok is None or tok.value in stop_values:
                return
            self.pos += 1

    def _is_type_keyword(self) -> bool:
        tok = self.peek()
        return tok is not None and tok.type == TokenType.KEYWORD and tok.value in self.TYPE_KEYWORDS

    def _is_rel_op(self, tok: Token) -> bool:
        return tok.type == TokenType.OPERATOR and tok.value in {"==", "!=", "<=", ">=", "<", ">"}

    # ── Программа ──────────────────────────────────────────────────────────────

    def parse_program(self) -> ASTNode:
        root = ASTNode("Program")
        if self.peek() and self.peek().type == TokenType.DELIMITER and self.peek().value == "#":
            root.add(self.parse_include())
        if self.peek() and self.peek().type == TokenType.KEYWORD and self.peek().value == "using":
            root.add(self.parse_using_namespace())
        while not self.at_end():
            root.add(self.parse_function_def())
        return root

    def parse_include(self) -> ASTNode:
        try:
            self.expect(TokenType.DELIMITER, "#", what="символ '#'")
            self.expect(TokenType.KEYWORD, "include", what="ключевое слово 'include'")
            self.expect(TokenType.OPERATOR, "<", what="'<' после include")
            tok = self.peek()
            if tok is None or tok.type not in {TokenType.IDENTIFIER, TokenType.KEYWORD}:
                raise ParseError(f"{'Конец потока' if tok is None else f'Строка {tok.line}'}: ожидалось имя заголовочного файла")
            header = self.advance()
            self.expect(TokenType.OPERATOR, ">", what="'>' после имени заголовка")
            return ASTNode("Include", attrs={"header": header.value})
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "{"})
            return ASTNode("Include", attrs={"error": "parse_failed"})

    def parse_using_namespace(self) -> ASTNode:
        try:
            self.expect(TokenType.KEYWORD, "using", what="ключевое слово 'using'")
            self.expect(TokenType.KEYWORD, "namespace", what="ключевое слово 'namespace'")
            ns = self.expect(TokenType.IDENTIFIER, what="имя пространства имён")
            self.expect(TokenType.DELIMITER, ";", what="';' в конце using namespace")
            return ASTNode("UsingNamespace", attrs={"name": ns.value})
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "{"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("UsingNamespace", attrs={"error": "parse_failed"})

    def parse_function_def(self) -> ASTNode:
        try:
            ret_type = self.parse_type()
            name_tok = self.peek()
            if name_tok is None or name_tok.type not in {TokenType.IDENTIFIER, TokenType.KEYWORD}:
                line = name_tok.line if name_tok else "?"
                raise ParseError(f"Строка {line}: ожидалось имя функции")
            name = self.advance()
            self.expect(TokenType.DELIMITER, "(", what="'(' после имени функции")
            params = self.parse_param_list()
            self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка параметров")
            body = self.parse_block()
            return ASTNode("FunctionDef", attrs={"name": name.value, "return_type": ret_type.value}, children=[params, body])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({"}"})
            self.match(TokenType.DELIMITER, "}")
            return ASTNode("FunctionDef", attrs={"error": "parse_failed"})

    def parse_param_list(self) -> ASTNode:
        node = ASTNode("ParamList")
        if not self._is_type_keyword():
            return node
        node.add(self.parse_param())
        while self.match(TokenType.DELIMITER, ","):
            node.add(self.parse_param())
        return node

    def parse_param(self) -> ASTNode:
        typ = self.parse_type()
        name = self.expect(TokenType.IDENTIFIER, what="имя параметра")
        return ASTNode("Param", attrs={"name": name.value, "type": typ.value})

    def parse_type(self) -> Token:
        tok = self.peek()
        expected_list = "/".join(sorted(self.TYPE_KEYWORDS))
        if tok is None:
            raise ParseError(f"Конец потока: ожидался тип ({expected_list})")
        if tok.type != TokenType.KEYWORD or tok.value not in self.TYPE_KEYWORDS:
            raise ParseError(
                f"Строка {tok.line}, столбец {tok.column}: "
                f"ожидался тип ({expected_list}), получено {tok.type.value} '{tok.value}'"
            )
        self.pos += 1
        return tok

    # ── Блоки и операторы ──────────────────────────────────────────────────────

    def parse_block(self) -> ASTNode:
        try:
            self.expect(TokenType.DELIMITER, "{", what="'{' — начало блока")
            body = self.parse_stmt_list()
            self.expect(TokenType.DELIMITER, "}", what="'}' — конец блока")
            return ASTNode("Block", children=[body])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({"}"})
            self.match(TokenType.DELIMITER, "}")
            return ASTNode("Block", attrs={"error": "unclosed_block"})

    def parse_stmt_list(self) -> ASTNode:
        body = ASTNode("Body")
        while True:
            tok = self.peek()
            if tok is None or (tok.type == TokenType.DELIMITER and tok.value == "}"):
                break
            body.add(self.parse_stmt())
        return body

    def parse_stmt_or_block(self) -> ASTNode:
        tok = self.peek()
        if tok is not None and tok.type == TokenType.DELIMITER and tok.value == "{":
            return self.parse_block()
        return self.parse_stmt()

    def parse_stmt(self) -> ASTNode:
        tok = self.peek()
        if tok is None:
            self.errors.append("Конец потока токенов: ожидался оператор")
            return ASTNode("Stmt", attrs={"error": "eof"})
        if tok.type == TokenType.KEYWORD and tok.value in self.TYPE_KEYWORDS:
            return self.parse_var_decl_stmt()
        if tok.type == TokenType.KEYWORD and tok.value == "if":
            return self.parse_if_stmt()
        if tok.type == TokenType.KEYWORD and tok.value == "for":
            return self.parse_for_stmt()
        if tok.type == TokenType.KEYWORD and tok.value == "while":
            return self.parse_while_stmt()
        if tok.type == TokenType.KEYWORD and tok.value == "return":
            return self.parse_return_stmt()
        if tok.type == TokenType.KEYWORD and tok.value == "cout":
            return self.parse_cout_stmt()
        if tok.type == TokenType.IDENTIFIER:
            next_tok = self.peek(1)
            if next_tok is not None and next_tok.type == TokenType.OPERATOR and next_tok.value == "=":
                return self.parse_assign_stmt()
            return self.parse_expr_stmt()
        self.errors.append(
            f"Строка {tok.line}, столбец {tok.column}: "
            f"неожиданный токен '{tok.value}' ({tok.type.value}) в начале оператора"
        )
        self.advance()
        self.sync_to({";", "}"})
        self.match(TokenType.DELIMITER, ";")
        return ASTNode("Stmt", attrs={"error": "unexpected_token", "got": tok.value})

    def parse_var_decl_stmt(self) -> ASTNode:
        try:
            typ = self.parse_type()
            node = ASTNode("VarDeclStmt", attrs={"type": typ.value})
            node.add(self.parse_var_init(typ.value))
            while self.match(TokenType.DELIMITER, ","):
                node.add(self.parse_var_init(typ.value))
            self.expect(TokenType.DELIMITER, ";", what="';' в конце объявления переменной")
            return node
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("VarDeclStmt", attrs={"error": "parse_failed"})

    def parse_var_init(self, type_str: str) -> ASTNode:
        name = self.expect(TokenType.IDENTIFIER, what="имя переменной")
        node = ASTNode("VarDecl", attrs={"name": name.value, "type": type_str})
        if self.match(TokenType.OPERATOR, "="):
            node.add(ASTNode("Init", children=[self.parse_expr()]))
        return node

    def parse_assign_stmt(self) -> ASTNode:
        try:
            name = self.expect(TokenType.IDENTIFIER, what="имя переменной (левая часть)")
            self.expect(TokenType.OPERATOR, "=", what="оператор присваивания '='")
            value = self.parse_expr()
            self.expect(TokenType.DELIMITER, ";", what="';' после оператора присваивания")
            return ASTNode("AssignStmt", attrs={"target": name.value}, children=[value])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("AssignStmt", attrs={"error": "parse_failed"})

    def parse_expr_stmt(self) -> ASTNode:
        try:
            expr = self.parse_expr()
            self.expect(TokenType.DELIMITER, ";", what="';' после выражения-оператора")
            return ASTNode("ExprStmt", children=[expr])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("ExprStmt", attrs={"error": "parse_failed"})

    def parse_if_stmt(self) -> ASTNode:
        try:
            self.expect(TokenType.KEYWORD, "if", what="ключевое слово 'if'")
            self.expect(TokenType.DELIMITER, "(", what="'(' после 'if'")
            cond = self.parse_expr()
            self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка условия if")
            then_branch = self.parse_stmt_or_block()
            node = ASTNode("IfStmt", children=[
                ASTNode("Condition", children=[cond]),
                ASTNode("Then", children=[then_branch]),
            ])
            if self.match(TokenType.KEYWORD, "else"):
                node.add(ASTNode("Else", children=[self.parse_stmt_or_block()]))
            return node
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("IfStmt", attrs={"error": "parse_failed"})

    def parse_for_stmt(self) -> ASTNode:
        try:
            self.expect(TokenType.KEYWORD, "for", what="ключевое слово 'for'")
            self.expect(TokenType.DELIMITER, "(", what="'(' после 'for'")
            init_node = self._parse_for_init()
            self.expect(TokenType.DELIMITER, ";", what="';' после инициализации for")
            cond_node = ASTNode("ForCondition")
            if not (self.peek() and self.peek().value == ";"):
                cond_node.add(self.parse_expr())
            self.expect(TokenType.DELIMITER, ";", what="';' после условия for")
            update_node = ASTNode("ForUpdate")
            if not (self.peek() and self.peek().value == ")"):
                update_node.add(self.parse_expr())
            self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка заголовка for")
            body = self.parse_stmt_or_block()
            return ASTNode("ForStmt", children=[init_node, cond_node, update_node, body])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({"}"})
            return ASTNode("ForStmt", attrs={"error": "parse_failed"})

    def _parse_for_init(self) -> ASTNode:
        tok = self.peek()
        if tok is None or (tok.type == TokenType.DELIMITER and tok.value == ";"):
            return ASTNode("ForInit")
        if tok.type == TokenType.KEYWORD and tok.value in self.TYPE_KEYWORDS:
            typ = self.parse_type()
            init = ASTNode("ForInit")
            init.add(self.parse_var_init(typ.value))
            return init
        init = ASTNode("ForInit")
        init.add(self.parse_expr())
        return init

    def parse_while_stmt(self) -> ASTNode:
        try:
            self.expect(TokenType.KEYWORD, "while", what="ключевое слово 'while'")
            self.expect(TokenType.DELIMITER, "(", what="'(' после 'while'")
            cond = self.parse_expr()
            self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка условия while")
            body = self.parse_stmt_or_block()
            return ASTNode("WhileStmt", children=[ASTNode("Condition", children=[cond]), body])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({"}"})
            return ASTNode("WhileStmt", attrs={"error": "parse_failed"})

    def parse_return_stmt(self) -> ASTNode:
        try:
            self.expect(TokenType.KEYWORD, "return", what="ключевое слово 'return'")
            node = ASTNode("ReturnStmt")
            if not (self.peek() and self.peek().value == ";"):
                node.add(self.parse_expr())
            self.expect(TokenType.DELIMITER, ";", what="';' после return")
            return node
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("ReturnStmt", attrs={"error": "parse_failed"})

    def parse_cout_stmt(self) -> ASTNode:
        try:
            self.expect(TokenType.KEYWORD, "cout", what="'cout'")
            if not self.match(TokenType.OPERATOR, "<<"):
                tok = self.peek()
                raise ParseError(
                    f"Строка {tok.line if tok else '?'}: ожидался '<<' после cout, "
                    f"получено {tok.type.value + ' ' + tok.value if tok else 'EOF'}"
                )
            node = ASTNode("CoutStmt")
            node.add(self.parse_cout_item())
            while self.match(TokenType.OPERATOR, "<<"):
                node.add(self.parse_cout_item())
            self.expect(TokenType.DELIMITER, ";", what="';' в конце cout")
            return node
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("CoutStmt", attrs={"error": "parse_failed"})

    def parse_cout_item(self) -> ASTNode:
        tok = self.peek()
        if tok is None:
            raise ParseError("Конец потока: ожидался элемент вывода после '<<'")
        if tok.type == TokenType.CONSTANT_STRING:
            self.advance()
            return ASTNode("StringLiteral", attrs={"value": tok.value})
        if tok.type in {TokenType.IDENTIFIER, TokenType.KEYWORD}:
            self.advance()
            return ASTNode("Identifier", attrs={"name": tok.value})
        if tok.type == TokenType.CONSTANT_INT:
            self.advance()
            return ASTNode("Literal", attrs={"type": "int", "value": tok.value})
        raise ParseError(
            f"Строка {tok.line}, столбец {tok.column}: "
            f"ожидалась строка, идентификатор или 'endl' после '<<', "
            f"получено {tok.type.value} '{tok.value}'"
        )

    # ── Выражения ──────────────────────────────────────────────────────────────

    def parse_expr(self) -> ASTNode:
        return self.parse_logical_expr()

    def parse_logical_expr(self) -> ASTNode:
        node = self.parse_rel_expr()
        while True:
            tok = self.peek()
            if tok is None or tok.type != TokenType.OPERATOR or tok.value not in {"&&", "||"}:
                break
            op = tok.value
            self.advance()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, self.parse_rel_expr()])
        return node

    def parse_rel_expr(self) -> ASTNode:
        node = self.parse_add_expr()
        tok = self.peek()
        if tok is not None and self._is_rel_op(tok):
            op = tok.value
            self.advance()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, self.parse_add_expr()])
        return node

    def parse_add_expr(self) -> ASTNode:
        node = self.parse_mul_expr()
        while True:
            tok = self.peek()
            if tok is None or tok.type != TokenType.OPERATOR or tok.value not in {"+", "-"}:
                break
            op = tok.value
            self.advance()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, self.parse_mul_expr()])
        return node

    def parse_mul_expr(self) -> ASTNode:
        node = self.parse_unary_expr()
        while True:
            tok = self.peek()
            if tok is None or tok.type != TokenType.OPERATOR or tok.value not in {"*", "/"}:
                break
            op = tok.value
            self.advance()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, self.parse_unary_expr()])
        return node

    def parse_unary_expr(self) -> ASTNode:
        tok = self.peek()
        if tok is not None and tok.type == TokenType.OPERATOR and tok.value in {"!", "-", "+"}:
            op = tok.value
            self.advance()
            return ASTNode("UnaryExpr", attrs={"op": op}, children=[self.parse_unary_expr()])
        return self.parse_postfix_expr()

    def parse_postfix_expr(self) -> ASTNode:
        node = self.parse_primary()
        tok = self.peek()
        if tok is not None and tok.type == TokenType.OPERATOR and tok.value in {"++", "--"}:
            op = tok.value
            self.advance()
            return ASTNode("PostfixExpr", attrs={"op": op}, children=[node])
        return node

    def parse_primary(self) -> ASTNode:
        tok = self.peek()
        if tok is None:
            raise ParseError("Конец потока токенов: ожидалось выражение")
        if tok.type in {TokenType.CONSTANT_INT, TokenType.CONSTANT_FLOAT, TokenType.CONSTANT_BOOL}:
            self.advance()
            type_map = {TokenType.CONSTANT_INT: "int", TokenType.CONSTANT_FLOAT: "float", TokenType.CONSTANT_BOOL: "bool"}
            return ASTNode("Literal", attrs={"type": type_map[tok.type], "value": tok.value})
        if tok.type == TokenType.CONSTANT_STRING:
            self.advance()
            return ASTNode("StringLiteral", attrs={"value": tok.value})
        if tok.type == TokenType.IDENTIFIER:
            self.advance()
            if self.peek() is not None and self.peek().type == TokenType.DELIMITER and self.peek().value == "(":
                self.advance()
                args = self.parse_arg_list()
                self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка аргументов")
                return ASTNode("FuncCall", attrs={"name": tok.value}, children=args)
            return ASTNode("Identifier", attrs={"name": tok.value})
        if tok.type == TokenType.DELIMITER and tok.value == "(":
            self.advance()
            expr = self.parse_expr()
            self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка выражения")
            return expr
        raise ParseError(
            f"Строка {tok.line}, столбец {tok.column}: "
            f"ожидалось выражение, получено {tok.type.value} '{tok.value}'"
        )

    def parse_arg_list(self) -> List[ASTNode]:
        args: List[ASTNode] = []
        tok = self.peek()
        if tok is None or (tok.type == TokenType.DELIMITER and tok.value == ")"):
            return args
        args.append(self.parse_expr())
        while self.match(TokenType.DELIMITER, ","):
            args.append(self.parse_expr())
        return args


# =============================================================================
# МОДУЛЬ 4: СЕМАНТИЧЕСКИЙ АНАЛИЗ
# =============================================================================

class SemanticAnalyzer:

    def __init__(self):
        self.symbol_table = {}
        self.errors: List[str] = []
        self.triads = []
        self.triad_num = 1
        # Реестр функций: имя → {"return_type": str, "params": [{"name": str, "type": str}, ...]}
        self.function_table: dict = {}
        # Текущая функция (для проверки return)
        self._current_func: str = None

    def add_triad(self, op, arg1, arg2):
        triad = (self.triad_num, op, arg1, arg2)
        self.triads.append(triad)
        self.triad_num += 1
        return f"^{triad[0]}"

    def analyze(self, node: ASTNode, scope: str = "global"):
        method = getattr(self, f"visit_{node.kind}", self.generic_visit)
        return method(node, scope)

    def generic_visit(self, node: ASTNode, scope: str):
        for child in node.children:
            self.analyze(child, scope)

    def visit_FunctionDef(self, node: ASTNode, scope: str):
        func_name = node.attrs.get("name")
        return_type = node.attrs.get("return_type", "unknown")

        # Собираем список параметров из дочернего узла ParamList
        params = []
        for child in node.children:
            if child.kind == "ParamList":
                for param in child.children:
                    params.append({
                        "name": param.attrs.get("name"),
                        "type": param.attrs.get("type"),
                    })

        # Регистрируем функцию
        self.function_table[func_name] = {
            "return_type": return_type,
            "params": params,
        }

        # Обходим тело функции, запомнив текущую функцию для проверки return
        prev_func = self._current_func
        self._current_func = func_name
        for child in node.children:
            self.analyze(child, func_name)
        self._current_func = prev_func

    def visit_ReturnStmt(self, node: ASTNode, scope: str):
        """Проверяет, что тип возвращаемого значения совпадает с объявленным типом функции."""
        if self._current_func is None or self._current_func not in self.function_table:
            self.generic_visit(node, scope)
            return

        expected_type = self.function_table[self._current_func]["return_type"]

        if not node.children:
            # return; — возвращает void
            if expected_type != "void":
                self.errors.append(
                    f"Семантическая ошибка: функция '{self._current_func}' "
                    f"объявлена как '{expected_type}', но возвращает void (пустой return)"
                )
            return

        expr = node.children[0]
        actual_type = self.get_expression_type(expr)

        if actual_type != expected_type:
            self.errors.append(
                f"Ошибка типов: функция '{self._current_func}' объявлена как '{expected_type}', "
                f"но оператор return возвращает значение типа '{actual_type}'"
            )

        # Генерируем триаду для return
        result = self.process_expression(expr)
        self.add_triad("return", result, "-")

    def visit_Param(self, node: ASTNode, scope: str):
        name = node.attrs["name"]
        if name in self.symbol_table:
            self.errors.append(f"Семантическая ошибка: повторное объявление параметра '{name}'")
        else:
            self.symbol_table[name] = {
                "type": node.attrs["type"], "declared": True,
                "initialized": True, "scope": scope
            }

    def visit_VarDecl(self, node: ASTNode, scope: str):
        name = node.attrs["name"]
        var_type = node.attrs["type"]
        if name in self.symbol_table:
            self.errors.append(f"Семантическая ошибка: повторное объявление переменной '{name}'")
            return
        self.symbol_table[name] = {
            "type": var_type, "declared": True,
            "initialized": False, "scope": scope
        }
        if node.children:
            init_node = node.children[0].children[0]
            expr_type = self.get_expression_type(init_node)
            if expr_type != var_type:
                self.errors.append(
                    f"Ошибка типов: переменная '{name}' имеет тип '{var_type}', "
                    f"но ей присваивается значение типа '{expr_type}'"
                )
            self.symbol_table[name]["initialized"] = True
            result = self.process_expression(init_node)
            self.add_triad(":=", name, result)

    def visit_ExprStmt(self, node: ASTNode, scope: str):
        """
        Проверяет выражение-оператор (ExprStmt).
        Голый идентификатор без операции — например, x; — является семантической ошибкой:
        переменная упомянута, но никакого действия не производится.
        Допустимы только: вызов функции (add(x,y);) и постфикс (i++;).
        """
        if not node.children:
            return
        expr = node.children[0]

        if expr.kind == "Identifier":
            name = expr.attrs.get("name", "?")
            self.errors.append(
                f"Семантическая ошибка: выражение-оператор '{name};' не имеет эффекта — "
                f"переменная упомянута без присваивания или вызова функции"
            )
            return

        if expr.kind == "Literal":
            self.errors.append(
                f"Семантическая ошибка: выражение-оператор '{expr.attrs.get('value')};' не имеет эффекта"
            )
            return

        # Допустимые случаи: FuncCall, PostfixExpr — обходим дочерние узлы
        self.generic_visit(node, scope)

    def visit_AssignStmt(self, node: ASTNode, scope: str):
        target = node.attrs["target"]
        if target not in self.symbol_table:
            self.errors.append(f"Семантическая ошибка: переменная '{target}' используется до объявления")
            return
        expr = node.children[0]
        left_type = self.symbol_table[target]["type"]
        right_type = self.get_expression_type(expr)
        if left_type != right_type:
            self.errors.append(
                f"Ошибка типов: переменная '{target}' имеет тип '{left_type}', "
                f"а выражение имеет тип '{right_type}'"
            )
        result = self.process_expression(expr)
        self.add_triad(":=", target, result)
        self.symbol_table[target]["initialized"] = True

    def get_expression_type(self, node: ASTNode) -> str:
        if node.kind == "Literal":
            return "bool" if str(node.attrs["value"]) in ["true", "false"] else "int"
        if node.kind == "Identifier":
            name = node.attrs["name"]
            if name not in self.symbol_table:
                self.errors.append(f"Семантическая ошибка: переменная '{name}' используется до объявления")
                return "unknown"
            if not self.symbol_table[name]["initialized"]:
                self.errors.append(f"Семантическая ошибка: переменная '{name}' используется до инициализации")
            return self.symbol_table[name]["type"]
        if node.kind == "BinaryExpr":
            left_type  = self.get_expression_type(node.children[0])
            right_type = self.get_expression_type(node.children[1])
            op = node.attrs["op"]
            if op in ["+", "-", "*", "/"]:
                if left_type != "int" or right_type != "int":
                    self.errors.append(f"Ошибка типов: арифметическая операция '{op}' допустима только для int")
                return "int"
            if op in [">", "<", ">=", "<=", "==", "!="]:
                if left_type != right_type:
                    self.errors.append(f"Ошибка типов: сравнение разных типов ('{left_type}' и '{right_type}')")
                return "bool"
            if op in ["&&", "||"]:
                if left_type != "bool" or right_type != "bool":
                    self.errors.append(f"Ошибка типов: логическая операция '{op}' требует bool")
                return "bool"
        if node.kind == "FuncCall":
            func_name = node.attrs["name"]
            if func_name in self.function_table:
                func_info = self.function_table[func_name]
                expected_params = func_info["params"]
                actual_args = node.children
                # Проверка количества аргументов
                if len(actual_args) != len(expected_params):
                    self.errors.append(
                        f"Семантическая ошибка: функция '{func_name}' ожидает "
                        f"{len(expected_params)} аргумент(а/ов), передано {len(actual_args)}"
                    )
                else:
                    # Проверка типов аргументов
                    for i, (arg, param) in enumerate(zip(actual_args, expected_params)):
                        arg_type = self.get_expression_type(arg)
                        if arg_type != param["type"]:
                            self.errors.append(
                                f"Ошибка типов: аргумент {i + 1} функции '{func_name}' "
                                f"должен быть '{param['type']}', передан '{arg_type}'"
                            )
                return func_info["return_type"]
            return "int"
        return "unknown"

    def process_expression(self, node: ASTNode) -> str:
        if node.kind == "Literal":
            return node.attrs["value"]
        if node.kind == "Identifier":
            return node.attrs["name"]
        if node.kind == "BinaryExpr":
            left  = self.process_expression(node.children[0])
            right = self.process_expression(node.children[1])
            return self.add_triad(node.attrs["op"], left, right)
        if node.kind == "FuncCall":
            func_name = node.attrs["name"]
            if func_name in self.function_table:
                expected_params = self.function_table[func_name]["params"]
                actual_args = node.children
                if len(actual_args) != len(expected_params):
                    # Ошибка уже добавлена в get_expression_type, просто генерируем триаду как есть
                    pass
            args = [self.process_expression(arg) for arg in node.children]
            return self.add_triad(f"call {func_name}", ", ".join(args), "-")
        if node.kind == "PostfixExpr":
            ident = self.process_expression(node.children[0])
            return self.add_triad(node.attrs["op"], ident, "-")
        return "?"

    def print_symbol_table(self):
        print("\nТАБЛИЦА СИМВОЛОВ")
        print("-" * 70)
        print(f"{'Имя':<15}{'Тип':<10}{'Объявлена':<15}{'Инициализирована':<20}{'Область'}")
        print("-" * 70)
        for name, info in self.symbol_table.items():
            print(f"{name:<15}{info['type']:<10}{str(info['declared']):<15}{str(info['initialized']):<20}{info['scope']}")

    def print_triads(self):
        print("\nТРИАДЫ")
        print("-" * 40)
        for num, op, a1, a2 in self.triads:
            print(f"{num}) ({op}, {a1}, {a2})")


# =============================================================================
# ТОЧКА ВХОДА
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Использование: python all.py <файл.cpp>")
        print("Пример:        python all.py test.cpp")
        sys.exit(1)

    input_file = sys.argv[1]
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Ошибка: файл '{input_file}' не найден")
        sys.exit(1)

    # ── 1. Препроцессор ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ЭТАП 1: ПРЕПРОЦЕССОР")
    print("=" * 60)
    cleaner = CodeCleaner()
    cleaned_code, pre_errors = cleaner.clean(source_code)
    print(cleaned_code)
    if pre_errors:
        for e in pre_errors:
            print(e)
        print("Препроцессор завершён с ошибками — дальнейший анализ невозможен.")
        sys.exit(1)
    else:
        print("\nПрепроцессор: ошибок не выявлено")

    # ── 2. Лексический анализ ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ЭТАП 2: ЛЕКСИЧЕСКИЙ АНАЛИЗ")
    print("=" * 60)
    lexer = LexicalAnalyzer(cleaned_code)
    tokens = lexer.tokenize()
    lexer.print_token_table(tokens)
    lexer.print_token_sequence(tokens)
    print(f"\nОбнаружено токенов: {len(tokens)}")
    lex_errors = lexer.get_errors()
    if lex_errors:
        print("\nЛексические ошибки:")
        for e in lex_errors:
            print(f"  {e}")
    else:
        print("Лексических ошибок не найдено.")

    # ── 3. Синтаксический анализ ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ЭТАП 3: СИНТАКСИЧЕСКИЙ АНАЛИЗ")
    print("=" * 60)
    parser = Parser(tokens)
    ast: Optional[ASTNode] = None
    try:
        ast = parser.parse_program()
    except ParseError as e:
        parser.errors.append(str(e))

    if parser.errors:
        print("Синтаксические ошибки:")
        for e in parser.errors:
            print(f"  {e}")
    else:
        print("Синтаксических ошибок не найдено.")

    if ast is not None:
        print("\nАСТ (Абстрактное синтаксическое дерево):")
        print_ast(ast)

    # ── 4. Семантический анализ ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ЭТАП 4: СЕМАНТИЧЕСКИЙ АНАЛИЗ")
    print("=" * 60)
    if ast is not None:
        sem = SemanticAnalyzer()
        sem.analyze(ast)
        sem.print_symbol_table()
        if sem.errors:
            print("\nСЕМАНТИЧЕСКИЕ ОШИБКИ:")
            for e in sem.errors:
                print(f"  {e}")
        else:
            print("\nСемантический анализ завершён успешно. Ошибок не найдено.")
        sem.print_triads()
    else:
        print("Семантический анализ пропущен (AST не построен).")

    # ── Итог ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    all_errors = pre_errors + lex_errors + parser.errors + (sem.errors if ast else [])
    if all_errors:
        print(f"Компиляция завершена с ошибками: {len(all_errors)} шт.")
    else:
        print("Компиляция завершена успешно. Ошибок не найдено.")
    print("=" * 60)


if __name__ == "__main__":
    main()