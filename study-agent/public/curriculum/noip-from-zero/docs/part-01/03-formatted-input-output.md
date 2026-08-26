[← 第 2 章：基础数据类型](./02-basic-data-types.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [第 4 章：计数器与累加器 →](./04-counters-and-accumulators.md)

---

# 第 3 章 格式化输入和输出

## 3.1 使用 `cin` 输入数据

```cpp
int age;
cin >> age;
```

程序运行到 `cin` 时，会等待输入。输入的整数会被保存到 `age` 中。

一次可以输入多个变量：

```cpp
int a, b, c;
cin >> a >> b >> c;
```

以下输入都可以被这条语句正确读取：

```text
10 20 30
```

或：

```text
10
20
30
```

对 `cin >>` 来说，空格和换行通常都可以分隔数据。

### 输入顺序很重要

```cpp
int length, width;
cin >> length >> width;
```

第一个数进入 `length`，第二个数进入 `width`。变量必须按照题目规定的顺序读取。

---

## 3.2 使用 `cout` 组合输出

`cout` 可以连续输出文字、变量和计算结果：

```cpp
int a = 12;
int b = 8;
cout << a << " + " << b << " = " << a + b << '\n';
```

输出：

```text
12 + 8 = 20
```

每一对 `<<` 都可以理解为“把右边的内容送到输出中”。

### 输出空格

```cpp
cout << a << ' ' << b << '\n';
```

`' '` 是一个空格字符。如果没有它：

```cpp
cout << a << b << '\n';
```

当 `a = 12`、`b = 8` 时，会输出 `128`，而不是 `12 8`。

### 输出换行

推荐在竞赛程序中使用：

```cpp
cout << '\n';
```

也可以使用：

```cpp
cout << endl;
```

初学时两者都能换行。竞赛中通常更常用 `\n`。

### 特殊字符

如果要在文字中输出双引号，需要写成 `\"`：

```cpp
cout << "She said, \"Hello!\"" << '\n';
```

输出：

```text
She said, "Hello!"
```

---

## 3.3 按指定小数位数输出

题目经常要求“保留两位小数”。需要使用 `<iomanip>` 工具：

```cpp
#include <iostream>
#include <iomanip>
using namespace std;

int main() {
    double price;
    cin >> price;
    cout << fixed << setprecision(2) << price << '\n';
    return 0;
}
```

输入：

```text
12.5
```

输出：

```text
12.50
```

含义如下：

- `fixed`：使用普通小数形式输出；
- `setprecision(2)`：小数点后保留 2 位。

### 四舍五入

```cpp
double x = 3.14159;
cout << fixed << setprecision(2) << x << '\n';
```

输出 `3.14`。

```cpp
double y = 2.71828;
cout << fixed << setprecision(3) << y << '\n';
```

输出 `2.718`。

### 容易混淆的地方

只写：

```cpp
cout << setprecision(2) << x;
```

不一定表示保留两位小数。对初学者而言，遇到“保留若干位小数”，请把 `fixed` 和 `setprecision` 一起使用。

---

## 3.4 计算平均数时的类型问题

输入三个整数成绩，输出平均分：

```cpp
int a, b, c;
cin >> a >> b >> c;
double average = (a + b + c) / 3.0;
cout << fixed << setprecision(1) << average << '\n';
```

为什么除数写成 `3.0`，而不是 `3`？

如果参与除法的两个数都是整数，C++ 会进行整数除法，小数部分会被舍去。例如：

```cpp
cout << 5 / 2 << '\n';       // 输出 2
cout << 5 / 2.0 << '\n';     // 输出 2.5
```

因此，需要小数结果时，要让除法中至少有一个数是小数类型。

也可以进行类型转换：

```cpp
double average = static_cast<double>(a + b + c) / 3;
```

现阶段使用 `/ 3.0` 更直观。

---

## 3.5 完整例题：购物小票

### 题目

一本练习册单价为 `price` 元，购买 `count` 本。输入单价和数量，输出总价，保留两位小数。

#### 样例输入

```text
8.5 3
```

#### 样例输出

```text
25.50
```

### 分析

```text
输入：单价 price、数量 count
处理：total = price × count
输出：total，保留两位小数
```

### 程序

```cpp
#include <iostream>
#include <iomanip>
using namespace std;

int main() {
    double price;
    int count;
    cin >> price >> count;

    double total = price * count;
    cout << fixed << setprecision(2) << total << '\n';
    return 0;
}
```

### 自己测试

至少测试：

- `8.5 3`：普通小数；
- `10 1`：整数单价；
- `0.25 4`：结果正好为 1；
- `99.99 0`：数量为 0。

---

## 第 3 章练习

### 基础练习 1：三数输出

输入三个整数，按照“第一个数、一个空格、第二个数、一个空格、第三个数”的格式输出。

### 基础练习 2：圆的周长

输入半径 `r`，使用 `3.14159` 作为圆周率，输出圆的周长，保留两位小数。

### 提高练习 3：平均分

输入语文、数学、英语三科的整数成绩，输出平均分，保留一位小数。

### 提高练习 4：交换展示

输入姓名（不含空格）和年龄，输出如下形式：

```text
Name: Linlin
Age: 13
```

### 本章闯关标准

- [ ] 我会一次读入多个数据，并知道读取顺序的重要性。
- [ ] 我会在输出的数字之间添加空格和换行。
- [ ] 我会用 `fixed << setprecision(n)` 保留小数位数。
- [ ] 我知道 `5 / 2` 和 `5 / 2.0` 的结果不同。

---

---

[← 第 2 章：基础数据类型](./02-basic-data-types.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [第 4 章：计数器与累加器 →](./04-counters-and-accumulators.md)

