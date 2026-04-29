#!/usr/bin/env python3
"""
Utility script to generate bcrypt password hashes for api.py
Usage: python hash_password.py [password]
"""

import bcrypt
import sys

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        
        return bcrypt.checkpw(password_bytes, hashed_password)
    except Exception as e:
        print(f"Verification error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Password Hash Generator")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = input("Enter password to hash: ")
    
    try:
        hashed = hash_password(password)
        print(f"\n✅ Hashed password:")
        print(f"{hashed}")
        print(f"\n📋 Copy this to api.py fake_users_db:")
        print(f'"hashed_password": "{hashed}",')
        
        # Verify it works
        print(f"\n✓ Verification test: ", end="")
        if verify_password(password, hashed):
            print("PASSED ✅")
        else:
            print("FAILED ❌")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


