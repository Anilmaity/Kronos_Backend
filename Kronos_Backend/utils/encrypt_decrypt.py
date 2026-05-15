from datetime import datetime
import os
import pytz
kolkata = pytz.timezone('Asia/Kolkata')


from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from base64 import b64encode, b64decode

def pad(data):
    # Padding the data to be a multiple of 16 bytes (AES block size)
    padding_length = AES.block_size - len(data) % AES.block_size
    padding = bytes([padding_length]) * padding_length
    return data + padding

def unpad(data):
    # Removing the padding added during encryption
    padding_length = data[-1]
    return data[:-padding_length]

def encrypt_data(data, db_secret_key="db_secret_key"):
    data = str(data)
    key = b64decode(db_secret_key)
    # Generate a random initialization vector (IV)
    iv = get_random_bytes(AES.block_size)
    # Create a new AES cipher object with Cipher Block Chaining (CBC) mode
    cipher = AES.new(key, AES.MODE_CBC, iv)
    # Pad the data and encrypt it
    encrypted_data = cipher.encrypt(pad(data.encode()))
    # Combine the IV and encrypted data
    combined_data = iv + encrypted_data
    # Base64 encode the result for better representation
    encode_combined_data = 'ALG'+b64encode(combined_data).decode()
    return encode_combined_data

def decrypt_data(encrypted_data, db_secret_key="db_secret_key"):
    key = b64decode(db_secret_key)
    # remove the "eyJ" from the encrypted data
    encrypted_data = encrypted_data[3:]
    # Decode the Base64 encoded data
    combined_data = b64decode(encrypted_data)
    # Extract the IV from the combined data
    iv = combined_data[:AES.block_size]
    # bytes to string
    # print("iv base64",iv)
    # print("iv string", b64encode(iv).decode())
    # Extract the encrypted data from the combined data
    encrypted_data = combined_data[AES.block_size:]
    # Create a new AES cipher object with Cipher Block Chaining (CBC) mode
    cipher = AES.new(key, AES.MODE_CBC, iv)
    # Decrypt the data and remove padding
    decrypted_data = unpad(cipher.decrypt(encrypted_data)).decode()

    return decrypted_data



def decrypt_and_reencrypt(data, secret_key="" , decrypt = True):
    if decrypt:
        decrypt__data = decrypt_data(data)
    else:
        decrypt__data = data
    secret_key = secret_key + "api_secret_key"
    encrypt__data = encrypt_data(decrypt__data, secret_key)
    encrypt__data = encrypt__data[3:]
    return encrypt__data

if __name__ == "__main__":
    # get random string of 44 length
    # print(api_secret_key)
    # key = get_random_bytes(32)
    # print("Key:", key)
    # # enkey =key
    # # print("Key:", key)
    # key = b64encode(key).decode()
    # print("Key:", key)
    # # payload = ""
    # print(decrypt_env("SECRET__KEY"))
    print(encrypt_data("BUY"))
    print(encrypt_data("SELL"))

