[← 第 6 章：浅层嵌套与边界测试](./06-nesting-and-boundaries.md) · [第二部分目录](./README.md) · [第二部分复习清单 →](./08-review-checklist.md)

---

# 综合项目：信奥闯关判定器

## 项目背景

某次信奥学习闯关记录三个整数：

- `score`：测验分数，合法范围是 `0～100`；
- `solved`：独立完成的题目数，合法范围是 `0～10`；
- `absent`：是否缺席，`0` 表示未缺席，`1` 表示缺席。

判定规则按下面的顺序执行：

1. 任意数据不合法，输出 `Invalid`；
2. 数据合法但缺席，输出 `Retry`；
3. 未缺席、分数至少 85 且完成题数至少 8，输出 `Excellent`；
4. 未缺席、分数至少 60 且完成题数至少 5，输出 `Pass`；
5. 其他情况输出 `Retry`。

每次只输出一行。

## 第一步：读懂“按顺序执行”

这是一条多分支链。从上到下找到第一个成立的条件，输出以后就不再进入后面的分支。

例如输入：

```text
90 9 1
```

分数和题数达到优秀标准，但 `absent == 1`，所以应该输出：

```text
Retry
```

缺席规则放在优秀规则之前，顺序不能随意交换。

## 第二步：写出合法范围

`score` 不合法：

```cpp
score < 0 || score > 100
```

`solved` 不合法：

```cpp
solved < 0 || solved > 10
```

`absent` 只能是 0 或 1。它不合法可以写成：

```cpp
absent != 0 && absent != 1
```

三个“不合法条件”中只要一个成立，整体就不合法，所以用 `||` 连接：

```cpp
(score < 0 || score > 100) ||
(solved < 0 || solved > 10) ||
(absent != 0 && absent != 1)
```

换行只是为了阅读，仍然是同一个条件。

## 第三步：写出各档条件

```text
缺席：      absent == 1
优秀：      score >= 85 && solved >= 8
通过：      score >= 60 && solved >= 5
其他：      else
```

## 第四步：完整程序

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score, solved, absent;
    scanf("%d%d%d", &score, &solved, &absent);

    if ((score < 0 || score > 100) ||
        (solved < 0 || solved > 10) ||
        (absent != 0 && absent != 1)) {
        printf("Invalid\n");
    } else if (absent == 1) {
        printf("Retry\n");
    } else if (score >= 85 && solved >= 8) {
        printf("Excellent\n");
    } else if (score >= 60 && solved >= 5) {
        printf("Pass\n");
    } else {
        printf("Retry\n");
    }

    return 0;
}
```

## 第五步：设计测试

不要只测试题目中最普通的情况。请先手算下表，再运行程序：

| 输入 | 要检查的情况 | 预期输出 |
|---|---|---|
| `90 9 0` | 普通优秀 | `Excellent` |
| `85 8 0` | 优秀的两个边界 | `Excellent` |
| `84 8 0` | 分数刚低于优秀线 | `Pass` |
| `85 7 0` | 题数刚低于优秀线 | `Pass` |
| `60 5 0` | 通过的两个边界 | `Pass` |
| `59 10 0` | 分数刚低于通过线 | `Retry` |
| `100 10 1` | 达标但缺席 | `Retry` |
| `101 5 0` | 分数不合法 | `Invalid` |
| `60 11 0` | 题数不合法 | `Invalid` |
| `60 5 2` | 缺席标记不合法 | `Invalid` |

## 项目验收

- [ ] 我能解释为什么先判断数据是否合法。
- [ ] 我能解释为什么缺席分支放在等级分支之前。
- [ ] 我能指出每个 `&&` 和 `||` 连接了哪些条件。
- [ ] 我能不看参考代码重新写出程序。
- [ ] 我至少测试了 10 组数据，并核对预期结果。
- [ ] 我没有使用循环、数组或自定义函数。

---

[← 第 6 章：浅层嵌套与边界测试](./06-nesting-and-boundaries.md) · [第二部分目录](./README.md) · [第二部分复习清单 →](./08-review-checklist.md)
