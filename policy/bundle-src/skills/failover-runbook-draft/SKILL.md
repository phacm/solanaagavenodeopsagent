# Skill: failover-runbook-draft (text only; mode-specific)

Source: Anza *Setup Node Failover* (S5). Re-verify both sections in W13. Withheld when the consensus mode is `unknown`.

## Tower BFT mode
- The tower file (`tower-*.bin`) carries vote/lockout state; it must move with the identity to the standby before the standby votes. [E] S5
- Never run two voting instances with the same identity. [E] S5
- The operator performs every step by hand.

## Alpenglow mode
- Vote history (`vote_history-<IDENTITY>.bin`) replaces the tower file; follow the Alpenglow section of S5 for what must move. [E] S5
- Never run two voting instances with the same identity. [E] S5
- The operator performs every step by hand.
