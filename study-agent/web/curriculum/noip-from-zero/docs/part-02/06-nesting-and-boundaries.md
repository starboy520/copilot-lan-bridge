[← 第 5 章：组合条件与逻辑运算](./05-logical-operators.md) · [第二部分目录](./README.md) · [综合项目：信奥闯关判定器 →](./07-project-challenge-judge.md)

---

# 第 6 章 浅层嵌套与边界测试

## 6.1 什么是嵌套

有时必须先通过第一道判断，才能进行第二道判断。例如：

```text
先判断成绩是否及格
  ├─ 不及格 → 输出 Fail
  └─ 及格 → 再判断是否达到优秀
```

把一个 `if` 放在另一个分支里面，叫作**嵌套**。

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score;
    scanf("%d", &score);

    if (score >= 60) {
        if (score >= 90) {
            printf("Excellent\n");
        } else {
            printf("Pass\n");
        }
    } else {
        printf("Fail\n");
    }

    return 0;
}
```

这里最多只进入两层判断。每深入一层，代码再向右缩进 4 个空格。

## 6.2 什么时候不需要嵌套

上面的成绩题也可以用更平直的多分支完成：

```cpp
if (score >= 90) {
    printf("Excellent\n");
} else if (score >= 60) {
    printf("Pass\n");
} else {
    printf("Fail\n");
}
```

这两种写法结果相同，但多分支更容易阅读。只有当题意本身确实是“先满足 A，再在 A 里面区分 B”时，才优先使用嵌套。

本阶段只学习一层浅嵌套，不写很多层“楼梯”。

## 6.3 数据是否合法也需要判断

题目如果没有保证输入一定合法，可以先检查范围。例如成绩应在 `0～100`：

```cpp
if (score < 0 || score > 100) {
    printf("Invalid\n");
} else if (score >= 60) {
    printf("Pass\n");
} else {
    printf("Fail\n");
}
```

条件 `score < 0 || score > 100` 表示成绩落在合法区间之外。

OI 题目通常会在数据范围中保证输入合法。这种情况下，不必额外检查题目已经保证的事情；按照题意处理即可。

## 6.4 什么是边界值

边界值是规则发生变化的位置。例如：

```cpp
score >= 60
```

边界是 `60`。最有价值的测试通常是：

```text
59  60  61
```

对于区间 `1～12`：

```text
0  1  12  13
```

它们覆盖了下边界外、下边界、上边界和上边界外。

## 6.5 系统设计测试数据

### 第一步：列出分支

以成绩等级为例：

```text
score >= 90       → Excellent
60 <= score < 90  → Pass
score < 60        → Fail
```

### 第二步：找到边界

边界是 `60` 和 `90`。

### 第三步：每个边界测三个数

```text
59 60 61
89 90 91
```

### 第四步：补普通值

再测试每个范围内部的普通值，例如 `30、75、95`。

## 6.6 完整例题：月份范围

### 题目

输入一个整数月份：

- 不在 `1～12`：输出 `Invalid`；
- `12、1、2`：输出 `Winter`；
- 其他合法月份：输出 `Other`。

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int month;
    scanf("%d", &month);

    if (month < 1 || month > 12) {
        printf("Invalid\n");
    } else if (month == 12 || month == 1 || month == 2) {
        printf("Winter\n");
    } else {
        printf("Other\n");
    }

    return 0;
}
```

注意不能写成：

```cpp
month == 12 || 1 || 2  // 错误写法
```

每一项都必须写成完整条件：

```cpp
month == 12 || month == 1 || month == 2
```

## 第 6 章练习

### 基础练习 1：边界数据

条件是 `age >= 12 && age <= 18`。请写出至少 6 个能覆盖两个边界的测试数据。

### 基础练习 2：合法成绩

输入成绩。范围外输出 `Invalid`；合法且至少 60 输出 `Pass`；其他输出 `Fail`。

### 提高练习 3：浅层嵌套

输入成绩和是否完成作业的标记 `homework`：

- 成绩低于 60：输出 `Retry`；
- 成绩至少 60 且 `homework == 1`：输出 `Complete`；
- 成绩至少 60 但未完成作业：输出 `Finish homework`。

请先画路线图，再使用一层嵌套完成。

### 测试设计 4

对于三档成绩程序，解释为什么只测试 `50、70、95` 还不够，并补充边界测试。

## 本章闯关标准

- [ ] 我能读懂一层嵌套，并按缩进跟踪执行路线。
- [ ] 能用多分支写清楚时，我不会故意增加嵌套。
- [ ] 我能找到条件中的边界值。
- [ ] 我会测试边界前一个、边界本身和边界后一个。
- [ ] 我知道题目已经保证输入合法时，不必重复检查。

---

[← 第 5 章：组合条件与逻辑运算](./05-logical-operators.md) · [第二部分目录](./README.md) · [综合项目：信奥闯关判定器 →](./07-project-challenge-judge.md)
