import re
from enum import Enum
from typing import List, Tuple, Optional

class TokenType(Enum):
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    CONSTANT_INT = "CONSTANT_INT"
    CONSTANT_FLOAT = "CONSTANT_FLOAT"
    CONSTANT_STRING = "CONSTANT_STRING"
    CONSTANT_BOOL = "CONSTANT_BOOL"
    OPERATOR = "OPERATOR"
    DELIMITER = "DELIMITER"
    ERROR = "ERROR"

class Token:
    def __init__(self, type_: TokenType, value: str, line: int, column: int):
        self.type = type_
        self.value = value
        self.line = line
        self.column = column
    
    def __repr__(self):
        return f"({self.type.value}, {self.value})"

class LexicalAnalyzer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.errors = []
        
        # Таблицы лексем 
        self.keywords = {
            "int", "bool", "if", "else", "for", "while", "return",
            "using", "namespace", "include", "iostream", "endl", "main", "cout"
        }
        
        self.boolean_constants = {"true", "false"}
        
        self.operators = {
            "=", "+", "-", "*", "/", ">", "<", ">=", "<=", "==", "!=",
            "&&", "||", "!", "++", "--", "+=", "-=", "*=", "/=", "<<", ">>"
        }
        
        self.delimiters = {';', ',', '(', ')', '{', '}', ':', '[', ']', '#', '<', '>'}
    
    def _is_keyword(self, word: str) -> bool:
        return word in self.keywords
    
    def _is_boolean_constant(self, word: str) -> bool:
        return word in self.boolean_constants
    
    def _is_operator_start(self, char: str) -> bool:
        return char in "=+-*/><&|!%"
    
    def _is_delimiter(self, char: str) -> bool:
        return char in self.delimiters
    
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
        else:
            # Проверка: идентификатор не должен начинаться с цифры
            if value[0].isdigit():
                self.errors.append(f"Лексическая ошибка: идентификатор не может начинаться с цифры '{value}' на строке {self.line}")
                return Token(TokenType.ERROR, value, self.line, start_col)
            return Token(TokenType.IDENTIFIER, value, self.line, start_col)
    
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
        
        # Проверка на наличие букв в числе
        if self.pos < len(self.source) and self.source[self.pos].isalpha():
            next_char = self.source[self.pos]
            self.errors.append(f"Лексическая ошибка: буква в числовой константе '{value}{next_char}' на строке {self.line}")
            return Token(TokenType.ERROR, value + next_char, self.line, start_col)
        
        if has_decimal:
            return Token(TokenType.CONSTANT_FLOAT, value, self.line, start_col)
        else:
            return Token(TokenType.CONSTANT_INT, value, self.line, start_col)
    
    def _read_string(self) -> Token:
        start_col = self.column
        value = ""
        quote = self.source[self.pos]  # " или '
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
        
        # Проверка двухсимвольных операторов
        if self.pos + 1 < len(self.source):
            two_char = self.source[self.pos:self.pos+2]
            if two_char in self.operators:
                self.pos += 2
                self.column += 2
                return Token(TokenType.OPERATOR, two_char, self.line, start_col)
        
        # Односимвольные операторы
        value = self.source[self.pos]
        if value in self.operators:
            self.pos += 1
            self.column += 1
            return Token(TokenType.OPERATOR, value, self.line, start_col)
        
        # Неизвестный оператор
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
            token = None
            
            # Идентификатор или ключевое слово
            if current.isalpha() or current == '_':
                token = self._read_identifier()
            
            # Числовая константа
            elif current.isdigit():
                token = self._read_number()
            
            # Строковая константа
            elif current == '"' or current == "'":
                token = self._read_string()
            
            # Оператор
            elif self._is_operator_start(current):
                token = self._read_operator()
            
            # Разделитель
            elif self._is_delimiter(current):
                token = Token(TokenType.DELIMITER, current, self.line, self.column)
                self.pos += 1
                self.column += 1
            
            # Недопустимый символ
            else:
                self.errors.append(f"Лексическая ошибка: недопустимый символ '{current}' на строке {self.line}")
                token = Token(TokenType.ERROR, current, self.line, self.column)
                self.pos += 1
                self.column += 1
            
            if token:
                tokens.append(token)
        
        return tokens
    
    def get_errors(self) -> List[str]:
        return self.errors
    
    def print_token_table(self, tokens: List[Token]):
        print(f"{'Лексема':<35} | Тип")
        print("-" * 35 + "+" + "-" * 20)
        
        for token in tokens:
            # Экранируем специальные символы для корректного отображения
            display_value = token.value.replace('\n', '\\n').replace('\r', '\\r')
            print(f"{display_value:<35} | {token.type.value}")
    
    def print_token_sequence(self, tokens: List[Token]):
        print("\n[", end="")
        for i, token in enumerate(tokens):
            # Экранируем специальные символы
            display_value = token.value.replace('\n', '\\n').replace('\r', '\\r')
            print(f"({token.type.value}, {display_value})", end="")
            if i < len(tokens) - 1:
                print(", ", end="")
        print("]")


def main():
    
    # Чтение очищенного файла из первой лабораторной работы
    try:
        with open("test_cleaned.cpp", "r", encoding="utf-8") as file:
            cleaned_code = file.read()
    except FileNotFoundError:
        print("Ошибка: файл test_cleaned.cpp не найден!")
        return
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return
    
    # Лексический анализ
    print("\nРезультат лексического анализа")
    analyzer = LexicalAnalyzer(cleaned_code)
    tokens = analyzer.tokenize()
    
    # Вывод результатов
    analyzer.print_token_table(tokens)
    analyzer.print_token_sequence(tokens)
    
    print(f"Обнаружено токенов: {len(tokens)}")
    
    errors = analyzer.get_errors()
    if not errors:
        print("Ошибок не найдено.")
    else:
        print("\nОбнаруженные ошибки")
        for error in errors:
            print(f"  {error}")


if __name__ == "__main__":
    main()