#include <bits/stdc++.h>
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
