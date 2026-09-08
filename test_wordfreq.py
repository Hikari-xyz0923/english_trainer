# 体检脚本：感受一下 wordfreq 怎么给单词"评频率分"
# Zipf 分数：分数越高 = 越常见（the 大约 7.5 分），越低 = 越罕见
from wordfreq import zipf_frequency

words = ["the", "water", "treacherous", "spectral", "finesse", "quaint"]
for w in words:
    score = zipf_frequency(w, "en")   # 查询这个词在英文里的 Zipf 频率分
    print(f"{w:15} Zipf分数 = {score:.2f}")
# 体检脚本 2.0：测试覆盖率扫描器（只读不写，放心跑）
from vocabulary_scanner import find_hard_words, coverage_report

text = """One rainy afternoon, a young woman entered the quaint little shop.
The walls were adorned with dusty spice jars, and the air was thick with
the scent of cinnamon. Her hearts pounding, she confessed her dream."""

print("=== 词汇量 2000 的读者 ===")
for w, s in find_hard_words(text, 2000):
    print(f"  生词: {w:15} Zipf={s}")

print("=== 词汇量 8000 的读者 ===")
print(f"  生词: {find_hard_words(text, 8000)}")

report = coverage_report(text, 2000)
print(f"\n=== 体检报告（2000档）===")
print(f"总词数: {report['total_words']} | 生词种数: {report['hard_count']} "
      f"| 覆盖率: {report['coverage']}%")