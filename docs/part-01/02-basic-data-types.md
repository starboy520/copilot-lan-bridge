[← 第 1 章：简单程序与 OI](./01-simple-programs-and-oi.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [第 3 章：格式化输入和输出 →](./03-formatted-input-output.md)

---

# 第 2 章 基础数据类型

## 2.1 变量：有名字的小盒子

程序需要记住很多数据，例如年龄、成绩、价格。我们可以把**变量**想象成贴了名字的小盒子：盒子中可以保存一个数据，盒子里的数据也可以改变。

```cpp
int age = 13;
```

这行代码表示：

- `int`：盒子用来保存整数；
- `age`：盒子的名字；
- `=`：把右边的值放进左边的变量；
- `13`：放入盒子的数据。

这里的 `=` 叫作**赋值号**。它表示“把右边的值交给左边”，不完全等同于数学中的等号。

```cpp
int score = 80;
score = 95;
```

执行后，`score` 中原来的 `80` 被新的 `95` 替换。

### 先声明，后赋值

也可以分两步写：

```cpp
int score;
score = 95;
```

第一行准备变量，第二行放入数据。

### 变量名规则

变量名可以使用英文字母、数字和下划线，但应遵守：

- 不能以数字开头；
- 不能含空格；
- 不能使用 `int`、`return` 等 C++ 已占用的单词；
- 区分大小写，`age` 和 `Age` 是不同名字；
- 尽量见名知意。

推荐：

```cpp
studentAge
mathScore
appleCount
```

不推荐：

```cpp
x1
abc
qwert
```

短小公式中使用 `a`、`b`、`n`、`i` 等常见短名字是可以的。

---

## 2.2 整数类型：`int` 和 `long long`

没有小数部分的数叫作整数，例如：

```text
-12, 0, 13, 2026
```

C++ 中常用两种整数类型。

### `int`

`int` 通常能保存大约负 21 亿到正 21 亿之间的整数。

```cpp
int age = 13;
int temperature = -5;
int students = 48;
```

### `long long`

数据可能很大时，使用 `long long`。

```cpp
long long population = 8000000000;
```

### 为什么会溢出

每种变量能保存的数据都有范围。好比一个只能显示 4 位数字的计数器，无法正确显示非常大的数。计算结果超过类型范围时，会发生**溢出**，得到错误结果。

例如，计算两个较大整数的乘积时，最好直接使用 `long long`：

```cpp
long long a, b;
cin >> a >> b;
cout << a * b << endl;
```

### 选择建议

- 普通人数、分数、较小编号：先考虑 `int`；
- 数据达到十亿附近，或者两个整数相乘可能很大：考虑 `long long`；
- 一定要阅读题目的数据范围。

---

## 2.3 小数类型：`double`

身高、平均分、温度等数据可能带有小数，可以使用 `double`：

```cpp
double height = 1.62;
double temperature = 36.5;
```

示例：输入长方形的长和宽，计算面积。

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    double length, width;
    cin >> length >> width;
    double area = length * width;
    cout << area << endl;
    return 0;
}
```

### 小数不是永远精确

计算机保存某些小数时只能得到非常接近的值。因此，小数计算偶尔可能出现 `0.30000000000000004` 之类的现象。这不是计算机不会加法，而是小数在计算机中的保存方式造成的。

现阶段记住：

- 能用整数准确表示时，优先使用整数；
- 输出小数位数时，使用后面要学习的格式控制；
- 小数还有一些需要特别注意的比较规则，等学到条件判断时再专门学习。

---

## 2.4 字符类型：`char`

单个字符可以用 `char` 保存：

```cpp
char grade = 'A';
char symbol = '#';
char digit = '7';
```

字符外面使用**单引号**。

```cpp
char letter = 'A';    // 正确：单个字符
```

`'7'` 是一个字符，不是整数 `7`。它们看起来相似，但用途不同。

### 特殊字符：第一次认识 `\n`

有些字符很难直接写在一对单引号中。例如，“换到下一行”不是键盘上的一个普通字母。C++ 用下面的写法表示它：

```cpp
char newLine = '\n';
cout << "第一行" << newLine;
cout << "第二行" << newLine;
```

这里的 `\n` 要作为一个整体来看：

- 外面的一对单引号表示“这是一个字符”；
- 反斜杠 `\` 告诉 C++，后面的字母有特殊含义；
- `n` 在这里表示换行；
- 所以 `\n` 不是先输出反斜杠、再输出字母 `n`，而是让输出换到下一行。

我们也可以不准备 `newLine` 变量，直接写：

```cpp
cout << "第一行" << '\n';
cout << "第二行" << '\n';
```

第 1 章使用的 `endl` 也能换行。从现在开始，示例会逐渐改用竞赛程序中更常见的 `\n`。

---

## 2.5 字符串类型：`string`

姓名、单词、句子由多个字符组成，可以用 `string` 保存。

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    string name;
    cin >> name;
    cout << "Hello, " << name << "!" << '\n';
    return 0;
}
```

