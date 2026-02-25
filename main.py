import sys
import re

if len(sys.argv) != 2:
    raise Exception()

s = sys.argv[1]

if not re.fullmatch(r"\s*\d+(?:\s*[+-]\s*\d+)*\s*", s):
    raise Exception()

nums = list(map(int, re.findall(r"\d+", s)))
ops = re.findall(r"[+-]", s)

res = nums[0]
for op, num in zip(ops, nums[1:]):
    res = res + num if op == "+" else res - num

print(res, end="")