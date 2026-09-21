# Skill: identity-balance

Source: S3 (monitor the identity account balance; votes cost SOL).

- Evidence: `get_identity_balance` below the floor P-02.
- Least-impact action: the operator funds the identity account from a wallet NOT stored on the validator host. No restart is warranted for a balance alert.
- No withdrawer or stake operation is ever proposed. [E] S4
