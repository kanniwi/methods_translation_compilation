from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import List, Optional

from analiser import LexicalAnalyzer, Token, TokenType

@dataclass
class ASTNode:
    kind: str
    attrs: dict = field(default_factory=dict)
    children: List[ASTNode] = field(default_factory=list)

    def add(self, child: ASTNode) -> ASTNode:
        """Добавить дочерний узел; возвращает self для цепочки вызовов."""
        self.children.append(child)
        return self



def _tree_lines(
    node: ASTNode,
    prefix: str = "",
    is_last: bool = True,
    *,
    is_root: bool = False,
) -> List[str]:
    """Рекурсивно собирает строки для консольного вывода дерева."""
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
    """Вывод AST в виде ASCII-дерева."""
    for line in _tree_lines(node, is_root=True):
        print(line)


class ParseError(Exception):
    """Выбрасывается методом expect() при несовпадении токена."""


class Parser:

    # Ключевые слова, обозначающие типы данных
    TYPE_KEYWORDS = {"int", "bool", "double", "char", "void", "float"}

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.errors: List[str] = []


    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def peek(self, k: int = 0) -> Optional[Token]:
        """Посмотреть токен на позиции pos+k, не двигая pos."""
        i = self.pos + k
        return self.tokens[i] if 0 <= i < len(self.tokens) else None

    def advance(self) -> Optional[Token]:
        """Взять текущий токен и сдвинуть pos."""
        tok = self.peek()
        if tok is not None:
            self.pos += 1
        return tok

    def match(self, typ: TokenType, value: str = None) -> Optional[Token]:
        """
        Мягкая проверка: если текущий токен подходит — съесть и вернуть.
        Иначе вернуть None, pos не трогать.
        """
        tok = self.peek()
        if tok is None:
            return None
        if tok.type != typ:
            return None
        if value is not None and tok.value != value:
            return None
        self.pos += 1
        return tok

    def expect(
        self,
        typ: TokenType,
        value: str = None,
        what: str = None,
    ) -> Token:
        
        tok = self.peek()
        expected = what or (f"{typ.value} '{value}'" if value else typ.value)

        if tok is None:
            raise ParseError(f"Конец потока токенов: ожидалось {expected}")

        if tok.type != typ or (value is not None and tok.value != value):
            got = f"{tok.type.value} '{tok.value}'"
            raise ParseError(
                f"Строка {tok.line}, столбец {tok.column}: "
                f"ожидалось {expected}, получено {got}"
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
        return (
            tok is not None
            and tok.type == TokenType.KEYWORD
            and tok.value in self.TYPE_KEYWORDS
        )

    def _is_rel_op(self, tok: Token) -> bool:
        """Токен — оператор сравнения?"""
        return (
            tok.type == TokenType.OPERATOR
            and tok.value in {"==", "!=", "<=", ">=", "<", ">"}
        )

    def parse_program(self) -> ASTNode:
        """Корень дерева: вся программа."""
        root = ASTNode("Program")

        # #include <iostream>
        if (
            self.peek()
            and self.peek().type == TokenType.DELIMITER
            and self.peek().value == "#"
        ):
            root.add(self.parse_include())

        # using namespace std;
        if (
            self.peek()
            and self.peek().type == TokenType.KEYWORD
            and self.peek().value == "using"
        ):
            root.add(self.parse_using_namespace())

        # Одна или несколько функций (add, main, …)
        while not self.at_end():
            root.add(self.parse_function_def())

        return root

    # include := '#' 'include' '<' HEADER '>'
    def parse_include(self) -> ASTNode:
        """#include <iostream> → Include[header=iostream]"""
        try:
            self.expect(TokenType.DELIMITER, "#", what="символ '#'")
            self.expect(TokenType.KEYWORD, "include", what="ключевое слово 'include'")
            # '<' токенизируется как OPERATOR (проходит через _is_operator_start)
            self.expect(TokenType.OPERATOR, "<", what="'<' после include")
            # 'iostream' в лексере ЛР2 является KEYWORD, не IDENTIFIER
            tok = self.peek()
            if tok is None or tok.type not in {TokenType.IDENTIFIER, TokenType.KEYWORD}:
                raise ParseError(
                    f"{'Конец потока' if tok is None else f'Строка {tok.line}'}: "
                    "ожидалось имя заголовочного файла"
                )
            header = self.advance()
            self.expect(TokenType.OPERATOR, ">", what="'>' после имени заголовка")
            return ASTNode("Include", attrs={"header": header.value})
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "{"})
            return ASTNode("Include", attrs={"error": "parse_failed"})

    # using_namespace := 'using' 'namespace' IDENTIFIER ';'
    def parse_using_namespace(self) -> ASTNode:
        """using namespace std; → UsingNamespace[name=std]"""
        try:
            self.expect(TokenType.KEYWORD, "using", what="ключевое слово 'using'")
            self.expect(TokenType.KEYWORD, "namespace", what="ключевое слово 'namespace'")
            ns = self.expect(TokenType.IDENTIFIER, what="имя пространства имён (например, std)")
            self.expect(TokenType.DELIMITER, ";", what="';' в конце using namespace")
            return ASTNode("UsingNamespace", attrs={"name": ns.value})
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "{"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("UsingNamespace", attrs={"error": "parse_failed"})

    # function_def := type FUNC_NAME '(' param_list ')' block
    def parse_function_def(self) -> ASTNode:
        try:
            ret_type = self.parse_type()

            # Имя функции: в лексере ЛР2 'main' является KEYWORD, 'add' — IDENTIFIER
            name_tok = self.peek()
            if name_tok is None or name_tok.type not in {
                TokenType.IDENTIFIER,
                TokenType.KEYWORD,
            }:
                line = name_tok.line if name_tok else "?"
                raise ParseError(
                    f"Строка {line}: ожидалось имя функции, "
                    f"получено {name_tok.type.value + ' ' + name_tok.value if name_tok else 'EOF'}"
                )
            name = self.advance()

            self.expect(TokenType.DELIMITER, "(", what="'(' после имени функции")
            params = self.parse_param_list()
            self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка параметров")
            body = self.parse_block()

            return ASTNode(
                "FunctionDef",
                attrs={"name": name.value, "return_type": ret_type.value},
                children=[params, body],
            )
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({"}"})
            self.match(TokenType.DELIMITER, "}")
            return ASTNode("FunctionDef", attrs={"error": "parse_failed"})

    # param_list := (param (',' param)*)?
    def parse_param_list(self) -> ASTNode:
        """Список параметров функции → ParamList[Param*, ...]"""
        node = ASTNode("ParamList")
        if not self._is_type_keyword():
            return node  # пустой список параметров
        node.add(self.parse_param())
        while self.match(TokenType.DELIMITER, ","):
            node.add(self.parse_param())
        return node

    # param := type IDENTIFIER
    def parse_param(self) -> ASTNode:
        """int a → Param[name=a, type=int]"""
        typ = self.parse_type()
        name = self.expect(TokenType.IDENTIFIER, what="имя параметра")
        return ASTNode("Param", attrs={"name": name.value, "type": typ.value})

    # type := KEYWORD (int|bool|double|char|void|float)
    def parse_type(self) -> Token:
        tok = self.peek()
        expected_list = "/".join(sorted(self.TYPE_KEYWORDS))
        if tok is None:
            raise ParseError(f"Конец потока: ожидался тип ({expected_list})")
        if tok.type != TokenType.KEYWORD or tok.value not in self.TYPE_KEYWORDS:
            raise ParseError(
                f"Строка {tok.line}, столбец {tok.column}: "
                f"ожидался тип ({expected_list}), "
                f"получено {tok.type.value} '{tok.value}'"
            )
        self.pos += 1
        return tok

    # block := '{' stmt_list '}'
    def parse_block(self) -> ASTNode:
        """{ операторы } → Block[Body[stmt*]]"""
        try:
            self.expect(TokenType.DELIMITER, "{", what="'{' — начало блока")
            body = self.parse_stmt_list()
            self.expect(TokenType.DELIMITER, "}", what="'}' — конец блока (незакрытый блок?)")
            return ASTNode("Block", children=[body])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({"}"})
            self.match(TokenType.DELIMITER, "}")
            return ASTNode("Block", attrs={"error": "unclosed_block"})

    # stmt_list := stmt*
    def parse_stmt_list(self) -> ASTNode:
        """Последовательность операторов до закрывающей '}'."""
        body = ASTNode("Body")
        while True:
            tok = self.peek()
            if tok is None or (tok.type == TokenType.DELIMITER and tok.value == "}"):
                break
            body.add(self.parse_stmt())
        return body

    def parse_stmt_or_block(self) -> ASTNode:
        """
        После if/else/for/while:
        либо блок { } , либо одиночный оператор.
        """
        tok = self.peek()
        if tok is not None and tok.type == TokenType.DELIMITER and tok.value == "{":
            return self.parse_block()
        return self.parse_stmt()

    # stmt := var_decl_stmt | assign_stmt | if_stmt | for_stmt
    #       | while_stmt | return_stmt | cout_stmt | expr_stmt
    def parse_stmt(self) -> ASTNode:
        """
        Выбор ветки по первому токену оператора.
        """
        tok = self.peek()
        if tok is None:
            self.errors.append("Конец потока токенов: ожидался оператор")
            return ASTNode("Stmt", attrs={"error": "eof"})

        # Объявление переменной: начинается с типа
        if tok.type == TokenType.KEYWORD and tok.value in self.TYPE_KEYWORDS:
            return self.parse_var_decl_stmt()

        # Условный оператор
        if tok.type == TokenType.KEYWORD and tok.value == "if":
            return self.parse_if_stmt()

        # Цикл for
        if tok.type == TokenType.KEYWORD and tok.value == "for":
            return self.parse_for_stmt()

        # Цикл while
        if tok.type == TokenType.KEYWORD and tok.value == "while":
            return self.parse_while_stmt()

        # Оператор return
        if tok.type == TokenType.KEYWORD and tok.value == "return":
            return self.parse_return_stmt()

        # Вывод cout
        if tok.type == TokenType.KEYWORD and tok.value == "cout":
            return self.parse_cout_stmt()

        # IDENTIFIER: присваивание или выражение-оператор
        if tok.type == TokenType.IDENTIFIER:
            next_tok = self.peek(1)
            if (
                next_tok is not None
                and next_tok.type == TokenType.OPERATOR
                and next_tok.value == "="
            ):
                return self.parse_assign_stmt()
            return self.parse_expr_stmt()

        # Неожиданный токен
        self.errors.append(
            f"Строка {tok.line}, столбец {tok.column}: "
            f"неожиданный токен '{tok.value}' ({tok.type.value}) "
            f"в начале оператора"
        )
        self.advance()
        self.sync_to({";", "}"})
        self.match(TokenType.DELIMITER, ";")
        return ASTNode("Stmt", attrs={"error": "unexpected_token", "got": tok.value})

    # var_decl_stmt := type var_init (',' var_init)* ';'
    def parse_var_decl_stmt(self) -> ASTNode:
        """
        int x = 5, y = 10;
        → VarDeclStmt[type=int]
            VarDecl[name=x, type=int]
                Init → Literal[type=int, value=5]
            VarDecl[name=y, type=int]
                Init → Literal[type=int, value=10]
        """
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

    # var_init := IDENTIFIER ('=' expr)?
    def parse_var_init(self, type_str: str) -> ASTNode:
        """
        x = 5  →  VarDecl[name=x, type=int]
                      Init → Literal[...]
        result →  VarDecl[name=result, type=int]   (без инициализатора)
        """
        name = self.expect(TokenType.IDENTIFIER, what="имя переменной")
        node = ASTNode("VarDecl", attrs={"name": name.value, "type": type_str})
        if self.match(TokenType.OPERATOR, "="):
            node.add(ASTNode("Init", children=[self.parse_expr()]))
        return node

    # assign_stmt := IDENTIFIER '=' expr ';'
    def parse_assign_stmt(self) -> ASTNode:
        """
        result = x * y - 3;
        → AssignStmt[target=result]
              BinaryExpr[op=-] ...
        """
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

    # expr_stmt := expr ';'
    def parse_expr_stmt(self) -> ASTNode:
        """
        j++;   →  ExprStmt → PostfixExpr[op=++] → Identifier[name=j]
        """
        try:
            expr = self.parse_expr()
            self.expect(TokenType.DELIMITER, ";", what="';' после выражения-оператора")
            return ASTNode("ExprStmt", children=[expr])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("ExprStmt", attrs={"error": "parse_failed"})

    # if_stmt := 'if' '(' expr ')' stmt_or_block ('else' stmt_or_block)?
    def parse_if_stmt(self) -> ASTNode:
        """
        if (result > 0) { ... } else { ... }
        → IfStmt
              Condition → BinaryExpr[op=>]
              Then → Block
              Else → Block
        """
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
                else_branch = self.parse_stmt_or_block()
                node.add(ASTNode("Else", children=[else_branch]))

            return node
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({";", "}"})
            self.match(TokenType.DELIMITER, ";")
            return ASTNode("IfStmt", attrs={"error": "parse_failed"})

    # for_stmt := 'for' '(' for_init ';' expr? ';' expr? ')' stmt_or_block
    def parse_for_stmt(self) -> ASTNode:
        """
        for (int i = 0; i < 3; i++) { ... }
        → ForStmt
              ForInit → VarDecl[name=i, type=int] → Init → Literal[0]
              ForCondition → BinaryExpr[op=<]
              ForUpdate → PostfixExpr[op=++]
              Block
        """
        try:
            self.expect(TokenType.KEYWORD, "for", what="ключевое слово 'for'")
            self.expect(TokenType.DELIMITER, "(", what="'(' после 'for'")

            init_node = self._parse_for_init()
            self.expect(TokenType.DELIMITER, ";", what="';' после инициализации for")

            # Условие (может быть пустым)
            cond_node = ASTNode("ForCondition")
            if not (self.peek() and self.peek().value == ";"):
                cond_node.add(self.parse_expr())
            self.expect(TokenType.DELIMITER, ";", what="';' после условия for")

            # Обновление (может быть пустым)
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
        """
        Инициализация цикла for (без завершающего ';'):
          int i = 0   →  ForInit → VarDecl[name=i, type=int]
          пусто       →  ForInit
        """
        tok = self.peek()
        if tok is None or (tok.type == TokenType.DELIMITER and tok.value == ";"):
            return ASTNode("ForInit")
        if tok.type == TokenType.KEYWORD and tok.value in self.TYPE_KEYWORDS:
            typ = self.parse_type()
            init = ASTNode("ForInit")
            init.add(self.parse_var_init(typ.value))
            return init
        # Присваивание или выражение без ';'
        init = ASTNode("ForInit")
        init.add(self.parse_expr())
        return init

    # while_stmt := 'while' '(' expr ')' stmt_or_block
    def parse_while_stmt(self) -> ASTNode:
        """
        while (j < 2) { j++; }
        → WhileStmt
              Condition → BinaryExpr[op=<]
              Block
        """
        try:
            self.expect(TokenType.KEYWORD, "while", what="ключевое слово 'while'")
            self.expect(TokenType.DELIMITER, "(", what="'(' после 'while'")
            cond = self.parse_expr()
            self.expect(TokenType.DELIMITER, ")", what="')' — закрывающая скобка условия while")
            body = self.parse_stmt_or_block()
            return ASTNode("WhileStmt", children=[
                ASTNode("Condition", children=[cond]),
                body,
            ])
        except ParseError as e:
            self.errors.append(str(e))
            self.sync_to({"}"})
            return ASTNode("WhileStmt", attrs={"error": "parse_failed"})

    # return_stmt := 'return' expr? ';'
    def parse_return_stmt(self) -> ASTNode:
        """
        return a + b;  →  ReturnStmt → BinaryExpr[op=+]
        return 0;      →  ReturnStmt → Literal[type=int, value=0]
        """
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

    # cout_stmt := 'cout' ('<<' cout_item)+ ';'
    def parse_cout_stmt(self) -> ASTNode:
        """
        cout << i << " ";
        → CoutStmt
              Identifier[name=i]
              StringLiteral[value= ]
        """
        try:
            # В лексере ЛР2 'cout' является KEYWORD
            self.expect(TokenType.KEYWORD, "cout", what="'cout'")
            if not self.match(TokenType.OPERATOR, "<<"):
                tok = self.peek()
                raise ParseError(
                    f"Строка {tok.line if tok else '?'}: "
                    f"ожидался '<<' после cout, "
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
        """
        Элемент вывода после '<<':
        строка, идентификатор или ключевое слово (endl).
        """
        tok = self.peek()
        if tok is None:
            raise ParseError("Конец потока: ожидался элемент вывода после '<<'")

        if tok.type == TokenType.CONSTANT_STRING:
            self.advance()
            return ASTNode("StringLiteral", attrs={"value": tok.value})

        # IDENTIFIER (переменная) или KEYWORD (endl) — оба допустимы в cout
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

    # ── Выражения (приоритет: || < && < сравнения < + - < * / < унарные < постфикс < primary)

    def parse_expr(self) -> ASTNode:
        """Точка входа в разбор выражений."""
        return self.parse_logical_expr()

    # logical_expr := rel_expr (('&&' | '||') rel_expr)*
    def parse_logical_expr(self) -> ASTNode:
        """
        x < y && isPositive
        → BinaryExpr[op=&&]
              BinaryExpr[op=<]
              Identifier[name=isPositive]
        """
        node = self.parse_rel_expr()
        while True:
            tok = self.peek()
            if (
                tok is None
                or tok.type != TokenType.OPERATOR
                or tok.value not in {"&&", "||"}
            ):
                break
            op = tok.value
            self.advance()
            rhs = self.parse_rel_expr()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, rhs])
        return node

    # rel_expr := add_expr (relop add_expr)?
    def parse_rel_expr(self) -> ASTNode:
        """
        result > 0
        → BinaryExpr[op=>]
              Identifier[name=result]
              Literal[type=int, value=0]
        """
        node = self.parse_add_expr()
        tok = self.peek()
        if tok is not None and self._is_rel_op(tok):
            op = tok.value
            self.advance()
            rhs = self.parse_add_expr()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, rhs])
        return node

    # add_expr := mul_expr (('+' | '-') mul_expr)*
    def parse_add_expr(self) -> ASTNode:
        node = self.parse_mul_expr()
        while True:
            tok = self.peek()
            if (
                tok is None
                or tok.type != TokenType.OPERATOR
                or tok.value not in {"+", "-"}
            ):
                break
            op = tok.value
            self.advance()
            rhs = self.parse_mul_expr()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, rhs])
        return node

    # mul_expr := unary_expr (('*' | '/') unary_expr)*
    def parse_mul_expr(self) -> ASTNode:
        node = self.parse_unary_expr()
        while True:
            tok = self.peek()
            if (
                tok is None
                or tok.type != TokenType.OPERATOR
                or tok.value not in {"*", "/"}
            ):
                break
            op = tok.value
            self.advance()
            rhs = self.parse_unary_expr()
            node = ASTNode("BinaryExpr", attrs={"op": op}, children=[node, rhs])
        return node

    # unary_expr := ('!' | '-' | '+') unary_expr | postfix_expr
    def parse_unary_expr(self) -> ASTNode:
        tok = self.peek()
        if (
            tok is not None
            and tok.type == TokenType.OPERATOR
            and tok.value in {"!", "-", "+"}
        ):
            op = tok.value
            self.advance()
            inner = self.parse_unary_expr()
            return ASTNode("UnaryExpr", attrs={"op": op}, children=[inner])
        return self.parse_postfix_expr()

    # postfix_expr := primary ('++' | '--')?
    def parse_postfix_expr(self) -> ASTNode:
        """
        i++  →  PostfixExpr[op=++] → Identifier[name=i]
        """
        node = self.parse_primary()
        tok = self.peek()
        if (
            tok is not None
            and tok.type == TokenType.OPERATOR
            and tok.value in {"++", "--"}
        ):
            op = tok.value
            self.advance()
            return ASTNode("PostfixExpr", attrs={"op": op}, children=[node])
        return node

    # primary := IDENTIFIER ('(' arg_list ')')? | literal | '(' expr ')'
    def parse_primary(self) -> ASTNode:
        """
        Листья выражения: константы, переменные, вызовы функций, скобки.
        """
        tok = self.peek()
        if tok is None:
            raise ParseError("Конец потока токенов: ожидалось выражение")

        # Числовые и булевы константы
        if tok.type in {
            TokenType.CONSTANT_INT,
            TokenType.CONSTANT_FLOAT,
            TokenType.CONSTANT_BOOL,
        }:
            self.advance()
            type_map = {
                TokenType.CONSTANT_INT: "int",
                TokenType.CONSTANT_FLOAT: "float",
                TokenType.CONSTANT_BOOL: "bool",
            }
            return ASTNode("Literal", attrs={"type": type_map[tok.type], "value": tok.value})

        # Строковая константа
        if tok.type == TokenType.CONSTANT_STRING:
            self.advance()
            return ASTNode("StringLiteral", attrs={"value": tok.value})

        # Идентификатор или вызов функции
        if tok.type == TokenType.IDENTIFIER:
            self.advance()
            # Проверяем '(' — вызов функции
            if (
                self.peek() is not None
                and self.peek().type == TokenType.DELIMITER
                and self.peek().value == "("
            ):
                self.advance()  # '('
                args = self.parse_arg_list()
                self.expect(
                    TokenType.DELIMITER, ")", what="')' — закрывающая скобка аргументов"
                )
                return ASTNode("FuncCall", attrs={"name": tok.value}, children=args)
            return ASTNode("Identifier", attrs={"name": tok.value})

        # Скобочное выражение
        if tok.type == TokenType.DELIMITER and tok.value == "(":
            self.advance()
            expr = self.parse_expr()
            self.expect(
                TokenType.DELIMITER, ")", what="')' — закрывающая скобка выражения"
            )
            return expr

        raise ParseError(
            f"Строка {tok.line}, столбец {tok.column}: "
            f"ожидалось выражение, получено {tok.type.value} '{tok.value}'"
        )

    # arg_list := (expr (',' expr)*)?
    def parse_arg_list(self) -> List[ASTNode]:
        """
        add(x, y)  →  [Identifier[name=x], Identifier[name=y]]
        """
        args: List[ASTNode] = []
        tok = self.peek()
        if tok is None or (tok.type == TokenType.DELIMITER and tok.value == ")"):
            return args  # пустой список аргументов
        args.append(self.parse_expr())
        while self.match(TokenType.DELIMITER, ","):
            args.append(self.parse_expr())
        return args



def main() -> None:
    try:
        with open("test_cleaned.cpp", "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print("Ошибка: файл test_cleaned.cpp не найден.")
        sys.exit(1)

    lex = LexicalAnalyzer(source)
    tokens = lex.tokenize()
    lex_errors = lex.get_errors()

    if lex_errors:
        print("Лексические ошибки (из ЛР2):")
        for e in lex_errors:
            print(f"  {e}")
        print()

    parser = Parser(tokens)
    ast: Optional[ASTNode] = None

    try:
        ast = parser.parse_program()
    except ParseError as e:
        parser.errors.append(str(e))


    if parser.errors:
        print("\nСинтаксические ошибки:")
        for e in parser.errors:
            print(f"  {e}")
        print()

    if ast is not None:
        print("\nАСТ (Абстрактное синтаксическое дерево):")
        print_ast(ast)

    print()
    if not parser.errors:
        print("Синтаксический анализ завершён успешно. Ошибок не найдено.")
    else:
        print("Синтаксический анализ завершён с ошибками.")


if __name__ == "__main__":
    main()