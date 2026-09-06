[← 第 3 章：双分支 if...else](./03-if-else.md) · [第二部分目录](./README.md) · [第 5 章：组合条件与逻辑运算 →](./05-logical-operators.md)

---

# 第 4 章 多分支 `if...else if...else`

## 4.1 情况超过两种怎么办

成绩可能分成优秀、通过和未通过三档；一个整数可能是正数、零或负数。遇到三种或更多互斥情况，可以使用多分支结构：

```cpp
if (条件1) {
    条件1成立时执行;
} else if (条件2) {
    条件1不成立、条件2成立时执行;
} else {
    前面的条件都不成立时执行;
}
```

`else if` 可以理解为“否则，再判断……”。程序从上到下检查，一旦进入某个分支，后面的分支就不再检查。

## 4.2 完整例题：正数、零、负数

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);

    if (n > 0) {
        printf("Positive\n");
    } else if (n == 0) {
        printf("Zero\n");
    } else {
        printf("Negative\n");
    }

    return 0;
}
```

为什么最后不必写 `n < 0`？因为能走到 `else`，说明 `n > 0` 和 `n == 0` 都不成立，剩下的只能是负数。

## 4.3 分支顺序会改变结果

### 题目

输入成绩：

- `90～100` 输出 `Excellent`；
- `60～89` 输出 `Pass`；
- `0～59` 输出 `Fail`。

正确程序：

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score;
    scanf("%d", &score);

    if (score >= 90) {
        printf("Excellent\n");
    } else if (score >= 60) {
        printf("Pass\n");
    } else {
        printf("Fail\n");
    }

    return 0;
}
```

输入 `95` 时，第一个条件已经成立，输出 `Excellent` 后就结束整个多分支。

如果把 `score >= 60` 放在最前面，`95` 也满足它，程序会过早输出 `Pass`。因此这种“从某个分数以上开始分档”的题，通常从最高标准向下判断。

## 4.4 为什么第二个条件不用写上限

第二个分支只写了：

```cpp
score >= 60
```

它看起来也包含 90 分以上，但程序能走到第二个分支，已经说明 `score >= 90` 不成立。因此第二个分支实际处理的是 `60～89`。

这叫作利用前面已经排除的情况，让条件更简洁。

## 4.5 不要写成三个互相独立的 `if`

下面三条 `if` 会分别判断：

```cpp
if (score >= 90) {
    printf("Excellent\n");
}
if (score >= 60) {
    printf("Pass\n");
}
if (score < 60) {
    printf("Fail\n");
}
```

输入 `95` 会同时输出 `Excellent` 和 `Pass`。题目要求只选一档，所以应该把它们连成一条 `if...else if...else` 链。

## 4.6 没有最后的 `else` 可以吗

语法上可以，但要看题目。如果只处理某几种特殊情况，可以没有最后的 `else`。如果所有输入都必须得到结果，保留最后的 `else` 更完整。

## 第 4 章练习

### 基础练习 1：温度提示

输入整数温度：低于 0 输出 `Freezing`；`0～29` 输出 `Normal`；至少 30 输出 `Hot`。

### 基础练习 2：两数关系

输入两个整数。第一个大于第二个输出 `Greater`，相等输出 `Equal`，否则输出 `Less`。

### 提高练习 3：等级

输入 `0～100` 的整数成绩：

- 至少 85：`A`
- 至少 70 但低于 85：`B`
- 至少 60 但低于 70：`C`
- 低于 60：`D`

### 代码阅读 4

如果输入 `88`，下面程序输出什么？为什么？

```cpp
if (score >= 60) {
    printf("Pass\n");
} else if (score >= 85) {
    printf("Great\n");
} else {
    printf("Fail\n");
}
```

## 本章闯关标准

- [ ] 我知道多分支从上到下判断，进入一支后就结束。
- [ ] 我能按照题意安排分支顺序。
- [ ] 我能利用前面已经排除的范围简化后面的条件。
- [ ] 我知道多个独立的 `if` 和一条多分支链不一样。

---

[← 第 3 章：双分支 if...else](./03-if-else.md) · [第二部分目录](./README.md) · [第 5 章：组合条件与逻辑运算 →](./05-logical-operators.md)
