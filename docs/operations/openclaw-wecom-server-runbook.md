# OpenClaw WeCom Server Runbook

This runbook captures the current server-side OpenClaw setup for Xingrun and the minimum steps needed to connect a new Enterprise WeChat bot to the server runtime.

## Current Server State

- Server: `ubuntu@49.234.185.86`
- Verified on: `2026-04-02`
- OpenClaw binary: `/usr/bin/openclaw`
- PM2 process: `openclaw`
- OpenClaw version: `2026.3.13`
- Gateway command: `openclaw gateway --port 18789`
- PM2 working directory: `/home/ubuntu`
- Gateway port: `127.0.0.1:18789`
- OpenClaw config directory: `/home/ubuntu/.openclaw`
- Main config file: `/home/ubuntu/.openclaw/openclaw.json`
- WeCom channel keys present in config:
  - `enabled`
  - `botId`
  - `secret`
  - `allowFrom`
  - `dmPolicy`

The server already has a working PM2-managed OpenClaw process. The operational goal is to keep configuration on the server, not on a local laptop.

## Useful Commands

From the repo root:

```bash
chmod +x scripts/manage_remote_openclaw.sh
SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' ./scripts/manage_remote_openclaw.sh status
SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' ./scripts/manage_remote_openclaw.sh backup
SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' SUDO_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' ./scripts/manage_remote_openclaw.sh update
```

The helper script intentionally defaults to the currently stable server version:

- `TARGET_VERSION=2026.3.13`
- `OPENCLAW_GATEWAY_COMMAND="openclaw gateway --port 18789"`

Directly on the server:

```bash
openclaw --version
pm2 show openclaw
ss -ltnp | grep 18789
tail -n 100 /home/ubuntu/.pm2/logs/openclaw-out.log
tail -n 100 /home/ubuntu/.pm2/logs/openclaw-error.log
```

## One-Time WeCom Bot Creation Checklist

Create a new Enterprise WeChat bot in the Enterprise WeChat admin console and collect:

1. `botId`
2. `secret`
3. The list of teacher Enterprise WeChat identities that should be allowed to talk to the bot

Map those values into the server config:

- `channels.wecom.enabled`
- `channels.wecom.botId`
- `channels.wecom.secret`
- `channels.wecom.allowFrom`
- `channels.wecom.dmPolicy`

Recommended first-pass policy:

- `enabled`: `true`
- `dmPolicy`: `pairing`
- `allowFrom`: the explicit teacher list for pilot users only

`pairing` is the safest default while we validate the consultation-upload flow.

## Applying WeCom Credentials On The Server

Back up the current OpenClaw config first:

```bash
SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' ./scripts/manage_remote_openclaw.sh backup
```

Then update the server config with environment variables instead of typing secrets into shell history by hand:

```bash
ssh ubuntu@49.234.185.86
export WECOM_BOT_ID='replace-with-bot-id'
export WECOM_BOT_SECRET='replace-with-secret'
export WECOM_ALLOW_FROM='teacher_a,teacher_b'

tmp_json="$(mktemp)"
jq \
  '.channels.wecom.enabled = true
  | .channels.wecom.botId = env.WECOM_BOT_ID
  | .channels.wecom.secret = env.WECOM_BOT_SECRET
  | .channels.wecom.allowFrom = (env.WECOM_ALLOW_FROM | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0)))
  | .channels.wecom.dmPolicy = "pairing"' \
  /home/ubuntu/.openclaw/openclaw.json > "$tmp_json"

mv "$tmp_json" /home/ubuntu/.openclaw/openclaw.json
pm2 restart openclaw
pm2 save
```

## Post-Config Validation

After the bot credentials are set:

1. Verify `pm2 show openclaw` still reports `online`.
2. Verify `ss -ltnp | grep 18789` still shows the gateway listening.
3. Send a pilot message from one allowed teacher account.
4. Tail the OpenClaw logs on the server and confirm the message was received without auth errors.

If the bot does not respond:

```bash
tail -n 200 /home/ubuntu/.pm2/logs/openclaw-error.log
tail -n 200 /home/ubuntu/.pm2/logs/openclaw-out.log
jq '.channels.wecom' /home/ubuntu/.openclaw/openclaw.json
```

If OpenClaw was recently upgraded, verify that PM2 is still using the intended gateway command:

```bash
pm2 show openclaw | grep 'script args'
```

Current stable expected value:

```text
-lc cd /home/ubuntu && openclaw gateway --port 18789
```

## Version Pin Note

The server was tested on `2026-04-02` with a newly provided WeCom bot credential set.

Observed behavior:

- `openclaw@2026.4.1` plus `@wecom/wecom-openclaw-plugin@2026.4.2` did not stabilize the WeCom channel for this bot.
- the stable server baseline remains `openclaw@2026.3.13`
- do not upgrade the production OpenClaw runtime past `2026.3.13` for the WeCom bot path until the newer channel/plugin combination is re-validated

If you intentionally test a newer version later, override both the version and the PM2 gateway command explicitly:

```bash
SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' \
SUDO_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' \
TARGET_VERSION='2026.4.1' \
OPENCLAW_GATEWAY_COMMAND='openclaw gateway run --port 18789' \
./scripts/manage_remote_openclaw.sh update
```

## Consultation Assistant Next Step

This runbook only covers keeping OpenClaw on the server and wiring the Enterprise WeChat bot to the server runtime.

The consultation assistant flow still needs one business layer on top of OpenClaw:

1. receive screenshot plus teacher notes
2. OCR and LLM extraction
3. draft confirmation from the teacher
4. write the confirmed payload into Xingrun via `/api/consultations`

That confirmation and persistence layer should stay in the Xingrun backend rather than inside transient OpenClaw session memory.