我们使用的 `<bits/stdc++.h>` 已经包含了处理字符串需要的常用工具，所以不需要再单独写 `#include <string>`。

输入：

```text
Linlin
```

输出：

```text
Hello, Linlin!
```

字符串常量使用**双引号**：

```cpp
string city = "Beijing";
```

简单记忆：

- 单个字符：`char letter = 'A';`
- 一串文字：`string word = "Apple";`

---

## 2.6 布尔类型：`bool`

有些问题只有“是”或“否”两种状态，可以用 `bool` 保存：

```cpp
bool isReady = true;
bool isFinished = false;
```

`true` 表示真，`false` 表示假。后面学习条件判断时会经常使用它。

---

## 2.7 表达式与赋值

由数据、变量和运算符组成的计算式叫作**表达式**。

```cpp
int price = 8;
int count = 5;
int total = price * count;
```

程序先计算右边的 `price * count`，得到 `40`，再把它存入 `total`。

变量可以根据原来的值更新：

```cpp
int score = 70;
score = score + 10;
```

这不是数学等式，而是一条操作指令：

1. 取出 `score` 原来的值 `70`；
2. 计算 `70 + 10`；
3. 把结果 `80` 放回 `score`。

最终 `score` 的值是 `80`。

### 简写形式

```cpp
score += 10;   // 等价于 score = score + 10;
score -= 5;    // 等价于 score = score - 5;
score *= 2;    // 等价于 score = score * 2;
score /= 5;    // 等价于 score = score / 5;
```

初学时如果觉得简写不直观，可以先写完整形式。

---

## 第 2 章练习

### 基础练习 1：选择类型

分别为下列数据选择合适的类型：

1. 学生年龄；
2. 身高 1.58 米；
3. 等级字符 `A`；
4. 姓名；
5. 一个可能达到一百亿的数量。

### 基础练习 2：预测结果

不运行程序，先写出输出结果：

```cpp
int x = 5;
x = x + 3;
x *= 2;
cout << x << '\n';
```

### 提高练习 3：零花钱

小雨原有 `money` 元，又得到 `add` 元，买文具花掉 `cost` 元。输入这三个整数，输出最后剩下的钱。

样例输入：

```text
20 10 8
```

样例输出：

```text
22
```

### 提高练习 4：总路程

某人每天行走 `distance` 米，连续行走 `days` 天。输入两个整数，输出总路程。题目保证结果可能超过 `int` 的范围，但不会超过 `long long` 的范围。

### 本章闯关标准

- [ ] 我能解释变量像什么、赋值在做什么。
- [ ] 我会根据数据选择 `int`、`long long`、`double`、`char` 或 `string`。
- [ ] 我能看懂并使用 `x = x + 1`。
- [ ] 我知道整数类型有范围，过大会溢出。

---

---

[← 第 1 章：简单程序与 OI](./01-simple-programs-and-oi.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [第 3 章：格式化输入和输出 →](./03-formatted-input-output.md)
