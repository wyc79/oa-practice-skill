// <bits/stdc++.h> is a libstdc++ extension: it exists for GCC (and so on most
// judges), but Apple clang ships libc++ and does not have it. Keep the convenience
// where it is available and fall back to the real headers where it is not.
#if __has_include(<bits/stdc++.h>)
#include <bits/stdc++.h>
#else
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <functional>
#include <iostream>
#include <map>
#include <numeric>
#include <queue>
#include <set>
#include <sstream>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
#endif
using namespace std;

/* ============================================================
   YOUR CODE GOES HERE. Everything below main() is plumbing —
   input is already parsed, output is already formatted.
   ============================================================ */
long long solve(const vector<long long>& a) {
    // TODO
    return 0;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;
    vector<long long> a(n);
    for (auto& x : a) cin >> x;

    cout << solve(a) << "\n";
    return 0;
}
