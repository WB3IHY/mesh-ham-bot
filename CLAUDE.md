# mesh-ham-bot Project Guidelines

## Deployment
- This project runs on an Ionos Ubuntu VPS as a systemd service called `mesh-ham-bot`
- Deploy by SSHing to the VPS, then: `cd /root/mesh-ham-bot && git pull && systemctl restart mesh-ham-bot`

## Git workflow
- After every change, always commit and push to GitHub immediately
- Never leave uncommitted changes on the VPS — the correct workflow is: edit locally → commit → push → pull on VPS
- Always save diffs for review before committing when making logic changes
- Commit messages must follow conventional commits format: `feat:`, `fix:`, `chore:`, `docs:`

## Database
- The BBS database is at `data/bbs.db`
- Never modify the schema without a migration plan
- Node IDs are always stored in `!hex` format (e.g. `!49b7a3c0`) in the database
