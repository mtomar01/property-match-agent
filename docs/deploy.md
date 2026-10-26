# Putting the beta on tispi.ai

The same server as on your Mac, in a small always-on machine on Fly.io, with the beta switched on by one
secret (D100). The private snapshot is copied into your private Fly image at build time and goes nowhere
else: not into git, not into the public repo. Nothing a visitor types is kept: a session is wiped 15 minutes
after its last request, and only one line of counts per session goes to the log.

You need `flyctl` (https://fly.io/docs/flyctl/install/) and a Fly account with a card on it. Fly builds the
image on its own builders, so no Docker is needed on the Mac. Expected cost: about $3 to $7 a month for the
machine; the chat turns are on the Anthropic key as before, capped at 30 a visitor and 150 a day.

## 1. The snapshot

```bash
mkdir -p data/private/deploy
cp <your 23 October 1,000-listing file> data/private/deploy/snapshot.jsonl
```

`data/private/` is ignored by git; `.dockerignore` lets only `data/private/deploy/` into the image.

## 2. The app on Fly

From the repo root:

```bash
fly auth login
fly launch --no-deploy --copy-config --name tispi --region fra   # takes fly.toml as it is; say no to Postgres and Redis
fly secrets set ANTHROPIC_API_KEY="<the key>" TISPI_INVITE="$(openssl rand -hex 16)"
fly secrets list                                                  # TISPI_INVITE is the token in your friends' link; keep it
fly deploy --remote-only
fly status && fly logs
```

The first deploy takes a few minutes (the React build and the Python install). `fly logs` should show
"Tispi beta on http://0.0.0.0:8765 (private snapshot, …)". If it says "synthetic listings", the snapshot was not
copied: check step 1.

To read the invite token later: `fly ssh console -C 'printenv TISPI_INVITE'`.

## 3. The domain

Fly needs an IP for the apex and a certificate for the name:

```bash
fly ips allocate-v4 --shared     # free; prints an IPv4
fly ips allocate-v6              # prints an IPv6
fly certs add tispi.ai
fly certs add www.tispi.ai
```

At GoDaddy, DNS for tispi.ai, remove the parking records and add:

| Type  | Name | Value                              | TTL   |
|-------|------|------------------------------------|-------|
| A     | @    | the IPv4 from `fly ips list`       | 600   |
| AAAA  | @    | the IPv6 from `fly ips list`       | 600   |
| CNAME | www  | tispi.fly.dev                      | 600   |

Then `fly certs check tispi.ai` until it says the certificate is issued (minutes to an hour). After that
https://tispi.ai shows the gate page, and https://tispi.ai/?invite=TOKEN opens the app.

## 4. Inviting

Send each tester the one link, privately:

    https://tispi.ai/?invite=<TISPI_INVITE>

The link sets a cookie for a week; the token never shows in the address bar after the first load. Anyone
without it sees the gate page. To end the beta or cut off a leaked link, rotate the token:
`fly secrets set TISPI_INVITE="$(openssl rand -hex 16)"` (the machine restarts, the old links stop working).

## 5. Watching it

- `fly logs` shows each session's end as one line: `beta session ended {"session": "…", "turns": 4, "minutes": 12.5, "searches": 1, "swipes": 18, "likes": 7, "like_rate": 0.39, …}`. No text anyone wrote is in it.
- The caps answer with a plain sentence in the chat ("The beta's budget for today is used up …"). Change them with `fly secrets set TISPI_TURNS_PER_DAY=300` or in `fly.toml`.
- `fly machine list` and `fly scale show` for the machine; `fly apps destroy tispi` when the beta is over.

## What is not in this setup, on purpose

No database, no accounts, no analytics beyond the one line of counts, no persistent disk: the sessions are
meant to vanish, so the machine's ephemeral disk is enough. If you ever want testers' swipes kept for the
learning eval, that is a decision to take first, not a volume to add.
