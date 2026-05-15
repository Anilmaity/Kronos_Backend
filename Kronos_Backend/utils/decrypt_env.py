import sys
from base64 import b64decode
from Crypto.Cipher import AES
import os
from dotenv import dotenv_values

env_vars = dotenv_values(".env")

if "KEY" in env_vars:
    env_key = env_vars["KEY"]
    server = False
else:
    server = True
    env_key = os.environ.get("KEY")

def unpad(data):
    # Removing the padding added during encryption
    padding_length = data[-1]
    return data[:-padding_length]
def decrypt_env(name, env_key=env_key):
    return env_vars[name]

    # if server:
    #     encrypted_data = os.environ.get(name)
    # else:
    #     encrypted_data = env_vars[name]
    #
    # if encrypted_data:
    #     key = b64decode(env_key)
    #     # remove the "eyJ" from the encrypted data
    #     encrypted_data = encrypted_data[3:]
    #     # Decode the Base64 encoded data
    #     combined_data = b64decode(encrypted_data)
    #     # Extract the IV from the combined data
    #     iv = combined_data[:AES.block_size]
    #
    #     encrypted_data = combined_data[AES.block_size:]
    #     # Create a new AES cipher object with Cipher Block Chaining (CBC) mode
    #     cipher = AES.new(key, AES.MODE_CBC, iv)
    #     # Decrypt the data and remove padding
    #     decrypted_data = unpad(cipher.decrypt(encrypted_data)).decode()
    #     return decrypted_data
    # else:
    #     return None

