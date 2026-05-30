from sintan import ASTNode, Parser, print_ast
from analiser import LexicalAnalyzer


class SemanticAnalyzer:

    def __init__(self):

        self.symbol_table = {}
        self.errors = []
        self.triads = []
        self.triad_num = 1

        # Реестр функций: имя → {"return_type": str, "params": [{"name": str, "type": str}, ...]}
        self.function_table = {}

        # Текущая функция (для проверки return)
        self._current_func = None

    # =====================================================
    # ТРИАДЫ
    # =====================================================

    def add_triad(self, op, arg1, arg2):

        triad = (
            self.triad_num,
            op,
            arg1,
            arg2
        )

        self.triads.append(triad)

        self.triad_num += 1

        return f"^{triad[0]}"

    # =====================================================
    # ОСНОВНОЙ ОБХОД
    # =====================================================

    def analyze(self, node, scope="global"):

        method = getattr(
            self,
            f"visit_{node.kind}",
            self.generic_visit
        )

        return method(node, scope)

    def generic_visit(self, node, scope):

        for child in node.children:
            self.analyze(child, scope)

    # =====================================================
    # ФУНКЦИИ
    # =====================================================

    def visit_FunctionDef(self, node, scope):

        func_name = node.attrs.get("name")
        return_type = node.attrs.get("return_type", "unknown")

        # Собираем список параметров из узла ParamList
        params = []
        for child in node.children:
            if child.kind == "ParamList":
                for param in child.children:
                    params.append({
                        "name": param.attrs.get("name"),
                        "type": param.attrs.get("type"),
                    })

        # Регистрируем функцию в таблице функций
        self.function_table[func_name] = {
            "return_type": return_type,
            "params": params,
        }

        # Обходим тело, запомнив текущую функцию для проверки return
        prev_func = self._current_func
        self._current_func = func_name

        for child in node.children:
            self.analyze(child, func_name)

        self._current_func = prev_func

    # =====================================================
    # ОПЕРАТОР RETURN
    # =====================================================

    def visit_ReturnStmt(self, node, scope):
        """
        Проверяет, что тип возвращаемого значения совпадает
        с объявленным типом функции.
        Например: функция объявлена как int, а return true; — ошибка.
        """

        if self._current_func is None or self._current_func not in self.function_table:
            self.generic_visit(node, scope)
            return

        expected_type = self.function_table[self._current_func]["return_type"]

        if not node.children:
            # return; — возвращает void
            if expected_type != "void":
                self.errors.append(
                    f"Семантическая ошибка: "
                    f"функция '{self._current_func}' объявлена как '{expected_type}', "
                    f"но возвращает void (пустой return)"
                )
            return

        expr = node.children[0]
        actual_type = self.get_expression_type(expr)

        if actual_type != expected_type:
            self.errors.append(
                f"Ошибка типов: "
                f"функция '{self._current_func}' объявлена как '{expected_type}', "
                f"но оператор return возвращает значение типа '{actual_type}'"
            )

        # Генерируем триаду для return
        result = self.process_expression(expr)
        self.add_triad("return", result, "-")

    # =====================================================
    # ПАРАМЕТРЫ
    # =====================================================

    def visit_Param(self, node, scope):

        name = node.attrs["name"]

        if name in self.symbol_table:

            self.errors.append(
                f"Семантическая ошибка: "
                f"повторное объявление параметра '{name}'"
            )

        else:

            self.symbol_table[name] = {
                "type": node.attrs["type"],
                "declared": True,
                "initialized": True,
                "scope": scope
            }

    # =====================================================
    # ОБЪЯВЛЕНИЕ ПЕРЕМЕННЫХ
    # =====================================================

    def visit_VarDecl(self, node, scope):

        name = node.attrs["name"]
        var_type = node.attrs["type"]

        # Повторное объявление
        if name in self.symbol_table:

            self.errors.append(
                f"Семантическая ошибка: "
                f"повторное объявление переменной '{name}'"
            )

            return

        initialized = False

        self.symbol_table[name] = {
            "type": var_type,
            "declared": True,
            "initialized": initialized,
            "scope": scope
        }

        # Инициализация
        if node.children:

            initialized = True

            init_node = node.children[0].children[0]

            expr_type = self.get_expression_type(init_node)

            # Проверка типов
            if expr_type != var_type:

                self.errors.append(
                    f"Ошибка типов: "
                    f"переменная '{name}' имеет тип '{var_type}', "
                    f"но ей присваивается значение типа '{expr_type}'"
                )

            self.symbol_table[name]["initialized"] = True

            result = self.process_expression(init_node)

            self.add_triad(":=", name, result)

    # =====================================================
    # ВЫРАЖЕНИЕ-ОПЕРАТОР (x; или i++;)
    # =====================================================

    def visit_ExprStmt(self, node, scope):
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
                f"Семантическая ошибка: "
                f"выражение-оператор '{name};' не имеет эффекта — "
                f"переменная упомянута без присваивания или вызова функции"
            )

            return

        if expr.kind == "Literal":

            self.errors.append(
                f"Семантическая ошибка: "
                f"выражение-оператор '{expr.attrs.get('value')};' не имеет эффекта"
            )

            return

        # Допустимые случаи: FuncCall, PostfixExpr — обходим дочерние узлы
        self.generic_visit(node, scope)

    # =====================================================
    # ПРИСВАИВАНИЕ
    # =====================================================

    def visit_AssignStmt(self, node, scope):

        target = node.attrs["target"]

        # Проверка объявления
        if target not in self.symbol_table:

            self.errors.append(
                f"Семантическая ошибка: "
                f"переменная '{target}' используется "
                f"до объявления"
            )

            return

        expr = node.children[0]

        left_type = self.symbol_table[target]["type"]

        right_type = self.get_expression_type(expr)

        # Проверка типов
        if left_type != right_type:

            self.errors.append(
                f"Ошибка типов: "
                f"переменная '{target}' имеет тип '{left_type}', "
                f"а выражение имеет тип '{right_type}'"
            )

        result = self.process_expression(expr)

        self.add_triad(":=", target, result)

        self.symbol_table[target]["initialized"] = True

    # =====================================================
    # ОПРЕДЕЛЕНИЕ ТИПА ВЫРАЖЕНИЯ
    # =====================================================

    def get_expression_type(self, node):

        # Константы
        if node.kind == "Literal":

            value = str(node.attrs["value"])

            if value in ["true", "false"]:
                return "bool"

            return "int"

        # Идентификаторы
        if node.kind == "Identifier":

            name = node.attrs["name"]

            if name not in self.symbol_table:

                self.errors.append(
                    f"Семантическая ошибка: "
                    f"переменная '{name}' используется "
                    f"до объявления"
                )

                return "unknown"

            # Проверка инициализации
            if not self.symbol_table[name]["initialized"]:

                self.errors.append(
                    f"Семантическая ошибка: "
                    f"переменная '{name}' используется "
                    f"до инициализации"
                )

            return self.symbol_table[name]["type"]

        # Бинарные выражения
        if node.kind == "BinaryExpr":

            left_type = self.get_expression_type(
                node.children[0]
            )

            right_type = self.get_expression_type(
                node.children[1]
            )

            op = node.attrs["op"]

            # Арифметические операции
            if op in ["+", "-", "*", "/"]:

                if left_type != "int" or right_type != "int":

                    self.errors.append(
                        f"Ошибка типов: "
                        f"арифметическая операция '{op}' "
                        f"допустима только для int"
                    )

                return "int"

            # Сравнение
            if op in [">", "<", ">=", "<=", "==", "!="]:

                if left_type != right_type:

                    self.errors.append(
                        f"Ошибка типов: "
                        f"сравнение разных типов "
                        f"('{left_type}' и '{right_type}')"
                    )

                return "bool"

            # Логические операции
            if op in ["&&", "||"]:

                if left_type != "bool" or right_type != "bool":

                    self.errors.append(
                        f"Ошибка типов: "
                        f"логическая операция '{op}' "
                        f"требует bool"
                    )

                return "bool"

        # Вызов функции
        if node.kind == "FuncCall":

            func_name = node.attrs["name"]

            if func_name in self.function_table:

                func_info = self.function_table[func_name]
                expected_params = func_info["params"]
                actual_args = node.children

                # Проверка количества аргументов
                if len(actual_args) != len(expected_params):

                    self.errors.append(
                        f"Семантическая ошибка: "
                        f"функция '{func_name}' ожидает "
                        f"{len(expected_params)} аргумент(а/ов), "
                        f"передано {len(actual_args)}"
                    )

                else:

                    # Проверка типов аргументов
                    for i, (arg, param) in enumerate(zip(actual_args, expected_params)):

                        arg_type = self.get_expression_type(arg)

                        if arg_type != param["type"]:

                            self.errors.append(
                                f"Ошибка типов: "
                                f"аргумент {i + 1} функции '{func_name}' "
                                f"должен быть '{param['type']}', "
                                f"передан '{arg_type}'"
                            )

                return func_info["return_type"]

            return "int"

        return "unknown"

    # =====================================================
    # ОБРАБОТКА ВЫРАЖЕНИЙ
    # =====================================================

    def process_expression(self, node):

        # Константа
        if node.kind == "Literal":

            return node.attrs["value"]

        # Идентификатор
        if node.kind == "Identifier":

            return node.attrs["name"]

        # Бинарное выражение
        if node.kind == "BinaryExpr":

            left = self.process_expression(
                node.children[0]
            )

            right = self.process_expression(
                node.children[1]
            )

            return self.add_triad(
                node.attrs["op"],
                left,
                right
            )

        # Вызов функции
        if node.kind == "FuncCall":

            func_name = node.attrs["name"]

            args = []

            for arg in node.children:

                args.append(
                    self.process_expression(arg)
                )

            return self.add_triad(
                f"call {func_name}",
                ", ".join(args),
                "-"
            )

        # Постфикс
        if node.kind == "PostfixExpr":

            ident = self.process_expression(
                node.children[0]
            )

            return self.add_triad(
                node.attrs["op"],
                ident,
                "-"
            )

        return "?"

    # =====================================================
    # ВЫВОД ТАБЛИЦЫ СИМВОЛОВ
    # =====================================================

    def print_symbol_table(self):

        print("\nТАБЛИЦА СИМВОЛОВ")

        print("-" * 70)

        print(
            f"{'Имя':<15}"
            f"{'Тип':<10}"
            f"{'Объявлена':<15}"
            f"{'Инициализирована':<20}"
            f"{'Область'}"
        )

        print("-" * 70)

        for name, info in self.symbol_table.items():

            print(
                f"{name:<15}"
                f"{info['type']:<10}"
                f"{str(info['declared']):<15}"
                f"{str(info['initialized']):<20}"
                f"{info['scope']}"
            )

    # =====================================================
    # ВЫВОД ТРИАД
    # =====================================================

    def print_triads(self):

        print("\nТРИАДЫ")

        print("-" * 40)

        for num, op, a1, a2 in self.triads:

            print(
                f"{num}) ({op}, {a1}, {a2})"
            )


# =========================================================
# MAIN
# =========================================================

def main():

    with open(
        "test_cleaned.cpp",
        "r",
        encoding="utf-8"
    ) as f:

        source = f.read()

    # Лексический анализ
    lexer = LexicalAnalyzer(source)

    tokens = lexer.tokenize()

    # Синтаксический анализ
    parser = Parser(tokens)

    ast = parser.parse_program()

    # Семантический анализ
    analyzer = SemanticAnalyzer()

    analyzer.analyze(ast)

    # Вывод таблицы
    analyzer.print_symbol_table()

    print()

    # Ошибки
    if analyzer.errors:

        print("СЕМАНТИЧЕСКИЕ ОШИБКИ:\n")

        for error in analyzer.errors:
            print(error)

    else:

        print(
            "Семантический анализ "
            "завершён успешно. "
            "Ошибок не найдено."
        )

    # Триады
    analyzer.print_triads()


if __name__ == "__main__":
    main()