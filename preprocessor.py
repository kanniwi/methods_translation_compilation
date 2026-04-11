"""
Модуль очистки исходного кода от служебных и избыточных символов
Удаляет комментарии, лишние пробелы и пустые строки
"""

import re
import sys


class CodeCleaner:
    """Класс для очистки исходного кода"""
    
    def __init__(self):
        self.single_comment = re.compile(r'//.*$', re.MULTILINE)      # Однострочные комментарии
        self.multi_comment = re.compile(r'/\*.*?\*/', re.DOTALL)      # Многострочные комментарии
        self.trim_spaces = re.compile(r'^\s+|\s+$', re.MULTILINE)     # Пробелы по краям
        self.multiple_spaces = re.compile(r'\s+')                      # Множественные пробелы
        self.empty_lines = re.compile(r'\n\s*\n')                      # Пустые строки
        self.invalid_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')  # Недопустимые символы
    
    def clean(self, code):
        errors = []
        
        # 1. Проверка на недопустимые символы
        for line_num, line in enumerate(code.split('\n'), 1):
            invalid = self.invalid_chars.findall(line)
            if invalid:
                errors.append(f"Строка {line_num}: недопустимые символы {invalid}")
        
        # 2. Проверка на незакрытые многострочные комментарии
        if code.count('/*') != code.count('*/'):
            errors.append("ОШИБКА: незакрытый многострочный комментарий")
            return "", errors
        
        # 3. Удаление комментариев
        cleaned = self.multi_comment.sub('', code)  # Сначала многострочные
        cleaned = self.single_comment.sub('', cleaned)  # Затем однострочные
        
        # 4. Удаление пробелов в начале и конце строк
        cleaned = self.trim_spaces.sub('', cleaned)
        
        # 5. Замена множественных пробелов на один
        cleaned = self.multiple_spaces.sub(' ', cleaned)
        
        # 6. Удаление пустых строк
        cleaned = self.empty_lines.sub('\n', cleaned)
        
        # 7. Удаление пустых строк в начале и конце
        cleaned = cleaned.strip('\n')
        
        return cleaned, errors


def main():
    # Проверка аргументов командной строки
    if len(sys.argv) < 2:
        print("Использование: python preprocessor.py <файл> [выходной_файл]")
        print("Пример: python preprocessor.py test.cpp")
        print("       python preprocessor.py test.cpp cleaned.cpp")
        sys.exit(1)
    
    # Чтение входного файла
    input_file = sys.argv[1]
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Ошибка: файл '{input_file}' не найден")
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        sys.exit(1)
    
    # Очистка кода
    cleaner = CodeCleaner()
    cleaned_code, errors = cleaner.clean(source_code)
    
    # Вывод результата
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТ ОЧИСТКИ:")
    print("="*60)
    print(cleaned_code)
    print("="*60)
    
    # Вывод сообщений
    if errors:
        for error in errors:
            print(f"{error}")
    else:
        print("Ошибок не выявлено")
    
    # Сохранение результата (опционально)
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)
        print(f"\nРезультат сохранен в: {output_file}")
    elif cleaned_code and not errors:
        # Автоматическое сохранение
        output_file = input_file.replace('.', '_cleaned.')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)
        print(f"\nРезультат сохранен в: {output_file}")


if __name__ == "__main__":
    main()