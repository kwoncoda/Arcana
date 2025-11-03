# sys_numadd.py
import sys

if len(sys.argv) != 3:   # 숫자 2개가 아닌 경우
    print("두 개의 정수를 입력하세요")
else:
    a = int(sys.argv[1])  # 첫 번째 숫자
    b = int(sys.argv[2])  # 두 번째 숫자
    print("두 수의 합은", a + b, "입니다.")
