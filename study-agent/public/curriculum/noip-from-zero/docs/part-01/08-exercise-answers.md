[← 第一部分复习清单](./07-review-checklist.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [给家长或老师的使用建议 →](./09-teaching-guide.md)

---

# 练习答案与提示

> 建议先独立完成，再核对。只看答案不会让解题能力增长。

## 第 1 章

### 练习 1

两处分别填写 `cout` 和 `endl`：

```cpp
#include <iostream>
using namespace std;

int main() {
    cout << "I can code!" << endl;
    return 0;
}
```

### 练习 2

```cpp
#include <iostream>
using namespace std;

int main() {
    cout << "I love C++." << endl;
    return 0;
}
```

### 练习 3

```cpp
#include <iostream>
using namespace std;

int main() {
    cout << 35 + 27 << endl;
    return 0;
}
```

结果为 `62`。

### 练习 4

```cpp
#include <iostream>
using namespace std;

int main() {
    int length, width;
    cin >> length >> width;
    cout << length * width << endl;
    return 0;
}
```

### 练习 5

```cpp
#include <iostream>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << b << " " << a << endl;
    return 0;
}
```

### 调试实验

1. 故障 1 缺少分号，应把输出语句改为 `cout << "Hello!" << endl;`，否则会出现 CE。
2. 故障 2 的 `Cout` 大小写错误，应改成 `cout`，否则会出现 CE。
3. 故障 3 把样例答案 `20` 直接写进了程序。它只会碰巧通过这一组样例，输入 `1 2` 时仍输出 `20`，提交后会得到 WA。正确输出语句是 `cout << a + b << endl;`。

## 第 2 章

### 练习 1

1. `int`
2. `double`
3. `char`
4. `string`
5. `long long`

### 练习 2

`x` 依次为 `5、8、16`，输出 `16`。

### 练习 3

```cpp
int money, add, cost;
cin >> money >> add >> cost;
cout << money + add - cost << '\n';
```

### 练习 4

使用 `long long` 保存 `distance`、`days` 和计算结果。

## 第 3 章

### 练习 1

```cpp
int a, b, c;
cin >> a >> b >> c;
cout << a << ' ' << b << ' ' << c << '\n';
```

### 练习 2

```cpp
double r;
cin >> r;
double circumference = 2 * 3.14159 * r;
cout << fixed << setprecision(2) << circumference << '\n';
```

### 练习 3

核心公式：

```cpp
double average = (chinese + math + english) / 3.0;
```

### 练习 4

```cpp
string name;
int age;
cin >> name >> age;
cout << "Name: " << name << '\n';
cout << "Age: " << age << '\n';
```

## 第 4 章

### 练习 1

`x` 依次为 `0、5、8、6、7`。

### 练习 2

准备 `int total = 0;`，读入四个整数后依次用 `total += ...` 加入。

### 练习 3

```cpp
int day1, day2, day3, day4, day5;
cin >> day1 >> day2 >> day3 >> day4 >> day5;

int total = 0;
total += day1;
total += day2;
total += day3;
total += day4;
total += day5;
```

### 练习 4

总分使用累加器；平均分为 `total / 5.0`。

## 第 5 章

### 练习 1

答案依次为：`4、3、5、0、0、7`。

### 练习 2

```cpp
cout << n / 8 << ' ' << n % 8 << '\n';
```

### 练习 3

```cpp
cout << totalMinutes / 60 << ' ' << totalMinutes % 60 << '\n';
```

### 练习 4

```cpp
int tens = n / 10;
int ones = n % 10;
cout << ones * 10 + tens << '\n';
```

### 练习 5

可以依次取出：

```cpp
int thousands = n / 1000;
int hundreds = (n / 100) % 10;
int tens = (n / 10) % 10;
int ones = n % 10;
```

### 练习 6

核心思路：

```cpp
int total = h * 60 + m + x;
int newHour = (total / 60) % 24;
int newMinute = total % 60;
```

---

---

[← 第一部分复习清单](./07-review-checklist.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [给家长或老师的使用建议 →](./09-teaching-guide.md)
