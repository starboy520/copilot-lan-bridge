[← 第一部分复习清单](./07-review-checklist.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [给家长或老师的使用建议 →](./09-teaching-guide.md)

---

# 练习答案与提示

> 建议先独立完成，再核对。只看答案不会让解题能力增长。

## 第 1 章

### 练习 1

两处分别填写 `cout` 和 `endl`：

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    cout << "I can code!" << endl;
    return 0;
}
```

### 练习 2

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    cout << "I love C++." << endl;
    return 0;
}
```

### 练习 3

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    cout << 35 + 27 << endl;
    return 0;
}
```

结果为 `62`。

### 练习 4

```cpp
#include <bits/stdc++.h>
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
#include <bits/stdc++.h>
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

### 二进制小探险（选学）

1. `1010` 中，`8` 和 `2` 两盏灯打开，所以结果是 `8 + 2 = 10`。
2. 十进制的 `6 = 4 + 2`，因此打开 `4` 和 `2` 两盏灯，写成四位二进制是 `0110`。最左边的 `0` 省略后写成 `110` 也可以。
3. 在目前常见的计算机中，1 个 `byte` 通常由 8 个 `bit` 组成。

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
#include <bits/stdc++.h>
using namespace std;

int main() {
    int money, add, cost;
    cin >> money >> add >> cost;
    cout << money + add - cost << '\n';
    return 0;
}
```

### 练习 4

使用 `long long` 保存 `distance`、`days` 和计算结果：

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    long long distance, days;
    cin >> distance >> days;
    cout << distance * days << '\n';
    return 0;
}
```

## 第 3 章

### 练习 1

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b, c;
    scanf("%d%d%d", &a, &b, &c);
    printf("%d %d %d\n", a, b, c);
    return 0;
}
```

### 练习 2

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    double r;
    scanf("%lf", &r);
    double circumference = 2 * 3.14159 * r;
    printf("%.2f\n", circumference);
    return 0;
}
```

### 练习 3

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int chinese, math, english;
    scanf("%d%d%d", &chinese, &math, &english);
    double average = (chinese + math + english) / 3.0;
    printf("%.1f\n", average);
    return 0;
}
```

### 练习 4

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int hour, minute;
    scanf("%d%d", &hour, &minute);
    printf("%02d:%02d\n", hour, minute);
    return 0;
}
```

## 第 4 章

### 练习 1

`x` 依次为 `0、5、8、6、7`。

### 练习 2

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int week1, week2, week3, week4;
    scanf("%d%d%d%d", &week1, &week2, &week3, &week4);

    int total = 0;
    total += week1;
    total += week2;
    total += week3;
    total += week4;

    printf("%d\n", total);
    return 0;
}
```

### 练习 3

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int day1, day2, day3, day4, day5;
    scanf("%d%d%d%d%d", &day1, &day2, &day3, &day4, &day5);

    int total = 0;
    total += day1;
    total += day2;
    total += day3;
    total += day4;
    total += day5;

    printf("%d\n", total);
    return 0;
}
```

### 练习 4

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int score1, score2, score3, score4, score5;
    scanf("%d%d%d%d%d", &score1, &score2, &score3, &score4, &score5);

    int total = 0;
    total += score1;
    total += score2;
    total += score3;
    total += score4;
    total += score5;

    double average = total / 5.0;
    printf("%d\n", total);
    printf("%.2f\n", average);
    return 0;
}
```

## 第 5 章

### 练习 1

答案依次为：`4、3、5、0、0、7`。

### 练习 2

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    printf("%d %d\n", n / 8, n % 8);
    return 0;
}
```

### 练习 3

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int totalMinutes;
    scanf("%d", &totalMinutes);
    printf("%d %d\n", totalMinutes / 60, totalMinutes % 60);
    return 0;
}
```

### 练习 4

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    int tens = n / 10;
    int ones = n % 10;
    printf("%d\n", ones * 10 + tens);
    return 0;
}
```

### 练习 5

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    int thousands = n / 1000;
    int hundreds = (n / 100) % 10;
    int tens = (n / 10) % 10;
    int ones = n % 10;
    printf("%d\n", thousands + hundreds + tens + ones);
    return 0;
}
```

### 练习 6

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int h, m, x;
    scanf("%d%d%d", &h, &m, &x);
    int total = h * 60 + m + x;
    int newHour = (total / 60) % 24;
    int newMinute = total % 60;
    printf("%d %d\n", newHour, newMinute);
    return 0;
}
```

---

---

[← 第一部分复习清单](./07-review-checklist.md) · [第一部分目录](./README.md) · [教程首页](../../README.md) · [给家长或老师的使用建议 →](./09-teaching-guide.md)
