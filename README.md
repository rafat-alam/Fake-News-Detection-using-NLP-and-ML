# Fake News App Backend

FastAPI + PostgreSQL + Redis backend for a Flutter news app. Readers browse news;
verified editors publish articles. **Posting or editing automatically classifies
the article and saves its label, confidence, and classifier.** There is no `/predict` API.

## Run locally

Use Python 3.13 with Neon PostgreSQL and local Redis, or Docker Compose.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m module.setup_nlp
```

Copy `.env.example` to `.env`, set `DATABASE_URL` to your Neon connection string
with `sslmode=require`, and set a random `JWT_SECRET` of at least 32 characters.
Use `REDIS_URL=redis://127.0.0.1:6379/0`. The database starts empty; tables and
indexes are created automatically at startup (`AUTO_CREATE_TABLES=true`). This
schema setup adds a missing news `model_key` column on older installations,
defaulting legacy articles to `logistic_regression`. Other legacy schema changes
still require a separate migration.

Keep `models/pretrained_model_01.pkl`, or place `True.csv` and `Fake.csv` in
`dataset/` and run `python train.py`. Only load model files you trust.

```sh
uvicorn app:app --host 0.0.0.0 --port 10000
```

Docker runs the API and Redis **inside the same container**. PostgreSQL is hosted
on Neon; use the connection string from your [Neon dashboard](https://neon.com/docs/connect/connect-from-any-app).
Redis listens only on the container's loopback interface and stores its data in
the persistent `redis_data` volume. No local PostgreSQL container is created.

```sh
docker compose up --build -d
docker compose logs -f fake-news-app
```

`DATABASE_URL` and Brevo credentials come from `.env`; the container sets
`REDIS_URL=redis://127.0.0.1:6379/0`. Redis starts before the API. Stopping the
container shuts down both processes; if either exits unexpectedly, the container
exits so Compose can restart it. When running Uvicorn directly outside Docker,
start a local Redis server yourself. To switch from the previous multi-container
Compose setup, run `docker compose up --build -d --remove-orphans`.

Startup repairs ownership of the mounted Redis volume before dropping to
`appuser` for Redis and the API. Existing Redis files are preserved, including
volumes created by a previous Redis image. Keep the image's default startup user.
For development with automatic source updates and rebuilds:

```sh
docker compose up --build --watch
```

After changing the Dockerfile, rebuild once before attaching a watcher to an
existing container: `docker compose up --build -d`, then `docker compose watch`.

API: `http://localhost:10000`, interactive docs: `/docs`, machine-readable
contract: `/openapi.json`. Native Flutter needs no CORS; set `CORS_ORIGINS` to
the exact Flutter Web origin(s), separated by commas.

## Email and editor access

OTP email delivery defaults to **Brevo SMTP**. In Brevo, configure your sender
and complete its verification requirements, then copy the SMTP login and generate
an SMTP key under **SMTP & API > SMTP**. The SMTP login can differ from your
account email. Use an **SMTP key**, not a Brevo API key or your account password.

Set these values in local `.env`, or in **Render > your service > Environment**:

```dotenv
EMAIL_MODE=brevo_smtp
BREVO_SENDER_EMAIL=your_verified_sender@example.com
BREVO_SENDER_NAME=NewsLens
BREVO_SMTP_LOGIN=your_brevo_smtp_login
BREVO_SMTP_KEY=your_brevo_smtp_key
BREVO_SMTP_PORT=2525
```

The server is `smtp-relay.brevo.com`. Port `2525` uses STARTTLS before login.
Port `587` also uses STARTTLS; port `465` uses implicit TLS. Certificate validation
is enabled in both cases. See [Brevo SMTP setup](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP).

Render Free [blocks outbound ports 25, 465 and 587](https://render.com/docs/free).
Brevo [supports port 2525 as an alternative](https://help.brevo.com/hc/en-us/articles/10905415650322-Which-SMTP-port-should-I-use-Port-587-465-or-2525),
so this project defaults to it. Connectivity and actual delivery must still be
verified from your deployed service. If SMTP remains unavailable, use the HTTPS
option below instead of disabling TLS.

**Brevo HTTPS option (port 443):**

```dotenv
EMAIL_MODE=brevo_api
BREVO_SENDER_EMAIL=your_verified_sender@example.com
BREVO_SENDER_NAME=NewsLens
BREVO_API_KEY=your_brevo_api_key
```

This mode uses Brevo's [transactional email API](https://developers.brevo.com/docs/send-a-transactional-email).
It requires an API key rather than an SMTP key. No automatic transport fallback
or retry is performed, to avoid duplicate OTP emails after ambiguous failures.

Deploy the updated code and replace any existing `EMAIL_MODE=gmail` setting.
Local `.env` files are excluded from Docker images; Render must receive the values
through its Environment settings. Do not put keys in Flutter or commit them to Git.
Keep `DATABASE_URL`, `JWT_SECRET`, and other backend settings configured as before.
Restart after changing `.env` (`docker compose up -d --force-recreate` for Docker),
or save the Render environment settings and redeploy. Codes are never returned in
API responses.

To check a deployment, open `/health/ready`, then request one signup/signin OTP
and check Brevo's Transactional email logs and the recipient's inbox. A healthy
readiness response checks database, Redis and model availability, not email delivery.
If sending fails, Render logs include `Authentication operation failed` with the
underlying error; API mode includes a safe HTTP status/hint without logging the key
or email body. No live delivery is tested by the automated unit tests.

Existing Gmail configuration is still supported with `EMAIL_MODE=gmail`,
`GMAIL_ADDRESS`, and `GMAIL_APP_PASSWORD` on hosts allowing Gmail SMTP.

For development without email, `EMAIL_MODE=console` logs OTPs locally. Other
providers remain supported with `EMAIL_MODE=smtp`, `SMTP_HOST`, `SMTP_FROM`,
`SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_PORT` (587 by default with STARTTLS).
Set `SMTP_SSL=true` for implicit TLS (port 465 by default).

Every signup creates a reader. A trusted operator grants editor access after signup:

```sh
python -m module.manage editor alice
python -m module.manage editor alice --revoke
# Docker equivalent:
docker compose exec fake-news-app python -m module.manage editor alice
```

Role changes take effect immediately. Users cannot grant themselves editor access.

## Flutter API conventions

Send JSON with `Content-Type: application/json`. Routes marked **Bearer** require
`Authorization: Bearer <session-token>`; **Editor** also requires editor access.
Save the session token in secure device storage. Challenge/reset tokens are
temporary and must never be used as session tokens.

Success responses for auth, profiles, and individual news operations:

```json
{"status":200,"message":"Profile retrieved","data":{}}
```

Failures use the actual HTTP status and `{"detail":"reason"}`. Validation
errors use HTTP 422 with `detail` as a list of field errors. Handle 400 (invalid
or expired OTP/content), 401 (invalid credentials/token; sign in again), 403
(permission denied), 404 (missing item), 409 (username/email conflict), 429
(rate limit), and 503 (dependency unavailable; retry later). News write failures
may return 500. Do not use the human-readable `message` to extract tokens.

IDs are UUID strings. Dates are UTC ISO 8601 strings. Labels: `1` means classified
real, `0` means classified fake. This is a statistical prediction, not verified fact;
confidence is a number from 0 to 1 or `null` when the model lacks probabilities.

## Authentication routes

All routes below use POST and are public unless marked Bearer.
`token` in each body means the token returned by the previous step in that flow.

| Route | JSON request | Success data |
|---|---|---|
| `/auth/signup` | `{"username":"alice","name":"Alice Smith","email":"alice@example.com","password":"strong-password"}` | OTP challenge |
| `/auth/signup/resend-otp` | `{"token":"challenge"}` | Replacement challenge |
| `/auth/signup/verify-otp` | `{"token":"challenge","otp":"123456"}` | HTTP 201, `{"user":User}`; then sign in |
| `/auth/signin` | `{"id":"alice","password":"strong-password"}` | OTP challenge; `id` accepts username or email |
| `/auth/signin/resend-otp` | `{"token":"challenge"}` | Replacement challenge |
| `/auth/signin/verify-otp` | `{"token":"challenge","otp":"123456"}` | Session and user |
| `/auth/forgot-password` | `{"email":"alice@example.com"}` | OTP challenge; 404 if unregistered |
| `/auth/forgot-password/resend-otp` | `{"token":"challenge"}` | Replacement challenge |
| `/auth/forgot-password/verify-otp` | `{"token":"challenge","otp":"123456"}` | Reset token |
| `/auth/forgot-password/reset` | `{"token":"reset-token","password":"new-strong-password"}` | `null`; sign in again |
| `/auth/change-details` **Bearer** | `{"field":"name","value":"Alice Jones"}` | OTP challenge |
| `/auth/change-details/resend-otp` **Bearer** | `{"token":"challenge"}` | Replacement challenge |
| `/auth/change-details/verify-otp` **Bearer** | `{"token":"challenge","otp":"123456"}` | `{"sign_in_required":false}`; true for password changes |
| `/auth/signout` **Bearer** | No body | `null`; revokes this session |

OTP challenge data:

```json
{"token":"<jwt>","token_type":"signup","expires_in":900,"otp_expires_in":600,"resend_after":60}
```

Challenge types are `signup`, `signin`, `forgot_pass`, and `change_details`.
Resending invalidates the old token: replace it in Flutter. Codes contain six
digits, expire in 10 minutes, and allow five incorrect attempts per challenge.
Resend cooldown is 60 seconds. Requests are limited per identity in 15-minute
windows: signup/recovery/change/resend allow five, signin allows ten.

Signin verification data:

```json
{
  "token":"<session-jwt>","token_type":"Bearer","expires_in":2592000,
  "user":{"user_id":"<uuid>","username":"alice","name":"Alice Smith","email":"alice@example.com","is_editor":false}
}
```

Sessions expire in 30 days. Logout invalidates one session. Password recovery or
password changes invalidate all existing sessions; there is no refresh endpoint.
Reset verification returns `{"token":"<jwt>","token_type":"reset","expires_in":300}`;
reset must complete within five minutes and is single use.

Usernames are normalized to lowercase and contain 3–50 letters, digits or
underscores. Emails are normalized to lowercase. Names are 2–100 characters;
new passwords are 8–128 characters. `change-details.field` accepts `username`,
`name`, `email`, or `password`. Email changes send the code to the new address;
other changes send it to the current address. The initiating user's session is
required for both resend and verification.

## Profile routes

| Method and route | Access | Response data |
|---|---|---|
| `GET /users/me` | Bearer | User: `user_id`, `username`, `name`, `email`, `is_editor` |
| `GET /users/{user_id}` | Public | Author: `user_id`, `username`, `name`, `is_editor`; no email |

Use `/users/me` when restoring the app session and checking editor controls.
Use `/users/{published_by}` to display an article's author.

## News routes

| Method and route | Access | Request / result |
|---|---|---|
| `GET /news` | Public | Paginated feed; filters below |
| `GET /news/subjects` | Public | `data` is a list of subjects currently used by articles |
| `GET /news/{news_id}` | Public | `data` is one News object; 404 if missing |
| `POST /news` | Editor | Full article body below; HTTP 201 with saved News |
| `PUT /news/{news_id}` | Owning editor | Full article replacement; HTTP 200 with reclassified News |
| `DELETE /news/{news_id}` | Owning editor | HTTP 200, `data:null` |

Posting and editing body:

```json
{
  "title":"Senate approves infrastructure bill",
  "text":"The senate passed legislation funding roads and public transportation.",
  "subject":"Politics",
  "model":"logistic_regression"
}
```

Title: 3–500 characters; text: 3–100,000; subject: 1–100. All are trimmed and
required. Optional `model` defaults to `logistic_regression`; choices also include
`passive_aggressive`, `naive_bayes`, `decision_tree`, and `random_forest`.
IDs, author, timestamp, label, and confidence are generated by the server.
Classification must succeed before the article is saved. Edits preserve the
original publication time and recompute the classification.

News object:

```json
{
  "news_id":"<uuid>","title":"Senate approves infrastructure bill",
  "text":"The senate passed legislation funding roads and public transportation.",
  "subject":"Politics","published_at":"2026-10-12T10:00:00Z",
  "published_by":"<author-uuid>","label":1,"confidence":0.97,
  "model_key":"logistic_regression"
}
```

Feed query parameters (all optional):

| Parameter | Default / meaning |
|---|---|
| `limit` | 20; allowed 1–100 |
| `offset` | 0; nonnegative |
| `published_by` | UUID; author's articles, including an editor's own feed |
| `subject` | Exact subject match |
| `label` | `0` or `1` |
| `q` | Case-insensitive literal substring in title or text, 1–200 characters |

Example: `GET /news?limit=20&offset=0&subject=Politics&q=senate&label=1`.
Filters combine with AND. The feed sorts newest first, then by UUID to break ties.

```json
{"status":200,"message":"News retrieved successfully!","data":[],"total":0,"limit":20,"offset":0,"has_more":false}
```

For infinite scroll, increase `offset` by the number of received articles while
`has_more` is true. Refresh from offset 0 after publishing or deleting. Concurrent
publishes can shift offset pagination; refreshing reconciles the feed.

## Service routes

| Method and route | Response |
|---|---|
| `GET /` | `{"status":"online","version":"2.0.0","documentation":"/docs","news":"/news"}` |
| `GET /health` | `{"status":"healthy"}`; process liveness |
| `GET /health/ready` | `{"status":"ready","database":"ok","redis":"ok","model":"ok"}` or HTTP 503 |
| `GET /metrics` | `{"metrics":{"model_key":{"model_name":"...","accuracy":0.99,"precision":0.99,"recall":0.99,"f1_score":0.99}}}` for all trained models |
| `GET /docs`, `GET /redoc` | Interactive API documentation |
| `GET /openapi.json` | Generated route and validation schemas |

## Flutter flow and testing

Signup → verify signup OTP → signin → verify signin OTP → store session →
`GET /users/me` → show the feed. Editors submit `POST /news` and display the
saved prediction from its response. On HTTP 401 clear the stored session and
show signin. Android emulator uses `http://10.0.2.2:10000`; a physical device
uses the server's LAN address. Use HTTPS for deployed clients.

```sh
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

News unit tests run without services. Integration tests are skipped unless both
`TEST_DATABASE_URL` and `TEST_REDIS_URL` are explicitly set. Use isolated local
containers, database name `fake_news_test`, and a dedicated Redis instance.
**These test stores are cleared between tests.** The integration suite exercises
real PostgreSQL, Redis, and the saved classifier; email delivery is mocked.
It covers auth, OTP expiry/replay/resend, permissions, search/pagination,
automatic classification, recovery, profile changes, and session revocation.
