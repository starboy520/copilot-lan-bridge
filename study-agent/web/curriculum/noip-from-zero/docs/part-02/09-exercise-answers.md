[← 第二部分复习清单](./08-review-checklist.md) · [第二部分目录](./README.md) · [教程首页](../../README.md) · [给家长或老师的使用建议 →](./10-teaching-guide.md)

---

# 练习答案与提示

> 请先独立思考和运行，再核对答案。代码写法不只一种，只要条件、分支和输出都符合题意，就是好答案。

## 第 1 章 条件与比较运算

### 基础练习 1：条件翻译

1. `age >= 12`
2. `score < 60`
3. `number == 100`
4. `n % 2 == 0`
5. `remainder != 0`

注意第 3 题是在比较是否相等，所以使用 `==`，不是赋值符号 `=`。

### 基础练习 2：判断结果

已知 `x` 等于 8，答案依次为：

1. `x > 5`：`true`
2. `x <= 8`：`true`
3. `x == 7`：`false`
4. `x != 7`：`true`
5. `x % 2 == 0`：`true`

### 提高练习 3：能否进入

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int age;
    scanf("%d", &age);

    bool canEnter = age >= 12;
    printf("%d\n", canEnter);
    return 0;
}
```

输入 `12` 时输出 `1`，输入 `11` 时输出 `0`。

## 第 2 章 单分支 `if`

### 基础练习 1：零

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);

    if (n == 0) {
        printf("Zero\n");
    }

    return 0;
}
```

### 基础练习 2：奖励

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score;
    scanf("%d", &score);

    if (score >= 90) {
        printf("Excellent\n");
    }

    return 0;
}
```

### 提高练习 3：整除

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    scanf("%d%d", &a, &b);

    if (a % b == 0) {
        printf("Divisible\n");
    }

    return 0;
}
```

题目保证 `b` 不为 0，所以可以直接计算 `a % b`。除数为 0 时不能进行除法或取余。

### 代码阅读 4

- 输入 `10`：条件成立，依次输出 `A`、`B`；
- 输入 `0`：条件也成立，依次输出 `A`、`B`；
- 输入 `-3`：条件不成立，只输出 `B`。

`printf("B\n");` 在 `if` 的花括号外面，所以每次都会执行。

## 第 3 章 双分支 `if...else`

### 基础练习 1：正数与非正数

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);

    if (n > 0) {
        printf("Positive\n");
    } else {
        printf("Non-positive\n");
    }

    return 0;
}
```

`0` 不大于 0，所以属于 `else` 处理的“非正数”。

### 基础练习 2：门票

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int age;
    scanf("%d", &age);

    if (age <= 6) {
        printf("Free\n");
    } else {
        printf("Paid\n");
    }

    return 0;
}
```

### 提高练习 3：较小值

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    scanf("%d%d", &a, &b);

    if (a < b) {
        printf("%d\n", a);
    } else {
        printf("%d\n", b);
    }

    return 0;
}
```

### 提高练习 4：能否整除

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    scanf("%d%d", &a, &b);

    if (a % b == 0) {
        printf("Yes\n");
    } else {
        printf("No\n");
    }

    return 0;
}
```

## 第 4 章 多分支

### 基础练习 1：温度提示

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int temperature;
    scanf("%d", &temperature);

    if (temperature < 0) {
        printf("Freezing\n");
    } else if (temperature < 30) {
        printf("Normal\n");
    } else {
        printf("Hot\n");
    }

    return 0;
}
```

能进入第二个分支，已经说明温度不低于 0，所以这里只需判断是否低于 30。

### 基础练习 2：两数关系

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    scanf("%d%d", &a, &b);

    if (a > b) {
        printf("Greater\n");
    } else if (a == b) {
        printf("Equal\n");
    } else {
        printf("Less\n");
    }

    return 0;
}
```

### 提高练习 3：等级

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score;
    scanf("%d", &score);

    if (score >= 85) {
        printf("A\n");
    } else if (score >= 70) {
        printf("B\n");
    } else if (score >= 60) {
        printf("C\n");
    } else {
        printf("D\n");
    }

    return 0;
}
```

分数线要从高到低判断。建议测试 `59、60、69、70、84、85`。

### 代码阅读 4

输入 `88` 时输出 `Pass`。第一个条件 `score >= 60` 已经成立，程序进入第一支后便不再检查 `score >= 85`。这说明较宽松的条件放在前面，会挡住后面更严格的条件。

## 第 5 章 组合条件与逻辑运算

### 基础练习 1：区间

```cpp
x >= 10 && x <= 20
```

“包含 10 和 20”说明两边都要带等号。

### 基础练习 2：优惠

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int age, student;
    scanf("%d%d", &age, &student);

    if (age <= 12 || student == 1) {
        printf("Discount\n");
    } else {
        printf("Regular\n");
    }

    return 0;
}
```

### 提高练习 3：闰年规则的第一步

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int year;
    scanf("%d", &year);

    if (year % 4 == 0 && year % 100 != 0) {
        printf("Special\n");
    } else {
        printf("Normal\n");
    }

    return 0;
}
```

这道题只实现题目给出的组合条件，不代表完整的闰年判断规则。

### 判断练习 4

条件成立：

- `score >= 60` 成立，但 `attendance >= 80` 不成立，所以括号中的 `&&` 整体不成立；
- `special == 1` 成立；
- `false || true` 的结果是 `true`。

## 第 6 章 浅层嵌套与边界测试

### 基础练习 1：边界数据

一种答案是：`11、12、13、17、18、19`。

- `11、12、13` 检查下边界的前一个、边界本身和后一个；
- `17、18、19` 检查上边界的前一个、边界本身和后一个。

### 基础练习 2：合法成绩

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score;
    scanf("%d", &score);

    if (score < 0 || score > 100) {
        printf("Invalid\n");
    } else if (score >= 60) {
        printf("Pass\n");
    } else {
        printf("Fail\n");
    }

    return 0;
}
```

### 提高练习 3：浅层嵌套

路线图：

```text
score >= 60 成立吗？
  ├─ 不成立 → 输出 Retry
  └─ 成立 → homework == 1 成立吗？
               ├─ 成立 → 输出 Complete
               └─ 不成立 → 输出 Finish homework
```

程序：

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score, homework;
    scanf("%d%d", &score, &homework);

    if (score >= 60) {
        if (homework == 1) {
            printf("Complete\n");
        } else {
            printf("Finish homework\n");
        }
    } else {
        printf("Retry\n");
    }

    return 0;
}
```

### 测试设计 4

`50、70、95` 分别位于三档内部，只能说明普通数据看起来正确，不能检查分数线上的等号和分支顺序。

至少还应补充：

```text
59 60 61
89 90 91
```

其中 `60` 和 `90` 是边界，左右相邻的数据能帮助发现 `>` 与 `>=` 写错等问题。

## 综合项目提示

综合项目正文已经给出分解过程和参考程序。真正的闯关方式是：合上参考代码，只保留五条判定规则，自己重新写一遍，再用表格中的 10 组数据测试。

如果卡住，按下面顺序逐级查看提示：

1. 先写 `scanf`，确认三个变量都能读入；
2. 先完成“不合法”与“合法”两条路线；
3. 在合法路线后依次增加缺席、优秀、通过和其他情况；
4. 每增加一个分支，马上运行一组能进入该分支的数据；
5. 最后再检查括号、分支顺序和边界。

---

[← 第二部分复习清单](./08-review-checklist.md) · [第二部分目录](./README.md) · [教程首页](../../README.md) · [给家长或老师的使用建议 →](./10-teaching-guide.md)
