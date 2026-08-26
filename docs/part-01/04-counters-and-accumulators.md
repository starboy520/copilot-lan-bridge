[← 第 3 章：格式化输入和输出](./03-formatted-input-output.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [第 5 章：整数与取余 →](./05-integers-and-modulo.md)

---

# 第 4 章 计数器与累加器

## 4.1 变量为什么要更新

许多程序不是只计算一次，而是在事情发生后不断更新记录：

- 每完成一道题，完成数量增加 1；
- 每获得一颗星，星星总数增加 1；
- 每记录一天步数，总步数加上当天步数；
- 每买一件物品，总价加上这件物品的价格。

这就要用到**计数器**和**累加器**。

---

## 4.2 计数器：记录发生了多少次

计数器通常从 `0` 开始，每发生一次目标事件，就增加 `1`。

```cpp
int count = 0;
count = count + 1;
count = count + 1;
count = count + 1;
cout << count << '\n';
```

输出：

```text
3
```

手工跟踪：

| 执行步骤 | `count` 的值 |
|---|---:|
| 初始化 | 0 |
| 第一次加 1 | 1 |
| 第二次加 1 | 2 |
| 第三次加 1 | 3 |

### 三种加一写法

```cpp
count = count + 1;
count += 1;
count++;
```

在这里，它们都能让 `count` 增加 1。刚开始可以使用第一种，因为它最清楚；熟悉后再使用 `count++`。

### 初始化不能忘

错误示例：

```cpp
int count;
count = count + 1;
```

`count` 没有先获得确定的初始值，就直接参与计算，结果不可相信。

正确写法：

```cpp
int count = 0;
```

---

## 4.3 累加器：记录一共有多少

计数器通常每次加 `1`；累加器每次加入的数可以不同。

三天步数分别为 3000、4500、5200：

```cpp
int totalSteps = 0;
totalSteps = totalSteps + 3000;
totalSteps = totalSteps + 4500;
totalSteps = totalSteps + 5200;
cout << totalSteps << '\n';
```

输出：

```text
12700
```

手工跟踪：

| 执行步骤 | 加入的步数 | `totalSteps` 的值 |
|---|---:|---:|
| 初始化 | — | 0 |
| 第 1 天 | 3000 | 3000 |
| 第 2 天 | 4500 | 7500 |
| 第 3 天 | 5200 | 12700 |

也可以写成：

```cpp
totalSteps += 3000;
totalSteps += 4500;
totalSteps += 5200;
```

---

## 4.4 计数器与累加器的区别

| 比较 | 计数器 | 累加器 |
|---|---|---|
| 作用 | 统计次数或个数 | 合计数值 |
| 常见初值 | 0 | 0 |
| 每次更新 | 通常加 1 | 加入当前数据 |
| 例子 | 做了几道题 | 总共得了多少分 |

例如记录三次练习：

```cpp
int solvedCount = 0;
int totalScore = 0;

solvedCount++;
totalScore += 80;

solvedCount++;
totalScore += 90;

solvedCount++;
totalScore += 70;
```

最终：

- `solvedCount` 是 `3`，表示记录了 3 次；
- `totalScore` 是 `240`，表示总分为 240。

平均分可以计算为：

```cpp
double average = 1.0 * totalScore / solvedCount;
```

`1.0 *` 让计算按小数除法进行。

---

## 4.5 完整例题：三天阅读记录

### 题目

输入三天分别阅读的页数，输出总页数和平均每天阅读的页数。平均数保留一位小数。

#### 样例输入

```text
12 20 25
```

#### 样例输出

```text
57
19.0
```

### 第一步：准备累加器

```cpp
int total = 0;
```

### 第二步：读入并累加

```cpp
int day1, day2, day3;
cin >> day1 >> day2 >> day3;
total += day1;
total += day2;
total += day3;
```

### 第三步：计算和输出

```cpp
double average = total / 3.0;
cout << total << '\n';
cout << fixed << setprecision(1) << average << '\n';
```

### 完整代码

```cpp
#include <iostream>
#include <iomanip>
using namespace std;

int main() {
    int day1, day2, day3;
    cin >> day1 >> day2 >> day3;

    int total = 0;
    total += day1;
    total += day2;
    total += day3;

    double average = total / 3.0;
    cout << total << '\n';
    cout << fixed << setprecision(1) << average << '\n';
    return 0;
}
```

---

## 第 4 章练习

### 基础练习 1：跟踪变量

写出每一步执行后 `x` 的值：

```cpp
int x = 0;
x += 5;
x += 3;
x -= 2;
x++;
```

### 基础练习 2：四周存钱

输入连续四周存下的钱数，使用累加器计算总数并输出。

### 提高练习 3：阅读统计

输入 5 天的阅读页数，分别用 5 个变量保存，再使用累加器输出总页数。

### 挑战练习 4：总分和平均分

输入 5 次测验的成绩，输出总分和平均分，平均分保留两位小数。

### 本章闯关标准

- [ ] 我能解释计数器和累加器的区别。
- [ ] 我会先把它们初始化为 0。
- [ ] 我能手工跟踪变量每一次更新后的值。
- [ ] 我知道 `x += y` 等价于 `x = x + y`。

---

---

[← 第 3 章：格式化输入和输出](./03-formatted-input-output.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [第 5 章：整数与取余 →](./05-integers-and-modulo.md)

