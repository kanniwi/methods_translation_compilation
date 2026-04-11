#include <iostream>
using namespace std;

// Функция для сложения
int add(int a, int b) {
    return a + b;  // Возвращаем сумму
}

int main() {
    // Объявление переменных
    int x = 5, y = 10;
    int result;
    bool isPositive = true;
    
    /* Арифметические
       выражения */
    result = x * y - 3;
    
    // Условный оператор
    if (result > 0) {
        isPositive = true;
    } else {
        isPositive = false;
    }
    
    // Цикл for
    for (int i = 0; i < 3; i++) {
        cout << i << " ";
    }
    cout << endl;
    
    // Цикл while
    int j = 0;
    while (j < 2) {
        j++;
    }
    
    // Логическое выражение
    if (x < y && isPositive) {
        result = add(x, y);  // Вызов функции
    }
    
    return 0;
}