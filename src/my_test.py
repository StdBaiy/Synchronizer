# import hashlib

# def generate_sha256_hash(input_string):
#     # 创建 SHA-256 哈希对象
#     sha256_hash = hashlib.sha512()

#     # 更新哈希对象的输入
#     sha256_hash.update(input_string.encode('utf-8'))

#     # 获取十六进制表示的哈希值
#     hashed_string = sha256_hash.hexdigest()

#     return hashed_string

# # 例子
# input_string = "Hello, World!"
# hashed_string = generate_sha256_hash(input_string)
# print(f"Input String: {input_string}")
# print(f"SHA-256 Hash: {hashed_string}")