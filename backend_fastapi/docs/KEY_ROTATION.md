# Key rotation

This app uses two kinds of keys; each can be rotated with minimal downtime by using a "previous" key during the transition.

---

## SECRET_KEY (JWT signing)

**Used for:** Signing and verifying JWTs and session cookies.

**Rotation steps:**

1. Generate a new key (e.g. `openssl rand -base64 32`).
2. Set **SECRET_KEY_PREVIOUS** to the **current** SECRET_KEY value.
3. Set **SECRET_KEY** to the **new** key.
4. Deploy / restart the app.
   - New tokens are signed with the new key.
   - Existing tokens still verify (tried with SECRET_KEY, then SECRET_KEY_PREVIOUS).
5. After all existing JWTs have expired (e.g. after `ACCESS_TOKEN_EXPIRE_MINUTES`), remove **SECRET_KEY_PREVIOUS** from config and redeploy.

**Rollback:** Set SECRET_KEY back to the old value; leave SECRET_KEY_PREVIOUS as the “new” value until you’re done rolling back.

---

## ENCRYPTION_KEY (OAuth tokens at rest)

**Used for:** Encrypting `access_token` and `refresh_token` in `auth_identities`.

**Rotation steps:**

1. Generate a new key (e.g. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
2. Set **ENCRYPTION_KEY_PREVIOUS** to the **current** ENCRYPTION_KEY value.
3. Set **ENCRYPTION_KEY** to the **new** key.
4. Deploy / restart the app.
   - New and updated tokens are encrypted with the new key.
   - Existing ciphertext still decrypts (tried with current key, then previous).
5. (Optional) Run a one-off job or script that reads each identity with tokens, writes them back (so they re-encrypt with the new key), then remove **ENCRYPTION_KEY_PREVIOUS** and redeploy. If you skip this, keep ENCRYPTION_KEY_PREVIOUS until you’re comfortable that all relevant rows have been re-saved (e.g. after users re-login and tokens are updated).

**Rollback:** Set ENCRYPTION_KEY back to the old value; set ENCRYPTION_KEY_PREVIOUS to the “new” value until rollback is complete.

---

## Summary

| Key                | Previous key config        | Sign/Encrypt | Verify/Decrypt      |
|--------------------|----------------------------|--------------|---------------------|
| SECRET_KEY         | SECRET_KEY_PREVIOUS        | Current only | Current, then previous |
| ENCRYPTION_KEY     | ENCRYPTION_KEY_PREVIOUS    | Current only | Current, then previous |

Never commit real keys; use env vars or a secrets manager.
